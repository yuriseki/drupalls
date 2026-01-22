# IMPLEMENTATION-019: Form and Service Dependency Injection Updates

Date: 2026-01

This document records the incremental updates made to fix Dependency Injection handling for Forms/Controllers and Service classes. It complements IMPLEMENTATION-018 (DI Code Action: Merge with Existing Code) by documenting the concrete code changes and rationale. The intent is to keep IMPLEMENTATION-018 as the core guide and add targeted IMPLEMENTATION-019 notes describing the January 2026 edits.

## Summary

- Added precise PHP class analysis to detect use statements, properties, constructors, and create() methods.
- Improved merging logic for constructors and create() methods to preserve promotions, docblocks, and existing bodies.
- Added ServiceDIStrategy to handle plain service classes and update the module's .services.yml to inject new dependencies.
- get_service_interface now synthesizes ServiceInterfaceInfo from the WorkspaceCache when possible; the strategy prefers interfaces for use statements and type hints.
- Added multi-file refactoring support via RefactoringEdit.target_uri to return edits for both PHP and .services.yml files.

## Files Changed (high-level)

- drupalls/lsp/capabilities/di_refactoring/php_class_analyzer.py
- drupalls/lsp/capabilities/di_refactoring/service_interfaces.py
- drupalls/lsp/capabilities/di_refactoring/strategies/controller_strategy.py
- drupalls/lsp/capabilities/di_refactoring/strategies/service_strategy.py
- drupalls/lsp/capabilities/di_refactoring/di_code_action.py
- drupalls/lsp/capabilities/di_refactoring/strategies/base.py
- tests/lsp/capabilities/di_refactoring/* (new/updated tests)

## Form/Controller DI updates

What changed
- PhpClassAnalyzer: Improved parsing to provide exact line numbers and docblock boundaries for use statements, properties, constructor, and create() methods.
- ControllerDIStrategy: Merging now:
  - Preserves existing constructor param texts (so property promotion is preserved).
  - Adds assignments only for non-promoted params.
  - Preserves existing constructor/create bodies and docblocks.
  - Avoids duplicate use statements and properties.

Why
- Prevents accidental deletion of unrelated code when replacing methods.

Notes
- The analyzer and merging logic ensure edits are minimal and localized.

## Service class DI updates

What changed
- ServiceDIStrategy: New strategy to handle classes registered as services (no create()). It:
  - Synthesizes interface info via get_service_interface(service_id, workspace_cache)
  - Prefers interface FQCN for use statements and @var docblocks, and interface short names for constructor param types
  - Merges/creates constructors while preserving promotions
  - Updates .services.yml: finds the service definition by class_file_path or class_name and appends missing arguments; normalizes service refs to use '@'

Why
- Services not implementing ContainerInjectionInterface are common; this ensures DI is added correctly and the service definition is updated to wire injected dependencies.

Notes and follow-ups

- Tests: Added comprehensive unit tests under tests/lsp/capabilities/di_refactoring that use realistic PHP and YAML fixtures and mock the workspace cache when needed.
- YAML: Current implementation uses yaml.dump() and may lose comments. If comment preservation is required, implement a targeted in-place arguments patcher instead of full dump/replace.

## How this maps to IMPLEMENTATION-018

IMPLEMENTATION-018 remains the primary guide describing the DI Code Action architecture and design. IMPLEMENTATION-019 documents the incremental, code-level updates applied to fix Form and Service DI handling. For full implementation details consult the listed files in the Files Changed section.

## Detailed Code Updates (with rationale)

Below are the concrete code changes introduced in this patch. Each section contains the code excerpt and a short explanation of why the change was made. These blocks are intended to be copy-pasteable and reflect the actual implementation (modern Python 3.9+ type hints are used).

### 1) Service interface synthesis (service_interfaces.py)

Reason: we need a defensive way to synthesize service interface information from the WorkspaceCache at runtime instead of a hardcoded mapping. This allows the refactoring to prefer project-specific interfaces when available.

```python
# drupalls/lsp/capabilities/di_refactoring/service_interfaces.py
from dataclasses import dataclass


@dataclass
class ServiceInterfaceInfo:
    interface_fqcn: str
    interface_short: str
    property_name: str
    use_statement: str


def get_service_interface(service_id: str, workspace_cache=None) -> ServiceInterfaceInfo | None:
    """Synthesize ServiceInterfaceInfo for service_id using WorkspaceCache.

    Returns None if the services cache does not contain a class for the
    service_id. Cache access is defensive and will not raise to callers.
    """
    try:
        if workspace_cache and hasattr(workspace_cache, "caches"):
            services_cache = workspace_cache.caches.get("services")
            if services_cache:
                service_def = services_cache.get(service_id)
                if service_def and service_def.class_name:
                    fqcn = service_def.class_name.lstrip("\\")
                    short = fqcn.split("\\")[-1]
                    prop = get_property_name(service_id)
                    use_stmt = f"use {fqcn};"
                    return ServiceInterfaceInfo(
                        interface_fqcn=fqcn,
                        interface_short=short,
                        property_name=prop,
                        use_statement=use_stmt,
                    )
    except Exception:
        # Cache lookups must never crash the refactoring flow
        pass

    return None
```

### 2) Prefer interfaces in ServiceDIStrategy (service_strategy.py)

Reason: when an interface is discoverable for a service id, generated use statements, @var docblocks and constructor type hints should reference the interface (best practice for DI). The strategy falls back to concrete class/type when the interface is not available.

```python
# drupalls/lsp/capabilities/di_refactoring/strategies/service_strategy.py
def _generate_use_statement_edits(self, class_info: PhpClassInfo, new_services, lines):
    edits = []
    new_use_statements: list[str] = []
    for service_id, info in new_services:
        if info is None:
            continue
        fqcn = info.interface_fqcn
        if not self.analyzer.has_use_statement(class_info, fqcn):
            if info.use_statement not in new_use_statements:
                new_use_statements.append(info.use_statement)

    if new_use_statements:
        insert_line = class_info.use_section_end
        if insert_line == 0:
            insert_line = class_info.class_line - 1
        text = "\n".join(new_use_statements) + "\n"
        edits.append(RefactoringEdit(description="Add use statements", text_edit=self._insert_at(insert_line, 0, text)))

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
        property_text += f"""  /**\n    * The {service_label} service.\n    *\n    * @var \\{interface_fqcn}\n    */\n   protected {type_decl}${prop_name};\n\n"""

    if property_text.strip():
        edits.append(RefactoringEdit(description="Add properties with docstrings", text_edit=self._insert_at(insert_line, 0, property_text)))

    return edits
```

### 3) Preserve property promotion when merging constructors

Reason: PHP constructor property promotion must be preserved — if an existing constructor parameter uses promotion, the refactor must not add a duplicate assignment. The merge logic therefore reuses original parameter texts when available and only generates assignments for non-promoted parameters.

```python
def _merge_constructor(self, class_info: PhpClassInfo, new_services, lines):
    ctor = class_info.constructor
    existing_params: list[str] = []
    for pt in getattr(ctor, "param_texts", []):
        existing_params.append(f"    {pt}")
    if not existing_params:
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

        # Check promotion in original param_texts
        promoted = False
        for pt in getattr(ctor, "param_texts", []):
            if f"${prop_name}" in pt and any(vis in pt for vis in ["private", "protected", "public"]):
                promoted = True
                break
        if not promoted:
            new_assignments.append(f"    $this->{prop_name} = ${prop_name};")

    all_params = existing_params + new_params
    # build merged body using existing ctor.body_lines and new_assignments
```

### 4) Fix create() parsing to correctly detect method end (php_class_analyzer.py)

Reason: the previous brace counting logic could produce incorrect end_line values, causing method replacements to delete unrelated code. The updated code tracks when the method body has opened and when braces return to balance.

```python
def _parse_create_method(self, lines: list[str], start_line: int, docblock_start: int | None, docblock_end: int | None) -> CreateMethodInfo:
    brace_count = 0
    end_line = start_line
    container_gets: list[str] = []
    found_open_brace = False

    for i in range(start_line, len(lines)):
        line = lines[i]
        for match in self.CONTAINER_GET_PATTERN.finditer(line):
            container_gets.append(match.group(1))
        if "{" in line:
            brace_count += line.count("{")
            found_open_brace = True
        if "}" in line:
            brace_count -= line.count("}")
        if found_open_brace and brace_count == 0:
            end_line = i
            break

    return CreateMethodInfo(start_line=start_line, end_line=end_line, container_gets=container_gets, docblock_start=docblock_start, docblock_end=docblock_end)
```

### 5) Multi-file edits support (strategies/base.py)

Reason: strategies need to return edits for other files (e.g., module .services.yml). RefactoringEdit was extended with an optional target_uri so di_code_action can aggregate edits by file into a single WorkspaceEdit.

```python
@dataclass
class RefactoringEdit:
    description: str
    text_edit: TextEdit
    target_uri: str | None = None  # optional; when set, edit applies to another file (e.g., services.yml)
```

### 6) Strategy selection: detect service classes via WorkspaceCache (di_code_action.py)

Reason: if the PHP file corresponds to a project service, use ServiceDIStrategy so constructor injection and services.yml updates are applied. The DI code action reverse-looks up the service definition by class_file_path or class_name in WorkspaceCache.caches['services'].

```python
services_cache = server.workspace_cache.caches.get("services") if hasattr(server, "workspace_cache") else None
target_service = None
if services_cache:
    for sid, sdef in services_cache.get_all().items():
        try:
            if sdef.class_file_path and Path(sdef.class_file_path).resolve() == file_path.resolve():
                target_service = sdef
                break
        except Exception:
            continue
if target_service:
    strategy = ServiceDIStrategy()
else:
    strategy = strategy_factory.get_for_type(drupal_type)
```
