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
from drupalls.workspace.cache import WorkspaceCache
from drupalls.utils.find_files import find_drupal_root
from pathlib import Path

# Find Drupal root (where core/ directory is)
project_root = Path('/path/to/project')
drupal_root = find_drupal_root(project_root)

# Initialize cache with both roots
cache = WorkspaceCache(project_root, drupal_root)
await cache.initialize()

# Access services cache
services_cache = cache.caches.get("services")

# Get all services
all_services = services_cache.get_all()  # Mapping[str, ServiceDefinition]

# Get specific service
service = services_cache.get('entity_type.manager')

# Search services
results = services_cache.search('entity', limit=10)

# Invalidate on file change
cache.invalidate_file(Path('/path/to/module.services.yml'))
```

## Integration with Server

```python
# In server.py
from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.utils.find_files import find_drupal_root
from lsprotocol.types import InitializeParams

@server.feature('initialize')
async def initialize(ls: DrupalLanguageServer, params: InitializeParams):
    workspace_folders = params.workspace_folders
    if not workspace_folders:
        return
    
    project_root = Path(workspace_folders[0].uri.replace('file://', ''))
    drupal_root = find_drupal_root(project_root)
    
    if not drupal_root:
        ls.show_message("Drupal installation not found")
        return
    
    ls.workspace_cache = WorkspaceCache(project_root, drupal_root)
    await ls.workspace_cache.initialize()

# In completion.py
@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: DrupalLanguageServer, params: CompletionParams):
    if not ls.workspace_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    services_cache = ls.workspace_cache.caches.get("services")
    if not services_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    all_services = services_cache.get_all()
    return CompletionList(items=[...])

# In text_sync.py
@server.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: DrupalLanguageServer, params: DidChangeTextDocumentParams):
    if not ls.workspace_cache:
        return
    
    file_path = Path(params.text_document.uri.replace('file://', ''))
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
- `APPENDIX-03-CACHE_USAGE.md` - Full guide
- `04-STORAGE_STRATEGY.md` - Architecture details

## API

### WorkspaceCache
**Constructor**: `WorkspaceCache(project_root: Path, workspace_root: Path, caches: dict | None = None)`
- `project_root` - LSP workspace root (where user opened project)
- `workspace_root` - Drupal root (where core/ directory is)

**Methods**:
- `async initialize()` - Scan workspace and populate caches
- `invalidate_file(path: Path)` - Re-parse specific file

**Access caches**: `workspace_cache.caches["services"]`

### ServicesCache (via `workspace_cache.caches["services"]`)
- `get(id: str)` - Get specific service
- `get_all()` - Get all services as `Mapping[str, ServiceDefinition]`
- `search(query: str, limit: int)` - Search services
- `invalidate_file(path: Path)` - Re-parse specific YAML file

### ServiceDefinition
- `id` - e.g., "entity_type.manager"
- `class_name` - e.g., "Drupal\\Core\\Entity\\EntityTypeManager"
- `description` - Description string
- `file_path` - Path to .services.yml file
- `line_number` - Line number in YAML
- `arguments` - List of service arguments
- `tags` - List of service tags

That's it! See APPENDIX-03-CACHE_USAGE.md for complete documentation.
