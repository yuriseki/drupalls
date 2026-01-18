# Text Synchronization Architecture

## Overview

This document explains how DrupalLS handles text synchronization (tracking document changes) and how caches stay up-to-date using a **hook-based self-management pattern**.

## The Core Question

When files change in the editor (services YAML, PHP files, config schemas), how do caches stay up-to-date?

## Architectural Decision

**Text synchronization is infrastructure** that provides **hook extension points** for caches to keep themselves updated.

### Key Principle

**Caches manage their own lifecycle** by registering text sync hooks. Capabilities simply use the cache without managing it.

```
┌──────────────────────────────────────────┐
│         TextSyncManager                  │
│         (Infrastructure)                 │
│  - Receives LSP text sync events        │
│  - Broadcasts to registered hooks       │
└─────────────┬────────────────────────────┘
              │
              ├─→ ServicesCache._on_save()
              ├─→ HooksCache._on_save()
              └─→ ConfigCache._on_save()
```

## Why This Architecture?

### Alternative 1: Capabilities Update Caches ❌

```python
# Don't do this
class ServicesCompletionCapability(CompletionCapability):
    def register(self):
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._update_cache)  # WRONG
```

**Problems:**
- Violates Single Responsibility Principle
- Multiple capabilities using same cache = duplicate hooks
- Tight coupling between capability and cache
- Cache updates scattered across capability files

### Alternative 2: Direct LSP Handler Registration ❌

```python
# Don't do this
@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls, params):
    # Hardcoded cache updates in server.py
    services_cache.update(params)
    hooks_cache.update(params)
    # ... etc
```

**Problems:**
- Not extensible (must modify core code to add new caches)
- No plugin-based architecture
- All cache logic in one file

### Chosen Approach: Cache Self-Management ✅

```python
# Do this instead
class ServicesCache(CachedWorkspace):
    def register_text_sync_hooks(self):
        """Cache registers hooks to keep itself up-to-date."""
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_services_file_saved)
    
    async def _on_services_file_saved(self, params):
        """Update self when .services.yml files are saved."""
        uri = params.text_document.uri
        if uri.endswith('.services.yml'):
            await self.parse_services_file(...)
```

**Benefits:**
- ✅ Single Responsibility: Caches manage data, capabilities provide features
- ✅ No duplication: One cache, one set of hooks
- ✅ Loose coupling: Capabilities don't know how cache updates
- ✅ Extensible: New caches can register hooks without modifying core
- ✅ Self-contained: Cache owns its lifecycle

## Component Responsibilities

| Component | Responsibility | Registers Hooks? |
|-----------|---------------|-----------------|
| **TextSyncManager** | Infrastructure: receives LSP notifications, broadcasts to hooks | N/A |
| **ServicesCache** | Data: parse and store services | ✅ YES |
| **HooksCache** | Data: parse and store hooks | ✅ YES |
| **ConfigCache** | Data: parse and store config | ✅ YES |
| **ServicesCompletionCapability** | Feature: provide LSP completion | ❌ NO |
| **ServicesHoverCapability** | Feature: provide LSP hover | ❌ NO |
| **ServicesDefinitionCapability** | Feature: provide LSP definition | ❌ NO |
| **DiagnosticsCapability** | Feature: run validation | ⚠️ MAYBE* |

\* Diagnostics capability may register hooks for diagnostic-specific operations, NOT cache updates.

## Architecture Flow

### Initialization Flow

```
Server Startup:
│
├─ 1. Create TextSyncManager
│   └─ Registers LSP text sync handlers
│      (textDocument/didOpen, didChange, didSave, didClose)
│
├─ 2. Create WorkspaceCache (with server reference)
│   ├─ Creates cache instances (ServicesCache, etc.)
│   ├─ Each cache receives server reference
│   ├─ Performs initial workspace scan
│   └─ Calls cache.register_text_sync_hooks() for each cache
│      └─ Each cache registers its hooks with TextSyncManager
│
└─ 3. Create CapabilityManager
    └─ Capabilities just use caches (no hook registration)
```

### Text Sync Event Flow

```
User Action:
│
├─ User saves mymodule.services.yml
│
├─ Editor sends textDocument/didSave notification
│
├─ TextSyncManager receives notification
│   └─ Calls _broadcast_on_save(params)
│
├─ TextSyncManager calls all registered hooks:
│   ├─ ServicesCache._on_services_file_saved(params)
│   │   ├─ Checks if file ends with .services.yml ✓
│   │   ├─ Parses the file
│   │   └─ Updates cache
│   │
│   ├─ HooksCache._on_php_file_saved(params)
│   │   └─ Checks if file is PHP ✗ (skips)
│   │
│   └─ ConfigCache._on_config_file_saved(params)
│       └─ Checks if file is .schema.yml ✗ (skips)
│
└─ Cache is now up-to-date
    └─ Capabilities automatically see fresh data
```

## Implementation Pattern

### Base Classes

```python
# drupalls/workspace/cache.py

class CachedWorkspace(ABC):
    """Base class for all caches."""
    
    def __init__(
        self, 
        workspace_cache: WorkspaceCache, 
        server: DrupalLanguageServer | None = None
    ):
        self.workspace_cache = workspace_cache
        self.server = server
    
    def register_text_sync_hooks(self) -> None:
        """
        Override this to register hooks that keep cache up-to-date.
        
        Example:
            text_sync = self.server.text_sync_manager
            text_sync.add_on_save_hook(self._on_save)
        """
        pass  # Override in subclasses


class WorkspaceCache:
    """Main workspace cache manager."""
    
    def __init__(
        self,
        project_root: Path,
        workspace_root: Path,
        server: DrupalLanguageServer | None = None
    ):
        self.server = server
        
        # Create caches with server reference
        self.caches = {
            "services": ServicesCache(self, server),
            "hooks": HooksCache(self, server),
        }
    
    async def initialize(self):
        """Initialize caches and register hooks."""
        # Scan workspace
        await self._scan_workspace()
        
        # Register text sync hooks
        self._register_text_sync_hooks()
    
    def _register_text_sync_hooks(self):
        """Let each cache register its hooks."""
        for cache in self.caches.values():
            if isinstance(cache, CachedWorkspace):
                cache.register_text_sync_hooks()
```

### Cache Implementation

```python
# drupalls/workspace/services_cache.py

from lsprotocol.types import DidSaveTextDocumentParams


class ServicesCache(CachedWorkspace):
    """Cache for Drupal service definitions."""
    
    def register_text_sync_hooks(self):
        """Register hooks to keep services cache up-to-date."""
        if not self.server or not hasattr(self.server, 'text_sync_manager'):
            return
        
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_services_file_saved)
    
    async def _on_services_file_saved(
        self, 
        params: DidSaveTextDocumentParams
    ):
        """Update cache when .services.yml files are saved."""
        uri = params.text_document.uri
        
        # Filter: only handle .services.yml files
        if not uri.endswith('.services.yml'):
            return
        
        # Convert URI to path
        file_path = Path(uri.replace('file://', ''))
        
        # Incremental update: only reparse this file
        await self.parse_services_file(file_path)
        
        # Log success
        if self.server:
            self.server.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"✓ Updated services: {file_path.name}"
                )
            )
```

### Server Initialization

```python
# drupalls/lsp/server.py

@server.feature("initialize")
async def initialize(ls: DrupalLanguageServer, params):
    """Initialize server with correct component order."""
    
    # 1. TextSyncManager FIRST
    ls.text_sync_manager = TextSyncManager(ls)
    ls.text_sync_manager.register_handlers()
    
    # 2. WorkspaceCache with server reference
    #    (will register hooks during initialize())
    ls.workspace_cache = WorkspaceCache(
        project_root,
        workspace_root,
        server=ls  # Pass server for hook registration
    )
    await ls.workspace_cache.initialize()
    
    # 3. CapabilityManager last
    ls.capability_manager = CapabilityManager(ls)
    ls.capability_manager.register_all()
```

## When Capabilities SHOULD Register Hooks

Capabilities should ONLY register hooks for feature-specific operations, NOT cache updates:

### ✅ Valid Capability Hooks

```python
# Diagnostics ARE the capability's feature
class DiagnosticsCapability:
    def register(self):
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._run_diagnostics)
    
    async def _run_diagnostics(self, params):
        diagnostics = await self._analyze_file(params.text_document.uri)
        self.server.publish_diagnostics(uri, diagnostics)
```

### ❌ Invalid Capability Hooks

```python
# Cache updates are NOT the capability's responsibility
class ServicesCompletionCapability:
    def register(self):
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._update_cache)  # WRONG!
    
    async def _update_cache(self, params):
        # Cache should update itself!
        services_cache.parse_services_file(...)
```

## Decision Tree

```
Need to register a text sync hook?
│
├─ Is it for updating a shared cache?
│   └─→ ✅ Put in CACHE class (cache.register_text_sync_hooks())
│
├─ Is it for a feature-specific operation?
│   └─→ ✅ Put in CAPABILITY class (capability.register())
│
└─ Is it for infrastructure?
    └─→ ✅ Already handled by TextSyncManager
```

## Performance Considerations

### Event Performance Targets

- **didChange**: < 1ms (runs on every keystroke - only mark dirty)
- **didSave**: < 100ms (can do expensive work like parsing YAML)
- **didOpen**: < 50ms (moderate work)
- **didClose**: < 10ms (fast cleanup only)

### Incremental Updates

Caches should use incremental updates (reparse only changed file):

```python
# ✅ Good: Incremental update
async def _on_services_file_saved(self, params):
    file_path = Path(params.text_document.uri.replace('file://', ''))
    await self.parse_services_file(file_path)  # Only this file

# ❌ Bad: Full rescan
async def _on_services_file_saved(self, params):
    await self.scan()  # Rescans entire workspace!
```

## Trade-offs

### Benefits ✅

- Clean separation of concerns (data vs features)
- No duplicate hook registrations
- Loose coupling between components
- Extensible without modifying core
- Self-contained cache lifecycle management

### Costs ❌

- More complex than direct registration
- Hook management overhead
- Need to pass server reference through constructors
- Initialization order matters

## See Also

- **Implementation Guide**: `docs/IMPLEMENTATION-007-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md`
- **Quick Reference**: `docs/APPENDIX-05-TEXT_SYNC_HOOKS_QUICK_REF.md`
- **TextSyncManager**: `drupalls/lsp/text_sync_manager.py`
- **Cache Base Classes**: `drupalls/workspace/cache.py`
- **Services Cache**: `drupalls/workspace/services_cache.py`
- **LSP Text Sync Spec**: [Text Synchronization](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_synchronization)

---

**Remember**: Caches manage data, capabilities provide features. Keep them separated!
