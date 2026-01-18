# Implementing Service References (Find All Usages)

## Overview

This guide implements the `textDocument/references` LSP feature for Drupal services, allowing users to find all places where a specific service is used in the codebase.

**What You'll Build**: A capability that finds all references to a Drupal service across PHP files (like `\Drupal::service('entity_type.manager')`).

## User Experience Flow

```php
// In any PHP file
\Drupal::service('entity_type.manager');
//                  ↑ Ctrl+Shift+F12 (Find References)

// Shows all locations:
├── src/Controller/MyController.php:15
├── src/Form/MyForm.php:22
├── modules/custom/my_module/src/Service/MyService.php:8
└── themes/custom/my_theme/my_theme.theme:12
```

## Architecture

### Add ReferencesCapability

```python
# drupalls/lsp/capabilities/capabilities.py

class ReferencesCapability(Capability):
    """Base class for references capabilities."""
    
    @abstractmethod
    async def can_handle(self, params: ReferenceParams) -> bool:
        pass
    
    @abstractmethod
    async def find_references(self, params: ReferenceParams) -> list[Location]:
        pass
```

### Service References Implementation

```python
# drupalls/lsp/capabilities/services_capabilities.py

from lsprotocol.types import ReferenceParams, TEXT_DOCUMENT_REFERENCES

class ServicesReferencesCapability(ReferencesCapability):
    """Find all references to Drupal services."""
    
    @property
    def name(self) -> str:
        return "services_references"
    
    @property
    def description(self) -> str:
        return "Find all usages of a Drupal service"
    
    async def can_handle(self, params: ReferenceParams) -> bool:
        """Check if cursor is on a service identifier."""
        if not self.workspace_cache:
            return False
        
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        return bool(SERVICE_PATTERN.search(line))
    
    async def find_references(self, params: ReferenceParams) -> list[Location]:
        """Find all references to the service under cursor."""
        if not self.workspace_cache:
            return []
        
        # Get service ID under cursor
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r'[A-Za-z_][A-Za-z0-9_.]*$'),
            re_end_word=re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*')
        )
        
        if not word:
            return []
        
        # Get services cache to verify this is a valid service
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache or not services_cache.get(word):
            return []
        
        # Search all PHP files for service usage
        locations = []
        await self._search_files_for_service(word, locations)
        
        return locations
    
    async def _search_files_for_service(self, service_id: str, locations: list[Location]):
        """Search all PHP files for usages of the service."""
        # Search patterns for service usage
        patterns = [
            rf'\b{Drupal::service}\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)',
            rf'\b{getContainer\(\)->get}\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)',
        ]
        
        # Get all PHP files in workspace
        php_files = []
        for root, dirs, files in os.walk(self.workspace_cache.workspace_root):
            for file in files:
                if file.endswith('.php'):
                    php_files.append(Path(root) / file)
        
        for php_file in php_files:
            await self._search_file_for_service(php_file, service_id, patterns, locations)
    
    async def _search_file_for_service(
        self, 
        file_path: Path, 
        service_id: str, 
        patterns: list[str], 
        locations: list[Location]
    ):
        """Search a single file for service references."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.splitlines()
            
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    # Get line number
                    line_num = content[:match.start()].count('\n')
                    
                    # Get column position of service ID within the line
                    line_start = content.rfind('\n', 0, match.start()) + 1
                    col_start = match.start() - line_start
                    
                    # Find the actual service ID within the match
                    service_match = re.search(rf'[\'"]({re.escape(service_id)})[\'"]', match.group())
                    if service_match:
                        service_col = col_start + service_match.start(1)
                        
                        locations.append(Location(
                            uri=file_path.as_uri(),
                            range=Range(
                                start=Position(line=line_num, character=service_col),
                                end=Position(line=line_num, character=service_col + len(service_id))
                            )
                        ))
        
        except Exception as e:
            # Log but continue with other files
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error searching {file_path}: {e}"
                    )
                )

# Register in CapabilityManager
capabilities = {
    "services_completion": ServicesCompletionCapability(server),
    "services_hover": ServicesHoverCapability(server),
    "services_definition": ServicesDefinitionCapability(server),
    "services_yaml_definition": ServicesYamlDefinitionCapability(server),
    "services_references": ServicesReferencesCapability(server),  # ADD THIS
}
```

### Integration with Server

```python
# drupalls/lsp/server.py

@server.feature(TEXT_DOCUMENT_REFERENCES)
async def references(ls: DrupalLanguageServer, params: ReferenceParams):
    if ls.capability_manager:
        return await ls.capability_manager.handle_references(params)
    return None

# In CapabilityManager
async def handle_references(self, params: ReferenceParams) -> list[Location] | None:
    """Handle references requests by delegating to capable handlers."""
    for capability in self.get_capabilities_by_type(ReferencesCapability):
        if await capability.can_handle(params):
            result = await capability.find_references(params)
            if result:
                return result
    return None
```

## Testing

```python
# tests/test_services_references.py

@pytest.mark.asyncio
async def test_find_service_references(tmp_path):
    """Test finding all references to a service."""
    # Setup test files
    php_file1 = tmp_path / "file1.php"
    php_file1.write_text("""
<?php
$service = \Drupal::service('entity_type.manager');
$other = \Drupal::service('different.service');
""")
    
    php_file2 = tmp_path / "file2.php"  
    php_file2.write_text("""
<?php
$manager = \Drupal::getContainer()->get('entity_type.manager');
""")
    
    # Create server and initialize
    server = create_server()
    # ... setup workspace cache ...
    
    # Create capability
    capability = ServicesReferencesCapability(server)
    
    # Mock params pointing to 'entity_type.manager' in file1.php
    params = ReferenceParams(
        text_document=TextDocumentIdentifier(uri=f'file://{php_file1}'),
        position=Position(line=1, character=25),  # On 'entity_type.manager'
        context=ReferenceContext(include_declaration=False)
    )
    
    # Find references
    locations = await capability.find_references(params)
    
    # Should find 2 references
    assert len(locations) == 2
    
    # Check URIs
    uris = {loc.uri for loc in locations}
    assert f'file://{php_file1}' in uris
    assert f'file://{php_file2}' in uris
```

## Performance Considerations

### File Scanning Optimization

For large projects, implement parallel scanning:

```python
async def _search_files_for_service(self, service_id: str, locations: list[Location]):
    """Search all PHP files in parallel."""
    php_files = []
    for root, dirs, files in os.walk(self.workspace_cache.workspace_root):
        for file in files:
            if file.endswith('.php'):
                php_files.append(Path(root) / file)
    
    # Process in batches to avoid overwhelming the system
    batch_size = 10
    for i in range(0, len(php_files), batch_size):
        batch = php_files[i:i + batch_size]
        await asyncio.gather(*[
            self._search_file_for_service(file_path, service_id, patterns, locations)
            for file_path in batch
        ])
```

### Regex Optimization

Pre-compile patterns and use more specific matching:

```python
# Pre-compile patterns in __init__
self._service_patterns = [
    re.compile(rf'\b{Drupal::service}\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)'),
    re.compile(rf'\b{getContainer\(\)->get}\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)'),
]

# Use in search
for pattern in self._service_patterns:
    for match in pattern.finditer(content):
        # Process match...
```

## Edge Cases

### 1. Dynamic Service Names

```php
// These are hard to detect statically
$service_id = 'entity_type.manager';
$service = \Drupal::service($service_id); // Not detectable

// But this is detectable
$service = \Drupal::service('entity_type.manager');
```

**Handling**: Focus on literal strings. Dynamic service names require more advanced analysis.

### 2. Service Aliases

```yaml
# services.yml
services:
  my_alias:
    alias: entity_type.manager
```

**Handling**: When finding references to 'my_alias', also find references to 'entity_type.manager' if desired.

### 3. Context Awareness

```php
// Should find
$service = \Drupal::service('entity_type.manager');

// Should NOT find (different service)
$other = \Drupal::service('other.service');
```

**Handling**: Use specific regex patterns that match the exact service ID.

## Integration with Existing Features

### Combine with Hover

```python
# In hover capability, add "Find References" link
content = f"**Service:** `{word}`\n\n"
content += f"**Class:** {service_def.class_name}\n\n"
content += f"[Find References](command:drupalls.findReferences?{json.dumps(params)})"
```

### Combine with Completion

```python
# In completion, show usage count
usage_count = await self._count_service_usages(service_id)
item = CompletionItem(
    label=f"{service_id} ({usage_count} usages)",
    # ...
)
```

## Summary

This implementation adds the missing `textDocument/references` feature for Drupal services, completing the core LSP features:

- ✅ **Completion**: Autocomplete service names
- ✅ **Hover**: Show service information  
- ✅ **Definition**: Go to service definition
- ✅ **References**: Find all service usages ← **NEW**

The implementation follows the existing capability plugin architecture and integrates seamlessly with the ServicesCache for efficient searching across the codebase.</content>
<parameter name="filePath">docs/APPENDIX-15-IMPLEMENTING_SERVICE_REFERENCES.md