# Workspace Cache Architecture

## Overview

The DrupalLS workspace cache is a **plugin-based, in-memory caching system** that stores parsed Drupal definitions (services, hooks, config schemas, etc.) for fast LSP operations. It provides sub-millisecond access times with optional disk persistence.

## Design Philosophy

### Core Principles

1. **In-memory first**: All data stored in Python dictionaries for O(1) lookup
2. **Extensible**: Plugin architecture allows adding new cache types without modifying core
3. **Incremental updates**: Re-parse only changed files (via hash comparison)
4. **Optional persistence**: JSON serialization to disk speeds up server restarts
5. **Type-safe**: Full type hints and dataclasses for IDE support

### Performance Targets

- **Access time**: < 1ms for cache lookups
- **Initial scan**: 2-5 seconds for typical Drupal project
- **Invalidation**: < 10ms to re-parse single file

## Key Design: Dictionary-Based Cache Storage

The `caches` attribute is implemented as `dict[str, CachedWorkspace]` for named access to cache plugins

### Benefits

1. **Named Access**: Access caches by semantic key instead of index
   ```python
   # Before (fragile)
   services_cache = workspace_cache.caches[0]  # What is index 0?
   
   # After (clear)
   services_cache = workspace_cache.caches['services']  # Explicit
   ```

2. **Order Independence**: No need to maintain specific order of cache registration
   ```python
   # Registration order doesn't matter
   caches = {
       "hooks": HooksCache(workspace_cache),
       "services": ServicesCache(workspace_cache),
   }
   ```

3. **Dynamic Cache Access**: Check if cache exists without exceptions
   ```python
   if 'hooks' in workspace_cache.caches:
       hooks = workspace_cache.caches['hooks'].get_all()
   ```

4. **Better Type Safety**: Keys are strings, making it clearer what cache you're accessing

### Implementation

```python
class WorkspaceCache:
    def __init__(
        self, 
        project_root: Path,
        workspace_root: Path, 
        caches: dict[str, CachedWorkspace] | None = None
    ):
        self.project_root = project_root        # Project root directory
        self.workspace_root = workspace_root    # Drupal root directory
        
        # Default cache registration
        self.caches = caches or {"services": ServicesCache(self)}
        self.file_info: dict[Path, FileInfo] = {}
```

**Iteration** (when needed):
```python
# Iterate over all caches
for cache_name, cache in self.caches.items():
    await cache.initialize()
    print(f"Initialized {cache_name}: {len(cache.get_all())} items")

# Or just values
for cache in self.caches.values():
    if isinstance(cache, CachedWorkspace):
        await cache.scan()
```

## Architecture Components

### 1. Core Classes

```
WorkspaceCache (Coordinator)
    ├── CachedWorkspace (Abstract Base)
    │   ├── ServicesCache (key: "services")
    │   ├── HooksCache (key: "hooks") (future)
    │   ├── ConfigSchemaCache (key: "config_schemas") (future)
    │   └── EntityTypesCache (key: "entity_types") (future)
    │
    ├── FileInfo (File tracking)
    └── CachedDataBase (Base data model)
```

### 2. Class Responsibilities

#### `WorkspaceCache`
**Purpose**: Central coordinator for all workspace caches

**Key attributes**:
```python
project_root: Path                      # Project root directory
workspace_root: Path                    # Drupal root directory (where core/ is)
caches: dict[str, CachedWorkspace]      # Registered cache plugins (keyed by name)
file_info: dict[Path, FileInfo]         # File state tracking
cache_dir: Path                         # .drupalls/cache/
enable_disk_cache: bool                 # Toggle persistence
```

**Key methods**:
- `initialize()` - Load from disk or scan workspace
- `invalidate_file(file_path)` - Refresh cache when file changes
- `_scan_workspace()` - Delegate scanning to all registered caches
- `_load_from_disk()` / `_save_to_disk()` - Persistence layer

**Lifecycle**:
```python
# 1. Server startup
cache = WorkspaceCache(project_root, drupal_root)
await cache.initialize()  # Loads or scans

# 2. File change event
cache.invalidate_file(changed_file)  # Incremental update

# 3. Cache access (via dictionary key)
service = cache.caches['services'].get('entity_type.manager')
```

---

#### `CachedWorkspace` (Abstract Base Class)
**Purpose**: Interface contract for all cache implementations

**Required methods**:
```python
async def initialize()
    # Called once during workspace initialization

async def scan()
    # Scan workspace and populate cache

def get(id: str) -> Optional[CachedDataBase]
    # Retrieve single item by ID

def get_all() -> Mapping[str, CachedDataBase]
    # Get all cached items

def search(query: str, limit: int) -> Sequence[CachedDataBase]
    # Search with fuzzy matching

def invalidate_file(file_path: Path)
    # Handle file changes

def load_from_disk() -> bool
    # Load from JSON cache

def save_to_disk()
    # Persist to JSON cache
```

**Design pattern**: Template Method + Strategy

**Shared state** (from parent):
```python
self.workspace_cache: WorkspaceCache  # Parent coordinator
self.project_root: Path               # Project root directory
self.workspace_root: Path             # Drupal root directory
self.file_info: Dict[Path, FileInfo]  # Shared file tracking
```

---

#### `CachedDataBase`
**Purpose**: Base dataclass for all cached entities

```python
@dataclass
class CachedDataBase:
    id: str                        # Unique identifier
    description: str               # Human-readable description
    file_path: Optional[Path]      # Source file
```

**Subclasses extend with domain-specific fields**:
```python
@dataclass
class ServiceDefinition(CachedDataBase):
    class_name: str                # FQCN of service class
    arguments: List[str]           # Constructor arguments
    tags: List[Dict]               # Service tags
```

---

#### `FileInfo`
**Purpose**: Track file state for cache invalidation

```python
@dataclass
class FileInfo:
    path: Path              # File location
    hash: str               # SHA256 content hash
    last_modified: datetime # mtime timestamp
```

**Usage**:
```python
# On initial parse
file_hash = calculate_file_hash(file_path)
file_info[file_path] = FileInfo(
    path=file_path,
    hash=file_hash,
    last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
)

# On file change
new_hash = calculate_file_hash(file_path)
if file_info[file_path].hash == new_hash:
    return  # Skip re-parsing
```

---

### 3. ServicesCache Implementation

**Purpose**: Cache Drupal service definitions from `*.services.yml` files

#### Data Structure
```python
self._services: Dict[str, ServiceDefinition] = {}
# Example:
# {
#   'entity_type.manager': ServiceDefinition(
#       id='entity_type.manager',
#       class_name='Drupal\\Core\\Entity\\EntityTypeManager',
#       description='Drupal\\Core\\Entity\\EntityTypeManager',
#       arguments=['@container', '@module_handler', ...],
#       tags=[],
#       file_path=Path('core/core.services.yml')
#   )
# }
```

#### Scanning Process

```python
async def scan(self):
    patterns = [
        "core/**/*.services.yml",
        "modules/**/*.services.yml",
        "profiles/**/*.services.yml",
        "themes/**/*.services.yml",
    ]
    
    for pattern in patterns:
        for services_file in workspace_root.glob(pattern):
            await parse_services_file(services_file)
```

**Parsing steps**:
1. Calculate SHA256 hash of file
2. Load YAML with `yaml.safe_load()`
3. Extract `services` key
4. For each service:
   - Parse `class`, `arguments`, `tags`
   - Create `ServiceDefinition` object
   - Store in `_services` dict
5. Track file in `file_info` for invalidation

#### Search Implementation

```python
def search(query: str, limit: int = 50) -> List[ServiceDefinition]:
    query_lower = query.lower()
    results = []
    
    for service_id, service_def in self._services.items():
        # Match against ID or class name
        if query_lower in service_id.lower():
            results.append(service_def)
        elif query_lower in service_def.class_name.lower():
            results.append(service_def)
    
    # Sort: starts-with matches first
    results.sort(key=lambda s: (
        not s.id.lower().startswith(query_lower),
        s.id
    ))
    
    return results[:limit]
```

**Example queries**:
- `"entity"` → Matches all service IDs containing "entity"
- `"EntityTypeManager"` → Matches class names
- Priority to prefix matches: `"cache"` → `cache.backend` before `cache_factory`

#### Invalidation Logic

```python
def invalidate_file(self, file_path: Path):
    if not file_path.exists():
        # File deleted - remove from cache
        del file_info[file_path]
        self._services = {
            sid: sdef for sid, sdef 
            in self._services.items()
            if sdef.file_path != file_path
        }
        return
    
    # Check hash
    new_hash = calculate_file_hash(file_path)
    old_info = file_info.get(file_path)
    
    if old_info and old_info.hash == new_hash:
        return  # No changes
    
    # Re-parse
    if file_path.name.endswith('.services.yml'):
        asyncio.create_task(parse_services_file(file_path))
```

**Optimization**: Hash comparison avoids re-parsing unchanged files (e.g., editor auto-save without changes)

#### Disk Persistence

**Save format** (`/.drupalls/cache/services.json`):
```json
{
  "version": 1,
  "timestamp": "2026-01-15T03:00:00",
  "services": {
    "entity_type.manager": {
      "id": "entity_type.manager",
      "class_name": "Drupal\\Core\\Entity\\EntityTypeManager",
      "description": "Drupal\\Core\\Entity\\EntityTypeManager",
      "arguments": ["@container", "@module_handler"],
      "tags": [],
      "file_path": "/path/to/core/core.services.yml"
    }
  }
}
```

**Load process**:
1. Check if `services.json` exists
2. Validate `version` field (cache invalidation)
3. Deserialize JSON → `ServiceDefinition` objects
4. Populate `_services` dict

**Benefits**:
- Skip 2-5s workspace scan on server restart
- Instant cache availability
- Version field allows cache schema evolution

---

## Cache Initialization Flow

### Detailed Sequence

```
┌─────────────────────────────────────────┐
│ LSP Server Startup                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ WorkspaceCache(workspace_root)          │
│ - Initialize empty caches list          │
│ - Register ServicesCache                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ await cache.initialize()                │
└─────────────────┬───────────────────────┘
                  │
                  ▼
          ┌───────────────┐
          │ Disk cache    │───Yes───┐
          │ exists?       │         │
          └───────┬───────┘         │
                  │                 │
                 No                 │
                  │                 ▼
                  │      ┌─────────────────────┐
                  │      │ load_from_disk()    │
                  │      │ - Read JSON files   │
                  │      │ - Deserialize       │
                  │      │ - Validate version  │
                  │      └──────────┬──────────┘
                  │                 │
                  ▼                 │
       ┌──────────────────────┐     │
       │ _scan_workspace()    │     │
       │ For each cache:      │     │
       │   - await scan()     │     │
       │   - Parse files      │     │
       │   - Populate dicts   │     │
       └──────────┬───────────┘     │
                  │                 │
                  ▼                 │
       ┌──────────────────────┐     │
       │ _save_to_disk()      │     │
       │ - Serialize to JSON  │     │
       │ - Write to .drupalls/│     │
       └──────────┬───────────┘     │
                  │                 │
                  └─────────┬───────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Cache ready      │
                  │ _initialized=True│
                  └──────────────────┘
```

### Code Example

```python
# server.py
from drupalls.workspace.cache import WorkspaceCache
from drupalls.utils.find_files import find_drupal_root
from pathlib import Path

@server.feature("initialize")
async def initialize(ls: DrupalLanguageServer, params):
    # Get workspace root from LSP params
    workspace_root = Path(params.root_uri.replace("file://", ""))
    
    # Find Drupal root
    project_root = workspace_root
    drupal_root = find_drupal_root(workspace_root)
    
    if drupal_root is None:
        ls.window_log_message("Drupal installation not found")
        return
    
    # Create and initialize cache
    ls.workspace_cache = WorkspaceCache(project_root, drupal_root)
    await ls.workspace_cache.initialize()
    
    # Cache is now ready for use
    services_cache = ls.workspace_cache.caches['services']
    count = len(services_cache.get_all())
    ls.window_log_message(f"Loaded {count} services")
```

---

## File Change Handling

### LSP Integration

```python
@server.feature(TEXT_DOCUMENT_DID_SAVE)
async def did_save(ls: LanguageServer, params: DidSaveTextDocumentParams):
    file_path = Path(params.text_document.uri.path)
    
    # Invalidate cache for changed file
    ls.workspace_cache.invalidate_file(file_path)
```

### Invalidation Cascade

```
File Change Event (*.services.yml)
        │
        ▼
WorkspaceCache.invalidate_file(file_path)
        │
        ▼
For each cache in self.caches:
    cache.invalidate_file(file_path)
        │
        ▼
ServicesCache.invalidate_file(file_path)
        │
        ├─── File deleted? ──────────────────┐
        │    Remove from _services dict      │
        │    Remove from file_info           │
        │                                    │
        └─── File modified? ────────────────┤
             Calculate new hash              │
             Compare with old hash           │
             │                               │
             ├─ Hash same? Skip parsing      │
             │                               │
             └─ Hash changed? ───────────────┤
               Re-parse file                 │
               Update _services dict         │
               Update file_info              │
                                             │
                                             ▼
                                    Cache updated
```

### Optimization Strategy

**Problem**: Editor auto-save triggers frequent file events

**Solution**: Hash-based change detection
```python
# Only re-parse if content actually changed
new_hash = calculate_file_hash(file_path)
if old_info and old_info.hash == new_hash:
    return  # Skip expensive YAML parsing
```

**Performance impact**:
- Hash calculation: ~1ms for typical .services.yml file
- YAML parsing: ~50-200ms
- **Savings**: 98% reduction in unnecessary parsing

---

## Adding New Cache Types

### Step-by-Step Guide

#### 1. Create Cache Class

```python
# drupalls/workspace/hooks_cache.py
from drupalls.workspace.cache import CachedWorkspace, CachedDataBase
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

@dataclass
class HookDefinition(CachedDataBase):
    """Drupal hook definition."""
    module: str
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    documentation: str = ""

class HooksCache(CachedWorkspace):
    def __init__(self, workspace_cache: WorkspaceCache):
        super().__init__(workspace_cache)
        self._hooks: Dict[str, HookDefinition] = {}
    
    async def initialize(self):
        await self.scan()
    
    async def scan(self):
        """Scan core API files for hook definitions."""
        api_files = self.workspace_root.glob("core/**/*.api.php")
        for api_file in api_files:
            await self._parse_api_file(api_file)
    
    async def _parse_api_file(self, file_path: Path):
        """Parse *.api.php file to extract hook definitions."""
        # Implementation: regex or AST parsing
        pass
    
    def get(self, hook_id: str) -> Optional[HookDefinition]:
        return self._hooks.get(hook_id)
    
    def get_all(self) -> Dict[str, HookDefinition]:
        return self._hooks
    
    def search(self, query: str, limit: int = 50) -> List[HookDefinition]:
        query_lower = query.lower()
        results = [
            hook for hook_id, hook in self._hooks.items()
            if query_lower in hook_id.lower()
        ]
        return results[:limit]
    
    def invalidate_file(self, file_path: Path):
        if file_path.suffix == '.php' and 'api.php' in file_path.name:
            # Re-parse API file
            asyncio.create_task(self._parse_api_file(file_path))
    
    def load_from_disk(self) -> bool:
        cache_file = self.workspace_cache.cache_dir / "hooks.json"
        if not cache_file.exists():
            return False
        # Load and deserialize
        return True
    
    def save_to_disk(self):
        cache_file = self.workspace_cache.cache_dir / "hooks.json"
        # Serialize and save
        pass
```

#### 2. Register Cache

```python
# server.py or cache.py initialization
workspace_cache = WorkspaceCache(
    workspace_root,
    caches={
        "services": ServicesCache(workspace_cache),
        "hooks": HooksCache(workspace_cache),              # New cache
        "config_schemas": ConfigSchemaCache(workspace_cache),  # Future
    }
)
```

#### 3. Access in LSP Features

```python
# features/completion.py
@server.feature(COMPLETION)
async def completion(ls: LanguageServer, params: CompletionParams):
    # Access hooks cache by dictionary key
    hooks_cache = ls.workspace_cache.caches['hooks']
    
    if context_is_hook_implementation():
        all_hooks = hooks_cache.get_all()
        return [create_completion_item(hook) for hook in all_hooks.values()]
```

---

## Best Practices

### 1. Efficient Scanning

**DO**:
```python
# Use Path.glob() for pattern matching
for file in workspace_root.glob("modules/**/*.services.yml"):
    await parse_file(file)
```

**DON'T**:
```python
# Avoid os.walk() - slower and verbose
for root, dirs, files in os.walk(workspace_root):
    for file in files:
        if file.endswith('.services.yml'):
            # ...
```

### 2. Error Handling

**DO**:
```python
try:
    data = yaml.safe_load(f)
except Exception as e:
    print(f"Error parsing {file_path}: {e}")
    return  # Continue with other files
```

**DON'T**:
```python
# Let exceptions crash the scan
data = yaml.safe_load(f)  # Unhandled exception
```

### 3. Type Safety

**DO**:
```python
def get(self, id: str) -> Optional[ServiceDefinition]:
    return self._services.get(id)
```

**DON'T**:
```python
def get(self, id):  # No type hints
    return self._services.get(id)
```

### 4. Async/Await

**DO**:
```python
async def scan(self):
    for file in self.workspace_root.glob("**/*.yml"):
        await self.parse_file(file)  # Can be parallelized later
```

**DON'T**:
```python
def scan(self):  # Blocking
    for file in self.workspace_root.glob("**/*.yml"):
        self.parse_file(file)
```

### 5. Cache Access Patterns

**DO** (Direct access by dictionary key):
```python
services_cache = workspace_cache.caches['services']
service = services_cache.get('entity_type.manager')
```

**ALSO GOOD** (Optional helper methods on WorkspaceCache):
```python
# Add to WorkspaceCache class for convenience:
def get_services_cache(self) -> ServicesCache:
    return self.caches['services']

# Usage:
service = workspace_cache.get_services_cache().get('entity_type.manager')
```

---

## Performance Considerations

### Memory Usage

**Typical Drupal 10 project**:
- ~500 services across core + contrib modules
- `ServiceDefinition` ~1KB per service
- **Total**: ~500KB for services cache

**Memory efficient**:
```python
# Store only essential data
@dataclass
class ServiceDefinition:
    id: str              # 50 bytes
    class_name: str      # 100 bytes
    arguments: List[str] # 200 bytes
    # Skip storing full YAML content
```

### Disk I/O

**Optimization**:
```python
# Read files in chunks (from utils.py)
def calculate_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):  # 8KB chunks
            sha256.update(chunk)
    return sha256.hexdigest()
```

### Parallelization (Future)

```python
# Scan files in parallel
import asyncio

async def scan(self):
    patterns = ["core/**/*.services.yml", "modules/**/*.services.yml"]
    
    # Collect all files first
    files = []
    for pattern in patterns:
        files.extend(self.workspace_root.glob(pattern))
    
    # Parse in parallel (limit concurrency)
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent parses
    
    async def parse_with_limit(file):
        async with semaphore:
            await self.parse_services_file(file)
    
    await asyncio.gather(*[parse_with_limit(f) for f in files])
```

---

## Testing Strategy

### Unit Tests

```python
# tests/workspace/test_services_cache.py
import pytest
from pathlib import Path
from drupalls.workspace import WorkspaceCache

@pytest.mark.asyncio
async def test_services_cache_scan(tmp_path):
    # Create mock .services.yml
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\test\\TestService
    arguments: ['@entity_type.manager']
""")
    
    # Initialize cache
    cache = WorkspaceCache(tmp_path)
    await cache.initialize()
    
    # Verify service was parsed (access by key)
    services_cache = cache.caches['services']
    service = services_cache.get('test.service')
    
    assert service is not None
    assert service.class_name == 'Drupal\\test\\TestService'
    assert len(service.arguments) == 1

@pytest.mark.asyncio
async def test_cache_invalidation(tmp_path):
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("services: {}")
    
    cache = WorkspaceCache(tmp_path)
    await cache.initialize()
    
    # Modify file
    services_file.write_text("""
services:
  new.service:
    class: NewClass
""")
    
    # Invalidate
    cache.invalidate_file(services_file)
    await asyncio.sleep(0.1)  # Wait for async re-parse
    
    # Verify update
    services_cache = cache.caches['services']
    assert services_cache.get('new.service') is not None
```

### Integration Tests

```python
# tests/integration/test_workspace_cache.py
@pytest.mark.asyncio
async def test_full_drupal_scan(drupal_project_path):
    """Test scanning real Drupal core."""
    cache = WorkspaceCache(drupal_project_path)
    await cache.initialize()
    
    services_cache = cache.caches['services']
    all_services = services_cache.get_all()
    
    # Core should have 300+ services
    assert len(all_services) > 300
    
    # Verify known services
    assert services_cache.get('entity_type.manager') is not None
    assert services_cache.get('cache.default') is not None
```

---

## Future Enhancements

### 1. Cache Warmup on Server Startup

```python
# Parallel scanning for faster startup
async def initialize(self):
    await asyncio.gather(
        self.caches['services'].scan(),
        self.caches['hooks'].scan(),
        self.caches['config_schemas'].scan(),
    )
```

### 2. Incremental Scanning

```python
# Only scan new/changed files on subsequent initializations
def _scan_workspace(self):
    for file_path in workspace_files:
        if file_path not in self.file_info:
            # New file
            await parse_file(file_path)
```

### 3. Cache Metrics

```python
@dataclass
class CacheMetrics:
    total_files: int
    parse_time_ms: float
    cache_hits: int
    cache_misses: int

# Add to WorkspaceCache
def get_metrics(self) -> CacheMetrics:
    return CacheMetrics(
        total_files=len(self.file_info),
        parse_time_ms=self._parse_duration,
        # ...
    )
```

### 4. Smart Search Ranking

```python
def search(self, query: str, limit: int = 50) -> List[ServiceDefinition]:
    # Rank by:
    # 1. Exact match
    # 2. Starts with query
    # 3. Contains query (weighted by position)
    # 4. Fuzzy match (Levenshtein distance)
    pass
```

### 5. Cache Preloading

```python
# Preload frequently used services
PRELOAD_SERVICES = [
    'entity_type.manager',
    'cache.default',
    'database',
    'config.factory',
]

async def initialize(self):
    await super().initialize()
    # Ensure these are loaded
    for service_id in PRELOAD_SERVICES:
        self.get(service_id)
```

---

## Conclusion

The DrupalLS workspace cache architecture provides:

✅ **Extensible**: Plugin system for adding new cache types  
✅ **Performant**: Sub-millisecond lookups, hash-based invalidation  
✅ **Persistent**: Optional disk caching for instant server restarts  
✅ **Type-safe**: Full type hints and dataclasses  
✅ **Testable**: Clear interfaces for unit and integration tests  

The design follows LSP best practices and scales from small custom modules to large enterprise Drupal sites with hundreds of modules.
