from pathlib import Path

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_REFERENCES,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    HoverParams,
    LogMessageParams,
    MessageType,
    ReferenceParams,
    ShowMessageParams,
)

from drupalls.lsp.capabilities.capabilities import CapabilityManager
from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.lsp.type_checker import TypeChecker
from drupalls.lsp.text_sync_manager import TextSyncManager
from drupalls.phpactor.client import PhpactorClient
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
    server.capability_manager = None
    server.text_sync_manager = None
    server.type_checker = None
    server.phpactor_client = None

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

        ls.window_log_message(
            LogMessageParams(MessageType.Info, f"Drupal root detected: {drupal_root}")
        )

        # Initialize TypeChecker (CLI-based)
        server.phpactor_client = PhpactorClient()
        if (server.phpactor_client.is_available()):
            server.type_checker = TypeChecker(server.phpactor_client)
        else:
            server.type_checker = TypeChecker()

        # Initialize TextSyncManager BEFORE capabilities
        # so capabilities can register hooks during their initialization.
        ls.text_sync_manager = TextSyncManager(ls)
        ls.text_sync_manager.register_handlers()

        # Initialize cache
        ls.workspace_cache = WorkspaceCache(project_root, drupal_root, server=ls)
        await ls.workspace_cache.initialize()

        count = len(ls.workspace_cache.caches["services"].get_all())
        message = LogMessageParams(MessageType.Info, f"Loaded {count} services")
        ls.window_log_message(message)

        # Initialize capability manager
        ls.capability_manager = CapabilityManager(ls)
        ls.capability_manager.register_all()


    # Register aggregated handlers
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    async def completion(ls: DrupalLanguageServer, params: CompletionParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_completion(params)
        return CompletionList(is_incomplete=False, items=[])

    @server.feature(TEXT_DOCUMENT_HOVER)
    async def hover(ls: DrupalLanguageServer, params: HoverParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_hover(params)
        return None

    @server.feature(TEXT_DOCUMENT_DEFINITION)
    async def definition(ls: DrupalLanguageServer, params: DefinitionParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_definition(params)
        return None

    @server.feature(TEXT_DOCUMENT_REFERENCES)
    async def references(ls: DrupalLanguageServer, params: ReferenceParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_references(params)
        return None

    return server
