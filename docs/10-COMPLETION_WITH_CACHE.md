# Completion Feature with WorkspaceCache Integration

## Overview

This guide explains how to update the completion feature (`drupalls/features/completion/completion.py`) to read services from the WorkspaceCache, based on the current implementation of `cache.py` and `server.py`.

## Current Architecture

### 1. Server Initialization (server.py)

The `DrupalLanguageServer` class has a custom attribute:
```python
class DrupalLanguageServer(LanguageServer):
    def __init__(self, name: str, version: str):
        super().__init__(name, version)
        self.workspace_cache: WorkspaceCache | None = None
```

During the `initialize` LSP request:
- Drupal root is detected
- WorkspaceCache is instantiated: `ls.workspace_cache = WorkspaceCache(drupal_root)`
- Cache is initialized: `await ls.workspace_cache.initialize()`
- Services are loaded and logged

### 2. WorkspaceCache Structure (cache.py)

The cache stores multiple types of data in the `caches` dictionary:
```python
self.caches = {
    "services": ServicesCache(self)
}
```

Access patterns:
- `cache.caches["services"].get(id)` - Get a specific service
- `cache.caches["services"].get_all()` - Get all services as a dictionary
- `cache.caches["services"].search(query)` - Search services

## Updating completion.py Line 52

### Problem

Line 52 in `completion.py` is currently empty and needs to read services from the cache.

### Solution Pattern

To access services in the completion handler:

```python
@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: LanguageServer, params: CompletionParams):
    # Step 1: Check if cache is available
    if not ls.workspace_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    # Step 2: Get the ServicesCache
    services_cache = ls.workspace_cache.caches.get("services")
    if not services_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    # Step 3: Get all services
    all_services = services_cache.get_all()
    
    # Step 4: Convert to CompletionItems
    items = []
    for service_id, service_data in all_services.items():
        items.append(
            CompletionItem(
                label=service_id,
                kind=CompletionItemKind.Class,
                detail=service_data.description,
                documentation=f"Defined in: {service_data.file_path}"
            )
        )
    
    return CompletionList(is_incomplete=False, items=items)
```

### Type Casting for DrupalLanguageServer

If you need type hints to work properly with `ls.workspace_cache`, cast the server:

```python
from drupalls.lsp.server import DrupalLanguageServer

@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: DrupalLanguageServer, params: CompletionParams):
    # Now ls.workspace_cache has proper type hints
    if not ls.workspace_cache:
        return CompletionList(is_incomplete=False, items=[])
```

## Complete Implementation Example

Here's a complete example that reads services from cache:

```python
from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    CompletionItemKind,
    TEXT_DOCUMENT_COMPLETION,
)
from drupalls.lsp.server import DrupalLanguageServer

def register_completion_handler(server):
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    async def completions(ls: DrupalLanguageServer, params: CompletionParams):
        # Guard: Check if cache is initialized
        if not ls.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get services cache
        services_cache = ls.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get all services from cache
        all_services = services_cache.get_all()
        
        # Build completion items
        completion_items = []
        for service_id, service_data in all_services.items():
            completion_items.append(
                CompletionItem(
                    label=service_id,
                    kind=CompletionItemKind.Class,
                    detail=service_data.description,
                    documentation=f"Service from: {service_data.file_path}"
                )
            )
        
        return CompletionList(
            is_incomplete=False,
            items=completion_items
        )
```

## Context-Aware Completion (Advanced)

For more intelligent completions that only trigger in specific contexts:

```python
@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls: DrupalLanguageServer, params: CompletionParams):
    if not ls.workspace_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    # Get document text to check context
    document = ls.workspace.get_text_document(params.text_document.uri)
    
    # Get line text at cursor position
    line = document.lines[params.position.line]
    
    # Only provide service completions if we're in a service context
    # e.g., \Drupal::service('...')
    if "::service(" not in line and "->get(" not in line:
        return CompletionList(is_incomplete=False, items=[])
    
    # Get services and return completions
    services_cache = ls.workspace_cache.caches.get("services")
    if not services_cache:
        return CompletionList(is_incomplete=False, items=[])
    
    all_services = services_cache.get_all()
    
    items = [
        CompletionItem(
            label=service_id,
            kind=CompletionItemKind.Class,
            detail=service_data.description
        )
        for service_id, service_data in all_services.items()
    ]
    
    return CompletionList(is_incomplete=False, items=items)
```

## Key Points

1. **Server Type**: Use `DrupalLanguageServer` instead of `LanguageServer` for type hints
2. **Cache Access**: `ls.workspace_cache.caches["services"]`
3. **Get All Services**: `services_cache.get_all()` returns a dict mapping
4. **Guard Clauses**: Always check if `workspace_cache` exists (it may be None)
5. **Service Data**: Each service has `id`, `description`, and `file_path` attributes

## Testing

After updating line 52:

1. Start the server
2. Open a Drupal project
3. Check logs for "Loaded X services" message
4. Type in a PHP file to trigger completions
5. Verify service names appear in autocomplete suggestions

## Related Files

- `drupalls/workspace/cache.py` - Cache architecture
- `drupalls/workspace/services_cache.py` - ServicesCache implementation
- `drupalls/lsp/server.py` - Server initialization
- `07-CACHE_USAGE.md` - General cache usage guide
