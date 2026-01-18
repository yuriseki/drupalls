"""
Text Synchronization Manager

Manages LSP text sync events and provides hook extension points
for capabilities to react to document lifecycle events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from lsprotocol.types import (
    DidChangeTextDocumentParams,
    DidCloseTextDocumentParams,
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    LogMessageParams,
    MessageType,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_SAVE,
)

if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer


# Type aliases for hook signatures
OnOpenHook = Callable[[DidOpenTextDocumentParams], Awaitable[None]]
OnChangeHook = Callable[[DidChangeTextDocumentParams], Awaitable[None]]
OnSaveHook = Callable[[DidSaveTextDocumentParams], Awaitable[None]]
OnCloseHook = Callable[[DidCloseTextDocumentParams], Awaitable[None]]


class TextSyncManager:
    """
    Manages text document synchronization and hook broadcasting.

    This is core LSP infrastructure that allows caches and capabilities
    to register hooks for document lifecycle events (open, change, save, close).

    Design Principles:
    - Text sync is infrastructure, NOT a capability
    - Provides extension points via hooks
    - Errors are isolated (one hook failure doesn't affect others)
    - Hooks run in registration order
    - No return values (notifications, not requests)

    Usage:
        # During server initialization (before caches/capabilities)
        text_sync = TextSyncManager(server)
        text_sync.register_handlers()
        server.text_sync_manager = text_sync

        # Caches register hooks to keep themselves up-to-date
        class ServicesCache(CachedWorkspace):
            def register_text_sync_hooks(self):
                text_sync = self.server.text_sync_manager
                text_sync.add_on_save_hook(self._on_services_file_saved)

        # Capabilities ONLY register hooks for feature-specific operations
        class DiagnosticsCapability(BaseCapability):
            def register(self):
                text_sync = self.server.text_sync_manager
                text_sync.add_on_save_hook(self._run_diagnostics)
    """
    
    def __init__(self, server: DrupalLanguageServer) -> None:
        """
        Initialize TextSyncManager.
        
        Args:
            server: The DrupalLanguageServer instance
        """
        self.server = server
        
        # Hook registries for each event type
        self._on_open_hooks: list[OnOpenHook] = []
        self._on_change_hooks: list[OnChangeHook] = []
        self._on_save_hooks: list[OnSaveHook] = []
        self._on_close_hooks: list[OnCloseHook] = []

    def add_on_open_hook(self, hook: OnOpenHook) -> None:
        """
        Register a hook for document open events.
        
        The hook will be called when a document is opened in the editor.
        
        Args:
            hook: Async function taking DidOpenTextDocumentParams
        
        Example:
            async def on_open(params: DidOpenTextDocumentParams):
                print(f"Opened: {params.text_document.uri}")
            
            text_sync.add_on_open_hook(on_open)
        """
        self._on_open_hooks.append(hook)
    
    def add_on_change_hook(self, hook: OnChangeHook) -> None:
        """
        Register a hook for document change events.
        
        The hook will be called on EVERY keystroke. Keep it FAST (< 1ms).
        
        Args:
            hook: Async function taking DidChangeTextDocumentParams
        
        Warning:
            Change hooks run on every keystroke. Only use for:
            - Marking files as dirty
            - Invalidating cache entries
            Never do expensive operations here!
        
        Example:
            async def on_change(params: DidChangeTextDocumentParams):
                self._dirty_files.add(params.text_document.uri)
            
            text_sync.add_on_change_hook(on_change)
        """
        self._on_change_hooks.append(hook)
    
    def add_on_save_hook(self, hook: OnSaveHook) -> None:
        """
        Register a hook for document save events.
        
        The hook will be called when a document is saved.
        This is the best place for cache updates and diagnostics.
        
        Args:
            hook: Async function taking DidSaveTextDocumentParams

        Example:
            async def on_save(params: DidSaveTextDocumentParams):
                if params.text_document.uri.endswith('.services.yml'):
                    await self._update_cache(params.text_document.uri)
            
            text_sync.add_on_save_hook(on_save)
        """
        self._on_save_hooks.append(hook)
    
    def add_on_close_hook(self, hook: OnCloseHook) -> None:
        """
        Register a hook for document close events.
        
        The hook will be called when a document is closed in the editor.
        Use for cleanup and resource deallocation.
        
        Args:
            hook: Async function taking DidCloseTextDocumentParams
        
        Example:
            async def on_close(params: DidCloseTextDocumentParams):
                self._open_files.discard(params.text_document.uri)
            
            text_sync.add_on_close_hook(on_close)
        """
        self._on_close_hooks.append(hook)


    async def _broadcast_on_open(
        self, params: DidOpenTextDocumentParams
    ) -> None:
        """
        Broadcast did_open event to all registered hooks.
        
        Hooks are called in registration order. Errors are caught
        and logged to prevent one hook from breaking others.
        
        Args:
            params: Document open parameters from LSP client
        """
        for hook in self._on_open_hooks:
            try:
                await hook(params)
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error in on_open hook {hook.__name__}: "
                                f"{type(e).__name__}: {e}"
                    )
                )
    
    async def _broadcast_on_change(
        self, params: DidChangeTextDocumentParams
    ) -> None:
        """
        Broadcast did_change event to all registered hooks.
        
        WARNING: This is called on EVERY keystroke. Hooks must be
        extremely fast (< 1ms) to avoid editor lag.
        
        Args:
            params: Document change parameters from LSP client
        """
        for hook in self._on_change_hooks:
            try:
                await hook(params)
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error in on_change hook {hook.__name__}: "
                                f"{type(e).__name__}: {e}"
                    )
                )
    
    async def _broadcast_on_save(
        self, params: DidSaveTextDocumentParams
    ) -> None:
        """
        Broadcast did_save event to all registered hooks.
        
        This is the most common hook type. Hooks can do more
        expensive work here since saves are user-initiated.
        
        Args:
            params: Document save parameters from LSP client
        """
        for hook in self._on_save_hooks:
            try:
                await hook(params)
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error in on_save hook {hook.__name__}: "
                                f"{type(e).__name__}: {e}"
                    )
                )
    
    async def _broadcast_on_close(
        self, params: DidCloseTextDocumentParams
    ) -> None:
        """
        Broadcast did_close event to all registered hooks.
        
        Used for cleanup. Hooks should be fast since the user
        is actively closing the file.
        
        Args:
            params: Document close parameters from LSP client
        """
        for hook in self._on_close_hooks:
            try:
                await hook(params)
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error in on_close hook {hook.__name__}: "
                                f"{type(e).__name__}: {e}"
                    )
                )

    def register_handlers(self) -> None:
        """
        Register LSP text synchronization handlers with the server.
        
        This should be called once during server initialization,
        BEFORE capabilities are registered (so they can add hooks).
        
        Registers handlers for:
        - textDocument/didOpen
        - textDocument/didChange
        - textDocument/didSave
        - textDocument/didClose
        """
        
        @self.server.feature(TEXT_DOCUMENT_DID_OPEN)
        async def did_open(
            ls: DrupalLanguageServer,
            params: DidOpenTextDocumentParams,
        ) -> None:
            """
            Handle document opened notification.
            
            Called when a document is opened in the editor.
            The document is automatically added to ls.workspace.text_documents
            by pygls before this handler runs.
            """
            ls.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"Document opened: {params.text_document.uri}"
                )
            )
            
            # Broadcast to registered hooks
            await self._broadcast_on_open(params)
        
        @self.server.feature(TEXT_DOCUMENT_DID_CHANGE)
        async def did_change(
            ls: DrupalLanguageServer,
            params: DidChangeTextDocumentParams,
        ) -> None:
            """
            Handle document changed notification.
            
            Called on EVERY keystroke in the editor.
            The workspace automatically updates the document content
            before this handler runs.
            
            WARNING: This runs frequently. Keep hooks fast!
            """
            ls.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"Document changed: {params.text_document.uri}"
                )
            )
            
            # Broadcast to registered hooks
            await self._broadcast_on_change(params)
        
        @self.server.feature(TEXT_DOCUMENT_DID_SAVE)
        async def did_save(
            ls: DrupalLanguageServer,
            params: DidSaveTextDocumentParams,
        ) -> None:
            """
            Handle document saved notification.
            
            Called when the document is saved to disk.
            This is the best place for cache updates and diagnostics.
            """
            ls.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"Document saved: {params.text_document.uri}"
                )
            )
            
            # Broadcast to registered hooks
            await self._broadcast_on_save(params)
        
        @self.server.feature(TEXT_DOCUMENT_DID_CLOSE)
        async def did_close(
            ls: DrupalLanguageServer,
            params: DidCloseTextDocumentParams,
        ) -> None:
            """
            Handle document closed notification.
            
            Called when a document is closed in the editor.
            Good place to clean up resources associated with the document.
            """
            ls.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"Document closed: {params.text_document.uri}"
                )
            )
            
            # Broadcast to registered hooks
            await self._broadcast_on_close(params)
