"""
DI strategy for generic Service classes.

File: drupalls/lsp/capabilities/di_refactoring/strategies/service_strategy.py
"""
from __future__ import annotations

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIStrategy,
    DIRefactoringContext,
    RefactoringEdit,
)
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    get_service_interface,
    get_property_name,
)
from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
    PhpClassInfo,
)

from lsprotocol.types import TextEdit
from pathlib import Path
import yaml


class ServiceDIStrategy(DIStrategy):
    """DI strategy for plain service classes (no create() method).

    This strategy will add use statements, properties, and merge/create
    constructors. It will also update the module's .services.yml entry to
    include the required service arguments when possible.
    """

    def __init__(self) -> None:
        self.analyzer = PhpClassAnalyzer()

    @property
    def name(self) -> str:
        return "Service DI Strategy"

    @property
    def supported_types(self) -> set[str]:
        return {"service"}

    def generate_edits(self, context: DIRefactoringContext) -> list[RefactoringEdit]:
        edits: list[RefactoringEdit] = []
        lines = context.file_content.split("\n")

        class_info = self.analyzer.analyze(context.file_content)
        context.class_info = class_info

        # Collect service info for new services only
        new_services: list[tuple[str, object | None]] = []
        for service_id in context.services_to_inject:
            # Skip if already exists as container get in class (unlikely)
            if class_info.constructor:
                # nothing to skip here; we'll rely on property existence
                pass

            info = get_service_interface(service_id, workspace_cache=context.workspace_cache)
            new_services.append((service_id, info))

        if not new_services:
            return edits

        # Use statements
        use_edits = self._generate_use_statement_edits(class_info, new_services, lines)
        edits.extend(use_edits)

        # Properties
        property_edits = self._generate_property_edits(class_info, new_services)
        edits.extend(property_edits)

        # Constructor (merge or create)
        constructor_edit = self._generate_constructor_edit(class_info, new_services, lines)
        if constructor_edit:
            edits.append(constructor_edit)

        # Update services.yml if workspace cache contains service definition
        yaml_edit = self._generate_services_yaml_edit(context, new_services)
        if yaml_edit:
            edits.append(yaml_edit)

        return edits

    def _generate_use_statement_edits(self, class_info: PhpClassInfo, new_services, lines):
        edits = []
        new_use_statements: list[str] = []
        for service_id, info in new_services:
            if info is None:
                continue
            fqcn = info.interface_fqcn
            if not self.analyzer.has_use_statement(class_info, fqcn):
                new_use_statements.append(info.use_statement)

        if new_use_statements:
            insert_line = class_info.use_section_end
            if insert_line == 0:
                insert_line = class_info.class_line - 1
            text = "\n".join(new_use_statements) + "\n"
            edits.append(
                RefactoringEdit(
                    description="Add use statements",
                    text_edit=self._insert_at(insert_line, 0, text),
                )
            )

        return edits

    def _generate_property_edits(self, class_info: PhpClassInfo, new_services):
        edits: list[RefactoringEdit] = []
        insert_line = self.analyzer.get_property_insert_line(class_info)

        property_text = "\n"
        for service_id, info in new_services:
            if info:
                prop_name = info.property_name
                interface_short = info.interface_short
                interface_fqcn = info.interface_fqcn
            else:
                prop_name = get_property_name(service_id)
                interface_short = ""
                interface_fqcn = "mixed"

            if prop_name in class_info.properties:
                continue

            service_label = service_id.replace(".", " ").replace("_", " ")
            type_decl = f"{interface_short} " if interface_short else ""
            property_text += f"""  /**
   * The {service_label} service.
   *
   * @var \\{interface_fqcn}
   */
  protected {type_decl}${prop_name};

"""

        if property_text.strip():
            edits.append(
                RefactoringEdit(
                    description="Add properties with docstrings",
                    text_edit=self._insert_at(insert_line, 0, property_text),
                )
            )

        return edits

    def _generate_constructor_edit(self, class_info: PhpClassInfo, new_services, lines):
        # Reuse ControllerDIStrategy merge/create logic by mirroring behavior
        # Simpler: if constructor exists, merge; else create new.
        if class_info.constructor:
            # copy merge logic adapted
            ctor = class_info.constructor
            existing_params: list[str] = []
            for param_name, type_hint in ctor.params:
                if type_hint:
                    existing_params.append(f"    {type_hint} ${param_name}")
                else:
                    existing_params.append(f"    ${param_name}")

            new_params: list[str] = []
            new_assignments: list[str] = []
            for service_id, info in new_services:
                if info:
                    prop_name = info.property_name
                    type_hint = info.interface_short
                else:
                    prop_name = get_property_name(service_id)
                    type_hint = ""

                if type_hint:
                    new_params.append(f"    {type_hint} ${prop_name}")
                else:
                    new_params.append(f"    ${prop_name}")
                new_assignments.append(f"    $this->{prop_name} = ${prop_name};")

            all_params = existing_params + new_params

            existing_body = "\n".join(ctor.body_lines).rstrip()
            if existing_body and not existing_body.endswith("\n"):
                existing_body += "\n"

            merged = (
                "  public function __construct(\n"
                + ",\n".join(all_params) + "\n"
                + "  ) {\n"
                + existing_body
                + "\n".join(new_assignments) + "\n"
                + "  }\n"
            )

            start_line = ctor.docblock_start if ctor.docblock_start else ctor.start_line
            end_line = ctor.end_line

            docblock = ""
            if ctor.docblock_start is not None and ctor.docblock_end is not None:
                docblock = "\n".join(lines[ctor.docblock_start:ctor.docblock_end + 1]) + "\n"

            return RefactoringEdit(
                description="Merge constructor with new services",
                text_edit=self._replace_lines(start_line, end_line, docblock + merged, lines),
            )
        else:
            params: list[str] = []
            assignments: list[str] = []
            for service_id, info in new_services:
                if info:
                    prop_name = info.property_name
                    type_hint = info.interface_short
                else:
                    prop_name = get_property_name(service_id)
                    type_hint = ""

                if type_hint:
                    params.append(f"    {type_hint} ${prop_name}")
                else:
                    params.append(f"    ${prop_name}")
                assignments.append(f"    $this->{prop_name} = ${prop_name};")

            constructor = (
                "\n  /**\n"
                "   * Constructs the object.\n"
                "   */\n"
                "  public function __construct(\n"
                + ",\n".join(params) + "\n"
                + "  ) {\n"
                + "\n".join(assignments) + "\n"
                + "  }\n\n"
            )

            insert_line = class_info.first_property_line or class_info.class_line + 2
            if class_info.properties:
                last_prop_line = max(p.line for p in class_info.properties.values())
                insert_line = last_prop_line + 2

            return RefactoringEdit(
                description="Add constructor",
                text_edit=self._insert_at(insert_line, 0, constructor),
            )

    def _generate_services_yaml_edit(self, context: DIRefactoringContext, new_services):
        """Generate an edit to update the module's services.yml arguments for the service.

        Uses workspace_cache services cache to find the service definition file and
        update its arguments list to include the injected services.
        """
        if not context.workspace_cache:
            return None

        services_cache = context.workspace_cache.caches.get("services") if hasattr(context.workspace_cache, "caches") else None
        if not services_cache:
            return None

        # Try to find a service id that corresponds to this class (reverse lookup)
        # We expect the service id to be in context.services_to_inject for this refactor
        # but we need the service definition for the current class. Find any service
        # whose class_name matches this PHP class FQCN.
        target_service_def = None
        class_fqcn = None
        # attempt to determine fqcn from file namespace + class name
        # fallback: search services_cache for an entry whose class_file_path matches file
        file_path = Path(context.file_uri.replace("file://", "")) if context.file_uri.startswith("file://") else Path(context.file_uri)

        for sid, sdef in services_cache.get_all().items():
            try:
                if sdef.class_file_path and Path(sdef.class_file_path).resolve() == file_path.resolve():
                    target_service_def = sdef
                    break
            except Exception:
                continue

        if not target_service_def:
            # try by class name matching
            # compute FQCN from namespace line in file content
            lines = context.file_content.split("\n")
            ns = ""
            cls = ""
            for line in lines:
                if line.strip().startswith("namespace "):
                    ns = line.strip().split()[1].rstrip(";")
                if line.strip().startswith("final class ") or line.strip().startswith("class "):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        cls = parts[2]
                    else:
                        cls = parts[1]
                    break
            if ns and cls:
                class_fqcn = f"{ns}\\{cls}"
                for sid, sdef in services_cache.get_all().items():
                    if sdef.class_name == class_fqcn:
                        target_service_def = sdef
                        break

        if not target_service_def or not getattr(target_service_def, "file_path", None):
            return None

        services_file_path = Path(target_service_def.file_path)
        try:
            with open(services_file_path, "r") as f:
                content = f.read()
        except Exception:
            return None

        # Parse YAML and update arguments for this service id
        try:
            data = yaml.safe_load(content) or {}
        except Exception:
            return None

        services = data.get("services", {})
        svc = services.get(target_service_def.id, {})
        existing_args = svc.get("arguments", []) if isinstance(svc, dict) else []

        # Normalize existing args (strip leading @ if present)
        normalized = [a[1:] if isinstance(a, str) and a.startswith("@") else a for a in existing_args]

        # Add each injected service id if not present
        to_add = []
        for service_id, _ in new_services:
            if service_id not in normalized:
                to_add.append(service_id)

        if not to_add:
            return None

        # Build new arguments list: keep original formatting for entries that started with @
        new_arguments = existing_args[:]  # copy
        # Append bare service ids (without @) as in expected output
        for sid in to_add:
            new_arguments.append(sid)

        # Replace the arguments in the YAML structure
        if isinstance(svc, dict):
            svc["arguments"] = new_arguments
            data["services"][target_service_def.id] = svc
        else:
            return None

        # Dump YAML back to string with block style
        new_yaml = yaml.dump(data, sort_keys=False)

        # Create a TextEdit replacing entire file content
        lines = content.split("\n")
        last_line = len(lines) - 1
        last_char = len(lines[-1]) if lines else 0

        text_edit = self._create_text_edit(0, 0, last_line, last_char, new_yaml)

        # Build file URI
        try:
            services_uri = (
                services_file_path.as_uri()
                if hasattr(services_file_path, "as_uri")
                else f"file://{str(services_file_path)}"
            )
        except Exception:
            services_uri = f"file://{str(services_file_path)}"

        return RefactoringEdit(description="Update services.yml", text_edit=text_edit, target_uri=services_uri)
