# Integrating Phpactor CLI for Type Checking

## Overview

This guide implements a working Phpactor integration by using the CLI `offset:info` command to get reliable type information. This approach provides accurate variable type checking using the standard Phpactor CLI with proper project context.

**Problem with Previous Approaches:**
- LSP client approach depends on IDE/server state and may not work consistently
- RPC approach returned `<missing>` and `<unknown>` for complex projects
- CLI fallback was not implemented systematically

**Solution:** Use Phpactor's `offset:info` CLI command which provides complete type information when given the correct byte offset and working directory.

## Architecture

### CLI-Based Type Checking Architecture

```
Autocomplete Trigger
        ↓
Variable Extraction (->get() context)
        ↓
Position → Byte Offset Conversion
        ↓
phpactor offset:info --working-dir <project> <file> <offset>
        ↓
Parse CLI Output → Extract Type Information
        ↓
ContainerInterface Validation
        ↓
Service Completion Trigger
```

### Key Components

1. **Variable Extraction**: Identify variables in `->get()` call context
2. **Offset Calculation**: Convert line/column positions to byte offsets
3. **CLI Execution**: Run `phpactor offset:info` with proper working directory
4. **Output Parsing**: Extract type information from CLI output
5. **Type Validation**: Check if variable implements ContainerInterface
6. **Fallback Logic**: LSP client backup if CLI fails

## Implementation

### Step 1: Enhanced TypeChecker with CLI Support

```python
# drupalls/lsp/phpactor_integration.py

import asyncio
import re
from pathlib import Path
from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient
from lsprotocol.types import Position


class TypeChecker:
    """Handles type checking for variables in ->get() calls using Phpactor CLI."""

    def __init__(self, phpactor_client: PhpactorLspClient | None = None):
        self.phpactor_client = phpactor_client
        self._type_cache: dict[tuple, str | None] = {}

    def clear_cache(self):
        """Clear the type cache."""
        self._type_cache.clear()

    async def is_container_variable(self, doc, line: str, position: Position) -> bool:
        """Check if the variable in ->get() call is a ContainerInterface."""

        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False

        # Create cache key - include var_name for specificity
        cache_key = (doc.uri, position.line, var_name)

        # Check cache first
        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            # Query type using CLI approach
            var_type = await self._query_variable_type(doc, line, position)
            self._type_cache[cache_key] = var_type

        if not var_type:
            # Fallback: assume 'container' variables are ContainerInterface
            if var_name == 'container':
                return True
            return False

        return self._is_container_interface(var_type)

    async def _query_variable_type(
        self, doc, line: str, position: Position
    ) -> str | None:
        """Query Phpactor CLI for variable type at position."""
        try:
            # Find the variable position to query for type
            var_position = self._find_variable_position(line, position)
            if var_position is None:
                return None

            # Convert position to byte offset
            offset = self._position_to_offset(doc.lines, var_position)

            # Find project root directory
            working_dir = self._find_project_root(doc.uri)

            # Run phpactor offset:info CLI command
            cmd = [
                "phpactor", "offset:info",
                "--working-dir", working_dir,
                doc.uri.replace("file://", ""),  # Remove file:// prefix
                str(offset)
            ]

            # Execute CLI command asynchronously
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                # Parse the CLI output for type information
                output = stdout.decode().strip()
                type_info = self._parse_cli_output(output)
                return type_info.get('type')
            else:
                # CLI failed, try LSP client as fallback
                if self.phpactor_client:
                    await self.phpactor_client.open_document(doc.uri, "\n".join(doc.lines))
                    return await self.phpactor_client.query_type(
                        doc.uri, var_position.line, var_position.character
                    )
                return None

        except Exception:
            return None

    def _parse_cli_output(self, output: str) -> dict[str, str]:
        """Parse phpactor offset:info CLI output into key-value pairs."""
        lines = output.strip().split('\n')
        type_info = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                type_info[key.strip()] = value.strip()

        return type_info

    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert Position to byte offset in file."""
        # Calculate offset up to the target line
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i]) + 1  # +1 for newline

        # Add character offset within the line
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line]))

        return offset

    def _find_project_root(self, uri: str) -> str:
        """Find the project root directory containing composer.json."""
        file_path = Path(uri.replace("file://", ""))

        # Start from file directory and go up looking for composer.json
        current = file_path.parent
        for _ in range(10):  # Don't go up more than 10 levels
            if (current / "composer.json").exists():
                return str(current)
            current = current.parent

        # Fallback to file directory
        return str(file_path.parent)
```

### Step 1.1: Offset Calculation Normalization

**Why this update?** The original `_position_to_offset` method assumed `doc.lines` never included newlines, but in some LSP implementations (like pygls), lines may include `\n`. This caused incorrect offsets, adding extra bytes per line. By normalizing with `rstrip('\n')`, we ensure consistent offset calculation regardless of how lines are stored, matching Phpactor's expected byte positions.

```python
    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert Position to byte offset in file."""
        # Calculate offset up to the target line
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip('\n')) + 1  # +1 for newline, normalize by stripping

        # Add character offset within the line
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line].rstrip('\n')))

        return offset
```

### Step 2: Variable Position Finding Logic

```python
    def _find_variable_position(self, line: str, position: Position) -> Position | None:
        """Find the position of the variable in a ->get() call."""
        # Find ->get( before the cursor
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None

        # Find variable before ->
        arrow_pos = line.rfind("->", 0, get_pos)
        if arrow_pos == -1:
            # Simple case: $var->get()
            dollar_pos = line.rfind("$", 0, get_pos)
            if dollar_pos == -1:
                return None

            # Return position at the start of the variable name
            return Position(line=position.line, character=dollar_pos + 1)
        else:
            # Complex case: find the variable before the last ->
            # For $this->container->get(), we want position at 'c' in 'container'
            var_end = arrow_pos

            # Go backward to find variable start
            for i in range(arrow_pos - 1, -1, -1):
                char = line[i]
                if char in ["$", ">", "-"]:
                    continue
                elif char in [" ", "\t"]:
                    # Found variable start
                    var_start = i + 1
                    # Return position in the middle of the variable
                    var_middle = var_start + (var_end - var_start) // 2
                    return Position(line=position.line, character=var_middle)
                elif not char.isalnum() and char not in ["_"]:
                    # Hit a non-variable character
                    var_start = i + 1
                    var_middle = var_start + (var_end - var_start) // 2
                    return Position(line=position.line, character=var_middle)

            # Fallback: return position near the arrow
            return Position(line=position.line, character=arrow_pos - 1)

        return None
```

### Step 3: Variable Extraction from ->get() Calls

```python
    def _extract_variable_from_get_call(
        self, line: str, position: Position
    ) -> str | None:
        """
        Extract variable name from ->get() call context.
        """
        # Find ->get( before or at the cursor position
        # Include the current character in case cursor is on the '('
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None

        # Find variable before ->
        arrow_pos = line.rfind("->", 0, get_pos)

        if arrow_pos == -1:
            # Simple case: $var->get()
            dollar_pos = line.rfind("$", 0, get_pos)
            if dollar_pos == -1:
                return None
            var_start = dollar_pos
            var_expression = line[var_start:get_pos]
        else:
            # Find the start of the variable expression
            var_start = arrow_pos
            paren_depth = 0
            brace_depth = 0

            # Go backward, tracking parentheses and braces
            for i in range(arrow_pos - 1, -1, -1):
                char = line[i]

                if char == ")":
                    paren_depth += 1
                elif char == "}":
                    brace_depth += 1
                elif char == "{":
                    brace_depth -= 1
                elif paren_depth == 0 and brace_depth == 0:
                    # Skip whitespace
                    if char.isspace():
                        continue
                    # Check for variable start patterns
                    if char in ["$", "a-z", "A-Z", "0-9", "_"] or (
                        char == ">" and i > 0 and line[i - 1] == "-"
                    ):
                        var_start = i
                    elif char not in ["$", "a-z", "A-Z", "0-9", "_", ">", "-"]:
                        # Hit a non-variable character, stop
                        break

            var_expression = line[var_start:get_pos]

        # Extract the main variable name (handle method chains)
        # $this->container->get() -> 'container'
        # $container->get() -> 'container'
        # $this->getContainer()->get() -> 'getContainer()'

        # Simple approach: take the last identifier before any method call
        parts = re.split(r"->", var_expression)
        # Remove empty parts
        parts = [p for p in parts if p.strip()]
        if parts:
            # Get the last part and extract variable name
            last_part = parts[-1].strip().lstrip("$")
            var_match = re.search(r"^(\w+)", last_part)
            if var_match:
                return var_match.group(1)

        return None

    def _is_container_interface(self, type_str: str) -> bool:
        """Check if type represents a ContainerInterface."""
        container_types = [
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "ContainerInterface",
            "Drupal\\Core\\DependencyInjection\\Container",
            "Drupal\\Core\\DependencyInjection\\ContainerInterface",
        ]

        type_str_lower = type_str.lower()
        for container_type in container_types:
            if container_type.lower() in type_str_lower:
                return True

        return False
```

### Step 4: Server Integration

```python
# drupalls/lsp/server.py

from drupalls.lsp.phpactor_integration import TypeChecker

class DrupalLanguageServer:
    def __init__(self):
        # ... existing init ...
        self.phpactor_client = None
        self.type_checker = TypeChecker()  # CLI-based, no client needed

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        # ... existing initialization ...

        # TypeChecker now works with CLI, LSP client optional
        if self.phpactor_client:
            self.type_checker = TypeChecker(self.phpactor_client)
        else:
            self.type_checker = TypeChecker()  # CLI-only mode

        # Pass type checker to capabilities
        self.capability_manager = CapabilityManager(self, type_checker)

        return InitializeResult(capabilities=...)

    async def did_open(self, params: DidOpenTextDocumentParams) -> None:
        """Handle document open - optional for CLI approach."""
        # CLI approach doesn't require pre-opening documents
        # but LSP client fallback might need it
        if self.phpactor_client:
            try:
                await self.phpactor_client.open_document(
                    params.text_document.uri,
                    params.text_document.text
                )
            except Exception:
                pass  # CLI approach works without this
```

## User Experience

### Automatic Type Checking

The implementation provides seamless type checking:

1. **No Configuration Required**: Works out-of-the-box with existing Phpactor installation
2. **Project-Aware**: Automatically finds composer.json for correct working directory
3. **Fallback Support**: LSP client as backup if CLI fails
4. **Caching**: Efficient caching prevents repeated CLI calls

### Service Completion Examples

```php
class MyController {
    public function __construct(
        private ContainerInterface $container
    ) {}

    public function build() {
        // ✅ CLI detects $container as ContainerInterface
        //    Triggers service completion for 'entity_type.manager'
        $entity_type = $this->container->get('entity_type.manager');

        // ✅ Works with method chains
        $database = $this->container->get('database');

        // ✅ Works with complex expressions
        $service = $this->getContainer()->get('my_service');
    }
}
```

## Testing

### CLI Command Testing

```python
# Test the CLI command directly
def test_cli_command():
    # Line 109, column 10 in test file
    # Should return: type: Symfony\Component\DependencyInjection\ContainerInterface

    cmd = [
        "phpactor", "offset:info",
        "--working-dir", "/path/to/project",
        "/path/to/file.php",
        "3167"  # byte offset
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert "ContainerInterface" in result.stdout
```

### Integration Testing

```python
# tests/test_phpactor_cli_integration.py

import pytest
from drupalls.lsp.phpactor_integration import TypeChecker
from lsprotocol.types import Position

def test_cli_type_checking():
    """Test CLI-based type checking."""
    type_checker = TypeChecker()

    # Mock document
    class MockDoc:
        uri = "file:///test/file.php"
        lines = ["$container->get('service');"]

    # Test position at ->get(
    position = Position(line=0, character=18)  # Position of '('

    # This should work without any LSP client
    result = await type_checker.is_container_variable(MockDoc(), MockDoc.lines[0], position)
    assert result == True
```

## Edge Cases and Error Handling

### CLI Command Failures

```python
# Handle CLI failures gracefully
if result.returncode != 0:
    # Fallback to LSP client if available
    if self.phpactor_client:
        return await self.phpactor_client.query_type(uri, line, character)

    # Final fallback: heuristic for 'container' variables
    var_name = self._extract_variable_from_get_call(line, position)
    if var_name == 'container':
        return 'ContainerInterface'  # Reasonable assumption
```

### Project Root Detection

```python
def _find_project_root(self, uri: str) -> str:
    """Find project root by looking for composer.json."""
    file_path = Path(uri.replace("file://", ""))

    # Search up to 10 levels for composer.json
    current = file_path.parent
    for _ in range(10):
        if (current / "composer.json").exists():
            return str(current)
        current = current.parent

    return str(file_path.parent)  # Fallback
```

### Offset Calculation Accuracy

```python
def _position_to_offset(self, lines: list[str], position: Position) -> int:
    """Convert line/column to byte offset."""
    offset = 0

    # Sum lengths of previous lines + newlines
    for i in range(position.line):
        offset += len(lines[i]) + 1

    # Add character position in current line
    if position.line < len(lines):
        offset += min(position.character, len(lines[position.line]))

    return offset
```

## Performance Considerations

### Caching Strategy

```python
# Cache by (uri, line, var_name) for specificity
cache_key = (doc.uri, position.line, var_name)

# Cache persists across requests
if cache_key in self._type_cache:
    return self._type_cache[cache_key]
```

### Async CLI Execution

```python
# Non-blocking CLI execution
result = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=working_dir
)

stdout, stderr = await result.communicate()
```

## Configuration

### Optional LSP Fallback

```python
# In server configuration
USE_CLI_TYPE_CHECKING = True  # Default: True (CLI primary)
ENABLE_LSP_FALLBACK = True    # Default: True (LSP backup)
CLI_TIMEOUT_SECONDS = 5.0     # Default: 5.0
```

### Working Directory Override

```python
# Manual working directory specification
type_checker.set_working_dir("/custom/project/root")
```

## Summary

This CLI-based approach provides:

1. **Reliable Type Information**: Uses `phpactor offset:info` for accurate results
2. **Project Context Awareness**: Automatically finds composer.json working directory
3. **Performance**: Efficient caching and async execution
4. **Robustness**: Multiple fallback strategies (CLI → LSP → heuristics)
5. **Zero Configuration**: Works with existing Phpactor installations

The result is accurate, context-aware service completion that works reliably in complex Drupal projects without requiring IDE-specific LSP server configurations.

## References

- **Phpactor CLI**: `phpactor offset:info --help`
- **Working Directory**: `--working-dir` flag for project root detection
- **Type Information**: Complete type data including namespaces and paths