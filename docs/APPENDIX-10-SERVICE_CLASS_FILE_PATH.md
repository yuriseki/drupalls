# Service Class File Path Implementation

## Overview

This document explains how the `class_file_path` field in `ServiceDefinition` works and how it could be used to optimize YAML-to-PHP class navigation. Currently, the field exists in the data structure but is not yet populated or used by the navigation capability.

## Current Implementation Status

### What's Implemented ✅

1. **Data Structure**: `ServiceDefinition.class_file_path` field exists (drupalls/workspace/services_cache.py:21)
2. **Navigation Capability**: `ServicesYamlDefinitionCapability` is fully implemented and functional (drupalls/lsp/capabilities/services_capabilities.py:238-470)
3. **Registration**: The capability is registered in `CapabilityManager` (drupalls/lsp/capabilities/capabilities.py:158)

### What's Not Yet Implemented ❌

1. **Field Population**: `class_file_path` is defined but not populated during cache initialization
2. **Field Usage**: The navigation capability resolves paths dynamically instead of using cached paths

### Current Behavior

The YAML-to-PHP navigation works by:
1. User triggers "Go to Definition" on a `class:` line in `.services.yml`
2. `ServicesYamlDefinitionCapability._extract_class_name()` extracts the FQCN from the YAML line
3. `ServicesYamlDefinitionCapability._resolve_class_file()` converts FQCN to file path **on-demand** using PSR-4 rules
4. Navigation occurs to the resolved PHP file

This works correctly but performs file system searches on every request.

## Architecture

### ServiceDefinition Data Structure

```python
@dataclass
class ServiceDefinition(CachedDataBase):
    """Represents a parsed Drupal service definition."""
    
    class_name: str  # FQCN like "Drupal\Core\Logger\LoggerChannelFactory"
    class_file_path: str  # INTENDED: Path to PHP file (NOT YET POPULATED)
    arguments: list[str] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)
```

**Current State**: 
- `class_name` is populated from YAML (e.g., from `class: Drupal\Core\Logger\LoggerChannelFactory`)
- `class_file_path` is defined but remains empty/None

### Navigation Flow

```
User Action (YAML file)
    ↓
ServicesYamlDefinitionCapability.can_handle()
    ↓ (checks if line contains "class:" and "\")
ServicesYamlDefinitionCapability.definition()
    ↓
_extract_class_name(line) → "Drupal\Core\Logger\LoggerChannelFactory"
    ↓
_resolve_class_file(fqcn) → Path("/workspace/core/lib/Drupal/Core/Logger/LoggerChannelFactory.php")
    ↓ (recursive search using rglob)
_find_class_definition_line() → 15
    ↓
Return Location(uri=file_uri, line=15)
```

## Optimization Opportunity: Pre-Caching Class Paths

### The Problem

Currently, `_resolve_class_file()` performs these operations **on every navigation request**:

```python
def _resolve_class_file(self, fqcn: str) -> Path | None:
    # For module classes, search recursively
    for base_dir in search_base_dirs:
        for module_dir in base_dir.rglob(module_name):  # SLOW: Recursive search
            if module_dir.is_dir():
                src_dir = module_dir / "src"
                if src_dir.exists():
                    class_file = src_dir / class_relative_path
                    if class_file.exists():
                        return class_file
```

**Performance Impact:**
- Recursive `rglob()` traverses entire directory tree
- Large projects with nested modules: 10-100ms per request
- Network file systems (NFS, WSL): Can be much slower

### The Solution: Populate class_file_path During Cache Initialization

Instead of searching on-demand, resolve paths **once** during cache initialization:

```python
# In ServicesCache.parse_services_file()
async def parse_services_file(self, file_path: Path):
    """Parse a single .services.yml file."""
    # ... existing parsing code ...
    
    for id, service_def in data["services"].items():
        class_name = service_def.get("class", "")
        
        # NEW: Resolve class file path during initialization
        class_file_path = self._resolve_class_file_path(class_name)
        
        if class_name:
            self._services[id] = ServiceDefinition(
                id=id,
                description=class_name,
                class_name=class_name,
                class_file_path=str(class_file_path) if class_file_path else "",  # POPULATE
                arguments=arguments,
                tags=tags,
                file_path=file_path,
                line_number=service_line_numbers.get(id, 0)
            )

def _resolve_class_file_path(self, fqcn: str) -> Path | None:
    """
    Resolve FQCN to file path using PSR-4 conventions.
    
    This is the same logic as ServicesYamlDefinitionCapability._resolve_class_file()
    but executed during cache initialization instead of on-demand.
    """
    # Same PSR-4 resolution logic...
```

Then, in `ServicesYamlDefinitionCapability`:

```python
async def definition(self, params: DefinitionParams) -> Location | None:
    """Provide definition location for the PHP class."""
    doc = self.server.workspace.get_text_document(params.text_document.uri)
    
    try:
        line = doc.lines[params.position.line]
    except IndexError:
        return None
    
    # Extract service ID from the YAML structure (if available)
    service_id = self._extract_service_id_from_context(doc, params.position.line)
    
    if service_id:
        # OPTIMIZATION: Use cached class_file_path from ServicesCache
        services_cache = self.workspace_cache.caches.get("services")
        if services_cache:
            service_def = services_cache.get(service_id)
            if service_def and service_def.class_file_path:
                class_file = Path(service_def.class_file_path)
                if class_file.exists():
                    # Find class definition line
                    class_line = self._find_class_definition_line(
                        class_file, 
                        service_def.class_name
                    )
                    
                    return Location(
                        uri=class_file.as_uri(),
                        range=Range(
                            start=Position(line=class_line, character=0),
                            end=Position(line=class_line, character=0),
                        )
                    )
    
    # FALLBACK: Dynamic resolution if cache lookup fails
    class_name = self._extract_class_name(line)
    if not class_name:
        return None
    
    class_file = self._resolve_class_file(class_name)
    # ... rest of existing logic ...
```

## Implementation Steps

### Step 1: Add PSR-4 Resolution to ServicesCache

Add a method to resolve class file paths in `drupalls/workspace/services_cache.py`:

```python
class ServicesCache(CachedWorkspace):
    # ... existing code ...
    
    def _resolve_class_file_path(self, fqcn: str) -> Path | None:
        """
        Resolve fully qualified class name to file path using PSR-4.
        
        This mirrors the logic in ServicesYamlDefinitionCapability
        but is executed once during cache initialization.
        
        Args:
            fqcn: Fully qualified class name (e.g., "Drupal\\Core\\Logger\\LoggerChannelFactory")
        
        Returns:
            Path to PHP file, or None if cannot resolve
        """
        if not fqcn:
            return None
        
        # Split namespace into parts
        parts = fqcn.split('\\')
        
        if len(parts) < 2:
            return None
        
        # Handle Drupal\Core\* classes
        if parts[0] == 'Drupal' and parts[1] == 'Core':
            relative_path = Path('core/lib') / '/'.join(parts)
            class_file = self.workspace_root / f"{relative_path}.php"
            if class_file.exists():
                return class_file
            return None
        
        # Handle Drupal\[module]\* classes
        if parts[0] == 'Drupal' and len(parts) >= 2:
            module_name = parts[1].lower()
            relative_parts = parts[2:]
            
            if not relative_parts:
                return None
            
            class_relative_path = Path('/'.join(relative_parts)).with_suffix('.php')
            
            # Search in common base directories
            search_base_dirs = [
                self.workspace_root / 'modules',
                self.workspace_root / 'core' / 'modules',
                self.workspace_root / 'profiles',
            ]
            
            for base_dir in search_base_dirs:
                if not base_dir.exists():
                    continue
                
                for module_dir in base_dir.rglob(module_name):
                    if module_dir.is_dir():
                        src_dir = module_dir / 'src'
                        if src_dir.exists() and src_dir.is_dir():
                            class_file = src_dir / class_relative_path
                            if class_file.exists():
                                return class_file
        
        return None
```

### Step 2: Populate class_file_path During Parsing

Update `parse_services_file()` to call the resolution method:

```python
async def parse_services_file(self, file_path: Path):
    """Parse a single .services.yml file."""
    try:
        # ... existing YAML parsing code ...
        
        # Parse each service definition
        for id, service_def in data["services"].items():
            if not isinstance(service_def, dict):
                continue
            
            class_name = service_def.get("class", "")
            arguments = service_def.get("arguments", [])
            tags = service_def.get("tags", [])
            
            # Resolve class file path
            class_file_path = None
            if class_name:
                resolved_path = self._resolve_class_file_path(class_name)
                if resolved_path:
                    class_file_path = str(resolved_path)
            
            # Create service definition with populated class_file_path
            if class_name:
                self._services[id] = ServiceDefinition(
                    id=id,
                    description=class_name,
                    class_name=class_name,
                    class_file_path=class_file_path or "",  # POPULATED
                    arguments=arguments,
                    tags=tags,
                    file_path=file_path,
                    line_number=service_line_numbers.get(id, 0)
                )
        
        # ... rest of method ...
```

### Step 3: Update Cache Persistence

Ensure `class_file_path` is saved/loaded from disk cache:

```python
# In load_from_disk()
self._services[id] = ServiceDefinition(
    id=service_dict["id"],
    class_name=service_dict["class_name"],
    class_file_path=service_dict.get("class_file_path", ""),  # LOAD
    description=service_dict.get("description", ""),
    arguments=service_dict.get("arguments", []),
    tags=service_dict.get("tags", []),
    file_path=Path(service_dict["file_path"]) if service_dict.get("file_path") else None,
    line_number=service_dict["line_number"]
)

# In save_to_disk()
data = {
    "version": 1,
    "timestamp": datetime.now().isoformat(),
    "services": {
        id: {
            "id": service_def.id,
            "class_name": service_def.class_name,
            "class_file_path": service_def.class_file_path,  # SAVE
            "description": service_def.description,
            "arguments": service_def.arguments,
            "tags": service_def.tags,
            "file_path": str(service_def.file_path) if service_def.file_path else None,
            "line_number": service_def.line_number,
        }
        for id, service_def in self._services.items()
    },
}
```

### Step 4: Optimize ServicesYamlDefinitionCapability

Update the capability to use cached paths when available:

```python
async def definition(self, params: DefinitionParams) -> Location | None:
    """
    Provide definition location for the PHP class.
    
    OPTIMIZATION: Try to use cached class_file_path from ServicesCache
    before falling back to dynamic resolution.
    """
    if not self.workspace_cache:
        return None
    
    doc = self.server.workspace.get_text_document(params.text_document.uri)
    
    try:
        line = doc.lines[params.position.line]
    except IndexError:
        return None
    
    # Extract the fully qualified class name
    class_name = self._extract_class_name(line)
    if not class_name:
        return None
    
    # OPTIMIZATION: Try to find service with this class in cache
    services_cache = self.workspace_cache.caches.get("services")
    if services_cache:
        # Search for service with matching class_name
        for service_def in services_cache.get_all().values():
            if service_def.class_name == class_name and service_def.class_file_path:
                class_file = Path(service_def.class_file_path)
                if class_file.exists():
                    class_line = self._find_class_definition_line(class_file, class_name)
                    
                    return Location(
                        uri=class_file.as_uri(),
                        range=Range(
                            start=Position(line=class_line, character=0),
                            end=Position(line=class_line, character=0),
                        )
                    )
    
    # FALLBACK: Dynamic resolution if cache doesn't have the path
    class_file = self._resolve_class_file(class_name)
    if not class_file or not class_file.exists():
        return None
    
    class_line = self._find_class_definition_line(class_file, class_name)
    
    return Location(
        uri=class_file.as_uri(),
        range=Range(
            start=Position(line=class_line, character=0),
            end=Position(line=class_line, character=0),
        )
    )
```

## Performance Comparison

### Before Optimization (Current)

```
User triggers navigation
    ↓
Extract class name: ~0.1ms
    ↓
Resolve file path: 10-100ms (recursive rglob search)
    ↓
Find class line: ~1ms (file read)
    ↓
Total: ~11-101ms per request
```

### After Optimization (With Pre-Caching)

**Initialization (once per project):**
```
Load workspace
    ↓
Parse all *.services.yml files
    ↓
Resolve all class paths: 10-100ms × N services
    ↓
Cache in memory + disk
    ↓
Total: 2-10 seconds (one-time cost)
```

**Navigation (per request):**
```
User triggers navigation
    ↓
Extract class name: ~0.1ms
    ↓
Lookup cached path: ~0.01ms (dict lookup)
    ↓
Find class line: ~1ms (file read)
    ↓
Total: ~1.11ms per request (10-100× faster)
```

## Edge Cases

### 1. Class File Doesn't Exist During Initialization

```yaml
services:
  my.service:
    class: NonExistent\Class\Name
```

**Handling**: 
- `_resolve_class_file_path()` returns `None`
- `class_file_path` is set to empty string `""`
- Navigation falls back to dynamic resolution (which also fails gracefully)

### 2. Class File Moved After Initialization

```
Initial scan: core/modules/node/src/Controller/NodeController.php
Later: File moved to different location
```

**Handling**:
- Cached path is now invalid
- Capability checks `class_file.exists()` before navigating
- Falls back to dynamic resolution
- Consider: Implement cache invalidation on file moves

### 3. Multiple Services Share Same Class

```yaml
services:
  logger.factory:
    class: Drupal\Core\Logger\LoggerChannelFactory
  logger.factory.alias:
    class: Drupal\Core\Logger\LoggerChannelFactory  # Same class
```

**Handling**:
- Both services store the same `class_file_path`
- Navigation works correctly for both
- Slight memory overhead (duplicated strings)
- Consider: Use string interning or shared references

## Future Enhancements

### 1. Separate Class Location Cache

Instead of storing `class_file_path` in `ServiceDefinition`, create a dedicated cache:

```python
class ClassLocationCache(CachedWorkspace):
    """Cache for PHP class file locations."""
    
    def __init__(self, workspace_cache: WorkspaceCache):
        super().__init__(workspace_cache)
        self._class_map: dict[str, Path] = {}  # FQCN → file path
    
    async def scan(self):
        """Build class map from PHP files."""
        for php_file in self.workspace_root.rglob("*.php"):
            fqcn = self._extract_fqcn_from_file(php_file)
            if fqcn:
                self._class_map[fqcn] = php_file
    
    def get(self, fqcn: str) -> Path | None:
        """O(1) lookup for any PHP class."""
        return self._class_map.get(fqcn)
```

**Benefits**:
- Works for **all** PHP classes, not just services
- Can be used by other capabilities (hooks, plugins, etc.)
- More maintainable (single source of truth)
- No duplication across ServiceDefinitions

### 2. Incremental Updates

Update class locations when PHP files are created/moved:

```python
async def on_file_created(self, file_path: Path):
    """Update cache when PHP file is created."""
    if file_path.suffix == '.php':
        fqcn = self._extract_fqcn_from_file(file_path)
        if fqcn:
            self._class_map[fqcn] = file_path

async def on_file_deleted(self, file_path: Path):
    """Update cache when PHP file is deleted."""
    # Remove from class_map
    fqcn_to_remove = None
    for fqcn, path in self._class_map.items():
        if path == file_path:
            fqcn_to_remove = fqcn
            break
    
    if fqcn_to_remove:
        del self._class_map[fqcn_to_remove]
```

### 3. Lazy Resolution Strategy

Hybrid approach: Resolve paths on first access, then cache:

```python
class ServiceDefinition(CachedDataBase):
    class_name: str
    _class_file_path: str | None = None  # Private, lazy-loaded
    
    @property
    def class_file_path(self) -> Path | None:
        """Lazy-load class file path on first access."""
        if self._class_file_path is None and self.class_name:
            self._class_file_path = str(self._resolve_class_file())
        return Path(self._class_file_path) if self._class_file_path else None
```

**Benefits**:
- No upfront cost during initialization
- Paths resolved only for actually-used services
- Still caches for subsequent accesses

## Testing

### Unit Tests

```python
import pytest
from pathlib import Path
from drupalls.workspace.services_cache import ServicesCache, ServiceDefinition

@pytest.mark.asyncio
async def test_class_file_path_populated(tmp_path):
    """Test that class_file_path is populated during parsing."""
    
    # Create test structure
    yaml_file = tmp_path / "test.services.yml"
    yaml_file.write_text("""
services:
  logger.factory:
    class: Drupal\\Core\\Logger\\LoggerChannelFactory
""")
    
    php_file = tmp_path / "core" / "lib" / "Drupal" / "Core" / "Logger" / "LoggerChannelFactory.php"
    php_file.parent.mkdir(parents=True, exist_ok=True)
    php_file.write_text("<?php\\nnamespace Drupal\\Core\\Logger;\\nclass LoggerChannelFactory {}")
    
    # Parse services
    from drupalls.workspace.cache import WorkspaceCache
    workspace_cache = WorkspaceCache(tmp_path, tmp_path)
    services_cache = ServicesCache(workspace_cache)
    await services_cache.parse_services_file(yaml_file)
    
    # Verify class_file_path is populated
    service = services_cache.get("logger.factory")
    assert service is not None
    assert service.class_file_path != ""
    assert Path(service.class_file_path).exists()
    assert "LoggerChannelFactory.php" in service.class_file_path


@pytest.mark.asyncio
async def test_class_file_path_nonexistent():
    """Test graceful handling when class file doesn't exist."""
    
    yaml_file = tmp_path / "test.services.yml"
    yaml_file.write_text("""
services:
  my.service:
    class: NonExistent\\Class
""")
    
    services_cache = ServicesCache(workspace_cache)
    await services_cache.parse_services_file(yaml_file)
    
    service = services_cache.get("my.service")
    assert service is not None
    assert service.class_file_path == ""  # Empty when not found
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_yaml_navigation_uses_cached_path(tmp_path):
    """Test that navigation uses cached class_file_path."""
    
    # Set up files
    yaml_file = tmp_path / "test.services.yml"
    php_file = tmp_path / "core" / "lib" / "Drupal" / "Core" / "Logger" / "LoggerChannelFactory.php"
    # ... create files ...
    
    # Initialize server and cache
    server = create_server()
    server.workspace_cache = WorkspaceCache(tmp_path, tmp_path)
    await server.workspace_cache.initialize()
    
    # Verify service has cached path
    services_cache = server.workspace_cache.caches.get("services")
    service = services_cache.get("logger.factory")
    assert service.class_file_path != ""
    
    # Test navigation
    capability = ServicesYamlDefinitionCapability(server)
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri=yaml_file.as_uri()),
        position=Position(line=2, character=15)
    )
    
    result = await capability.definition(params)
    
    assert result is not None
    assert php_file.as_uri() in result.uri
```

## References

- **APPENDIX-07-SERVICE_CLASS_DEFINITION_GUIDE.md**: Full implementation guide for YAML-to-PHP navigation
- **02-WORKSPACE_CACHE_ARCHITECTURE.md**: Cache architecture patterns
- **Drupal PSR-4**: [PSR-4 Autoloading](https://www.drupal.org/docs/develop/coding-standards/psr-4-namespaces-and-autoloading-in-drupal-8)
- **Performance Considerations**: APPENDIX-07 lines 533-585

## Summary

The `class_file_path` field in `ServiceDefinition` provides a clear optimization path for YAML-to-PHP navigation:

1. **Current State**: Field defined but not populated; navigation uses dynamic resolution
2. **Proposed Optimization**: Populate `class_file_path` during cache initialization
3. **Performance Gain**: 10-100× faster navigation (1ms vs 11-101ms)
4. **Trade-off**: Slightly longer initialization (2-10s one-time cost)
5. **Future**: Consider dedicated `ClassLocationCache` for broader use

The implementation is straightforward and follows existing cache architecture patterns. The optimization is particularly valuable for large projects with deeply nested module structures where `rglob()` searches are expensive.
