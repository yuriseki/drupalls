# Workspace Cache Usage Guide

## Overview

The `WorkspaceCache` class manages all parsed Drupal data in memory for fast access. It's the foundation for all features (completion, hover, go-to-definition, etc.).

## Installation

```bash
poetry add pyyaml
poetry install
```

## Basic Usage

### 1. Initialize Cache in Server

```python
# drupalls/lsp/server.py
from pathlib import Path
from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.workspace.cache import WorkspaceCache
from drupalls.utils.find_files import find_drupal_root
from lsprotocol.types import InitializeParams

def create_server() -> DrupalLanguageServer:
    server = DrupalLanguageServer("drupalls", "0.1.0")
    
    @server.feature('initialize')
    async def initialize(ls: DrupalLanguageServer, params: InitializeParams):
        # Get workspace root from params
        workspace_folders = params.workspace_folders
        if not workspace_folders:
            return
        
        project_root = Path(workspace_folders[0].uri.replace('file://', ''))
        
        # Find Drupal root (where core/ directory is located)
        drupal_root = find_drupal_root(project_root)
        if not drupal_root:
            ls.show_message("Drupal installation not found")
            return
        
        # Initialize cache with both roots
        ls.workspace_cache = WorkspaceCache(project_root, drupal_root)
        await ls.workspace_cache.initialize()
        
        # Access services via caches dictionary
        services_cache = ls.workspace_cache.caches.get("services")
        if services_cache:
            service_count = len(services_cache.get_all())
            ls.show_message_log(f"Scanned {service_count} services")
    
    return server
```

### 2. Use Cache in Features

```python
# drupalls/lsp/features/completion.py
from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    CompletionItemKind,
    TEXT_DOCUMENT_COMPLETION,
)
from drupalls.lsp.drupal_language_server import DrupalLanguageServer

@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: DrupalLanguageServer, params: CompletionParams) -> CompletionList:
    # Guard: check if cache is available
    if not ls.workspace_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    doc = ls.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]
    
    # Check if we're completing a service
    if "::service('" in line or '::service("' in line:
        # Get services cache
        services_cache = ls.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get all services from cache
        all_services = services_cache.get_all()
        
        items = [
            CompletionItem(
                label=service_id,
                kind=CompletionItemKind.Value,
                detail=service_def.class_name,
                documentation=service_def.description,
                insert_text=service_id,
            )
            for service_id, service_def in all_services.items()
        ]
        
        return CompletionList(is_incomplete=False, items=items)
    
    return CompletionList(is_incomplete=False, items=[])
```

### 3. Invalidate Cache on File Changes

```python
# drupalls/lsp/features/text_sync.py
from pathlib import Path
from lsprotocol.types import (
    DidChangeTextDocumentParams,
    TEXT_DOCUMENT_DID_CHANGE,
)
from drupalls.lsp.drupal_language_server import DrupalLanguageServer

@server.feature(TEXT_DOCUMENT_DID_CHANGE)
async def did_change(ls: DrupalLanguageServer, params: DidChangeTextDocumentParams):
    if not ls.workspace_cache:
        return
    
    file_path = Path(params.text_document.uri.replace('file://', ''))
    
    # If it's a services.yml file, invalidate cache
    if file_path.name.endswith('.services.yml'):
        ls.workspace_cache.invalidate_file(file_path)
        ls.show_message_log(f"Re-parsed {file_path.name}")
```

## API Reference

### WorkspaceCache

#### `__init__(project_root: Path, workspace_root: Path, caches: dict[str, CachedWorkspace] | None = None)`
Create a new cache for the workspace.

**Parameters:**
- `project_root`: LSP workspace root (where user opened the project)
- `workspace_root`: Drupal root (where `core/` directory is located)
- `caches`: Optional dictionary of cache implementations (defaults to `{"services": ServicesCache(self)}`)

#### `async initialize()`
Scan workspace and populate all caches. Call this once when workspace opens.

Loads from disk cache if available, otherwise scans the workspace.

#### `invalidate_file(file_path: Path)`
Invalidate and re-parse a specific file across all caches.

### Accessing Caches

WorkspaceCache uses a dictionary-based plugin architecture. Access specific caches via the `caches` attribute:

```python
# Get the services cache
services_cache = workspace_cache.caches.get("services")
if services_cache:
    # Get all services
    all_services = services_cache.get_all()  # Returns dict[str, ServiceDefinition]
    
    # Get specific service
    service = services_cache.get("entity_type.manager")
    
    # Search services
    results = services_cache.search("entity", limit=10)
```

### ServicesCache (CachedWorkspace)

Accessed via `workspace_cache.caches["services"]`

#### `get(id: str) -> ServiceDefinition | None`
Get a specific service by ID.

```python
services_cache = workspace_cache.caches["services"]
service = services_cache.get('entity_type.manager')
if service:
    print(f"Class: {service.class_name}")
    print(f"Description: {service.description}")
```

#### `get_all() -> Mapping[str, ServiceDefinition]`
Get all services as a dictionary mapping service ID to ServiceDefinition.

```python
all_services = services_cache.get_all()
for service_id, service_def in all_services.items():
    print(f"{service_id}: {service_def.class_name}")
```

#### `search(query: str, limit: int = 50) -> Sequence[ServiceDefinition]`
Search services by partial match on ID or class name.

```python
# Find all services containing "entity"
results = services_cache.search('entity', limit=10)
for service in results:
    print(service.id)
```

#### `invalidate_file(file_path: Path)`
Invalidate and re-parse a specific services YAML file.

### ServiceDefinition

Defined in `drupalls/workspace/services_cache.py`:

```python
@dataclass
class ServiceDefinition(CachedDataBase):
    """Represents a Drupal service definition."""
    
    # Inherited from CachedDataBase:
    id: str                  # Service ID (e.g., "entity_type.manager")
    description: str         # Description
    file_path: Path | None   # Source .services.yml file
    line_number: int         # Line number in YAML file
    
    # ServicesDefinition-specific:
    class_name: str          # e.g., "Drupal\\Core\\Entity\\EntityTypeManager"
    arguments: list[str]     # Constructor arguments (service references)
    tags: list[dict]         # Service tags
    
    def __init__(
        self,
        id: str,
        class_name: str,
        description: str = "",
        arguments: list[str] | None = None,
        tags: list[dict] | None = None,
        file_path: Path | None = None,
        line_number: int = 0,
    ):
        super().__init__(id, description, file_path, line_number)
        self.class_name = class_name
        self.arguments = arguments or []
        self.tags = tags or []
```

### Future: HookDefinition (Not Yet Implemented)

Will follow similar pattern using `CachedDataBase`:

```python
@dataclass
class HookDefinition(CachedDataBase):
    hook_name: str           # e.g., "hook_form_alter"
    signature: str           # Function signature
    parameters: List[Dict]   # Parameter details
    return_type: str         # Return type
    group: str               # Category (Form API, System, etc.)
```

## Configuration

### Enable/Disable Disk Cache

```python
cache = WorkspaceCache(project_root, drupal_root)
cache.enable_disk_cache = False  # Disable persistence
await cache.initialize()
```

### Cache Location

Cache is stored in `.drupalls/cache/` in the project root:

```
project_root/              # LSP workspace root
├── .drupalls/
│   └── cache/
│       ├── services.json
│       ├── hooks.json (future)
│       └── config.json (future)
└── web/                   # workspace_root (Drupal root)
    ├── core/
    ├── modules/
    └── ...
```

**Note:** `project_root` is where the user opened the workspace, while `workspace_root` (Drupal root) is where the `core/` directory is located.

### Cache Invalidation

The cache automatically invalidates when:
1. File hash changes (detected on re-parse)
2. File is deleted
3. You call `invalidate_file()` manually

## Performance

### Initial Scan Performance

For a typical Drupal installation:

| Project Size | Services | Scan Time | Memory |
|-------------|----------|-----------|--------|
| Small (< 10 modules) | ~200 | < 1s | ~5MB |
| Medium (10-50 modules) | ~500 | 2-3s | ~10MB |
| Large (50+ modules) | ~1000+ | 5-10s | ~20MB |

### Access Performance

Once cached:
- `get_service()`: O(1) - < 1ms
- `search_services()`: O(n) - < 10ms for 1000 services
- `get_services()`: O(1) - < 1ms (returns reference)

### Disk Cache

With disk cache enabled:
- First load: Scan time (as above)
- Subsequent loads: < 100ms (load from JSON)
- Cache file size: ~100KB per 100 services

## Testing

```python
# tests/workspace/test_workspace_cache.py
import pytest
from pathlib import Path
from drupalls.workspace.cache import WorkspaceCache

@pytest.mark.asyncio
async def test_scan_services(tmp_path):
    # Create test Drupal structure
    drupal_root = tmp_path / "web"
    drupal_root.mkdir()
    
    # Create core directory structure
    core_lib = drupal_root / "core" / "lib" / "Drupal"
    core_lib.mkdir(parents=True)
    
    # Create services file
    services_file = drupal_root / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Test\\TestService
    """)
    
    # Initialize cache with both roots
    cache = WorkspaceCache(tmp_path, drupal_root)
    await cache.initialize()
    
    # Check services were loaded
    services_cache = cache.caches.get("services")
    assert services_cache is not None
    all_services = services_cache.get_all()
    assert len(all_services) == 1
    assert services_cache.get('test.service') is not None

@pytest.mark.asyncio
async def test_search_services(tmp_path):
    drupal_root = tmp_path / "web"
    drupal_root.mkdir()
    core_lib = drupal_root / "core" / "lib" / "Drupal"
    core_lib.mkdir(parents=True)
    
    # ... create services file ...
    
    cache = WorkspaceCache(tmp_path, drupal_root)
    await cache.initialize()
    
    services_cache = cache.caches.get("services")
    results = services_cache.search('test')
    assert len(results) > 0
    assert results[0].id == 'test.service'
```

## Advanced: Adding Custom Caches

The WorkspaceCache uses a plugin architecture. To add a new cache type:

### 1. Create a Cache Implementation

```python
# drupalls/workspace/hooks_cache.py
from pathlib import Path
from drupalls.workspace.cache import CachedWorkspace, CachedDataBase
from dataclasses import dataclass

@dataclass
class HookDefinition(CachedDataBase):
    """Represents a Drupal hook definition."""
    hook_name: str
    signature: str
    parameters: list[dict]

class HooksCache(CachedWorkspace):
    """Cache for Drupal hook definitions."""
    
    def __init__(self, workspace_cache):
        super().__init__(workspace_cache)
        self._hooks: dict[str, HookDefinition] = {}
    
    async def initialize(self):
        """Initialize the cache."""
        pass
    
    def get(self, id: str) -> HookDefinition | None:
        return self._hooks.get(id)
    
    def get_all(self) -> dict[str, HookDefinition]:
        return self._hooks
    
    def search(self, query: str, limit: int = 50) -> list[HookDefinition]:
        results = []
        for hook in self._hooks.values():
            if query in hook.id.lower():
                results.append(hook)
                if len(results) >= limit:
                    break
        return results
    
    async def scan(self):
        """Scan workspace for hook definitions."""
        # Implementation: parse .api.php files
        pass
    
    def load_from_disk(self) -> bool:
        return False
    
    def save_to_disk(self):
        pass
    
    def invalidate_file(self, file_path: Path):
        """Re-parse specific .api.php file."""
        pass
```

### 2. Register the Cache

```python
# During WorkspaceCache initialization
from drupalls.workspace.hooks_cache import HooksCache

cache = WorkspaceCache(
    project_root,
    drupal_root,
    caches={
        "services": ServicesCache(self),
        "hooks": HooksCache(self),  # Add your custom cache
    }
)
```

### 3. Use the Cache

```python
# In LSP feature handlers
hooks_cache = ls.workspace_cache.caches.get("hooks")
if hooks_cache:
    all_hooks = hooks_cache.get_all()
    hook = hooks_cache.get("hook_form_alter")
```

## Comparison: In-Memory vs SQLite

| Aspect | In-Memory (Our Approach) | SQLite |
|--------|-------------------------|---------|
| Speed | ⭐⭐⭐⭐⭐ < 1ms | ⭐⭐⭐ 5-20ms |
| Memory | ~20MB for large project | ~5MB |
| Persistence | Optional (JSON) | Yes |
| Complexity | Simple | Medium |
| Query Capability | Python code | SQL |
| Invalidation | Simple | Complex |
| **Recommendation** | **Use this** | Not needed |

## Why Not SQLite?

1. **Latency:** Every completion needs 20+ service lookups. SQLite adds 5-20ms per query = noticeable lag
2. **Complexity:** Schema management, migrations, query optimization
3. **Overkill:** Services change infrequently, don't need ACID properties
4. **Memory:** 20MB RAM is acceptable for typical projects
5. **Simplicity:** Python dicts are easier to work with than SQL

## When to Use SQLite

Consider SQLite only if:
- ✓ You have 100+ modules (1000s of services)
- ✓ Memory is severely constrained (< 100MB available)
- ✓ You need complex cross-data queries
- ✓ You're sharing data between multiple processes

For 99% of Drupal projects, in-memory is the right choice.

## Next Steps

1. **Integrate with Server:** Add cache initialization to your server
2. **Update Features:** Use cache in completion, hover, etc.
3. **Test:** Verify performance with your Drupal codebase
4. **Extend:** Add scanners for other Drupal constructs (hooks, config, entities)

See `APPENDIX-01-DEVELOPMENT_GUIDE.md` for full examples!
