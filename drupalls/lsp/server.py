from pathlib import Path

from lsprotocol.types import LogMessageParams, MessageType

from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.lsp.features.completion import register_completion_handler
from drupalls.lsp.features.hover import register_hover_handler
from drupalls.lsp.features.text_sync import register_text_sync_handlers
from drupalls.utils.find_files import find_drupal_root
from drupalls.workspace.cache import WorkspaceCache


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

    @server.feature("initialize")
    async def initialize(ls: DrupalLanguageServer, params):
        """
        Initialize the server and set up any necessary state.
        """
        # Get workspace root from LSP params
        workspace_root = Path(params.root_uri.replace("file://", ""))

        # Find Drupal root
        project_root = workspace_root
        drupal_root = find_drupal_root(workspace_root)

        if drupal_root is None:
            ls.window_log_message(
                LogMessageParams(
                    MessageType.Info, "Drupal installation not found in workspace"
                )
            )
            return

        ls.window_log_message(LogMessageParams(MessageType.Info, f"Drupal root detected: {drupal_root}"))

        # Initialize cache
        ls.workspace_cache = WorkspaceCache(project_root, drupal_root)
        await ls.workspace_cache.initialize()

        count = len(ls.workspace_cache.caches["services"].get_all())
        message = LogMessageParams(MessageType.Info, f"Loaded {count} services")
        ls.window_log_message(message)

    # Register all feature handlers
    register_text_sync_handlers(server)
    register_completion_handler(server)
    register_hover_handler(server)

    return server
