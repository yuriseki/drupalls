# File Path Best Practices for ServiceDefinition

## Question

Should the `file_path` property in `ServiceDefinition` be:
1. **Full absolute path**: `/home/user/projects/mysite/web/core/core.services.yml`
2. **Relative to Drupal root**: `core/core.services.yml`
3. **Relative to workspace root**: `web/core/core.services.yml`

## Recommendation: Use Absolute Path (Path Object)

**Store the full absolute path as a `Path` object.**

## Current Implementation

Looking at `services_cache.py` line 123:

```python
self._services[id] = ServiceDefinition(
    id=id,
    description=class_name,
    class_name=class_name,
    arguments=arguments,
    tags=tags,
    file_path=file_path,  # ✅ This is already a Path object (absolute)
)
```

The `file_path` parameter receives the absolute `Path` object from the scanning loop, which is correct.

## Rationale

### ✅ Advantages of Absolute Path

1. **Simplicity**: No need to calculate relative paths
2. **Consistency**: Works regardless of workspace structure
3. **LSP Compatibility**: Can convert directly to `file://` URIs
4. **File Operations**: Easy to check if file exists, read, stat, etc.
5. **No Context Needed**: Path is usable without knowing workspace root

### ❌ Disadvantages of Relative Path

1. **Context Dependency**: Always need workspace/drupal root to resolve
2. **Conversion Overhead**: Must convert back to absolute for file operations
3. **Complexity**: Which root? Workspace or Drupal root?
4. **Edge Cases**: Multi-site, symlinks, subdirectories

## Best Practice Pattern

### Storage (in memory)
```python
@dataclass
class ServiceDefinition(CachedDataBase):
    # Store as absolute Path object
    file_path: Path | None
```

### Display (to user)
When showing to users (hover, diagnostics), convert to relative for readability:

```python
def get_relative_path(self, service: ServiceDefinition) -> str:
    """Get user-friendly relative path for display."""
    if not service.file_path:
        return "unknown"
    
    try:
        # Relative to Drupal root for clarity
        return str(service.file_path.relative_to(self.workspace_root))
    except ValueError:
        # File outside workspace (shouldn't happen, but be safe)
        return str(service.file_path)
```

### Persistence (disk cache)
When saving to JSON, convert to string:

```python
# Save to disk (line 232 in services_cache.py)
"file_path": (
    str(service_def.file_path)  # ✅ Absolute path as string
    if service_def.file_path
    else None
),
```

When loading from JSON, convert back to Path:

```python
# Load from disk (line 204 in services_cache.py)
file_path=(
    Path(service_dict["file_path"])  # ✅ Convert string back to Path
    if service_dict.get("file_path")
    else None
),
```

### LSP Features (URIs)
When sending to LSP client, convert to URI:

```python
from urllib.parse import quote
from pathlib import Path

def path_to_uri(path: Path) -> str:
    """Convert absolute Path to file:// URI."""
    # Use as_uri() for proper encoding
    return path.as_uri()

# Example usage in hover
@server.feature(TEXT_DOCUMENT_HOVER)
def hover(ls: DrupalLanguageServer, params: HoverParams):
    service = ls.workspace_cache.caches["services"].get("entity_type.manager")
    
    if service and service.file_path:
        # Convert to URI for LSP
        file_uri = service.file_path.as_uri()
        
        # Display relative path for readability
        relative_path = service.file_path.relative_to(ls.workspace_cache.workspace_root)
        
        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.Markdown,
                value=f"**Service:** {service.id}\n\n"
                      f"**Class:** {service.class_name}\n\n"
                      f"**Defined in:** [{relative_path}]({file_uri})"
            )
        )
```

## Implementation Examples

### ✅ Correct: Absolute Path Storage

```python
# When scanning
for services_file in base_path.rglob("*.services.yml"):
    if services_file.is_file():
        # services_file is absolute Path object
        await self.parse_services_file(services_file)  # ✅

# When creating ServiceDefinition
self._services[id] = ServiceDefinition(
    id=id,
    class_name=class_name,
    file_path=file_path,  # ✅ Absolute Path object
)
```

### ✅ Correct: Display to User

```python
# In completion item
def get_completion_item(service: ServiceDefinition) -> CompletionItem:
    # Show relative path for readability
    relative = service.file_path.relative_to(workspace_root)
    
    return CompletionItem(
        label=service.id,
        detail=service.class_name,
        documentation=f"Defined in: {relative}"  # ✅ Relative for display
    )
```

### ✅ Correct: Go to Definition

```python
@server.feature(TEXT_DOCUMENT_DEFINITION)
def definition(ls: DrupalLanguageServer, params: DefinitionParams):
    service = ls.workspace_cache.caches["services"].get("some.service")
    
    if service and service.file_path:
        return Location(
            uri=service.file_path.as_uri(),  # ✅ Convert to URI
            range=Range(...)  # Line/column where service is defined
        )
```

### ❌ Incorrect: Relative Path Storage

```python
# DON'T DO THIS
self._services[id] = ServiceDefinition(
    file_path=file_path.relative_to(workspace_root),  # ❌ Don't store relative
)
```

## Summary

| Aspect | Format | Example |
|--------|--------|---------|
| **Storage (in-memory)** | `Path` object (absolute) | `Path("/var/www/drupal/core/core.services.yml")` |
| **Persistence (JSON)** | `str` (absolute) | `"/var/www/drupal/core/core.services.yml"` |
| **Display (to user)** | `str` (relative) | `"core/core.services.yml"` |
| **LSP Protocol (URIs)** | `str` (file:// URI) | `"file:///var/www/drupal/core/core.services.yml"` |

## Current Implementation Status

✅ **Your current implementation is already correct!**

The `file_path` parameter in line 123 of `services_cache.py` receives an absolute `Path` object from the scanning loop and stores it as-is. This is the recommended approach.

## When to Convert

Convert absolute paths to relative **only** when:
1. Displaying to users (completion details, hover text)
2. Logging/debugging messages
3. Generating human-readable documentation

Always keep the absolute `Path` object internally for:
1. File operations (exists, read, stat)
2. Cache invalidation checks
3. LSP URI generation
4. Internal references
