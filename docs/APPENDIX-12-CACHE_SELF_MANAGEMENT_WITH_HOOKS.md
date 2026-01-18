# Cache Self-Management with Text Sync Hooks

## Overview

This guide explains how DrupalLS caches automatically keep themselves up-to-date using text synchronization hooks. This is the **correct architecture pattern** where caches own their data lifecycle, not capabilities.

**Key Principle**: Caches register their own text sync hooks to keep their data fresh. Capabilities simply use the cache without managing it.

## Problem Statement

When files change in the editor (services YAML, PHP files, config schemas), the cache needs to update. The question is: **Who is responsible for updating the cache?**

### ❌ Wrong Approach: Capabilities Update Caches

```python
# DON'T DO THIS
class ServicesCompletionCapability(CompletionCapability):
    def register(self) -> None:
        # Capability registers hook to update cache - WRONG!
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._update_services_cache)
    
    async def _update_services_cache(self, params):
        # Capability manages cache updates - violates SRP!
        services_cache = self.workspace_cache.caches['services']
        await services_cache.parse_services_file(...)
```

**Problems with this approach:**
- Violates Single Responsibility Principle (capabilities have two jobs)
- Multiple capabilities using same cache = duplicate hooks
- Tight coupling between capability and cache implementation
- Cache updates scattered across multiple capability files

### ✅ Correct Approach: Caches Manage Themselves

```python
# DO THIS INSTEAD
class ServicesCache(CachedWorkspace):
    def register_text_sync_hooks(self) -> None:
        """Cache registers hooks to keep itself up-to-date."""
        if not self.server or not hasattr(self.server, 'text_sync_manager'):
            return
        
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_services_file_saved)
    
    async def _on_services_file_saved(self, params):
        """Update self when .services.yml files are saved."""
        uri = params.text_document.uri
        if uri.endswith('.services.yml'):
            file_path = Path(uri.replace('file://', ''))
            await self.parse_services_file(file_path)


class ServicesCompletionCapability(CompletionCapability):
    def register(self) -> None:
        """No hooks needed - cache manages itself."""
        pass  # Cache updates automatically, we just use it
    
    async def complete(self, params):
        """Just use the cache - it's always fresh."""
        services_cache = self.workspace_cache.caches['services']
        services = services_cache.get_all()
        # Build completion items...
```

**Benefits of this approach:**
- ✅ Single Responsibility: Caches manage data, capabilities provide features
- ✅ No duplication: One cache, one set of hooks
- ✅ Loose coupling: Capabilities don't know how cache updates
- ✅ Self-contained: Cache owns its lifecycle

## Architecture

```
Server Initialization Flow:
│
├─ 1. Initialize TextSyncManager
│   └─ Registers LSP text sync handlers
│
├─ 2. Initialize WorkspaceCache
│   ├─ Creates all cache instances (ServicesCache, HooksCache, etc.)
│   ├─ Each cache has reference to server
│   ├─ Performs initial scan
│   └─ Calls cache.register_text_sync_hooks() for each cache
│
└─ 3. Initialize CapabilityManager
    └─ Capabilities just use caches (no hook registration)

Text Sync Event Flow:
│
├─ User saves .services.yml file
│
├─ Editor sends textDocument/didSave notification
│
├─ TextSyncManager receives notification
│
├─ TextSyncManager broadcasts to all registered hooks
│
└─ ServicesCache hook executes
    └─ Updates cache for that specific file
```

## Responsibility Matrix

| Component | Responsibility | Registers Text Sync Hooks? |
|-----------|---------------|---------------------------|
| **TextSyncManager** | Infrastructure: receives LSP notifications, broadcasts to hooks | N/A (is the infrastructure) |
| **ServicesCache** | Data: parse and store services | ✅ YES - updates self on file save |
| **HooksCache** | Data: parse and store hooks | ✅ YES - updates self on file save |
| **ConfigCache** | Data: parse and store config | ✅ YES - updates self on file save |
| **ServicesCompletionCapability** | Feature: provide LSP completion | ❌ NO - just uses cache |
| **ServicesHoverCapability** | Feature: provide LSP hover | ❌ NO - just uses cache |
| **ServicesDefinitionCapability** | Feature: provide LSP definition | ❌ NO - just uses cache |
| **DiagnosticsCapability** | Feature: run validation checks | ⚠️ MAYBE - for diagnostic logic, not cache updates |

## Implementation Guide

### Step 1: Update CachedWorkspace Base Class

Add hook registration support to the base class:

```python
# drupalls/workspace/cache.py

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer


class CachedWorkspace(ABC):
    """
    Abstract base class for Drupal workspace caches.
    
    Subclasses should implement register_text_sync_hooks() to keep
    their cache up-to-date automatically.
    """
    
    def __init__(
        self, 
        workspace_cache: WorkspaceCache, 
        server: DrupalLanguageServer | None = None
    ):
        """
        Initialize cache.
        
        Args:
            workspace_cache: Reference to parent WorkspaceCache
            server: DrupalLanguageServer instance (needed for text sync hooks)
        """
        self.workspace_cache = workspace_cache
        self.project_root = workspace_cache.project_root
        self.workspace_root = workspace_cache.workspace_root
        self.file_info = workspace_cache.file_info
        self.server = server
    
    def register_text_sync_hooks(self) -> None:
        """
        Register text sync hooks to keep cache up-to-date.
        
        Override this in subclasses to register hooks with
        self.server.text_sync_manager that update the cache
        when relevant files change.
        
        Example:
            def register_text_sync_hooks(self):
                if not self.server or not hasattr(self.server, 'text_sync_manager'):
                    return
                
                text_sync = self.server.text_sync_manager
                if text_sync:
                    text_sync.add_on_save_hook(self._on_file_saved)
        """
        pass  # Default: no hooks (override in subclasses)
    
    @abstractmethod
    async def initialize(self):
        """Initialize cache (scan workspace)."""
        pass
    
    @abstractmethod
    def get(self, id: str) -> CachedDataBase | None:
        """Get a specific item by ID."""
        pass
    
    @abstractmethod
    def get_all(self) -> Mapping[str, CachedDataBase]:
        """Get all cached items."""
        pass
    
    # ... rest of abstract methods ...
```

### Step 2: Update WorkspaceCache

Add server parameter and hook registration:

```python
# drupalls/workspace/cache.py

class WorkspaceCache:
    """
    Central cache for all parsed workspace data.
    """
    
    def __init__(
        self,
        project_root: Path,
        workspace_root: Path,
        server: DrupalLanguageServer | None = None
    ):
        """
        Initialize workspace cache.
        
        Args:
            project_root: Drupal project root
            workspace_root: LSP workspace root
            server: DrupalLanguageServer instance (passed to caches for hooks)
        """
        from drupalls.workspace.services_cache import ServicesCache
        
        self.project_root = project_root
        self.workspace_root = workspace_root
        self.server = server
        
        # In-memory caches
        self.file_info: dict[Path, FileInfo] = {}
        
        # Initialize caches WITH server reference
        self.caches = {
            "services": ServicesCache(self, server),
            "hooks": HooksCache(self, server),  # Future
            "config": ConfigCache(self, server),  # Future
        }
        
        # State
        self._initialized = False
        self._last_scan: datetime | None = None
        
        # Configuration
        self.cache_dir = project_root / ".drupalls" / "cache"
        self.enable_disk_cache = True
    
    async def initialize(self):
        """
        Initialize the cache by scanning the workspace.
        
        This is called once when the workspace is opened.
        """
        if self._initialized:
            return
        
        # Try to load from disk cache first
        if self.enable_disk_cache and self._load_from_disk():
            self._initialized = True
            # Still register hooks even if loaded from disk
            self._register_text_sync_hooks()
            return
        
        # Initialize each cache (performs scan)
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.initialize()
        
        # Save to disk for next time
        if self.enable_disk_cache:
            self._save_to_disk()
        
        # Register text sync hooks for all caches
        self._register_text_sync_hooks()
        
        self._initialized = True
        self._last_scan = datetime.now()
    
    def _register_text_sync_hooks(self) -> None:
        """
        Register text sync hooks for all caches.
        
        Called after initial scan completes, allowing caches
        to keep themselves up-to-date as files change.
        """
        if not self.server:
            return
        
        for cache_name, cache in self.caches.items():
            if isinstance(cache, CachedWorkspace):
                cache.register_text_sync_hooks()
    
    # ... rest of WorkspaceCache methods ...
```

### Step 3: Implement Cache-Level Hooks

Each cache implements `register_text_sync_hooks()`:

```python
# drupalls/workspace/services_cache.py

from pathlib import Path
from lsprotocol.types import (
    DidSaveTextDocumentParams, 
    LogMessageParams, 
    MessageType
)


class ServicesCache(CachedWorkspace):
    """Cache for Drupal service definitions."""
    
    def __init__(
        self, 
        workspace_cache: WorkspaceCache, 
        server=None
    ):
        super().__init__(workspace_cache, server)
        self._services: dict[str, ServiceDefinition] = {}
    
    def register_text_sync_hooks(self) -> None:
        """
        Register hooks to keep services cache up-to-date.
        
        Registers a save hook that updates the cache when
        .services.yml files are saved.
        """
        # Check if server and text_sync_manager are available
        if not self.server or not hasattr(self.server, 'text_sync_manager'):
            return
        
        text_sync = self.server.text_sync_manager
        if not text_sync:
            return
        
        # Register hook for .services.yml file saves
        text_sync.add_on_save_hook(self._on_services_file_saved)
    
    async def _on_services_file_saved(
        self, 
        params: DidSaveTextDocumentParams
    ) -> None:
        """
        Update cache when a .services.yml file is saved.
        
        Args:
            params: Save event parameters from LSP client
        """
        uri = params.text_document.uri
        
        # Filter: Only handle .services.yml files
        if not uri.endswith('.services.yml'):
            return
        
        try:
            # Convert URI to file path
            file_path = Path(uri.replace('file://', ''))
            
            # Check if file is within workspace
            if not self._is_in_workspace(file_path):
                return
            
            # Reparse this specific file (incremental update)
            await self.parse_services_file(file_path)
            
            # Log success
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated services cache: {file_path.name}"
                    )
                )
        
        except FileNotFoundError:
            # File was deleted - remove from cache
            self._remove_services_from_file(file_path)
            
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Services file deleted: {file_path.name}"
                    )
                )
        
        except Exception as e:
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating services cache: {type(e).__name__}: {e}"
                    )
                )
    
    def _is_in_workspace(self, file_path: Path) -> bool:
        """Check if file is within workspace root."""
        try:
            file_path.relative_to(self.workspace_cache.workspace_root)
            return True
        except ValueError:
            return False
    
    def _remove_services_from_file(self, file_path: Path) -> None:
        """Remove all services defined in a specific file."""
        self._services = {
            sid: sdef
            for sid, sdef in self._services.items()
            if sdef.file_path != file_path
        }
        
        # Remove from file tracking
        if file_path in self.file_info:
            del self.file_info[file_path]
    
    # ... rest of ServicesCache methods ...
```

### Step 4: Update Server Initialization

Ensure correct component initialization order:

```python
# drupalls/lsp/server.py

@server.feature("initialize")
async def initialize(ls: DrupalLanguageServer, params):
    """Initialize server with correct component order."""
    
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
    await ls.workspace_cache.initialize()  # Scans + registers hooks
    
    # 3. Initialize CapabilityManager
    #    (Capabilities just use caches, don't register hooks)
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
```

### Step 5: Simplify Capability Classes

Capabilities no longer need to register hooks:

```python
# drupalls/lsp/capabilities/services_capabilities.py

class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""
    
    @property
    def name(self) -> str:
        return "services_completion"
    
    @property
    def description(self) -> str:
        return "Autocomplete Drupal service names"
    
    def register(self) -> None:
        """
        No hooks needed - ServicesCache manages itself.
        
        The ServicesCache automatically registers text sync hooks
        to keep itself up-to-date. This capability just uses the cache.
        """
        pass  # Cache handles updates, we just use it
    
    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is in a service context."""
        # Your can_handle logic...
        return True
    
    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide service completions from cache."""
        if not self.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        services_cache = self.workspace_cache.caches.get('services')
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Just use the cache - it's always fresh!
        services = services_cache.get_all()
        
        items = [
            CompletionItem(
                label=service_id,
                kind=CompletionItemKind.Value,
                detail=service_def.class_name,
            )
            for service_id, service_def in services.items()
        ]
        
        return CompletionList(is_incomplete=False, items=items)
```

## When Capabilities SHOULD Register Hooks

Capabilities should ONLY register hooks for actions specific to their LSP feature, NOT for cache updates:

### ✅ Valid Capability Hook Use Cases

```python
# VALID: Diagnostic capability runs diagnostics on save
class DiagnosticsCapability(BaseCapability):
    """Provides real-time diagnostics (errors, warnings)."""
    
    def register(self) -> None:
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._run_diagnostics)
    
    async def _run_diagnostics(self, params):
        """Run diagnostics - this is the capability's job."""
        # This is valid because diagnostics ARE the feature
        diagnostics = await self._analyze_file(params.text_document.uri)
        self.server.publish_diagnostics(
            params.text_document.uri, 
            diagnostics
        )


# VALID: Formatting capability auto-formats on save (if enabled)
class FormattingCapability(BaseCapability):
    """Provides document formatting."""
    
    def register(self) -> None:
        if self.config.get('format_on_save'):
            text_sync = self.server.text_sync_manager
            text_sync.add_on_save_hook(self._format_on_save)
    
    async def _format_on_save(self, params):
        """Auto-format document - this is the capability's job."""
        formatted_text = await self._format(params.text_document.uri)
        # Apply formatting via workspace edit...
```

### ❌ Invalid Capability Hook Use Cases

```python
# INVALID: Capability updating shared cache
class ServicesCompletionCapability(CompletionCapability):
    def register(self) -> None:
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._update_services_cache)  # WRONG
    
    async def _update_services_cache(self, params):
        # This is wrong - cache should update itself
        services_cache = self.workspace_cache.caches['services']
        await services_cache.parse_services_file(...)


# INVALID: Multiple capabilities updating same cache
class ServicesHoverCapability(HoverCapability):
    def register(self) -> None:
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._update_services_cache)  # DUPLICATE!
    
    async def _update_services_cache(self, params):
        # Now we have TWO hooks updating the same cache - wasteful!
        services_cache = self.workspace_cache.caches['services']
        await services_cache.parse_services_file(...)
```

## Decision Tree: Where Should This Hook Go?

```
Need to register a text sync hook?
│
├─ Is it for updating a shared cache?
│   └─→ ✅ Put hook in the CACHE class
│       (cache.register_text_sync_hooks())
│
├─ Is it for a feature-specific operation?
│   └─→ ✅ Put hook in the CAPABILITY class
│       (capability.register())
│
└─ Is it for multiple capabilities to coordinate?
    └─→ ⚠️  Consider if a cache should handle it instead
```

## Testing

### Test Cache Hook Registration

```python
# tests/test_services_cache_hooks.py

import pytest
from pathlib import Path
from lsprotocol.types import (
    DidSaveTextDocumentParams,
    TextDocumentIdentifier,
)


@pytest.mark.asyncio
async def test_services_cache_registers_hooks(server):
    """Test that ServicesCache registers text sync hooks."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from drupalls.workspace.cache import WorkspaceCache
    
    # Setup TextSyncManager
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    # Create workspace cache with server reference
    workspace_cache = WorkspaceCache(
        Path("/tmp/drupal"),
        Path("/tmp/drupal"),
        server=server
    )
    
    # Get services cache
    cache = workspace_cache.caches['services']
    
    # Register hooks
    cache.register_text_sync_hooks()
    
    # Verify hook was registered
    assert len(text_sync._on_save_hooks) == 1
    assert cache._on_services_file_saved in text_sync._on_save_hooks


@pytest.mark.asyncio
async def test_services_cache_updates_on_save(server, tmp_path):
    """Test that ServicesCache updates when .services.yml is saved."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from drupalls.workspace.cache import WorkspaceCache
    
    # Setup
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    workspace_cache = WorkspaceCache(
        tmp_path,
        tmp_path,
        server=server
    )
    cache = workspace_cache.caches['services']
    cache.register_text_sync_hooks()
    
    # Create a test services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Core\\Test\\TestService
""")
    
    # Create save event
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(
            uri=f'file://{services_file}'
        )
    )
    
    # Trigger hook via TextSyncManager
    await text_sync._broadcast_on_save(params)
    
    # Verify cache was updated
    assert cache.get('test.service') is not None
    assert cache.get('test.service').class_name == 'Drupal\\Core\\Test\\TestService'


@pytest.mark.asyncio
async def test_capability_does_not_register_hooks(server):
    """Test that ServicesCompletionCapability does NOT register hooks."""
    from drupalls.lsp.capabilities.services_capabilities import (
        ServicesCompletionCapability
    )
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Setup TextSyncManager
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    # Create and register capability
    capability = ServicesCompletionCapability(server)
    capability.register()
    
    # Verify NO hooks were registered by capability
    assert len(text_sync._on_save_hooks) == 0
```

## Performance Considerations

### Hook Performance

- **didSave**: Can do expensive work (parsing YAML, PHP analysis)
- **didChange**: Must be FAST (< 1ms) - only mark files as dirty
- **didOpen**: Moderate work (validate file, prepare cache)
- **didClose**: Fast cleanup only

### Incremental Updates

Caches should parse only the changed file, not rescan entire workspace:

```python
async def _on_services_file_saved(self, params):
    """Incremental update - only reparse this file."""
    uri = params.text_document.uri
    
    if not uri.endswith('.services.yml'):
        return
    
    file_path = Path(uri.replace('file://', ''))
    
    # Only reparse THIS file (fast)
    await self.parse_services_file(file_path)
    
    # NOT this (slow):
    # await self.scan()  # Would rescan entire workspace!
```

## Migration Checklist

If you have existing code with capabilities registering cache update hooks:

- [ ] Add `server` parameter to `CachedWorkspace.__init__()`
- [ ] Add `register_text_sync_hooks()` method to `CachedWorkspace` base class
- [ ] Implement `register_text_sync_hooks()` in each cache class (ServicesCache, HooksCache, etc.)
- [ ] Update `WorkspaceCache.__init__()` to accept and pass `server` parameter
- [ ] Add `_register_text_sync_hooks()` call to `WorkspaceCache.initialize()`
- [ ] Update `server.py` to pass `server=ls` when creating `WorkspaceCache`
- [ ] Remove hook registration from capability `register()` methods
- [ ] Update tests to verify caches (not capabilities) register hooks
- [ ] Verify initialization order: TextSyncManager → WorkspaceCache → CapabilityManager

## Summary

### Key Principles

1. **Caches own their data lifecycle** - They register hooks to keep themselves up-to-date
2. **Capabilities provide LSP features** - They use caches but don't manage them
3. **Separation of concerns** - Data management (cache) vs feature provision (capability)
4. **No duplication** - One cache, one set of hooks (even if multiple capabilities use it)
5. **Initialization order matters** - TextSyncManager must exist before caches try to register hooks

### Benefits

- ✅ Clean separation of responsibilities
- ✅ No duplicate hook registrations
- ✅ Loose coupling between components
- ✅ Easy to add new capabilities without touching cache code
- ✅ Easy to add new caches without touching capability code

## See Also

- **TextSyncManager Implementation**: `drupalls/lsp/text_sync_manager.py`
- **Base Cache Classes**: `drupalls/workspace/cache.py`
- **Services Cache Example**: `drupalls/workspace/services_cache.py`
- **LSP Text Sync Spec**: [Text Synchronization](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_synchronization)

---

**Remember**: Caches manage data, capabilities provide features. Keep them separated!
