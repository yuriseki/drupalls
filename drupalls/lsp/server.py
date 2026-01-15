from pathlib import Path
from typing import Optional
from lsprotocol.types import LogMessageParams, MessageType
from pygls.lsp.server import LanguageServer
from drupalls.lsp.features.text_sync import register_text_sync_handlers
from drupalls.lsp.features.completion import register_completion_handler
from drupalls.lsp.features.hover import register_hover_handler
from drupalls.workspace.cache import WorkspaceCache

class DrupalLanguageServer(LanguageServer):
    """
    Custom Language Server with Drupal-specific attributes.
    
    Attributes:
        workspace_cache: Cache for parsed Drupal data (services, hooks, etc.)
    """
    
    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.workspace_cache: Optional[WorkspaceCache] = None



def create_server() -> DrupalLanguageServer:
    """
    Creates and returns a configured Language Server instance.

    The LanguageServer class from pygls handles:
    - JSON-RPC communication with clients (editors)
    - Request/response lifecycle
    - Notifications and event handling
    """
    server = DrupalLanguageServer("drupalls", "0.1.0")

    # Store cache on server instance
    server.workspace_cache = None
    @server.feature('initialize')
    async def initialize(ls: DrupalLanguageServer, params):
        """
        Initialize the server and set up any necessary state.
        """
        # Get workspace root from params
        workspace_root = Path(params.root_uri.replace("file://", ""))

        # Initialize cache
        ls.workspace_cache = WorkspaceCache(workspace_root)
        await ls.workspace_cache.initialize()

        count = len(ls.workspace_cache.caches["services"].get_all())
        message = LogMessageParams(MessageType.Info, f"Loaded {count} services")
        ls.window_log_message(message)

    # Register all feature handlers
    register_text_sync_handlers(server)
    register_completion_handler(server)
    register_hover_handler(server)

    return server
