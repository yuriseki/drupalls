"""
Services-related LSP capabilities.

Provides completion, hover, and definition for Drupal services.
"""

import re
from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    FileOperationClientCapabilities,
    Hover,
    HoverParams,
    Location,
    MarkupContent,
    MarkupKind,
    Position,
    Range,
)
from pygls import workspace
from drupalls.lsp.capabilities.capabilities import (
    CompletionCapability,
    DefinitionCapability,
    HoverCapability,
)

from drupalls.workspace.services_cache import ServiceDefinition, ServicesCache


# Check for service patterns
SERVICE_PATTERN = re.compile(r'::service\([\'"]?|getContainer\(\)->get\([\'"]?')


class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""

    @property
    def name(self) -> str:
        return "service_completion"

    @property
    def description(self) -> str:
        return "Autopcomplete Drupal service names in ::serivice() and getContainer()->get() calls"

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor in in a service context."""
        if not self.workspace_cache:
            return False

        # Get the document and line
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide service name completions."""
        if not self.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])

        # Get services cache
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])

        # Get all services
        all_services: dict[str, ServiceDefinition] = (
            services_cache.get_all()
        )  # pyright: ignore

        # Build completion items
        items = []
        for service_id, service_def in all_services.items():
            # Get relative path for display
            file_path_str = "unknown"
            if service_def.file_path:
                try:
                    relative = service_def.file_path.relative_to(
                        self.workspace_cache.workspace_root
                    )
                    file_path_str = str(relative)
                except ValueError:
                    file_path_str = str(service_def.file_path)

            items.append(
                CompletionItem(
                    label=service_id,
                    kind=CompletionItemKind.Value,
                    detail=service_def.class_name,
                    documentation=f"Defined in: {file_path_str}",
                    insert_text=service_id,
                )
            )

        return CompletionList(is_incomplete=False, items=items)


class ServicesHoverCapability(HoverCapability):
    """Provides hover information for Drupal services."""

    @property
    def name(self) -> str:
        return "services_hover"

    @property
    def description(self) -> str:
        return "Suow information about Drupal services on hover"

    async def can_handle(self, params: HoverParams) -> bool:
        """Check if hovering over a service identifier."""
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def hover(self, params: HoverParams) -> Hover | None:
        """Provide hover information for services"""
        if not self.workspace_cache:
            return None

        # Get word under cursor using LSP's built in word_at_position
        doc = self.server.workspace.get_text_document(params.text_document.uri)

        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None

        service_def = services_cache.get(word)
        if service_def:
            # Found the service
            relative_path = "unknown"
            if service_def.file_path:
                try:
                    relative_path = str(
                        service_def.file_path.relative_to(
                            self.workspace_cache.workspace_root
                        )
                    )
                except ValueError:
                    relative_path = str(service_def.file_path)

            content = (
                f"**Drupal Service:** `{word}`{chr(10)}"
                f"**Class:** {service_def.class_name}{chr(10)}"
                f"**Defined in:** {relative_path}"
            )

            if service_def.arguments:
                content += f"{chr(10)}**Arguments:** ({service_def.arguments})"

            if service_def.tags:
                content += f"{chr(10)}**Tags:** {service_def.tags}"

            return Hover(
                contents=MarkupContent(kind=MarkupKind.Markdown, value=content)
            )

        return None


class ServicesDefinitionCapability(DefinitionCapability):
    """Provides go-to-definition for Drupal services."""

    @property
    def name(self) -> str:
        return "services_definition"

    @property
    def description(self) -> str:
        return "Navigate to service definition in .services.yml files"

    async def can_handle(self, params: DefinitionParams) -> bool:
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def definition(self, params: DefinitionParams) -> Location | None:
        """Provide definition location for services."""
        if not self.workspace_cache:
            return None

        # Get service ID under cursor
        doc = self.server.workspace.get_text_document(params.text_document.uri)

        # Extract service ID with custom pattern for dots
        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None

        # Look up the service definition
        service_def = services_cache.get(word)
        if service_def and service_def.file_path:
            # Get the exact line number from the service definition
            # ServiceDefinition stores the line number where it was defined.
            line_number = (
                service_def.line_number - 1
                if hasattr(service_def, "line_number")
                else 0
            )

            # Return the location pointing to the service definition in .services.yml
            return Location(
                uri=service_def.file_path.as_uri(),
                range=Range(
                    start=Position(line=line_number, character=0),
                    end=Position(line=line_number, character=0),
                ),
            )

        return None
