"""
DI strategy for Controllers and Forms.

File: drupalls/lsp/capabilities/di_refactoring/strategies/controller_strategy.py
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
    ServiceInterfaceInfo,
)
from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
    PhpClassInfo,
)


class ControllerDIStrategy(DIStrategy):
    """DI strategy for Controllers and Forms using ContainerInjectionInterface."""

    def __init__(self) -> None:
        self.analyzer = PhpClassAnalyzer()

    @property
    def name(self) -> str:
        return "Controller/Form DI Strategy"

    @property
    def supported_types(self) -> set[str]:
        return {"controller", "form"}

    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits for Controller/Form DI pattern."""
        edits: list[RefactoringEdit] = []
        lines = context.file_content.split("\n")

        # Analyze existing class structure
        class_info = self.analyzer.analyze(context.file_content)
        context.class_info = class_info

        # Collect service info for new services only
        new_services: list[tuple[str, ServiceInterfaceInfo | None]] = []
        for service_id in context.services_to_inject:
            # Skip if already injected in constructor
            if class_info.constructor:
                existing_gets = (
                    class_info.create_method.container_gets
                    if class_info.create_method
                    else []
                )
                if service_id in existing_gets:
                    continue

            info = get_service_interface(service_id)
            new_services.append((service_id, info))

        if not new_services:
            return edits

        # 1. Generate use statement edits (only for new ones)
        use_edits = self._generate_use_statement_edits(
            class_info, new_services, lines
        )
        edits.extend(use_edits)

        # 2. Generate property edits (with docstrings)
        property_edits = self._generate_property_edits(
            class_info, new_services
        )
        edits.extend(property_edits)

        # 3. Generate constructor edit (merge or create)
        constructor_edit = self._generate_constructor_edit(
            class_info, new_services, lines
        )
        if constructor_edit:
            edits.append(constructor_edit)

        # 4. Generate create() edit (merge or create)
        create_edit = self._generate_create_edit(
            class_info, new_services, lines
        )
        if create_edit:
            edits.append(create_edit)

        return edits

    def _generate_use_statement_edits(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> list[RefactoringEdit]:
        """Generate use statement edits, avoiding duplicates."""
        edits: list[RefactoringEdit] = []
        new_use_statements: list[str] = []

        for service_id, info in new_services:
            if info is None:
                continue

            # Extract FQCN from use statement
            fqcn = info.interface_fqcn

            # Check if already exists
            if not self.analyzer.has_use_statement(class_info, fqcn):
                new_use_statements.append(info.use_statement)

        if new_use_statements:
            # Insert before class declaration
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

    def _generate_property_edits(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> list[RefactoringEdit]:
        """Generate property declarations with docstrings."""
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

            # Skip if property already exists
            if prop_name in class_info.properties:
                continue

            # Generate docstring
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

    def _generate_constructor_edit(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Generate constructor edit - merge with existing or create new."""
        if class_info.constructor:
            return self._merge_constructor(
                class_info, new_services, lines
            )
        else:
            return self._create_new_constructor(
                class_info, new_services
            )

    def _merge_constructor(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Merge new parameters into existing constructor."""
        ctor = class_info.constructor
        if ctor is None:
            return None

        # Build existing parameters string
        existing_params: list[str] = []
        for param_name, type_hint in ctor.params:
            if type_hint:
                existing_params.append(f"    {type_hint} ${param_name}")
            else:
                existing_params.append(f"    ${param_name}")

        # Add new parameters
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

        # Extract existing body (without closing brace)
        existing_body = "\n".join(ctor.body_lines).rstrip()
        if existing_body and not existing_body.endswith("\n"):
            existing_body += "\n"

        # Build merged constructor
        merged = (
            "  public function __construct(\n"
            + ",\n".join(all_params) + "\n"
            + "  ) {\n"
            + existing_body
            + "\n".join(new_assignments) + "\n"
            + "  }\n"
        )

        # Determine range to replace (including docblock if exists)
        start_line = (
            ctor.docblock_start if ctor.docblock_start else ctor.start_line
        )
        end_line = ctor.end_line

        # Get existing docblock
        docblock = ""
        if ctor.docblock_start is not None and ctor.docblock_end is not None:
            docblock = "\n".join(
                lines[ctor.docblock_start:ctor.docblock_end + 1]
            ) + "\n"

        return RefactoringEdit(
            description="Merge constructor with new services",
            text_edit=self._replace_lines(
                start_line, end_line, docblock + merged, lines
            ),
        )

    def _create_new_constructor(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> RefactoringEdit | None:
        """Create new constructor when none exists."""
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

        # Insert after properties
        insert_line = class_info.first_property_line or class_info.class_line + 2
        if class_info.properties:
            # Find last property
            last_prop_line = max(p.line for p in class_info.properties.values())
            insert_line = last_prop_line + 2

        return RefactoringEdit(
            description="Add constructor",
            text_edit=self._insert_at(insert_line, 0, constructor),
        )

    def _generate_create_edit(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Generate create() edit - merge or create."""
        if class_info.create_method:
            return self._merge_create_method(
                class_info, new_services, lines
            )
        else:
            return self._create_new_create_method(
                class_info, new_services
            )

    def _merge_create_method(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Merge new container gets into existing create()."""
        create = class_info.create_method
        if create is None:
            return None

        # Get existing container gets
        existing_gets = [
            f"      $container->get('{sid}')"
            for sid in create.container_gets
        ]

        # Add new container gets
        new_gets = [
            f"      $container->get('{service_id}')"
            for service_id, _ in new_services
        ]

        all_gets = existing_gets + new_gets

        merged = (
            "  /**\n"
            "   * {@inheritdoc}\n"
            "   */\n"
            "  public static function create(ContainerInterface $container) {\n"
            "    return new static(\n"
            + ",\n".join(all_gets) + "\n"
            + "    );\n"
            + "  }\n"
        )

        start_line = (
            create.docblock_start if create.docblock_start else create.start_line
        )
        end_line = create.end_line

        return RefactoringEdit(
            description="Merge create() with new container gets",
            text_edit=self._replace_lines(start_line, end_line, merged, lines),
        )

    def _create_new_create_method(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> RefactoringEdit | None:
        """Create new create() method."""
        gets = [
            f"      $container->get('{service_id}')"
            for service_id, _ in new_services
        ]

        create = (
            "\n  /**\n"
            "   * {@inheritdoc}\n"
            "   */\n"
            "  public static function create(ContainerInterface $container) {\n"
            "    return new static(\n"
            + ",\n".join(gets) + "\n"
            + "    );\n"
            + "  }\n\n"
        )

        # Insert after constructor if exists
        if class_info.constructor:
            insert_line = class_info.constructor.end_line + 1
        else:
            insert_line = class_info.class_line + 2

        return RefactoringEdit(
            description="Add create() method",
            text_edit=self._insert_at(insert_line, 0, create),
        )
