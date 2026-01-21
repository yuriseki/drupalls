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
)


class ControllerDIStrategy(DIStrategy):
    """DI strategy for Controllers and Forms using ContainerInjectionInterface."""

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

        # Collect service info
        services_info = []
        for service_id in context.services_to_inject:
            info = get_service_interface(service_id)
            if info:
                services_info.append((service_id, info))
            else:
                # Generate basic info for unknown services
                prop_name = get_property_name(service_id)
                services_info.append((service_id, None, prop_name))

        # Generate use statements
        use_statements = self._generate_use_statements(services_info)
        if use_statements:
            edits.append(
                RefactoringEdit(
                    description="Add use statements",
                    text_edit=self._insert_at(
                        line=self._find_use_insert_line(context),
                        character=0,
                        text=use_statements,
                    ),
                )
            )

        # Generate properties
        properties = self._generate_properties(services_info)
        if properties:
            edits.append(
                RefactoringEdit(
                    description="Add properties",
                    text_edit=self._insert_at(
                        line=context.class_line + 1,
                        character=0,
                        text=properties,
                    ),
                )
            )

        # Generate constructor
        constructor = self._generate_constructor(services_info)
        if constructor:
            edits.append(
                RefactoringEdit(
                    description="Add/modify constructor",
                    text_edit=self._insert_at(
                        line=self._find_constructor_insert_line(context),
                        character=0,
                        text=constructor,
                    ),
                )
            )

        # Generate create() method
        create_method = self._generate_create_method(services_info)
        if create_method:
            edits.append(
                RefactoringEdit(
                    description="Add/modify create() method",
                    text_edit=self._insert_at(
                        line=self._find_create_insert_line(context),
                        character=0,
                        text=create_method,
                    ),
                )
            )

        return edits

    def _find_use_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert use statements."""
        lines = context.file_content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                return i
        return 5  # Default after namespace

    def _find_constructor_insert_line(
        self, context: DIRefactoringContext
    ) -> int:
        """Find line to insert constructor."""
        return context.class_line + 10  # After properties

    def _find_create_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert create method."""
        return context.class_line + 5  # After properties

    def _generate_use_statements(self, services_info: list) -> str:
        """Generate use statements for services."""
        statements = []
        for item in services_info:
            if len(item) == 2 and item[1]:
                statements.append(item[1].use_statement)
        # Add ContainerInterface
        statements.append(
            "use Symfony\\Component\\DependencyInjection\\ContainerInterface;"
        )
        return "\n".join(statements) + "\n"

    def _generate_properties(self, services_info: list) -> str:
        """Generate property declarations."""
        lines = ["\n"]
        for item in services_info:
            if len(item) == 2 and item[1]:
                info = item[1]
                lines.append(
                    f"  protected {info.interface_short} ${info.property_name};\n"
                )
            elif len(item) == 3:
                prop_name = item[2]
                lines.append(f"  protected ${prop_name};\n")
        lines.append("\n")
        return "".join(lines)

    def _generate_constructor(self, services_info: list) -> str:
        """Generate constructor."""
        params = []
        assignments = []
        for item in services_info:
            if len(item) == 2 and item[1]:
                info = item[1]
                params.append(f"    {info.interface_short} ${info.property_name}")
                assignments.append(
                    f"    $this->{info.property_name} = ${info.property_name};"
                )
            elif len(item) == 3:
                prop_name = item[2]
                params.append(f"    ${prop_name}")
                assignments.append(f"    $this->{prop_name} = ${prop_name};")

        return (
            "  public function __construct(\n"
            + ",\n".join(params)
            + "\n  ) {\n"
            + "\n".join(assignments)
            + "\n  }\n\n"
        )

    def _generate_create_method(self, services_info: list) -> str:
        """Generate create() method for ContainerInjectionInterface."""
        container_gets = []
        for item in services_info:
            if len(item) >= 2:
                service_id = item[0]
                container_gets.append(f"      $container->get('{service_id}')")

        return (
            "  public static function create(ContainerInterface $container): static {\n"
            "    return new static(\n"
            + ",\n".join(container_gets)
            + "\n    );\n"
            "  }\n\n"
        )
