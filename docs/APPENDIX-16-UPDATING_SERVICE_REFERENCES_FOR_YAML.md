# Updating Service References to Support YAML Files

## Overview

This guide extends the existing `ServicesReferencesCapability` to handle "Find All References" requests when the cursor is positioned on a service ID in `.services.yml` files.

**Current Behavior**: The capability only works when finding references from PHP code (where services are consumed).

**New Behavior**: The capability now also works when finding references from YAML files (where services are defined), allowing developers to see all places where a service is used by clicking on its definition in `.services.yml`.

## Problem Statement

The current implementation only handles references when in PHP files:

```php
// ✅ Works: Cursor on 'entity_type.manager' in PHP
\Drupal::service('entity_type.manager');
```

But doesn't handle references when in YAML files:

```yaml
# ❌ Doesn't work: Cursor on 'entity_type.manager' in YAML
services:
  entity_type.manager:
    class: Drupal\Core\Entity\EntityTypeManager
```

## Solution: Update can_handle Method

### Current Implementation

```python
# drupalls/lsp/capabilities/services_capabilities.py

async def can_handle(self, params: ReferenceParams) -> bool:
    """Check if cursor is on a service identifier."""
    if not self.workspace_cache:
        return False

    doc = self.server.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]

    return bool(SERVICE_PATTERN.search(line))
```

### Updated Implementation

```python
async def can_handle(self, params: ReferenceParams) -> bool:
    """Check if cursor is on a service identifier in PHP or YAML files."""
    if not self.workspace_cache:
        return False

    doc = self.server.workspace.get_text_document(params.text_document.uri)
    
    # Handle YAML files (.services.yml)
    if doc.uri.endswith('.services.yml'):
        return await self._can_handle_yaml_file(params, doc)
    
    # Handle PHP files (existing logic)
    line = doc.lines[params.position.line]
    return bool(SERVICE_PATTERN.search(line))

async def _can_handle_yaml_file(self, params: ReferenceParams, doc) -> bool:
    """Check if cursor is on a service ID in a YAML file."""
    # Get the word under cursor
    word = doc.word_at_position(
        params.position,
        re_start_word=re.compile(r'[A-Za-z_][A-Za-z0-9_.]*$'),
        re_end_word=re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*')
    )
    
    if not word:
        return False
    
    # Check if this word is a valid service ID
    services_cache = self.workspace_cache.caches.get("services")
    if not services_cache:
        return False
        
    return services_cache.get(word) is not None
```

## User Experience Flow

### Before Update

```yaml
# In services.yml - no references functionality
services:
  entity_type.manager:  # Cursor here: No "Find References" available
    class: Drupal\Core\Entity\EntityTypeManager
```

### After Update

```yaml
# In services.yml - references now work
services:
  entity_type.manager:  # Cursor here: "Find References" shows all usages
    class: Drupal\Core\Entity\EntityTypeManager

# Results show:
# - src/Controller/MyController.php:15
# - src/Form/MyForm.php:22  
# - modules/custom/my_module/src/Service/MyService.php:8
```

## Implementation Details

### 1. File Type Detection

The updated `can_handle` method now checks the file extension:

```python
# Check if this is a services YAML file
if doc.uri.endswith('.services.yml'):
    return await self._can_handle_yaml_file(params, doc)
```

### 2. Service ID Extraction in YAML

For YAML files, we extract the service ID using the same word extraction logic as PHP files:

```python
word = doc.word_at_position(
    params.position,
    re_start_word=re.compile(r'[A-Za-z_][A-Za-z0-9_.]*$'),
    re_end_word=re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*')
)
```

This correctly identifies service IDs like:
- `entity_type.manager`
- `logger.factory`
- `cache.default`

### 3. Service Validation

Before proceeding with reference search, we validate that the word under cursor is actually a defined service:

```python
# Check if this word is a valid service ID
services_cache = self.workspace_cache.caches.get("services")
if not services_cache:
    return False
    
return services_cache.get(word) is not None
```

This prevents false positives when the cursor is on non-service text.

## Testing the Update

### Test Case 1: YAML File References

```python
@pytest.mark.asyncio
async def test_find_references_from_yaml(tmp_path):
    """Test finding references when cursor is in .services.yml file."""
    
    # Create a services.yml file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Test\\TestService
""")
    
    # Create PHP file that uses the service
    php_file = tmp_path / "test.php"
    php_file.write_text("""
<?php
$service = \\Drupal::service('test.service');
""")
    
    # Setup server and capability
    server = create_server()
    capability = ServicesReferencesCapability(server)
    
    # Position cursor on 'test.service' in YAML file
    params = ReferenceParams(
        text_document=TextDocumentIdentifier(uri=f'file://{services_file}'),
        position=Position(line=1, character=4),  # On 'test.service'
        context=ReferenceContext(include_declaration=False)
    )
    
    # Should find the reference in PHP file
    locations = await capability.find_references(params)
    
    assert len(locations) == 1
    assert locations[0].uri == f'file://{php_file}'
```

### Test Case 2: Invalid Cursor Position

```python
@pytest.mark.asyncio  
async def test_yaml_references_invalid_position(tmp_path):
    """Test that invalid positions in YAML don't trigger references."""
    
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Test\\TestService
""")
    
    server = create_server()
    capability = ServicesReferencesCapability(server)
    
    # Position cursor on 'class:' (not a service ID)
    params = ReferenceParams(
        text_document=TextDocumentIdentifier(uri=f'file://{services_file}'),
        position=Position(line=2, character=6),  # On 'class:'
        context=ReferenceContext(include_declaration=False)
    )
    
    # Should return empty list
    locations = await capability.find_references(params)
    assert locations == []
```

## Edge Cases Handled

### 1. Nested YAML Structure

```yaml
services:
  parent:
    class: Drupal\\Test\\ParentService
  parent.child:  # ✅ This works
    class: Drupal\\Test\\ChildService
```

The word extraction correctly identifies `parent.child` as a valid service ID.

### 2. Comments and Formatting

```yaml
services:
  # This is a comment
  test.service:  # ✅ Cursor here works
    class: Drupal\\Test\\TestService
```

Comments don't interfere with service ID detection.

### 3. Invalid Service IDs

```yaml
services:
  invalid.service.id:  # If this service doesn't exist in cache
    class: SomeClass     # No references found
```

The validation step prevents searching for non-existent services.

## Performance Considerations

### Cache Validation

The YAML handling includes a cache lookup to validate service existence:

```python
return services_cache.get(word) is not None
```

This is an O(1) dictionary lookup, so it doesn't impact performance.

### File Scanning Unchanged

The actual reference searching (`_search_files_for_service`) remains unchanged and continues to work efficiently across PHP files.

## Integration with Existing Features

### Consistent with Other Capabilities

This update maintains consistency with other service capabilities:

- **Completion**: Works in PHP files only
- **Hover**: Works in PHP files only  
- **Definition**: Works in both PHP and YAML files
- **References**: Now works in both PHP and YAML files ← **Updated**

### LSP Feature Completeness

With this update, the service references feature now supports the complete LSP workflow:

1. **Define service** in `.services.yml`
2. **Find all usages** from the definition (YAML → PHP)
3. **Go to definition** from usage (PHP → YAML)
4. **Find references** from either location

## Summary

This update extends `ServicesReferencesCapability` to handle YAML files by:

1. **Detecting file type**: Check for `.services.yml` extension
2. **Extracting service IDs**: Use word-at-position for YAML content
3. **Validating services**: Ensure the ID exists in the services cache
4. **Reusing search logic**: Leverage existing PHP file scanning

The change is minimal but enables a complete "Find All References" experience across both definition and usage sites in Drupal projects.

## References

- LSP Specification: `textDocument/references`
- Related: `docs/APPENDIX-15-IMPLEMENTING_SERVICE_REFERENCES.md`
- Service Definition: `docs/APPENDIX-07-SERVICE_CLASS_DEFINITION_GUIDE.md`