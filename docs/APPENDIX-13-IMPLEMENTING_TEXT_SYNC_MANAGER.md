# Implementing the TextSyncManager

## Overview

This guide walks through implementing the **TextSyncManager** - the core infrastructure component that handles LSP text synchronization notifications and provides hook extension points for caches and capabilities.

**Target Audience**: Core DrupalLS developers implementing or modifying the TextSyncManager.

**What You'll Build**: A TextSyncManager class that:

1. Registers LSP text sync handlers (did_open, did_change, did_save, did_close)
2. Maintains hook registries for each event type
3. Broadcasts events to registered hooks
4. Handles errors gracefully (isolated hook failures)

## Prerequisites

Before implementing TextSyncManager, you should understand:

- LSP text synchronization protocol (notifications, not requests)
- pygls v2 async/await patterns and `@server.feature()` decorators
- Python type hints for callable types
- DrupalLS's DrupalLanguageServer class

**Related Reading**:

- `docs/05-TEXT_SYNC_ARCHITECTURE.md` - Architecture overview
- `docs/APPENDIX-11-TEXT_SYNC_HOOKS_QUICK_REF.md` - Quick reference for using hooks
- `docs/APPENDIX-12-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md` - How caches use hooks
- [LSP Text Sync Spec](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_synchronization)

## Architecture Overview

### Component Structure

```
TextSyncManager
├── __init__(server: DrupalLanguageServer)
│   └── Initialize hook registries
│
├── register_handlers()
│   └── Register LSP handlers with @server.feature()
│
├── Hook Registration Methods:
│   ├── add_on_open_hook()
│   ├── add_on_change_hook()
│   ├── add_on_save_hook()
│   └── add_on_close_hook()
│
└── Private Hook Broadcasting (called by LSP handlers):
    ├── _broadcast_on_open()
    ├── _broadcast_on_change()
    ├── _broadcast_on_save()
    └── _broadcast_on_close()
```

### Execution Flow

```
1. Editor sends textDocument/didSave notification
   ↓
2. pygls routes to @server.feature(TEXT_DOCUMENT_DID_SAVE) handler
   ↓
3. Handler logs event, then calls TextSyncManager._broadcast_on_save()
   ↓
4. TextSyncManager loops through registered on_save hooks
   ↓
5. Each hook is called with DidSaveTextDocumentParams
   ├─ ServicesCache._on_services_file_saved() ← Cache updates itself
   ├─ HooksCache._on_hooks_file_saved() ← Cache updates itself
   └─ DiagnosticsCapability._run_diagnostics() ← Capability feature
   ↓
6. Hook errors are caught and logged (isolated failures)
   ↓
7. Returns (notification, no response)
```

## Implementation Steps

### Step 1: File Location

The file already exists at: `drupalls/lsp/text_sync_manager.py`

### Step 2: Import Dependencies

```python
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
```

**Note**: We import `LogMessageParams` and `MessageType` for pygls v2 logging API.

### Step 3: Define Type Aliases

```python
# Type aliases for hook signatures
OnOpenHook = Callable[[DidOpenTextDocumentParams], Awaitable[None]]
OnChangeHook = Callable[[DidChangeTextDocumentParams], Awaitable[None]]
OnSaveHook = Callable[[DidSaveTextDocumentParams], Awaitable[None]]
OnCloseHook = Callable[[DidCloseTextDocumentParams], Awaitable[None]]
```

### Step 4: Implement the TextSyncManager Class

#### 4.1 Class Definition and Constructor

```python
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
```

#### 4.2 Hook Registration Methods

```python
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

        Example (Cache):
            async def on_save(params: DidSaveTextDocumentParams):
                if params.text_document.uri.endswith('.services.yml'):
                    await self.parse_services_file(uri)

            text_sync.add_on_save_hook(on_save)

        Example (Capability):
            async def on_save(params: DidSaveTextDocumentParams):
                diagnostics = await self._analyze_file(uri)
                self.server.publish_diagnostics(uri, diagnostics)

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
```

#### 4.3 Hook Broadcasting Methods

**IMPORTANT**: Use pygls v2 logging API (`window_log_message` with `LogMessageParams`):

```python
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
```

#### 4.4 LSP Handler Registration

```python
    def register_handlers(self) -> None:
        """
        Register LSP text synchronization handlers with the server.

        This should be called once during server initialization,
        BEFORE WorkspaceCache is initialized (so caches can register hooks).

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
```

## Step 5: Integrate with Server

### 5.1 Update server.py

Ensure correct initialization order in `drupalls/lsp/server.py`:

```python
from drupalls.lsp.text_sync_manager import TextSyncManager

def create_server() -> DrupalLanguageServer:
    """Creates and returns a configured Language Server instance."""
    server = DrupalLanguageServer("drupalls", "0.1.0")

    # Store attributes on server instance
    server.workspace_cache = None
    server.capability_manager = None
    server.text_sync_manager = None

    @server.feature("initialize")
    async def initialize(ls: DrupalLanguageServer, params):
        """Initialize the server with correct component order."""

        # Get workspace root
        workspace_root = Path(params.root_uri.replace("file://", ""))
        drupal_root = find_drupal_root(workspace_root)

        if not drupal_root:
            ls.window_log_message(
                LogMessageParams(
                    MessageType.Warning,
                    "Drupal installation not found"
                )
            )
            return

        # 1. Initialize TextSyncManager FIRST
        #    (Must exist before caches try to register hooks)
        ls.text_sync_manager = TextSyncManager(ls)
        ls.text_sync_manager.register_handlers()

        # 2. Initialize WorkspaceCache with server reference
        #    (Caches will register hooks during initialize())
        ls.workspace_cache = WorkspaceCache(
            workspace_root,
            drupal_root,
            server=ls  # Pass server for hook registration
        )
        await ls.workspace_cache.initialize()

        # 3. Initialize CapabilityManager last
        #    (Capabilities may register feature-specific hooks)
        ls.capability_manager = CapabilityManager(ls)
        ls.capability_manager.register_all()

        # Log success
        count = len(ls.workspace_cache.caches["services"].get_all())
        ls.window_log_message(
            LogMessageParams(
                MessageType.Info,
                f"Loaded {count} services"
            )
        )

    # ... rest of server.py ...

    return server
```

**Critical**: The initialization order is:

1. **TextSyncManager** - must exist first
2. **WorkspaceCache** - registers cache hooks
3. **CapabilityManager** - may register feature hooks

### 5.2 Update DrupalLanguageServer Type Hints

In `drupalls/lsp/drupal_language_server.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from pygls.server import LanguageServer

if TYPE_CHECKING:
    from drupalls.lsp.capabilities.capabilities import CapabilityManager
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from drupalls.workspace.cache import WorkspaceCache


class DrupalLanguageServer(LanguageServer):
    """Extended LanguageServer with DrupalLS-specific attributes."""

    workspace_cache: WorkspaceCache | None
    capability_manager: CapabilityManager | None
    text_sync_manager: TextSyncManager | None
```

## Step 6: Testing

### 6.1 Unit Tests

Create `tests/test_text_sync_manager.py`:

```python
import pytest
from lsprotocol.types import (
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    TextDocumentIdentifier,
    TextDocumentItem,
    LogMessageParams,
    MessageType,
)

from drupalls.lsp.text_sync_manager import TextSyncManager


@pytest.fixture
def server():
    """Create a mock server for testing."""
    from unittest.mock import Mock

    server = Mock()
    server.window_log_message = Mock()
    return server


@pytest.fixture
def text_sync(server):
    """Create TextSyncManager instance."""
    return TextSyncManager(server)


@pytest.mark.asyncio
async def test_hook_registration(text_sync):
    """Test that hooks can be registered."""
    async def test_hook(params):
        pass

    text_sync.add_on_save_hook(test_hook)

    assert len(text_sync._on_save_hooks) == 1
    assert text_sync._on_save_hooks[0] == test_hook


@pytest.mark.asyncio
async def test_hook_execution(text_sync):
    """Test that registered hooks are called."""
    hook_called = False
    received_uri = None

    async def test_hook(params: DidSaveTextDocumentParams):
        nonlocal hook_called, received_uri
        hook_called = True
        received_uri = params.text_document.uri

    text_sync.add_on_save_hook(test_hook)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(
            uri='file:///test/file.php'
        )
    )

    await text_sync._broadcast_on_save(params)

    assert hook_called
    assert received_uri == 'file:///test/file.php'


@pytest.mark.asyncio
async def test_multiple_hooks_execution_order(text_sync):
    """Test that multiple hooks run in registration order."""
    execution_order = []

    async def hook1(params):
        execution_order.append(1)

    async def hook2(params):
        execution_order.append(2)

    async def hook3(params):
        execution_order.append(3)

    text_sync.add_on_save_hook(hook1)
    text_sync.add_on_save_hook(hook2)
    text_sync.add_on_save_hook(hook3)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri='file:///test.php')
    )

    await text_sync._broadcast_on_save(params)

    assert execution_order == [1, 2, 3]


@pytest.mark.asyncio
async def test_hook_error_isolation(text_sync, server):
    """Test that hook errors don't prevent other hooks from running."""
    hook2_called = False

    async def failing_hook(params):
        raise ValueError("Test error")

    async def successful_hook(params):
        nonlocal hook2_called
        hook2_called = True

    text_sync.add_on_save_hook(failing_hook)
    text_sync.add_on_save_hook(successful_hook)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri='file:///test.php')
    )

    # Should not raise exception
    await text_sync._broadcast_on_save(params)

    # Second hook should still run
    assert hook2_called

    # Error should be logged
    assert server.window_log_message.called
    # Check that error was logged
    call_args = server.window_log_message.call_args[0][0]
    assert isinstance(call_args, LogMessageParams)
    assert call_args.type == MessageType.Error
```

### 6.2 Integration Test

Create `tests/test_text_sync_integration.py`:

```python
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_cache_registers_hooks(create_test_server):
    """Test that caches register hooks during initialization."""
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from drupalls.workspace.cache import WorkspaceCache

    server = create_test_server()

    # Initialize TextSyncManager
    text_sync = TextSyncManager(server)
    text_sync.register_handlers()
    server.text_sync_manager = text_sync

    # Initialize WorkspaceCache (will register hooks)
    workspace_cache = WorkspaceCache(
        Path("/tmp/drupal"),
        Path("/tmp/drupal"),
        server=server
    )
    await workspace_cache.initialize()

    # Verify ServicesCache registered hooks
    assert len(text_sync._on_save_hooks) > 0


@pytest.mark.asyncio
async def test_cache_updates_on_save(create_test_server, tmp_path):
    """Test that cache updates when relevant file is saved."""
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from drupalls.workspace.cache import WorkspaceCache
    from lsprotocol.types import (
        DidSaveTextDocumentParams,
        TextDocumentIdentifier,
    )

    # Setup
    server = create_test_server()
    text_sync = TextSyncManager(server)
    text_sync.register_handlers()
    server.text_sync_manager = text_sync

    workspace_cache = WorkspaceCache(
        tmp_path,
        tmp_path,
        server=server
    )
    await workspace_cache.initialize()

    # Create test services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Core\\Test\\TestService
""")

    # Trigger save event
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(
            uri=f'file://{services_file}'
        )
    )
    await text_sync._broadcast_on_save(params)

    # Verify cache was updated
    services_cache = workspace_cache.caches['services']
    assert services_cache.get('test.service') is not None
```

## Common Issues and Solutions

### Issue 1: Wrong Logging API

**Symptom**: `AttributeError: 'DrupalLanguageServer' object has no attribute 'show_message_log'`

**Cause**: Using old pygls v1 logging API.

**Solution**: Use pygls v2 API:

```python
# ❌ Wrong (pygls v1)
self.server.show_message_log("Message")

# ✅ Correct (pygls v2)
self.server.window_log_message(
    LogMessageParams(
        type=MessageType.Info,
        message="Message"
    )
)
```

### Issue 2: Initialization Order Wrong

**Symptom**: Caches can't register hooks, `text_sync_manager` is None.

**Cause**: WorkspaceCache initialized before TextSyncManager.

**Solution**: Ensure correct order in `server.py`:

```python
# ✅ Correct order
ls.text_sync_manager = TextSyncManager(ls)
ls.text_sync_manager.register_handlers()

ls.workspace_cache = WorkspaceCache(root, root, server=ls)
await ls.workspace_cache.initialize()

ls.capability_manager = CapabilityManager(ls)
ls.capability_manager.register_all()
```

### Issue 3: Capabilities Registering Cache Hooks

**Symptom**: Duplicate cache updates, multiple hooks doing same work.

**Cause**: Capabilities registering hooks to update caches (WRONG pattern).

**Solution**: Caches register their own hooks:

```python
# ❌ Wrong: Capability updating cache
class ServicesCompletionCapability:
    def register(self):
        text_sync.add_on_save_hook(self._update_cache)

# ✅ Correct: Cache updates itself
class ServicesCache:
    def register_text_sync_hooks(self):
        text_sync.add_on_save_hook(self._on_services_file_saved)
```

See `docs/APPENDIX-12-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md` for details.

## Best Practices

### 1. Error Handling

Always wrap hook execution in try/except with proper logging:

```python
for hook in self._on_save_hooks:
    try:
        await hook(params)
    except Exception as e:
        self.server.window_log_message(
            LogMessageParams(
                type=MessageType.Error,
                message=f"Error in hook {hook.__name__}: {e}"
            )
        )
```

### 2. Type Safety

Use type aliases for hook signatures:

```python
OnSaveHook = Callable[[DidSaveTextDocumentParams], Awaitable[None]]

def add_on_save_hook(self, hook: OnSaveHook) -> None:
    self._on_save_hooks.append(hook)
```

### 3. Documentation

Document initialization order requirements:

```python
def register_handlers(self) -> None:
    """
    Register LSP handlers.

    Must be called BEFORE WorkspaceCache.initialize() so caches
    can register hooks during their initialization.

    Hook execution:
    - Hooks run in registration order
    - Errors are caught and logged
    - One hook failure doesn't affect others
    """
```

## Next Steps

After implementing TextSyncManager:

1. **Update caches** to implement `register_text_sync_hooks()`
2. **Review capabilities** to ensure they don't register cache update hooks
3. **Add tests** for error isolation and execution order
4. **Monitor performance** - especially `did_change` hooks
5. **Document patterns** for cache and capability authors

## References

- **Architecture Overview**: `docs/05-TEXT_SYNC_ARCHITECTURE.md`
- **Quick Reference**: `docs/APPENDIX-11-TEXT_SYNC_HOOKS_QUICK_REF.md`
- **Cache Self-Management**: `docs/APPENDIX-12-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md`
- **Current Implementation**: `drupalls/lsp/text_sync_manager.py`
- **LSP Spec**: [Text Synchronization](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_synchronization)

---

**Summary**: The TextSyncManager is core infrastructure that bridges LSP text sync notifications with DrupalLS's hook system. By providing extension points, it allows caches to self-manage their data and capabilities to implement feature-specific operations without modifying core code.
