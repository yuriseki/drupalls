"""
Completion (Autocomplete) feature.

This provides suggestions as the user types. For Drupal, we want to suggest:
- Drupal hooks (hook_form_alter, hook_node_view, etc.)
- Service names (\\Drupal::service('...'))
- Configuration keys
- Entity types
- Field types
"""

import re
from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    CompletionItemKind,
    TEXT_DOCUMENT_COMPLETION,
)
from pygls.lsp.server import LanguageServer

from drupalls.lsp.server import DrupalLanguageServer


def register_completion_handler(server: LanguageServer):
    """
    Register the completion handler.
    
    This is a REQUEST - the client expects a response with completion items.
    """
    
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    def completions(ls: DrupalLanguageServer, params: CompletionParams):
        """
        Provide completion items at the cursor position.
        
        params contains:
        - text_document: The document identifier
        - position: The cursor position (line, character)
        - context: Additional context (trigger character, etc.)
        
        Returns: CompletionList with completion items
        """
        # Get the document content
        document = ls.workspace.get_text_document(params.text_document.uri)
        
        # Get the current line to understand context
        current_line = document.lines[params.position.line]
        
        # Simple example: provide Drupal hook completions
        # In a real implementation, you'd parse the context and provide relevant completions
        items = []

        # Check if cache is available.
        if not ls.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])

        # Get the ServicesCache
        services_cache = ls.workspace_cache.caches.get("services")
        drupal_services = services_cache.get_all()

        
        # Example: If user is typing "hook_", suggest common hooks
        if "hook_" in current_line:
            drupal_hooks = [
                ("hook_form_alter", "Alter forms before they are rendered"),
                ("hook_node_view", "Act on a node being viewed"),
                ("hook_cron", "Perform periodic actions"),
                ("hook_install", "Perform setup tasks when module is installed"),
                ("hook_uninstall", "Perform cleanup when module is uninstalled"),
                ("hook_help", "Provide online help"),
                ("hook_theme", "Register theme implementations"),
            ]
            
            for hook_name, description in drupal_hooks:
                items.append(
                    CompletionItem(
                        label=hook_name,
                        kind=CompletionItemKind.Function,
                        detail="Drupal Hook",
                        documentation=description,
                        insert_text=f"{hook_name}(&$form, $form_state) {{\n  // TODO: Implement {hook_name}\n}}"
                        if "form_alter" in hook_name else None
                    )
                )
        
        # Example: If user is typing "\\Drupal::service(", suggest services
        SERVICE_PATTERN = re.compile(r'::service\([\'"]?|getContainer\(\)->get\([\'"]?')
        if SERVICE_PATTERN.search(current_line):
            for _, service in drupal_services.items():
                documentation = ""
                if service.file_path:
                    relative_path = service.file_path.relative_to(ls.workspace_cache.workspace_root)
                    documentation = f"Defined in: {relative_path}"

                items.append(
                    CompletionItem(
                        label=service.id,
                        kind=CompletionItemKind.Value,
                        detail=service.description,
                        documentation=documentation,
                    )
                )
        
        return CompletionList(
            is_incomplete=False,  # True if there are more items available
            items=items
        )
