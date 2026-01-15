"""
Completion (Autocomplete) feature.

This provides suggestions as the user types. For Drupal, we want to suggest:
- Drupal hooks (hook_form_alter, hook_node_view, etc.)
- Service names (\\Drupal::service('...'))
- Configuration keys
- Entity types
- Field types
"""

from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    CompletionItemKind,
    TEXT_DOCUMENT_COMPLETION,
)
from pygls.lsp.server import LanguageServer

def register_completion_handler(server: LanguageServer):
    """
    Register the completion handler.
    
    This is a REQUEST - the client expects a response with completion items.
    """
    
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    async def completions(ls: LanguageServer, params: CompletionParams):

 
