from pygls.lsp.server import LanguageServer
from drupalls.lsp.features.text_sync import register_text_sync_handlers
from drupalls.lsp.features.completion import register_completion_handler
from drupalls.lsp.features.hover import register_hover_handler


def create_server() -> LanguageServer:
    """
    Creates and returns a configured Language Server instance.
    
    The LanguageServer class from pygls handles:
    - JSON-RPC communication with clients (editors)
    - Request/response lifecycle
    - Notifications and event handling
    """
    server = LanguageServer("drupalls", "0.1.0")
    
    # Register all feature handlers
    register_text_sync_handlers(server)
    register_completion_handler(server)
    register_hover_handler(server)
    
    return server
