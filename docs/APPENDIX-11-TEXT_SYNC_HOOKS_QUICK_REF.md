# Text Sync Hooks Quick Reference

## Quick Start

### For Cache Developers

**To make your cache self-updating:**

```python
from lsprotocol.types import DidSaveTextDocumentParams
from drupalls.workspace.cache import CachedWorkspace


class MyCache(CachedWorkspace):
    """Your custom cache."""
    
    def register_text_sync_hooks(self) -> None:
        """Register hooks to keep cache up-to-date."""
        if not self.server or not hasattr(self.server, 'text_sync_manager'):
            return
        
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_file_saved)
    
    async def _on_file_saved(self, params: DidSaveTextDocumentParams) -> None:
        """Update cache when relevant files are saved."""
        uri = params.text_document.uri
        
        # Filter for your file type
        if not uri.endswith('.your_extension'):
            return
        
        # Update cache incrementally
        file_path = Path(uri.replace('file://', ''))
        await self.parse_file(file_path)
```

### For Capability Developers

**Capabilities DON'T register cache update hooks:**

```python
class MyCompletionCapability(CompletionCapability):
    """Your LSP feature capability."""
    
    def register(self) -> None:
        """No hooks needed - cache manages itself."""
        pass  # Cache updates automatically
    
    async def complete(self, params):
        """Just use the cache - it's always fresh."""
        my_cache = self.workspace_cache.caches['my_cache']
        data = my_cache.get_all()
        # Build completions...
```

**ONLY register hooks for feature-specific operations:**

```python
class DiagnosticsCapability(BaseCapability):
    """Diagnostics are a feature, not cache management."""
    
    def register(self) -> None:
        # This is OK - diagnostics ARE the feature
        text_sync = self.server.text_sync_manager
        text_sync.add_on_save_hook(self._run_diagnostics)
    
    async def _run_diagnostics(self, params):
        diagnostics = await self._analyze_file(params.text_document.uri)
        self.server.publish_diagnostics(uri, diagnostics)
```

## Hook Types

### Available Hooks

```python
text_sync = self.server.text_sync_manager

# File opened in editor
text_sync.add_on_open_hook(self._on_open)

# File changed (EVERY KEYSTROKE - keep fast!)
text_sync.add_on_change_hook(self._on_change)

# File saved (best for cache updates)
text_sync.add_on_save_hook(self._on_save)

# File closed in editor
text_sync.add_on_close_hook(self._on_close)
```

### Hook Signatures

```python
from lsprotocol.types import (
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    DidSaveTextDocumentParams,
    DidCloseTextDocumentParams,
)

# Open hook
async def _on_open(self, params: DidOpenTextDocumentParams) -> None:
    uri = params.text_document.uri
    text = params.text_document.text
    # ...

# Change hook (MUST BE FAST < 1ms)
async def _on_change(self, params: DidChangeTextDocumentParams) -> None:
    uri = params.text_document.uri
    # Only mark as dirty, don't parse!
    self._dirty_files.add(uri)

# Save hook (can do expensive work)
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    # Parse, update cache, etc.
    await self.parse_file(uri)

# Close hook
async def _on_close(self, params: DidCloseTextDocumentParams) -> None:
    uri = params.text_document.uri
    # Cleanup resources
    self._open_files.discard(uri)
```

## Common Patterns

### Pattern 1: Filter by File Extension

```python
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    
    # Only handle specific file types
    if not uri.endswith('.services.yml'):
        return  # Skip other files
    
    # Process your file type
    await self.parse_services_file(uri)
```

### Pattern 2: Convert URI to Path

```python
from pathlib import Path

async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    
    # Convert URI to filesystem path
    file_path = Path(uri.replace('file://', ''))
    
    # Use file path
    await self.parse_file(file_path)
```

### Pattern 3: Check Workspace Scope

```python
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    file_path = Path(uri.replace('file://', ''))
    
    # Only process files in workspace
    try:
        file_path.relative_to(self.workspace_cache.workspace_root)
    except ValueError:
        return  # File outside workspace
    
    await self.parse_file(file_path)
```

### Pattern 4: Handle File Deletion

```python
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    file_path = Path(uri.replace('file://', ''))
    
    try:
        # Try to parse file
        await self.parse_file(file_path)
    except FileNotFoundError:
        # File was deleted - remove from cache
        self._remove_entries_from_file(file_path)
```

### Pattern 5: Incremental Update

```python
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    file_path = Path(uri.replace('file://', ''))
    
    # ✅ Good: Only reparse this file
    await self.parse_file(file_path)
    
    # ❌ Bad: Rescan entire workspace
    # await self.scan()
```

### Pattern 6: Error Handling

```python
async def _on_save(self, params: DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    
    try:
        await self.parse_file(uri)
        
        # Log success
        if self.server:
            self.server.window_log_message(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"✓ Updated cache: {Path(uri).name}"
                )
            )
    
    except FileNotFoundError:
        # Handle deletion
        self._remove_entries(uri)
        
        if self.server:
            self.server.window_log_message(
                LogMessageParams(
                    type=MessageType.Warning,
                    message=f"File deleted: {Path(uri).name}"
                )
            )
    
    except Exception as e:
        # Log error but don't crash
        if self.server:
            self.server.window_log_message(
                LogMessageParams(
                    type=MessageType.Error,
                    message=f"Error updating cache: {type(e).__name__}: {e}"
                )
            )
```

## Performance Guidelines

### Hook Performance Targets

| Hook Type | Target | Purpose |
|-----------|--------|---------|
| `on_change` | **< 1ms** | Mark file dirty only (runs on every keystroke!) |
| `on_save` | < 100ms | Parse files, update caches |
| `on_open` | < 50ms | Initial validation, prepare cache |
| `on_close` | < 10ms | Fast cleanup only |

### DO and DON'T

#### ✅ DO

```python
# DO: Quick dirty marking in on_change
async def _on_change(self, params):
    uri = params.text_document.uri
    self._dirty_files.add(uri)  # Fast!

# DO: Full parsing in on_save
async def _on_save(self, params):
    uri = params.text_document.uri
    await self.parse_file(uri)  # OK - user expects delay on save

# DO: Filter early
async def _on_save(self, params):
    if not params.text_document.uri.endswith('.yml'):
        return  # Skip immediately
    # ... expensive work ...

# DO: Incremental updates
async def _on_save(self, params):
    file_path = Path(params.text_document.uri.replace('file://', ''))
    await self.parse_file(file_path)  # Only this file
```

#### ❌ DON'T

```python
# DON'T: Expensive work in on_change
async def _on_change(self, params):
    await self.parse_file(params.text_document.uri)  # TOO SLOW!

# DON'T: Full workspace scans
async def _on_save(self, params):
    await self.scan()  # Rescans everything - very slow!

# DON'T: Blocking I/O without checking file type
async def _on_save(self, params):
    # Checks ALL files, even non-YAML
    file_path = Path(params.text_document.uri.replace('file://', ''))
    if file_path.suffix != '.yml':
        return
    # ... work ...

# Better:
async def _on_save(self, params):
    # Check URI string first (no I/O)
    if not params.text_document.uri.endswith('.yml'):
        return
    # ... work ...
```

## Initialization Order

**CRITICAL**: Components must be initialized in this order:

```python
# drupalls/lsp/server.py

@server.feature("initialize")
async def initialize(ls, params):
    # 1. TextSyncManager FIRST
    ls.text_sync_manager = TextSyncManager(ls)
    ls.text_sync_manager.register_handlers()
    
    # 2. WorkspaceCache with server reference
    ls.workspace_cache = WorkspaceCache(
        project_root,
        workspace_root,
        server=ls  # Pass server!
    )
    await ls.workspace_cache.initialize()  # Registers hooks
    
    # 3. CapabilityManager last
    ls.capability_manager = CapabilityManager(ls)
    ls.capability_manager.register_all()
```

**Why?** Caches need `text_sync_manager` to exist when they call `register_text_sync_hooks()`.

## Testing

### Test Cache Registers Hooks

```python
@pytest.mark.asyncio
async def test_cache_registers_hooks(server):
    """Test that cache registers hooks correctly."""
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Setup
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    # Create cache with server
    cache = MyCache(workspace_cache, server=server)
    cache.register_text_sync_hooks()
    
    # Verify
    assert len(text_sync._on_save_hooks) == 1
    assert cache._on_file_saved in text_sync._on_save_hooks
```

### Test Hook Execution

```python
@pytest.mark.asyncio
async def test_cache_updates_on_save(server, tmp_path):
    """Test that cache updates when file is saved."""
    from drupalls.lsp.text_sync_manager import TextSyncManager
    from lsprotocol.types import (
        DidSaveTextDocumentParams,
        TextDocumentIdentifier,
    )
    
    # Setup
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    cache = MyCache(workspace_cache, server=server)
    cache.register_text_sync_hooks()
    
    # Create test file
    test_file = tmp_path / "test.yml"
    test_file.write_text("data: value")
    
    # Trigger save event
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=f'file://{test_file}')
    )
    await text_sync._broadcast_on_save(params)
    
    # Verify cache updated
    assert cache.get('test_key') is not None
```

## Decision Checklist

### Should I Register a Hook?

Ask yourself:

1. **Am I implementing a cache?**
   - ✅ YES → Register hooks in `register_text_sync_hooks()`
   - ❌ NO → Go to question 2

2. **Am I implementing a capability?**
   - ✅ YES → Go to question 3
   - ❌ NO → You probably don't need hooks

3. **Is this hook for updating a shared cache?**
   - ✅ YES → DON'T register hook (let cache manage itself)
   - ❌ NO → Go to question 4

4. **Is this hook for a feature-specific operation?**
   - ✅ YES (diagnostics, formatting, etc.) → Register in `capability.register()`
   - ❌ NO → You probably don't need hooks

## Troubleshooting

### Hook Not Called

**Problem**: Your hook never executes.

**Solutions**:
1. Check initialization order (TextSyncManager must exist first)
2. Verify `server.text_sync_manager` is not None
3. Check your file extension filter
4. Use logging to verify hook registration

```python
def register_text_sync_hooks(self):
    if not self.server or not hasattr(self.server, 'text_sync_manager'):
        print("WARNING: No text_sync_manager available!")
        return
    
    text_sync = self.server.text_sync_manager
    if not text_sync:
        print("WARNING: text_sync_manager is None!")
        return
    
    text_sync.add_on_save_hook(self._on_save)
    print(f"✓ Registered hook: {self._on_save.__name__}")
```

### Hook Called Too Many Times

**Problem**: Cache updates multiple times per save.

**Solutions**:
1. Check if multiple capabilities are registering cache update hooks (WRONG!)
2. Ensure only the cache itself registers hooks
3. Use debouncing if needed

### Hook Too Slow

**Problem**: Editor lags when typing or saving files.

**Solutions**:
1. If using `on_change`: Only mark dirty, don't parse
2. Filter file extensions EARLY (check URI string before file I/O)
3. Use incremental updates (reparse one file, not entire workspace)
4. Profile with timing logs

```python
import time

async def _on_save(self, params):
    start = time.time()
    
    uri = params.text_document.uri
    
    # Early filter (fast)
    if not uri.endswith('.services.yml'):
        return
    
    # Parse (may be slow)
    await self.parse_file(uri)
    
    elapsed = (time.time() - start) * 1000
    print(f"Hook took {elapsed:.2f}ms")
```

## See Also

- **Full Guide**: `docs/APPENDIX-12-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md`
- **Architecture**: `docs/05-TEXT_SYNC_ARCHITECTURE.md`
- **TextSyncManager**: `drupalls/lsp/text_sync_manager.py`
- **Cache Base**: `drupalls/workspace/cache.py`
- **Services Cache Example**: `drupalls/workspace/services_cache.py`

---

**Remember**: Caches register hooks, capabilities use caches!
