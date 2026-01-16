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
    FileOperationClientCapabilities,
)
from pygls import workspace
from drupalls.lsp.capabilities.capabilities import CompletionCapability
from drupalls.workspace.services_cache import ServiceDefinition, ServicesCache


class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""

    @property
    def name(self) -> str:
        return "service_completion"

    @property
    def description(self) -> str:
        return "Autopcomplete Drupal service names in ::serivice() and getContainer()->get() calls"

    def register(self) -> None:
        """Register is handled by CapabilityManager aggregation."""
        # The CapabilityManager handles registration via handle_completion()
        # Individual capabilities don't register directly with @server.feature()
        pass

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor in in a service context."""
        if not self.workspace_cache:
            return False

        # Get the document and line
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        # Check for service patterns
        SERVICE_PATTERN = re.compile(r'::service\([\'"]?|getContainer\(\)->get\([\'"]?')

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
                    documentation=f"Defined in: {service_id}",
                    insert_text=service_id,
                )
            )

        return CompletionList(is_incomplete=False, items=items)
