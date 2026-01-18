# Implementing Text Sync Hooks in ServicesCache

## Overview

This guide walks through implementing text synchronization hooks in `ServicesCache` so that the cache automatically updates when `.services.yml` files are saved. This enables real-time updates for service references in completion, hover, and other LSP features.

**What You'll Implement**: Self-managing cache that registers its own text sync hooks to stay fresh when Drupal service files change.

## Prerequisites

Before implementing cache hooks, you should understand:

- **TextSyncManager**: Provides hook registration API (from `docs/IMPLEMENTATION-008-IMPLEMENTING_TEXT_SYNC_MANAGER.md`)
- **Cache Self-Management**: Why caches should manage themselves (from `docs/IMPLEMENTATION-007-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md`)
- **ServicesCache**: Current implementation (from `docs/APPENDIX-03-CACHE_USAGE.md`)

## Current Architecture Review

### How Services Are Currently Used

```python
# In completion capability
async def complete(self, params: CompletionParams) -> CompletionList:
    services_cache = self.workspace_cache.caches['services']
    all_services = services_cache.get_all()  # Gets cached services
    
    # Build completion items from cache
    items = [
        CompletionItem(label=service_id, ...)
        for service_id, service_def in all_services.items()
    ]
    return CompletionList(is_incomplete=False, items=items)
```

**Problem**: If a `.services.yml` file changes, the cache becomes stale until server restart.

### Desired Behavior

```
1. Developer edits mymodule.services.yml
2. Adds new service: 'mymodule.custom_service'
3. Saves file
4. Cache automatically updates
5. Service appears in completion without restart
```

## Implementation Steps

### Step 1: Update CachedWorkspace Base Class

First, ensure the base class supports hook registration:

```python
# drupalls/workspace/cache.py

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer

class CachedWorkspace(ABC):
    """Abstract base class for workspace caches."""
    
    def __init__(
        self, 
        workspace_cache: WorkspaceCache, 
        server: DrupalLanguageServer | None = None
    ):
        self.workspace_cache = workspace_cache
        self.server = server  # Server reference for hooks
        
        # ... existing attributes ...
    
    def register_text_sync_hooks(self) -> None:
        """
        Register text sync hooks to keep cache up-to-date.
        
        Override in subclasses to register hooks with TextSyncManager
        that update the cache when relevant files change.
        """
        pass  # Default: no hooks
```

### Step 2: Update WorkspaceCache Constructor

Ensure caches receive the server reference:

```python
# drupalls/workspace/cache.py

class WorkspaceCache:
    def __init__(
        self,
        project_root: Path,
        workspace_root: Path,
        server: DrupalLanguageServer | None = None
    ):
        self.server = server
        
        # Initialize caches WITH server reference
        self.caches = {
            "services": ServicesCache(self, server),  # Pass server
        }
    
    async def initialize(self):
        # ... existing initialization ...
        
        # After scanning, register hooks for all caches
        self._register_text_sync_hooks()
    
    def _register_text_sync_hooks(self) -> None:
        """Register text sync hooks for all caches."""
        for cache in self.caches.values():
            if isinstance(cache, CachedWorkspace):
                cache.register_text_sync_hooks()
```

### Step 3: Implement Hook Registration in ServicesCache

Add hook registration and handling methods:

```python
# drupalls/workspace/services_cache.py

from pathlib import Path
from lsprotocol.types import (
    DidSaveTextDocumentParams,
    LogMessageParams,
    MessageType,
)

class ServicesCache(CachedWorkspace):
    """Cache for Drupal service definitions with self-updating hooks."""
    
    def register_text_sync_hooks(self) -> None:
        """
        Register hooks to keep services cache up-to-date.
        
        Registers a save hook that updates the cache when
        .services.yml files are saved.
        """
        if not self.server or not hasattr(self.server, 'text_sync_manager'):
            return
        
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_services_file_saved)
    
    async def _on_services_file_saved(
        self, 
        params: DidSaveTextDocumentParams
    ) -> None:
        """
        Update cache when a .services.yml file is saved.
        
        This method is called automatically by TextSyncManager
        when any file is saved. We filter for .services.yml files
        and update the cache incrementally.
        """
        uri = params.text_document.uri
        
        # Filter: Only handle .services.yml files
        if not uri.endswith('.services.yml'):
            return
        
        try:
            # Convert URI to file path
            file_path = Path(uri.replace('file://', ''))
            
            # Check if file is within our workspace
            if not self._is_in_workspace(file_path):
                return
            
            # Re-parse this specific file (incremental update)
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
            # File was deleted - remove services from cache
            self._remove_services_from_file(file_path)
            
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Services file deleted: {file_path.name}"
                    )
                )
        
        except Exception as e:
            # Log errors but don't crash
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating services cache: {type(e).__name__}: {e}"
                    )
                )
    
    def _is_in_workspace(self, file_path: Path) -> bool:
        """Check if file path is within workspace root."""
        try:
            file_path.relative_to(self.workspace_cache.workspace_root)
            return True
        except ValueError:
            return False
    
    def _remove_services_from_file(self, file_path: Path) -> None:
        """Remove all services defined in a specific file."""
        # Remove services that came from this file
        self._services = {
            service_id: service_def
            for service_id, service_def in self._services.items()
            if service_def.file_path != file_path
        }
        
        # Remove file from tracking
        if file_path in self.file_info:
            del self.file_info[file_path]
```

### Step 4: Update Server Initialization

Ensure correct initialization order:

```python
# drupalls/lsp/server.py

def create_server() -> DrupalLanguageServer:
    server = DrupalLanguageServer("drupalls", "0.1.0")
    
    @server.feature("initialize")
    async def initialize(ls: DrupalLanguageServer, params):
        # 1. Initialize TextSyncManager FIRST
        ls.text_sync_manager = TextSyncManager(ls)
        ls.text_sync_manager.register_handlers()
        
        # 2. Initialize WorkspaceCache with server reference
        workspace_root = Path(params.root_uri.replace("file://", ""))
        drupal_root = find_drupal_root(workspace_root)
        
        ls.workspace_cache = WorkspaceCache(
            workspace_root,
            drupal_root,
            server=ls  # Pass server for hook registration
        )
        await ls.workspace_cache.initialize()  # Scans + registers hooks
        
        # 3. Initialize CapabilityManager
        ls.capability_manager = CapabilityManager(ls)
        ls.capability_manager.register_all()
```

### Step 5: Update parse_services_file for Incremental Updates

Ensure the parsing method can handle updates to existing files:

```python
# drupalls/workspace/services_cache.py

async def parse_services_file(self, file_path: Path) -> None:
    """
    Parse a single .services.yml file and update cache.
    
    This method handles both initial scanning and incremental updates.
    """
    # Calculate file hash for change detection
    file_hash = calculate_file_hash(file_path)
    
    # Load and parse YAML
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Extract services
    services = data.get('services', {}) if data else {}
    
    # Remove existing services from this file (for updates)
    self._services = {
        sid: sdef for sid, sdef in self._services.items()
        if sdef.file_path != file_path
    }
    
    # Add/update services from this file
    for service_id, service_data in services.items():
        service_def = ServiceDefinition(
            id=service_id,
            class_name=service_data.get('class', ''),
            description=service_data.get('class', ''),
            arguments=service_data.get('arguments', []),
            tags=service_data.get('tags', []),
            file_path=file_path,
            line_number=self._find_service_line(file_path, service_id),
        )
        self._services[service_id] = service_def
    
    # Track file for future updates
    self.file_info[file_path] = FileInfo(
        path=file_path,
        hash=file_hash,
        last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
    )

def _find_service_line(self, file_path: Path, service_id: str) -> int:
    """Find the line number where a service is defined."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if f'{service_id}:' in line:
                return i
    except Exception:
        pass
    
    return 0
```

## Testing the Implementation

### Unit Test: Hook Registration

```python
# tests/test_services_cache_hooks.py

import pytest
from pathlib import Path
from lsprotocol.types import DidSaveTextDocumentParams, TextDocumentIdentifier

@pytest.mark.asyncio
async def test_services_cache_registers_hooks(tmp_path):
    """Test that ServicesCache registers text sync hooks."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Mock server with text sync manager
    server = Mock()
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    # Create workspace cache
    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    
    # Get services cache and register hooks
    cache = workspace_cache.caches['services']
    cache.register_text_sync_hooks()
    
    # Verify hook was registered
    assert len(text_sync._on_save_hooks) == 1
    assert cache._on_services_file_saved in text_sync._on_save_hooks

@pytest.mark.asyncio
async def test_services_cache_updates_on_save(tmp_path):
    """Test that cache updates when .services.yml file is saved."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Setup
    server = Mock()
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    cache = workspace_cache.caches['services']
    cache.register_text_sync_hooks()
    
    # Create test services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Core\\Test\\TestService
""")
    
    # Simulate save event
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=f'file://{services_file}')
    )
    
    # Trigger hook
    await text_sync._broadcast_on_save(params)
    
    # Verify cache was updated
    service = cache.get('test.service')
    assert service is not None
    assert service.class_name == 'Drupal\\Core\\Test\\TestService'
```

### Integration Test: End-to-End Flow

```python
# tests/test_services_cache_integration.py

@pytest.mark.asyncio
async def test_edit_services_file_updates_cache(tmp_path):
    """Test that editing a services file updates the cache in real-time."""
    from drupalls.workspace.services_cache import ServicesCache
    
    # Setup full server
    server = create_server()
    text_sync = TextSyncManager(server)
    text_sync.register_handlers()
    server.text_sync_manager = text_sync
    
    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    await workspace_cache.initialize()
    
    # Initially empty
    cache = workspace_cache.caches['services']
    assert len(cache.get_all()) == 0
    
    # Create services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  initial.service:
    class: Drupal\\Core\\Initial\\InitialService
""")
    
    # Simulate save (this would normally be triggered by LSP)
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=f'file://{services_file}')
    )
    await text_sync._broadcast_on_save(params)
    
    # Verify service was added
    assert cache.get('initial.service') is not None
    
    # Edit file to add another service
    services_file.write_text("""
services:
  initial.service:
    class: Drupal\\Core\\Initial\\InitialService
  new.service:
    class: Drupal\\Core\\New\\NewService
""")
    
    # Simulate another save
    await text_sync._broadcast_on_save(params)
    
    # Verify both services exist
    assert cache.get('initial.service') is not None
    assert cache.get('new.service') is not None
    assert len(cache.get_all()) == 2
```

## Performance Considerations

### Incremental vs Full Updates

**✅ Correct (Incremental)**:
```python
async def _on_services_file_saved(self, params):
    # Only re-parse the changed file
    file_path = Path(uri.replace('file://', ''))
    await self.parse_services_file(file_path)
```

**❌ Wrong (Full Scan)**:
```python
async def _on_services_file_saved(self, params):
    # DON'T DO THIS - rescans entire workspace!
    await self.scan()  # Slow for large projects
```

### Hook Performance

- **didSave hooks can be slower** (parsing YAML is acceptable)
- **didChange hooks must be fast** (< 1ms - only mark dirty)
- **Use file hashing** to avoid unnecessary re-parsing

```python
# In parse_services_file
new_hash = calculate_file_hash(file_path)
old_info = self.file_info.get(file_path)

if old_info and old_info.hash == new_hash:
    return  # Skip parsing if content unchanged
```

## Error Handling

### File Access Errors

```python
async def _on_services_file_saved(self, params):
    try:
        file_path = Path(uri.replace('file://', ''))
        await self.parse_services_file(file_path)
    except FileNotFoundError:
        # File was deleted
        self._remove_services_from_file(file_path)
    except PermissionError:
        # Can't read file
        self.server.window_log_message("Permission denied: {file_path}")
    except yaml.YAMLError as e:
        # Invalid YAML
        self.server.window_log_message(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        # Catch-all for unexpected errors
        self.server.window_log_message(f"Unexpected error updating cache: {e}")
```

### Hook Isolation

TextSyncManager catches hook errors automatically, so one failing cache doesn't break others:

```python
# In TextSyncManager._broadcast_on_save
for hook in self._on_save_hooks:
    try:
        await hook(params)
    except Exception as e:
        self.server.window_log_message(
            LogMessageParams(
                type=MessageType.Error,
                message=f"Hook error in {hook.__name__}: {e}"
            )
        )
```

## Debugging

### Enable Debug Logging

```python
# In _on_services_file_saved
self.server.window_log_message(
    LogMessageParams(
        type=MessageType.Info,
        message=f"Processing services file: {file_path.name}"
    )
)

# After parsing
service_count = len([s for s in self._services.values() if s.file_path == file_path])
self.server.window_log_message(
    LogMessageParams(
        type=MessageType.Info,
        message=f"Loaded {service_count} services from {file_path.name}"
    )
)
```

### Check Hook Registration

```python
# In register_text_sync_hooks
if text_sync:
    self.server.window_log_message(
        LogMessageParams(
            type=MessageType.Info,
            message="ServicesCache registered save hook"
        )
    )
```

### Verify Cache Updates

```python
# After parsing
if self.server:
    services = list(self._services.keys())[:3]  # First 3 services
    self.server.window_log_message(
        LogMessageParams(
            type=MessageType.Info,
            message=f"Cache contains: {', '.join(services)}"
        )
    )
```

## Migration from Manual Updates

If you have existing code that manually updates the cache:

### Before (Manual Updates)

```python
# In capability.register()
def register(self):
    text_sync.add_on_save_hook(self._update_cache)

async def _update_cache(self, params):
    if params.text_document.uri.endswith('.services.yml'):
        # Manual cache update
        services_cache = self.workspace_cache.caches['services']
        await services_cache.parse_services_file(...)
```

### After (Self-Managing Cache)

```python
# In ServicesCache.register_text_sync_hooks()
def register_text_sync_hooks(self):
    text_sync.add_on_save_hook(self._on_services_file_saved)

async def _on_services_file_saved(self, params):
    # Cache updates itself
    if params.text_document.uri.endswith('.services.yml'):
        file_path = Path(params.text_document.uri.replace('file://', ''))
        await self.parse_services_file(file_path)

# In capability.register()
def register(self):
    # No hooks needed - cache manages itself
    pass
```

## Summary

### What You Implemented

1. **Self-Registering Hooks**: ServicesCache automatically registers text sync hooks
2. **Incremental Updates**: Only changed files are re-parsed, not entire workspace
3. **Real-Time Updates**: Service references update immediately when files are saved
4. **Error Isolation**: Hook failures don't break other functionality
5. **Proper Separation**: Cache manages data, capabilities provide features

### Benefits

- ✅ **Real-time updates**: No restart needed when editing services
- ✅ **Better performance**: Incremental parsing instead of full scans
- ✅ **Clean architecture**: Caches own their lifecycle
- ✅ **Reliability**: Error handling prevents crashes
- ✅ **Maintainability**: Clear separation of concerns

### Key Files Modified

- `drupalls/workspace/cache.py` - Added server parameter and hook registration
- `drupalls/workspace/services_cache.py` - Added hook registration and incremental updates
- `drupalls/lsp/server.py` - Updated initialization order
- `tests/` - Added tests for hook registration and updates

### Next Steps

1. **Test thoroughly** with real Drupal projects
2. **Monitor performance** in large codebases
3. **Apply pattern** to other caches (HooksCache, ConfigCache)
4. **Update documentation** to reflect the new architecture

This implementation enables DrupalLS to provide accurate, real-time service completion and references without requiring server restarts!</content>
<parameter name="filePath">docs/IMPLEMENTATION-009-IMPLEMENTING_CACHE_HOOKS_SERVICES.md