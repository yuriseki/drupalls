# Extending LanguageServer with Custom Attributes

## The Problem

When you try to add custom attributes to the `LanguageServer` instance:

```python
from pygls.lsp.server import LanguageServer

server = LanguageServer("drupalls", "0.1.0")
server.workspace_cache = None  # ❌ Type error!
```

You get this error:
```
Cannot assign to attribute "workspace_cache" for class "LanguageServer"
Attribute "workspace_cache" is unknown [reportAttributeAccessIssue]
```

## Solution: Create a Custom Server Class (⭐ Recommended)

Extend `LanguageServer` to add your own attributes with proper type hints:

```python
# drupalls/lsp/server.py
from pygls.lsp.server import LanguageServer
from drupalls.workspace import WorkspaceCache


class DrupalLanguageServer(LanguageServer):
    """
    Custom Language Server with Drupal-specific attributes.

    Attributes:
        workspace_cache: Cache for parsed Drupal data (services, hooks, etc.)
    """

    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.workspace_cache: WorkspaceCache | None = None


def create_server() -> DrupalLanguageServer:
    """Creates and returns a configured Drupal Language Server instance."""
    server = DrupalLanguageServer("drupalls", "0.1.0")
    
    # Register features
    from drupalls.lsp.features.text_sync import register_text_sync_handlers
    from drupalls.lsp.features.completion import register_completion_handler
    
    register_text_sync_handlers(server)
    register_completion_handler(server)
    
    return server
```

### Benefits
- ✅ Full type safety
- ✅ IDE autocomplete works
- ✅ Clear documentation
- ✅ Easy to extend

### Usage in Features

```python
# drupalls/lsp/features/completion.py
from drupalls.lsp.server import DrupalLanguageServer

@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(ls: DrupalLanguageServer, params: CompletionParams):
    if ls.workspace_cache:
        services = ls.workspace_cache.get_services()
        # ... your logic
```

## Alternative: Use `# type: ignore`

If you don't want to create a custom class:

```python
server = LanguageServer("drupalls", "0.1.0")
server.workspace_cache = None  # type: ignore[attr-defined]
```

**Downsides:**
- ❌ No autocomplete
- ❌ Silences type checker

## Complete Example

```python
# drupalls/lsp/server.py
from pygls.lsp.server import LanguageServer
class DrupalLanguageServer(LanguageServer):
    """Drupal-specific Language Server with custom attributes."""

    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.workspace_cache: WorkspaceCache | None = None


def create_server() -> DrupalLanguageServer:
    """Create and configure the Drupal Language Server."""
    server = DrupalLanguageServer("drupalls", "0.1.0")
    
    # Initialize handler
    @server.feature('initialize')
    async def initialize(ls: DrupalLanguageServer, params: InitializeParams):
        if params.root_uri:
            workspace_root = Path(params.root_uri.replace('file://', ''))
            ls.workspace_cache = WorkspaceCache(workspace_root)
            await ls.workspace_cache.initialize()
            
            count = len(ls.workspace_cache.get_services())
            ls.show_message_log(f"Loaded {count} services")
    
    # Register other features...
    return server
```

## Adding More Attributes

Easily extend with more:

```python
class DrupalLanguageServer(LanguageServer):
    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        
        # Caches
        self.workspace_cache: WorkspaceCache | None = None

        # Configuration
        self.drupal_version: str | None = None
        self.enable_experimental: bool = False
```

## Summary

**Use a custom `DrupalLanguageServer` class** - it's the cleanest, most maintainable approach with full type safety. This is the standard pattern used by professional LSP implementations.
