# Workspace Cache Quick Reference

## TL;DR

**Use in-memory cache (NOT SQLite)** - It's 10-20x faster and simpler!

## Installation

```bash
poetry add pyyaml
poetry install
```

## Basic Usage

```python
from drupalls.workspace import WorkspaceCache
from pathlib import Path

# Initialize
cache = WorkspaceCache(Path('/path/to/drupal'))
await cache.initialize()

# Get all services
services = cache.get_services()  # Dict[str, ServiceDefinition]

# Get specific service
service = cache.get_service('entity_type.manager')

# Search services
results = cache.search_services('entity', limit=10)

# Invalidate on file change
cache.invalidate_file(Path('/path/to/module.services.yml'))
```

## Integration with Server

```python
# In server.py
@server.feature('initialize')
async def initialize(ls, params):
    workspace_root = Path(params.root_uri.replace('file://', ''))
    ls.workspace_cache = WorkspaceCache(workspace_root)
    await ls.workspace_cache.initialize()

# In completion.py
@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(ls, params):
    services = ls.workspace_cache.get_services()
    return CompletionList(items=[...])

# In text_sync.py
@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params):
    if file_path.name.endswith('.services.yml'):
        ls.workspace_cache.invalidate_file(file_path)
```

## Performance

| Operation | Time |
|-----------|------|
| Initial scan | 2-5s (medium project) |
| get_service() | < 1ms |
| search_services() | < 10ms |
| Load from disk | < 100ms |

## Why Not SQLite?

- ✅ In-Memory: < 1ms per query
- ❌ SQLite: 5-20ms per query

For 20 completions: **20ms vs 400ms** - huge difference in UX!

## Files

- `drupalls/workspace/cache.py` - Implementation
- `07-CACHE_USAGE.md` - Full guide
- `04-STORAGE_STRATEGY.md` - Architecture details

## API

### WorkspaceCache
- `get_services()` - Get all services
- `get_service(id)` - Get specific service
- `search_services(query, limit)` - Search services
- `invalidate_file(path)` - Re-parse file

### ServiceDefinition
- `service_id` - e.g., "entity_type.manager"
- `class_name` - e.g., "Drupal\\Core\\Entity\\EntityTypeManager"
- `short_description` - Friendly name

That's it! See 07-CACHE_USAGE.md for complete documentation.
