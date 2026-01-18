# Updating Service Capabilities for Dependency Injection with Type Checking

## Overview

This guide updates the service capabilities to handle dependency injection patterns where services are accessed via `->get()` on ContainerInterface variables, using proper type checking to avoid false positives.

**Current Support:**
```php
// ✅ Already supported
\Drupal::service('entity_type.manager');
\Drupal::getContainer()->get('entity_type.manager');
```

**New Support (with type validation):**
```php
// ✅ Will be supported (only for ContainerInterface variables)
$this->container->get('entity_type.manager');
$container->get('entity_type.manager');

// ❌ Will NOT be supported (not ContainerInterface)
$array->get('some_key');
$config->get('some.key');
```

## Problem Statement

The current `SERVICE_PATTERN` only matches direct calls to `\Drupal::service()` and `\Drupal::getContainer()->get()`. However, in Drupal dependency injection, services are often accessed through injected container variables. The challenge is distinguishing between container `->get()` calls and other `->get()` methods.

## Solution: Type-Aware Pattern Matching

### Architecture Challenge

To properly detect ContainerInterface variables, we need:

1. **Detect `->get()` calls** in source code
2. **Extract variable names** from the calls
3. **Query type information** for those variables
4. **Validate ContainerInterface** before providing completions

### Phpactor Integration

We'll integrate with Phpactor's type analysis to determine variable types.

#### 1. Define Type Query System

```python
# drupalls/lsp/phpactor_integration.py

from typing import Optional
import re

class TypeChecker:
    """Handles type checking for variables in ->get() calls."""
    
    def __init__(self, phpactor_client=None):
        self.phpactor_client = phpactor_client
        
    async def is_container_variable(self, doc, line: str, position: Position) -> bool:
        """Check if the variable in ->get() call is a ContainerInterface."""
        
        # Extract variable name from ->get() context
        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False
            
        # Query Phpactor for type
        var_type = await self._query_variable_type(doc, line, position)
        if not var_type:
            return False
            
        return self._is_container_interface(var_type)
        
    def _extract_variable_from_get_call(self, line: str, position: Position) -> Optional[str]:
        """Extract variable name from ->get() call context."""
        # Find ->get( before cursor
        get_pos = line.rfind("->get(", 0, position.character)
        if get_pos == -1:
            return None
            
        # Find the variable before ->
        arrow_pos = line.rfind("->", 0, get_pos)
        if arrow_pos == -1:
            return None
            
        # Extract variable (handle $this->var and $var patterns)
        var_part = line[arrow_pos - 20:arrow_pos].strip()
        
        # Match variable patterns
        match = re.search(r'\$?(\w+)$', var_part)
        return match.group(1) if match else None
        
    async def _query_variable_type(self, doc, line: str, position: Position) -> Optional[str]:
        """Query Phpactor for variable type at position."""
        if not self.phpactor_client:
            return None
            
        try:
            # This would integrate with Phpactor's type analysis
            # Implementation depends on chosen Phpactor integration approach
            return await self.phpactor_client.query_type(
                doc.uri, position.line, position.character
            )
        except Exception:
            return None
            
    def _is_container_interface(self, type_str: str) -> bool:
        """Check if type represents a ContainerInterface."""
        container_types = [
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "ContainerInterface",
            # Add Drupal-specific types
            "Drupal\\Core\\DependencyInjection\\Container"
        ]
        
        return any(container_type in type_str for container_type in container_types)
```

#### 2. Update Service Capabilities

```python
# drupalls/lsp/capabilities/services_capabilities.py

class ServicesCompletionCapability(CompletionCapability):
    def __init__(self, server: DrupalLanguageServer, type_checker: TypeChecker = None):
        super().__init__(server)
        self.type_checker = type_checker
        
    async def can_handle(self, params: CompletionParams) -> bool:
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        # Check existing patterns
        if SERVICE_PATTERN.search(line):
            return True
            
        # Check for ->get() calls with type validation
        if "->get(" in line:
            return await self.type_checker.is_container_variable(doc, line, params.position)
            
        return False
```

### Implementation Options

#### Option 1: LSP-Based Phpactor Integration

```python
# drupalls/lsp/phpactor_client.py

class PhpactorLspClient:
    """LSP client for querying Phpactor."""
    
    async def query_type(self, uri: str, line: int, character: int) -> Optional[str]:
        """Query type information via LSP."""
        # Implementation would send custom LSP request to Phpactor
        # and parse the type response
        pass
```

#### Option 2: Direct Phpactor RPC

```python
# drupalls/lsp/phpactor_rpc.py

class PhpactorRpcClient:
    """RPC client for Phpactor type queries."""
    
    def query_type_at_offset(self, file_path: str, offset: int) -> Optional[str]:
        """Query type using Phpactor RPC."""
        # Implementation would call phpactor RPC commands
        pass
```

## Updated SERVICE_PATTERN

```python
# Keep the pattern broad for initial detection
SERVICE_PATTERN = re.compile(r'(::service\([\'"]?|getContainer\(\)->get\([\'"]?|->get\([\'"]?)')
```

The pattern remains broad for initial detection, but type checking provides the accuracy.

## User Experience Flow

### Type-Aware Completion

```php
class MyController {
    /** @var \Symfony\Component\DependencyInjection\ContainerInterface */
    protected $container;
    
    /** @var \Some\Other\Service */
    protected $otherService;
    
    public function build() {
        // ✅ Triggers completion (ContainerInterface)
        $service = $this->container->get('entity_type.manager');
        
        // ❌ No completion (not ContainerInterface) 
        $value = $this->otherService->get('some_param');
        
        // ✅ Traditional patterns still work
        $service2 = \Drupal::service('database');
    }
}
```

## Testing

### Test Case: Type Validation

```python
@pytest.mark.asyncio
async def test_container_type_validation(tmp_path):
    """Test that ->get() only triggers for ContainerInterface variables."""
    
    php_file = tmp_path / "test.php"
    php_file.write_text("""
<?php

class TestController {
    /** @var \Symfony\Component\DependencyInjection\ContainerInterface */
    protected $container;
    
    /** @var \Some\Other\Service */
    protected $otherService;
    
    public function test() {
        $service = $this->container->get('entity_type.manager');    // Should work
        $value = $this->otherService->get('param');               // Should not work
    }
}
""")
    
    # Setup with type checker
    type_checker = TypeChecker(phpactor_client=MockPhpactorClient())
    server = create_server()
    capability = ServicesCompletionCapability(server, type_checker)
    
    # Test container variable
    params1 = CompletionParams(
        text_document=TextDocumentIdentifier(uri=f'file://{php_file}'),
        position=Position(line=8, character=42)  # On 'entity_type.manager'
    )
    assert await capability.can_handle(params1) == True
    
    # Test non-container variable
    params2 = CompletionParams(
        text_document=TextDocumentIdentifier(uri=f'file://{php_file}'),
        position=Position(line=9, character=38)  # On 'param'
    )
    assert await capability.can_handle(params2) == False
```

## Error Handling and Fallbacks

### Phpactor Unavailable

```python
async def can_handle(self, params: CompletionParams) -> bool:
    # ... existing checks ...
    
    if "->get(" in line:
        if self.type_checker:
            try:
                return await self.type_checker.is_container_variable(doc, line, params.position)
            except Exception:
                # Fallback to basic pattern (may have false positives)
                return self._basic_container_check(line)
        else:
            # No type checker available
            return self._basic_container_check(line)
            
    return False

def _basic_container_check(self, line: str) -> bool:
    """Basic heuristic check for container variables."""
    # Look for variable names suggesting containers
    if re.search(r'\$[^>]*container[^>]*->get\(', line):
        return True
        
    # Look for PHPDoc hints
    if "@var.*ContainerInterface" in line:
        return True
        
    return False
```

## Performance Considerations

### Caching Type Queries

```python
class TypeCache:
    """Cache type queries to improve performance."""
    
    def __init__(self):
        self._cache = {}
        self._ttl = 300  # 5 minutes
        
    async def get_type(self, key: tuple, fetcher) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]
            
        type_info = await fetcher()
        if type_info:
            self._cache[key] = type_info
            
        return type_info
```

### Asynchronous Processing

Type queries should be non-blocking to avoid slowing down the LSP server.

## Integration with Existing Features

### Consistent Type Checking

Apply the same type checking to all service capabilities:

```python
class ServicesHoverCapability(HoverCapability):
    # Use the same TypeChecker instance
    
class ServicesDefinitionCapability(DefinitionCapability):
    # Use the same TypeChecker instance
```

## Configuration

### Optional Type Checking

```python
# In server configuration
ENABLE_TYPE_CHECKING = True  # Enable for accuracy
# or
ENABLE_TYPE_CHECKING = False  # Disable for performance/simplicity
```

## Summary

This implementation provides accurate, type-aware service completion:

1. **Detect `->get()` calls** in source code
2. **Query variable types** using Phpactor integration
3. **Validate ContainerInterface** before providing completions
4. **Fallback gracefully** when type checking is unavailable

The result is precise service completion that only triggers for actual dependency injection usage, eliminating false positives from other `get()` methods while maintaining high performance through caching and asynchronous processing.

## References

- **Symfony ContainerInterface**: https://symfony.com/doc/current/service_container.html
- **Phpactor RPC Documentation**: https://phpactor.readthedocs.io/en/master/usage/rpc.html
- **LSP Type Queries**: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_hover