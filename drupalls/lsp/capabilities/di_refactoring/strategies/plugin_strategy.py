"""
DI strategy for Plugins (Blocks, Field Formatters, QueueWorkers, etc.).

File: drupalls/lsp/capabilities/di_refactoring/strategies/plugin_strategy.py
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


class PluginDIStrategy(DIStrategy):
    """DI strategy for Plugins using ContainerFactoryPluginInterface."""

    @property
    def name(self) -> str:
        return "Plugin DI Strategy"

    @property
    def supported_types(self) -> set[str]:
        return {"plugin", "block", "formatter", "widget", "queue_worker"}

    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits for Plugin DI pattern."""
        edits: list[RefactoringEdit] = []

        # Collect service info
        services_info = []
        for service_id in context.services_to_inject:
            info = get_service_interface(service_id, workspace_cache=context.workspace_cache)
            if info:
                services_info.append((service_id, info))

        # Generate interface implementation
        interface_edit = self._generate_interface_implementation(context)
        if interface_edit:
            edits.append(interface_edit)

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

        # Generate constructor (with plugin args first)
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

        # Generate create() method (plugin signature)
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
        return 5

    def _find_constructor_insert_line(
        self, context: DIRefactoringContext
    ) -> int:
        """Find line to insert constructor."""
        return context.class_line + 10

    def _find_create_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert create method."""
        return context.class_line + 5

    def _generate_interface_implementation(
        self, context: DIRefactoringContext
    ) -> RefactoringEdit | None:
        """Add ContainerFactoryPluginInterface to class declaration."""
        # Check if already implements
        if "ContainerFactoryPluginInterface" in context.file_content:
            return None

        # Find class declaration and add interface
        lines = context.file_content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("class ") and "{" in line:
                # Add interface implementation
                new_line = (
                    line.rstrip(" {")
                    + " implements ContainerFactoryPluginInterface {"
                )
                return RefactoringEdit(
                    description="Add ContainerFactoryPluginInterface",
                    text_edit=self._create_text_edit(
                        line=i,
                        character=0,
                        end_line=i,
                        end_character=len(line),
                        new_text=new_line,
                    ),
                )
        return None

    def _generate_use_statements(self, services_info: list) -> str:
        """Generate use statements for services."""
        statements = []
        for service_id, info in services_info:
            statements.append(info.use_statement)
        # Add plugin interface
        statements.append(
            "use Drupal\\Core\\Plugin\\ContainerFactoryPluginInterface;"
        )
        statements.append(
            "use Symfony\\Component\\DependencyInjection\\ContainerInterface;"
        )
        return "\n".join(statements) + "\n"

    def _generate_properties(self, services_info: list) -> str:
        """Generate property declarations."""
        lines = ["\n"]
        for service_id, info in services_info:
            lines.append(
                f"  protected {info.interface_short} ${info.property_name};\n"
            )
        lines.append("\n")
        return "".join(lines)

    def _generate_constructor(self, services_info: list) -> str:
        """Generate constructor with plugin args first."""
        # Plugin constructor has standard args first
        plugin_params = [
            "    array $configuration",
            "    $plugin_id",
            "    $plugin_definition",
        ]

        service_params = []
        assignments = []
        for service_id, info in services_info:
            service_params.append(
                f"    {info.interface_short} ${info.property_name}"
            )
            assignments.append(
                f"    $this->{info.property_name} = ${info.property_name};"
            )

        all_params = plugin_params + service_params

        return (
            "  public function __construct(\n"
            + ",\n".join(all_params)
            + "\n  ) {\n"
            "    parent::__construct($configuration, $plugin_id, $plugin_definition);\n"
            + "\n".join(assignments)
            + "\n  }\n\n"
        )

    def _generate_create_method(self, services_info: list) -> str:
        """Generate create() method for ContainerFactoryPluginInterface."""
        container_gets = []
        for service_id, info in services_info:
            container_gets.append(f"      $container->get('{service_id}')")

        return (
            "  public static function create(\n"
            "    ContainerInterface $container,\n"
            "    array $configuration,\n"
            "    $plugin_id,\n"
            "    $plugin_definition\n"
            "  ): static {\n"
            "    return new static(\n"
            "      $configuration,\n"
            "      $plugin_id,\n"
            "      $plugin_definition,\n"
            + ",\n".join(container_gets)
            + "\n    );\n"
            "  }\n\n"
        )
