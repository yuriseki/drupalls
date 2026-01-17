# Service to Class Definition Navigation

## Overview

This guide documents how to implement "Go to Definition" functionality that navigates from Drupal service definitions in `*.services.yml` files to their corresponding PHP class files. This complements the existing service definition capability which navigates from PHP code to YAML files.

## User Experience Flow

### Current Flow (PHP → YAML)
```php
// In PHP file: src/Controller/MyController.php
$logger = \Drupal::service('logger.factory');
//                          ↑ Ctrl+Click here
// → Navigates to: core/core.services.yml:123 (service definition)
```

### New Flow (YAML → PHP Class)
```yaml
# In YAML file: core/core.services.yml
services:
  logger.factory:
    class: Drupal\Core\Logger\LoggerChannelFactory
    #      ↑ Ctrl+Click here
    # → Navigates to: core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
```

## Architecture

### Plugin Structure

Following the capability plugin architecture, we'll create a new capability class:

```
ServicesYamlDefinitionCapability(DefinitionCapability)
├── can_handle() - Check if in YAML file on class property
├── definition() - Navigate to PHP class file
└── Helper methods:
    ├── extract_class_name() - Get class name from YAML
    ├── resolve_class_file() - Convert FQCN to file path
    └── find_class_definition_line() - Parse PHP for class declaration
```

### How It Works

1. **Trigger**: User invokes "Go to Definition" (Ctrl+Click) in a `*.services.yml` file
2. **Context Check**: `can_handle()` verifies:
   - File ends with `.services.yml`
   - Cursor is on the `class:` property line
   - Line contains a valid PHP class name
3. **Extraction**: Extract the fully qualified class name (FQCN)
4. **Resolution**: Convert FQCN to file path using Drupal's PSR-4 autoloading conventions
5. **Navigation**: Return `Location` pointing to the class definition line

## Implementation Guide

### Step 1: Create the Capability Class

Create or extend `drupalls/lsp/capabilities/services_capabilities.py`:

```python
"""
Services-related LSP capabilities.

Provides completion, hover, and definition for Drupal services.
"""

import re
from pathlib import Path
from lsprotocol.types import (
    DefinitionParams,
    Location,
    Position,
    Range,
)

from drupalls.lsp.capabilities.capabilities import DefinitionCapability


class ServicesYamlDefinitionCapability(DefinitionCapability):
    """
    Provides go-to-definition from .services.yml files to PHP class definitions.
    
    Navigates from:
        services:
          logger.factory:
            class: Drupal\Core\Logger\LoggerChannelFactory
    
    To:
        core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
    """
    
    @property
    def name(self) -> str:
        return "services_yaml_to_class_definition"
    
    @property
    def description(self) -> str:
        return "Navigate from service class in YAML to PHP class definition"
    
    def register(self) -> None:
        """Register is handled by CapabilityManager aggregation."""
        pass
    
    async def can_handle(self, params: DefinitionParams) -> bool:
        """
        Check if we should handle this definition request.
        
        Returns True if:
        1. File is a .services.yml file
        2. Cursor is on a line containing "class:" property
        3. Line contains a valid PHP class name
        """
        # Get document URI
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        
        # Check if file is a services YAML file
        if not doc.uri.endswith('.services.yml'):
            return False
        
        # Get current line
        try:
            line = doc.lines[params.position.line]
        except IndexError:
            return False
        
        # Check if line contains "class:" property
        # Format: "    class: Drupal\Core\Logger\LoggerChannelFactory"
        if 'class:' not in line:
            return False
        
        # Check if line has a PHP namespace (contains backslash)
        if '\\' not in line:
            return False
        
        return True
    
    async def definition(self, params: DefinitionParams) -> Location | None:
        """
        Provide definition location for the PHP class.
        
        Process:
        1. Extract FQCN from the current line
        2. Convert FQCN to file path
        3. Find the class definition line in the file
        4. Return Location pointing to class declaration
        """
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        
        try:
            line = doc.lines[params.position.line]
        except IndexError:
            return None
        
        # Extract the fully qualified class name
        class_name = self._extract_class_name(line)
        if not class_name:
            return None
        
        # Resolve FQCN to file path
        class_file = self._resolve_class_file(class_name)
        if not class_file or not class_file.exists():
            return None
        
        # Find the class definition line
        class_line = self._find_class_definition_line(class_file, class_name)
        
        # Return location
        return Location(
            uri=class_file.as_uri(),
            range=Range(
                start=Position(line=class_line, character=0),
                end=Position(line=class_line, character=0),
            )
        )
    
    def _extract_class_name(self, line: str) -> str | None:
        """
        Extract fully qualified class name from YAML line.
        
        Examples:
            "    class: Drupal\\Core\\Logger\\LoggerChannelFactory"
            "    class: 'Drupal\\Core\\Logger\\LoggerChannelFactory'"
            "    class: \"Drupal\\Core\\Logger\\LoggerChannelFactory\""
        
        Returns:
            "Drupal\\Core\\Logger\\LoggerChannelFactory"
        """
        # Pattern: class: optionally quoted PHP namespace
        pattern = re.compile(r'class:\s*["\']?([A-Za-z0-9\\_]+)["\']?')
        match = pattern.search(line)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def _resolve_class_file(self, fqcn: str) -> Path | None:
        """
        Convert fully qualified class name to file path.
        
        Uses Drupal's PSR-4 autoloading conventions:
        - Drupal\\Core\\...       → core/lib/Drupal/Core/...
        - Drupal\\[module]\\...   → modules/.../src/...
        
        Args:
            fqcn: Fully qualified class name (e.g., "Drupal\\Core\\Logger\\LoggerChannelFactory")
        
        Returns:
            Path to PHP file, or None if cannot resolve
        """
        if not self.workspace_cache:
            return None
        
        workspace_root = self.workspace_cache.workspace_root
        
        # Split namespace into parts
        parts = fqcn.split('\\')
        
        if len(parts) < 2:
            return None
        
        # Handle Drupal\Core\* classes
        if parts[0] == 'Drupal' and parts[1] == 'Core':
            # Drupal\Core\Logger\LoggerChannelFactory
            # → core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
            relative_path = Path('core/lib') / '/'.join(parts)
            class_file = workspace_root / f"{relative_path}.php"
            return class_file
        
        # Handle Drupal\[module]\* classes
        if parts[0] == 'Drupal' and len(parts) >= 2:
            # Drupal\mymodule\Controller\MyController
            # → modules/.../mymodule/src/Controller/MyController.php
            module_name = parts[1].lower()  # Module names are lowercase
            
            # Remaining namespace parts after "Drupal\[module]\"
            relative_parts = parts[2:]  # Skip "Drupal" and module name
            
            # Build the relative path within the module's src/ directory
            if relative_parts:
                class_relative_path = Path('/'.join(relative_parts)).with_suffix('.php')
            else:
                return None
            
            # Search for module recursively in common base directories
            # This handles nested directories like modules/custom/vendor/mymodule
            search_base_dirs = [
                workspace_root / 'modules',
                workspace_root / 'core' / 'modules',
            ]
            
            for base_dir in search_base_dirs:
                if not base_dir.exists():
                    continue
                
                # Use rglob to search recursively for module directories
                # Look for any directory matching the module name that contains a src/ folder
                for module_dir in base_dir.rglob(module_name):
                    if module_dir.is_dir():
                        src_dir = module_dir / 'src'
                        if src_dir.exists() and src_dir.is_dir():
                            class_file = src_dir / class_relative_path
                            if class_file.exists():
                                return class_file
        
        return None
    
    def _find_class_definition_line(self, file_path: Path, fqcn: str) -> int:
        """
        Find the line number where the class is declared.
        
        Searches for patterns like:
        - class LoggerChannelFactory
        - final class LoggerChannelFactory
        - abstract class LoggerChannelFactory
        - interface LoggerChannelFactoryInterface
        - trait LoggerChannelFactoryTrait
        
        Args:
            file_path: Path to PHP file
            fqcn: Fully qualified class name
        
        Returns:
            Line number (0-indexed) where class is declared, or 0 if not found
        """
        # Extract simple class name (last part after backslash)
        class_name = fqcn.split('\\')[-1]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Pattern for class/interface/trait declaration
            # Matches: class ClassName, final class ClassName, etc.
            pattern = re.compile(
                rf'^\s*(final|abstract)?\s*(class|interface|trait)\s+{re.escape(class_name)}\b'
            )
            
            for line_num, line in enumerate(lines):
                if pattern.search(line):
                    return line_num
            
        except Exception:
            # If file read fails, return 0
            pass
        
        return 0
```

### Step 2: Register the Capability

Update `drupalls/lsp/capabilities/capabilities.py` to include the new capability:

```python
class CapabilityManager:
    def __init__(
        self,
        server: DrupalLanguageServer,
        capabilities: dict[str, Capability] | None = None
    ):
        self.server = server
        
        if capabilities is None:
            from drupalls.lsp.capabilities.services_capabilities import (
                ServicesCompletionCapability,
                ServicesHoverCapability,
                ServicesDefinitionCapability,
                ServicesYamlDefinitionCapability,  # ADD THIS
            )
            
            capabilities = {
                "services_completion": ServicesCompletionCapability(server),
                "services_hover": ServicesHoverCapability(server),
                "services_definition": ServicesDefinitionCapability(server),
                "services_yaml_definition": ServicesYamlDefinitionCapability(server),  # ADD THIS
            }
        
        self.capabilities = capabilities
        self._registered = False
```

### Step 3: Test the Implementation

Create test scenarios:

```python
# tests/test_services_yaml_definition.py
from unittest.mock import Mock

import pytest
from lsprotocol.types import DefinitionParams, Position, TextDocumentIdentifier

from drupalls.lsp.capabilities.services_capabilities import (
    ServicesYamlDefinitionCapability,
)
from drupalls.lsp.server import create_server
from drupalls.workspace.cache import WorkspaceCache


@pytest.mark.asyncio
async def test_yaml_to_class_navigation(tmp_path, mocker):
    """Test navigating from YAML service definition to PHP class."""

    # Given: A .services.yml file with a service class
    yaml_uri = "file:///path/to/mymodule.services.yml"
    yaml_content = """
services:
  logger.factory:
    class: Drupal\\Core\\Logger\\LoggerChannelFactory
    arguments: ['@container']
"""

    # Set up temporary Drupal file structure
    php_file = tmp_path / "core" / "lib" / "Drupal" / "Core" / "Logger" / "LoggerChannelFactory.php"
    php_file.parent.mkdir(parents=True, exist_ok=True)
    php_file.write_text("<?php\nclass LoggerChannelFactory {}\n")

    # Create server and initialize workspace cache
    server = create_server()
    server.workspace_cache = WorkspaceCache(tmp_path, tmp_path)
    await server.workspace_cache.initialize()

    # Mock the workspace
    mock_workspace = Mock()
    server.protocol._workspace = mock_workspace

    # Mock the document retrieval
    mock_doc = Mock()
    mock_doc.lines = yaml_content.strip().split('\n')
    mock_workspace.get_text_document.return_value = mock_doc

    # Create capability
    capability = ServicesYamlDefinitionCapability(server)

    # When: User invokes "Go to Definition" on the class line
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri=yaml_uri),
        position=Position(line=2, character=15)  # On "Drupal\Core\..."
    )
    result = await capability.definition(params)

    # Then: Should navigate to the PHP class file
    assert result is not None
    assert not isinstance(result, list)  # Should be a single Location
    assert php_file.as_uri() == result.uri
    assert result.range.start.line == 1  # Class declaration on line 1 (0-indexed)

```

## PSR-4 Autoloading Reference

### Drupal Core Classes

```
Drupal\Core\[Namespace]\ClassName
→ core/lib/Drupal/Core/[Namespace]/ClassName.php

Examples:
Drupal\Core\Logger\LoggerChannelFactory
→ core/lib/Drupal/Core/Logger/LoggerChannelFactory.php

Drupal\Core\Database\Connection
→ core/lib/Drupal/Core/Database/Connection.php
```

### Module Classes

```
Drupal\[module]\[Namespace]\ClassName
→ modules/[module]/src/[Namespace]/ClassName.php

Examples:
Drupal\node\Controller\NodeController
→ core/modules/node/src/Controller/NodeController.php

Drupal\mymodule\Plugin\Block\MyBlock
→ modules/custom/mymodule/src/Plugin/Block/MyBlock.php
```

### Search Order for Modules

When resolving module classes, the system performs a **recursive search** in these base directories:

1. `workspace_root/modules/` - Searches recursively for module directories
   - Handles: `modules/mymodule/`, `modules/custom/mymodule/`, `modules/custom/vendor/mymodule/`
   - Handles: `modules/contrib/mymodule/`, `modules/contrib/vendor/mymodule/`
   - Any nested structure under `modules/`

2. `workspace_root/core/modules/` - Searches recursively for core module directories
   - Handles: `core/modules/node/`, `core/modules/user/`, etc.

**Search Algorithm:**
- Uses `rglob(module_name)` to find directories matching the module name
- Checks if found directory contains a `src/` subdirectory
- Verifies the class file exists at the expected PSR-4 path
- Returns the first matching file found

**Examples of Supported Structures:**
```
modules/mymodule/src/Controller/MyController.php
modules/custom/mymodule/src/Controller/MyController.php
modules/custom/vendor/mymodule/src/Controller/MyController.php
modules/contrib/mymodule/src/Controller/MyController.php
modules/contrib/vendor/mymodule/src/Plugin/Block/MyBlock.php
core/modules/node/src/Controller/NodeController.php
```

**Performance Note:** The recursive search may take longer in large projects. Consider implementing a class location cache (see Performance Considerations section) to avoid repeated file system traversals.

## Edge Cases to Handle

### 1. Class Not Found
```yaml
services:
  my.service:
    class: NonExistent\Class\Name  # Class file doesn't exist
```
**Handling**: Return `None` gracefully, no error to user

### 2. Invalid YAML Syntax
```yaml
services:
  my.service:
    class: "Drupal\Core\Logger  # Missing closing quote
```
**Handling**: `can_handle()` returns `False`, capability doesn't activate

### 3. Aliased Classes
```yaml
services:
  my.service:
    alias: logger.factory  # Not a class, but an alias
```
**Handling**: `can_handle()` checks for `class:` keyword, returns `False` for aliases

### 4. Multiple Namespaces in Line
```yaml
services:
  my.service:
    class: Drupal\Core\Logger\LoggerChannelFactory  # Actual use case
    # Note: Some complex YAML might have comments with namespaces
```
**Handling**: Extract first match after `class:` keyword

### 5. Cursor Position

User might click anywhere on the line:
```yaml
    class: Drupal\Core\Logger\LoggerChannelFactory
    ^      ^                                      ^
    |      |                                      |
    here   or here                                or here
```
**Handling**: `can_handle()` checks if line contains `class:`, extraction works regardless of cursor position

### 6. Deeply Nested Module Structures

Some projects may have very deep nesting:
```
modules/custom/vendor/category/subcategory/mymodule/src/Controller/MyController.php
```
**Handling**: The recursive `rglob()` search finds modules at any depth, but this can impact performance. Consider implementing a cache (see Performance Considerations) to avoid repeated deep searches.

### 7. Multiple Modules with Same Name

Rare case where modules have the same name in different locations:
```
modules/custom/mymodule/src/MyClass.php
modules/contrib/mymodule/src/MyClass.php
```
**Handling**: Returns the first match found. The order depends on the search order (modules/ before core/modules/), and `rglob()` order within each base directory. Document this behavior or add configuration for search priority.

## Performance Considerations

### File System Lookups

Resolving class paths requires file system operations, and the recursive search can be expensive:

```python
# Recursive search through module directories
for module_dir in base_dir.rglob(module_name):
    if module_dir.is_dir():
        # Check for src/ directory and class file
```

**Performance Impact:**
- **Recursive search** (`rglob`) traverses all subdirectories under `modules/`
- In large projects with hundreds of modules, this can take 10-100ms per request
- Multiple nested levels increase search time
- Network file systems (NFS, WSL) amplify the performance impact

**Optimization Strategies:**
1. **Cache Class Locations**: Build a cache of FQCN → file path mappings during workspace initialization (recommended)
2. **Lazy Loading**: Only search when definition is requested (current approach)
3. **Parallel Search**: Search multiple base directories concurrently using asyncio
4. **Smart Path Prediction**: Try common paths first before recursive search
5. **Limit Search Depth**: Stop at reasonable depth (e.g., 3-4 levels)

### Example: Cached Class Resolution

```python
class ClassLocationCache(CachedWorkspace):
    """Cache for PHP class file locations."""
    
    def __init__(self, workspace_cache: WorkspaceCache):
        super().__init__(workspace_cache)
        self._class_map: dict[str, Path] = {}
    
    async def scan(self):
        """Scan all PHP files and build class → file mapping."""
        for php_file in self.workspace_root.rglob("*.php"):
            fqcn = self._extract_fqcn_from_file(php_file)
            if fqcn:
                self._class_map[fqcn] = php_file
    
    def get(self, fqcn: str) -> Path | None:
        """Get file path for a class name (O(1) lookup)."""
        return self._class_map.get(fqcn)
```

**Benefits:**
- O(1) lookups instead of file system searches
- Consistent with existing workspace cache architecture
- Can be invalidated when PHP files change

## Integration with Existing Capabilities

### Capability Priority

The `CapabilityManager.handle_definition()` method processes capabilities in order. Ensure proper ordering:

```python
capabilities = {
    "services_yaml_definition": ServicesYamlDefinitionCapability(server),  # YAML → PHP
    "services_definition": ServicesDefinitionCapability(server),          # PHP → YAML
}
```

Both can coexist because `can_handle()` checks file type:
- `ServicesYamlDefinitionCapability`: Only handles `.services.yml` files
- `ServicesDefinitionCapability`: Only handles `.php` files with service patterns

### Combined User Flow

```
PHP Code ←→ YAML Definition ←→ PHP Class
   |              |                 |
   |              |                 |
\Drupal::       logger.factory:   class: Drupal\Core\Logger\...
  service('        ↓                 ↓
logger.factory')  Ctrl+Click      Ctrl+Click
   ↓              navigates        navigates
Ctrl+Click        to YAML          to PHP class
navigates      
to YAML
```

Users can now navigate the full chain:
1. PHP usage → YAML definition (existing)
2. YAML definition → PHP class (new)
3. PHP class → PHP usage (Phpactor handles this)

## Future Enhancements

### 1. Navigate to Constructor/Methods

Instead of just the class line, navigate to specific methods:

```yaml
services:
  my.service:
    class: Drupal\mymodule\MyService
    calls:
      - [setLogger, ['@logger']]  # Navigate to setLogger() method
```

### 2. Hover Information in YAML

Show class information when hovering over class names in YAML:

```yaml
services:
  logger.factory:
    class: Drupal\Core\Logger\LoggerChannelFactory
           ↑ Hover shows: "Creates logger channels | Implements LoggerChannelFactoryInterface"
```

### 3. Completion for Class Names

Autocomplete PHP class names when typing in YAML:

```yaml
services:
  my.service:
    class: Drupal\Core\Log|  # Suggests: Logger\LoggerChannelFactory
```

### 4. Validation

Validate that classes exist and show diagnostics:

```yaml
services:
  my.service:
    class: NonExistent\Class  # Red squiggly: "Class not found"
```

## Testing Checklist

- [ ] Navigate from core service to core class
- [ ] Navigate from custom module service to custom module class (direct path: `modules/mymodule/`)
- [ ] Navigate from custom module service to custom module class (nested: `modules/custom/mymodule/`)
- [ ] Navigate from custom module service to custom module class (deep nested: `modules/custom/vendor/mymodule/`)
- [ ] Navigate from contrib module service to contrib module class (nested: `modules/contrib/mymodule/`)
- [ ] Navigate from contrib module service to contrib module class (deep nested: `modules/contrib/vendor/mymodule/`)
- [ ] Handle cursor at different positions on line
- [ ] Handle non-existent class gracefully
- [ ] Handle invalid YAML gracefully
- [ ] Handle service aliases (should not activate)
- [ ] Performance with large codebases (1000+ services, nested modules)
- [ ] Performance with deeply nested module structures (4-5 levels)
- [ ] Works alongside existing PHP → YAML navigation

## References

- **Plugin Architecture**: `03-CAPABILITY_PLUGIN_ARCHITECTURE.md`
- **LSP Definition Specification**: [LSP textDocument/definition](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_definition)
- **Drupal PSR-4**: [Drupal PSR-4 Documentation](https://www.drupal.org/docs/develop/coding-standards/psr-4-namespaces-and-autoloading-in-drupal-8)
- **Existing Implementation**: `drupalls/lsp/capabilities/services_capabilities.py`

## Summary

This guide provides a complete blueprint for implementing bidirectional navigation between Drupal service YAML definitions and their PHP class implementations. The implementation follows the established capability plugin architecture, ensuring consistency with existing features and maintainability for future enhancements.

Key takeaways:
- Use the `DefinitionCapability` base class
- Implement PSR-4 path resolution for class location
- Handle edge cases gracefully with `can_handle()`
- Consider caching for performance optimization
- Integrate seamlessly with existing capabilities
