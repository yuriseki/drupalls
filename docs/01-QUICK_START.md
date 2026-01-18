# DrupalLS Quick Start Guide

## What is DrupalLS?

**DrupalLS** is a complete Language Server Protocol (LSP) implementation for Drupal development built with Python and pygls v2. It provides intelligent IDE features like autocompletion, hover information, and go-to-definition for Drupal-specific constructs.

## What We Built

✅ **Plugin Architecture** - Extensible capability and cache system  
✅ **Services Support** - Completion, hover, and definition for Drupal services  
✅ **Workspace Cache** - Fast in-memory caching (< 1ms lookups)  
✅ **Text Synchronization** - Real-time file tracking  
✅ **Smart Detection** - Automatic Drupal root detection  

## Project Structure

```
drupalls/
├── lsp/
│   ├── server.py                           # Server creation (create_server())
│   ├── drupal_language_server.py           # Custom LanguageServer subclass
│   ├── capabilities/
│   │   ├── capabilities.py                 # Capability base classes & CapabilityManager
│   │   └── services_capabilities.py        # Services completion/hover/definition
│   └── features/
│       └── text_sync.py                    # Document synchronization handlers
├── workspace/
│   ├── cache.py                            # WorkspaceCache & CachedWorkspace base
│   ├── services_cache.py                   # ServicesCache implementation
│   └── utils.py                            # File utilities (hashing, etc.)
├── utils/
│   └── find_files.py                       # Drupal root detection
└── main.py                                 # Entry point
```

## Architecture Overview

### 1. Plugin System

DrupalLS uses a **dual plugin architecture**:

```
Server Initialization
    ↓
WorkspaceCache (manages cached data)
├── caches: dict[str, CachedWorkspace]
│   ├── "services" → ServicesCache
│   ├── "hooks" → HooksCache (future)
│   └── "config" → ConfigCache (future)
    ↓
CapabilityManager (manages LSP features)
├── capabilities: dict[str, Capability]
│   ├── "services_completion" → ServicesCompletionCapability
│   ├── "services_hover" → ServicesHoverCapability
│   ├── "services_definition" → ServicesDefinitionCapability
│   └── "services_yaml_definition" → ServicesYamlDefinitionCapability
```

### 2. Key Components

#### DrupalLanguageServer

Custom LanguageServer subclass with Drupal-specific attributes:

```python
# drupalls/lsp/drupal_language_server.py
from pygls.server import LanguageServer

class DrupalLanguageServer(LanguageServer):
    """Extended LanguageServer with Drupal-specific attributes."""
    
    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.workspace_cache: WorkspaceCache | None = None
        self.capability_manager: CapabilityManager | None = None
```

#### WorkspaceCache

Central manager for all parsed Drupal data:

```python
# drupalls/workspace/cache.py
class WorkspaceCache:
    """
    Manages all parsed workspace data in memory.
    
    Attributes:
        project_root: Project root directory
        workspace_root: Drupal root directory
        caches: Dict of cache plugins (by name)
        file_info: File state tracking for invalidation
    """
    
    def __init__(self, project_root: Path, workspace_root: Path):
        self.project_root = project_root
        self.workspace_root = workspace_root
        self.caches = {
            "services": ServicesCache(self)
        }
        self.file_info: dict[Path, FileInfo] = {}
    
    async def initialize(self):
        """Scan workspace and populate all caches."""
        for cache in self.caches.values():
            await cache.initialize()
```

#### CapabilityManager

Coordinates all LSP capability handlers:

```python
# drupalls/lsp/capabilities/capabilities.py
class CapabilityManager:
    """
    Manages all LSP capabilities using plugin pattern.
    
    Delegates requests to appropriate capability handlers based on context.
    """
    
    def __init__(self, server: DrupalLanguageServer):
        self.server = server
        self.capabilities = {
            "services_completion": ServicesCompletionCapability(server),
            "services_hover": ServicesHoverCapability(server),
            "services_definition": ServicesDefinitionCapability(server),
            "services_yaml_definition": ServicesYamlDefinitionCapability(server),
        }
    
    async def handle_completion(self, params: CompletionParams) -> CompletionList:
        """Aggregate results from all completion capabilities."""
        all_items = []
        for capability in self.get_capabilities_by_type(CompletionCapability):
            if await capability.can_handle(params):
                result = await capability.complete(params)
                all_items.extend(result.items)
        return CompletionList(is_incomplete=False, items=all_items)
```

## How It Works: Server Initialization

```python
# drupalls/lsp/server.py
def create_server() -> DrupalLanguageServer:
    """Create and configure the language server."""
    server = DrupalLanguageServer("drupalls", "0.1.0")
    
    # Initialize empty attributes
    server.workspace_cache = None
    server.capability_manager = None
    
    @server.feature("initialize")
    async def initialize(ls: DrupalLanguageServer, params):
        """Initialize workspace and capabilities."""
        
        # 1. Get workspace root from LSP params
        workspace_root = Path(params.root_uri.replace("file://", ""))
        
        # 2. Find Drupal root
        drupal_root = find_drupal_root(workspace_root)
        if drupal_root is None:
            ls.window_log_message(LogMessageParams(
                MessageType.Info, 
                "Drupal installation not found"
            ))
            return
        
        # 3. Initialize workspace cache
        ls.workspace_cache = WorkspaceCache(workspace_root, drupal_root)
        await ls.workspace_cache.initialize()
        
        # 4. Initialize capability manager
        ls.capability_manager = CapabilityManager(ls)
        ls.capability_manager.register_all()
        
        # 5. Log success
        count = len(ls.workspace_cache.caches["services"].get_all())
        ls.window_log_message(LogMessageParams(
            MessageType.Info,
            f"Loaded {count} services"
        ))
    
    # Register aggregated LSP handlers
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    async def completion(ls: DrupalLanguageServer, params: CompletionParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_completion(params)
        return CompletionList(is_incomplete=False, items=[])
    
    @server.feature(TEXT_DOCUMENT_HOVER)
    async def hover(ls: DrupalLanguageServer, params: HoverParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_hover(params)
        return None
    
    @server.feature(TEXT_DOCUMENT_DEFINITION)
    async def definition(ls: DrupalLanguageServer, params: DefinitionParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_definition(params)
        return None
    
    # Register text synchronization handlers
    register_text_sync_handlers(server)
    
    return server
```

## How It Works: Capability Plugins

### Example: Services Completion

```python
# drupalls/lsp/capabilities/services_capabilities.py
class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""
    
    @property
    def name(self) -> str:
        return "services_completion"
    
    @property
    def description(self) -> str:
        return "Autocomplete Drupal service names in ::service() calls"
    
    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is in a service context."""
        if not self.workspace_cache:
            return False
        
        # Get document and line
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        # Check for service patterns
        return bool(SERVICE_PATTERN.search(line))
    
    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide service name completions."""
        # Get services cache
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get all services
        all_services = services_cache.get_all()
        
        # Build completion items
        items = []
        for service_id, service_def in all_services.items():
            items.append(CompletionItem(
                label=service_id,
                kind=CompletionItemKind.Value,
                detail=service_def.class_name,
                documentation=f"Defined in: {service_def.file_path}",
                insert_text=service_id,
            ))
        
        return CompletionList(is_incomplete=False, items=items)
```

## How It Works: Cache Plugins

### Example: Services Cache

```python
# drupalls/workspace/services_cache.py
class ServicesCache(CachedWorkspace):
    """Caches Drupal service definitions from *.services.yml files."""
    
    def __init__(self, workspace_cache: WorkspaceCache):
        super().__init__(workspace_cache)
        self._services: dict[str, ServiceDefinition] = {}
    
    async def scan(self):
        """Scan all *.services.yml files."""
        base_dirs = ["core", "modules", "profiles", "themes"]
        
        for base_name in base_dirs:
            base_path = self.workspace_root / base_name
            if not base_path.is_dir():
                continue
            
            # Find all .services.yml files recursively
            for services_file in base_path.rglob("*.services.yml"):
                if services_file.is_file():
                    await self.parse_services_file(services_file)
    
    async def parse_services_file(self, file_path: Path):
        """Parse a single .services.yml file."""
        # Calculate hash for cache invalidation
        file_hash = calculate_file_hash(file_path)
        
        # Parse YAML
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        
        # Extract services
        services = data.get("services", {})
        for service_id, service_data in services.items():
            # Create ServiceDefinition
            self._services[service_id] = ServiceDefinition(
                id=service_id,
                description=service_data.get("class", ""),
                class_name=service_data.get("class", ""),
                arguments=service_data.get("arguments", []),
                tags=service_data.get("tags", []),
                file_path=file_path,
                line_number=line_num  # From line tracking
            )
        
        # Track file for invalidation
        self.file_info[file_path] = FileInfo(
            path=file_path,
            hash=file_hash,
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
        )
    
    def get(self, service_id: str) -> ServiceDefinition | None:
        """Get a specific service by ID."""
        return self._services.get(service_id)
    
    def get_all(self) -> dict[str, ServiceDefinition]:
        """Get all services."""
        return self._services
```

## Running the Server

```bash
# Install dependencies
poetry install

# Run the server
poetry run python -m drupalls

# Run tests
poetry run pytest -v

# Run with debugging
poetry run python -m debugpy --listen 5678 --wait-for-client drupalls/main.py
```

## Current Features

### 1. Service Autocompletion

```php
// Type in PHP file:
\Drupal::service('entity_type.manager')
                ↑
                Suggests all 500+ Drupal services
```

### 2. Service Hover Information

```php
// Hover over service name:
\Drupal::service('logger.factory')
                ↑
Shows:
- **Service ID**: logger.factory
- **Class**: Drupal\Core\Logger\LoggerChannelFactory
- **Defined in**: core/core.services.yml:123
```

### 3. Go to Definition (PHP → YAML)

```php
// Ctrl+Click on service name:
\Drupal::service('cache.default')
                ↑
Jumps to: core/core.services.yml line 45
```

### 4. Go to Definition (YAML → PHP Class)

```yaml
# Ctrl+Click on class name in .services.yml:
services:
  entity_type.manager:
    class: Drupal\Core\Entity\EntityTypeManager
           ↑
Jumps to: core/lib/Drupal/Core/Entity/EntityTypeManager.php
```

## Adding New Features

### Add a New Cache Type

1. Create `drupalls/workspace/hooks_cache.py`:

```python
from drupalls.workspace.cache import CachedWorkspace, CachedDataBase

@dataclass
class HookDefinition(CachedDataBase):
    """Drupal hook definition."""
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None

class HooksCache(CachedWorkspace):
    def __init__(self, workspace_cache: WorkspaceCache):
        super().__init__(workspace_cache)
        self._hooks: dict[str, HookDefinition] = {}
    
    async def scan(self):
        """Scan *.api.php files for hook definitions."""
        api_files = self.workspace_root.glob("core/**/*.api.php")
        for api_file in api_files:
            await self._parse_api_file(api_file)
    
    def get(self, hook_id: str) -> HookDefinition | None:
        return self._hooks.get(hook_id)
    
    def get_all(self) -> dict[str, HookDefinition]:
        return self._hooks
```

2. Register in `WorkspaceCache.__init__()`:

```python
self.caches = {
    "services": ServicesCache(self),
    "hooks": HooksCache(self),  # Add this
}
```

### Add a New Capability

1. Create capability in `services_capabilities.py`:

```python
class HooksCompletionCapability(CompletionCapability):
    @property
    def name(self) -> str:
        return "hooks_completion"
    
    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if in hook context."""
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        return "function" in line and "hook_" in line
    
    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide hook completions."""
        hooks_cache = self.workspace_cache.caches.get("hooks")
        if not hooks_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        all_hooks = hooks_cache.get_all()
        items = [
            CompletionItem(
                label=hook_id,
                kind=CompletionItemKind.Function,
                detail=hook.return_type or "void"
            )
            for hook_id, hook in all_hooks.items()
        ]
        return CompletionList(is_incomplete=False, items=items)
```

2. Register in `CapabilityManager.__init__()`:

```python
capabilities = {
    "services_completion": ServicesCompletionCapability(server),
    "hooks_completion": HooksCompletionCapability(server),  # Add this
    # ...
}
```

## Key Design Patterns

1. **Plugin Architecture**: Add features without modifying core
2. **Aggregation Pattern**: CapabilityManager aggregates results from multiple handlers
3. **Dictionary-Based Registration**: Named access to caches and capabilities
4. **Type-Safe**: Abstract base classes enforce consistent interfaces
5. **Async-First**: All I/O operations use async/await
6. **In-Memory First**: Fast lookups with optional disk persistence

## Next Steps

1. **Read Architecture Docs**:
   - `02-WORKSPACE_CACHE_ARCHITECTURE.md` - Cache design
   - `03-CAPABILITY_PLUGIN_ARCHITECTURE.md` - Capability design
   - `04-STORAGE_STRATEGY.md` - Why in-memory caching

2. **Explore Appendices**:
   - `APPENDIX-01-DEVELOPMENT_GUIDE.md` - Complete LSP reference (1400+ lines)
   - `APPENDIX-03-CACHE_USAGE.md` - How to use WorkspaceCache API
    - `IMPLEMENTATION-003-COMPLETION_WITH_CACHE.md` - Building completion features

3. **Implement New Features**:
   - Add hooks support (completion, hover, definition)
   - Add config schema validation
   - Add entity type awareness
   - Add plugin annotation support

## Resources

- **LSP Specification**: https://microsoft.github.io/language-server-protocol/
- **pygls Documentation**: https://pygls.readthedocs.io/
- **Drupal API**: https://api.drupal.org/
- **Project README**: `../README.md`
