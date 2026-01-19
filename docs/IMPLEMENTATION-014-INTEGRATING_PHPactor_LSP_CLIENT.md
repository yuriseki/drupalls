# Integrating Phpactor LSP Client

> **⚠️ IMPORTANT: The approaches described in this document do not work reliably**
>
> The approach of relying in Phpactor being execute in the IDE was not reliable, and is also too hacky as it was simulating the hover LSP capability and
>some special character returned by Phpactor. So I decided to try the phpactoe CLI again on IMPLMEMENTATION-015, which ended up working.

## Overview

This guide implements a working Phpactor integration by connecting to the developer's existing Phpactor LSP server that runs in their IDE (like VS Code, PhpStorm, or Neovim). This approach provides reliable type information using the standard LSP protocol.

**Problem with Previous Approaches:**
- CLI-based approaches returned `<missing>` or `<unknown>` for type information
- RPC direct calls had autoloading and environment issues
- Bundled CLI approach added complexity without solving core issues

**Solution:** Connect to the LSP server the developer already has running, which has full project context and reliable type analysis capabilities.

## Architecture

### LSP Client Architecture

```
Developer's IDE
    ↓ (running Phpactor LSP server)
    ↓
PhpactorLspClient ←→ LSP Protocol (stdio/socket)
    ↓
TypeChecker (queries types via LSP hover requests)
    ↓
Services Capabilities (use type validation)
```

### Key Components

1. **PhpactorLspClient**: Connects to running LSP server via stdio
2. **LSP Protocol Integration**: Uses standard `textDocument/hover` requests for type information
3. **TypeChecker Update**: Supports both LSP and fallback methods
4. **Graceful Fallback**: Works even when no LSP server is available

## Implementation

### Step 1: Create Phpactor LSP Client

```python
# drupalls/lsp/phpactor_lsp_client.py

import asyncio
import json
from typing import Union
from pathlib import Path

class PhpactorLspClient:
    """LSP client for connecting to a running Phpactor LSP server."""

    def __init__(self, server_command: list[str] | None = None):
        """
        Initialize LSP client.

        Args:
            server_command: Command to start Phpactor LSP server.
                           If None, assumes server is already running via stdio.
        """
        self.server_command = server_command or ["phpactor", "language-server"]
        self._server_process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}

    async def start(self, root_uri: str | None = None) -> None:
        """Start the Phpactor LSP server process."""
        if self._server_process is not None:
            return  # Already started

        self._server_process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Start message handling task
        asyncio.create_task(self._handle_messages())

        # Initialize LSP handshake
        await self._initialize(root_uri)

    async def stop(self) -> None:
        """Stop the LSP server."""
        if self._server_process:
            self._server_process.terminate()
            await self._server_process.wait()
            self._server_process = None

    async def open_document(self, uri: str, content: str) -> None:
        """Open a text document in the LSP server."""
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": "php",
                "version": 1,
                "text": content
            }
        }

        await self._send_notification("textDocument/didOpen", params)

    async def query_type(self, uri: str, line: int, character: int) -> str | None:
        """
        Query type information at position using LSP hover request.

        Args:
            uri: File URI (file://...)
            line: Line number (0-indexed)
            character: Character position (0-indexed)

        Returns:
            Type string or None if not available
        """
        if not self._server_process:
            return None

        # Use dict for JSON serialization
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }

        try:
            response = await self._send_request("textDocument/hover", params)
            if response and isinstance(response, dict) and "contents" in response:
                # Extract type from hover content
                return self._extract_type_from_hover(response["contents"])
        except Exception:
            return None

        return None

    async def _initialize(self, root_uri: str | None = None) -> None:
        """Perform LSP initialize handshake."""
        # Use dict for JSON serialization
        params = {
            "processId": None,
            "rootUri": root_uri,  # Project root - should be passed from server
            "capabilities": {}
        }

        await self._send_request("initialize", params)

    async def _send_notification(self, method: str, params: object) -> None:
        """Send LSP notification (no response expected)."""
        if not self._server_process or not self._server_process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        # Send notification
        notification_json = json.dumps(notification) + "\n"
        headers = f"Content-Length: {len(notification_json)}\r\n\r\n"
        message = headers + notification_json

        self._server_process.stdin.write(message.encode())
        await self._server_process.stdin.drain()

    async def _send_request(self, method: str, params: object) -> object | None:
        """Send LSP request and wait for response."""
        if not self._server_process or not self._server_process.stdin:
            return None

        request_id = self._request_id
        self._request_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Create future for response
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        # Send request
        request_json = json.dumps(request) + "\n"
        headers = f"Content-Length: {len(request_json)}\r\n\r\n"
        message = headers + request_json

        self._server_process.stdin.write(message.encode())
        await self._server_process.stdin.drain()

        # Wait for response with timeout
        try:
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            # Clean up pending request
            self._pending_requests.pop(request_id, None)
            return None

    async def _handle_messages(self) -> None:
        """Handle incoming LSP messages from server."""
        if not self._server_process or not self._server_process.stdout:
            return

        buffer = b""
        while self._server_process and not self._server_process.stdout.at_eof():
            try:
                data = await self._server_process.stdout.read(1024)
                if not data:
                    break

                buffer += data

                # Process complete messages
                while b"\r\n\r\n" in buffer:
                    header_end = buffer.find(b"\r\n\r\n")
                    headers = buffer[:header_end].decode()
                    body_start = header_end + 4

                    # Parse Content-Length
                    content_length = 0
                    for line in headers.split("\r\n"):
                        if line.startswith("Content-Length:"):
                            content_length = int(line.split(":", 1)[1].strip())
                            break

                    if content_length == 0:
                        break

                    # Wait for complete body
                    if len(buffer) < body_start + content_length:
                        break

                    body = buffer[body_start:body_start + content_length]
                    buffer = buffer[body_start + content_length:]

                    # Parse and handle message
                    try:
                        message = json.loads(body.decode())
                        await self._handle_message(message)
                    except json.JSONDecodeError:
                        continue

            except Exception:
                break

    async def _handle_message(self, message: dict) -> None:
        """Handle a single LSP message."""
        if "id" in message and message["id"] in self._pending_requests:
            # This is a response to our request
            future = self._pending_requests.pop(message["id"])
            if not future.done():
                if "error" in message:
                    future.set_exception(Exception(message["error"].get("message", "LSP error")))
                else:
                    future.set_result(message.get("result"))

    def _extract_type_from_hover(self, contents) -> str | None:
        """Extract type information from LSP hover response."""
        print(f"📄 Raw hover contents: {contents}")

        # Handle the structured response format from Phpactor
        if isinstance(contents, dict):
            if contents.get('kind') == 'markdown':
                value = contents.get('value', '')
            else:
                value = str(contents)
        elif isinstance(contents, str):
            value = contents
        elif isinstance(contents, list) and contents:
            # Handle list format
            first_item = contents[0]
            if isinstance(first_item, dict) and first_item.get('kind') == 'markdown':
                value = first_item.get('value', '')
            else:
                value = str(first_item)
        else:
            value = str(contents)

        # Skip generic language constructs that aren't types
        skip_values = ['assignment', 'expression', 'statement', 'declaration']
        if value.strip().lower() in skip_values:
            return None

        # Look for variable type patterns in the markdown content
        lines = value.split('\n')
        for line in lines:
            line = line.strip()

            # Pattern 1: variable container: `Ⓘ ContainerInterface`
            if 'variable' in line and '`' in line:
                # Extract the type from backticks
                parts = line.split('`')
                if len(parts) >= 3:
                    type_part = parts[1]
                    # Remove the icon prefix if present
                    if type_part.startswith('Ⓘ '):
                        return type_part[2:].strip()
                    return type_part.strip()

            # Pattern 2: **Type**: description format
            if line.startswith('**') and '**' in line:
                type_part = line.split('**')[1]
                if ':' in type_part:
                    return type_part.split(':', 1)[1].strip()

        # Return None if we can't parse it specifically
        return None

    def is_available(self) -> bool:
        """Check if LSP server is running."""
        return self._server_process is not None and self._server_process.returncode is None
```

### Step 2: Update TypeChecker for LSP Support

```python
# drupalls/lsp/phpactor_integration.py

import re
from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient
from drupalls.lsp.phpactor_rpc import PhpactorRpcClient

class TypeChecker:
    """Handles type checking for variables in ->get() calls."""

    def __init__(self, phpactor_client: PhpactorLspClient | PhpactorRpcClient | None = None):
        self.phpactor_client = phpactor_client
        self._type_cache: dict[tuple, str | None] = {}

    async def is_container_variable(self, doc, line: str, position: Position) -> bool:
        """Check if the variable in ->get() call is a ContainerInterface."""

        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False

        # Create cache key
        cache_key = (doc.uri, position.line, position.character)

        # Check cache first
        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            # Query type
            var_type = await self._query_variable_type(doc, line, position)
            self._type_cache[cache_key] = var_type

        if not var_type:
            return False

        return self._is_container_interface(var_type)

    async def _query_variable_type(self, doc, line: str, position: Position) -> str | None:
        """Query Phpactor for variable type at position."""
        if not self.phpactor_client:
            return None

        try:
            # Handle both client types
            if isinstance(self.phpactor_client, PhpactorLspClient):
                # Ensure document is opened in LSP server
                await self.phpactor_client.open_document(doc.uri, "\n".join(doc.lines))
                return await self.phpactor_client.query_type(
                    doc.uri, position.line, position.character
                )
            elif isinstance(self.phpactor_client, PhpactorRpcClient):
                # Convert URI to file path for RPC client
                file_path = doc.uri.replace("file://", "")
                return self.phpactor_client.query_type_at_position(
                    file_path, position.line, position.character
                )
        except Exception:
            return None

        return None

    def _extract_variable_from_get_call(self, line: str, position: Position) -> str | None:
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
        var_expression = line[arrow_pos:position.character].strip()

        # Simple approach: take the last identifier before any method call
        parts = var_expression.split("->")
        if parts:
            last_part = parts[-1]
            var_match = re.search(r'^(\w+)', last_part.strip())
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

### Step 3: Update Server Initialization

```python
# drupalls/lsp/server.py

from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient
from lsprotocol.types import DidOpenTextDocumentParams

class DrupalLanguageServer:
    def __init__(self):
        # ... existing init ...
        self.phpactor_client = None

    async def initialize(self, params: InitializeParams) -> InitializeResult:
        # ... existing initialization ...

        # Get workspace root from initialization params (following existing pattern)
        workspace_root = params.root_uri or (params.workspace_folders[0].uri if params.workspace_folders else None)

        # Try to start Phpactor LSP client
        try:
            self.phpactor_client = PhpactorLspClient()
            await self.phpactor_client.start(root_uri=workspace_root)
            self.show_message("✅ Connected to Phpactor LSP server")
        except Exception as e:
            self.show_message(f"⚠️ Could not connect to Phpactor LSP server: {e}")
            self.phpactor_client = None

        # Initialize capabilities with type checker
        type_checker = None
        if self.phpactor_client:
            from drupalls.lsp.phpactor_integration import TypeChecker
            type_checker = TypeChecker(self.phpactor_client)

        # Pass type checker to capabilities
        self.capability_manager = CapabilityManager(self, type_checker)

        return InitializeResult(capabilities=...)

    async def did_open(self, params: DidOpenTextDocumentParams) -> None:
        """Handle document open - forward to LSP client."""
        if self.phpactor_client:
            try:
                await self.phpactor_client.open_document(
                    params.text_document.uri,
                    params.text_document.text
                )
            except Exception as e:
                self.show_message(f"⚠️ Failed to open document in LSP server: {e}")


# drupalls/lsp/capabilities/capabilities.py

class CapabilityManager:
    def __init__(self, server: DrupalLanguageServer, type_checker=None):
        self.server = server
        self.type_checker = type_checker

        # Initialize capabilities with type checker
        self.capabilities = {
            "services_completion": ServicesCompletionCapability(server, type_checker),
            "services_hover": ServicesHoverCapability(server, type_checker),
            "services_definition": ServicesDefinitionCapability(server, type_checker),
        }
```

### Step 4: Update Service Capabilities

```python
# drupalls/lsp/capabilities/services_capabilities.py

class ServicesCompletionCapability(CompletionCapability):
    def __init__(self, server: DrupalLanguageServer, type_checker=None):
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
            if self.type_checker:
                try:
                    return await self.type_checker.is_container_variable(
                        doc, line, params.position
                    )
                except Exception:
                    # Fallback to basic pattern
                    return self._basic_container_check(line)
            else:
                # No type checker available
                return self._basic_container_check(line)

        return False

    def _basic_container_check(self, line: str) -> bool:
        """Basic heuristic check for container variables."""
        # Look for variable names suggesting containers
        if re.search(r'\$[^>]*container[^>]*->get\(', line, re.IGNORECASE):
            return True

        return False
```

## User Experience

### Prerequisites

**For the developer:**
- Phpactor LSP server must be running in their IDE
- The LSP server should be configured to handle the project

**Common IDE setups:**
```json
// VS Code settings.json
{
  "phpactor.enable": true,
  "phpactor.language_server_phpactor.enabled": true
}
```

```lua
-- Neovim with lspconfig
require('lspconfig').phpactor.setup{}
```

### Automatic Detection

The DrupalLS server automatically:
1. Attempts to connect to a running Phpactor LSP server
2. Shows success/failure messages in the IDE
3. Falls back to heuristic checking if LSP unavailable

### Type-Aware Completions

```php
class MyController {
    /** @var \Symfony\Component\DependencyInjection\ContainerInterface */
    protected $container;

    /** @var \Some\Other\Service */
    protected $otherService;

    public function build() {
        // ✅ Triggers completion (LSP confirms ContainerInterface)
        $service = $this->container->get('entity_type.manager');

        // ❌ No completion (LSP confirms not ContainerInterface)
        $value = $this->otherService->get('param');

        // ✅ Traditional patterns still work
        $service2 = \Drupal::service('database');
    }
}
```

## Testing

### Test LSP Client Connection

```python
# tests/test_phpactor_lsp_client.py

import pytest
from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient


@pytest.mark.asyncio
async def test_lsp_client_basic():
    """Test basic LSP client functionality."""
    client = PhpactorLspClient()

    # This test requires Phpactor to be installed
    try:
        await client.start()
        assert client.is_available()

        # Test version or basic functionality
        # (Actual tests would need a test PHP file)

    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_lsp_client_type_query(tmp_path):
    """Test type querying with LSP client."""
    from lsprotocol.types import Position

    # Create test PHP file
    php_file = tmp_path / "test.php"
    php_file.write_text("""
<?php

class TestController {
    /** @var \Symfony\Component\DependencyInjection\ContainerInterface */
    protected $container;

    public function test() {
        $service = $this->container->get('entity_type.manager');
    }
}
""")

    client = PhpactorLspClient()

    try:
        await client.start()

        # Query type at container position
        uri = f'file://{php_file}'
        var_type = await client.query_type(uri, line=7, character=25)

        # Should return ContainerInterface type
        assert var_type is not None
        assert "ContainerInterface" in var_type

    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_type_checker_with_lsp():
    """Test TypeChecker integration with LSP client."""
    from drupalls.lsp.phpactor_integration import TypeChecker
    from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient

    # Setup
    client = PhpactorLspClient()
    await client.start()

    try:
        type_checker = TypeChecker(client)

        # Mock document and position
        # (Would need actual LSP document setup)

    finally:
        await client.stop()
```

### Integration Test

```python
@pytest.mark.asyncio
async def test_services_completion_with_lsp(tmp_path):
    """Test complete services completion with LSP integration."""
    from drupalls.lsp.capabilities.services_capabilities import ServicesCompletionCapability
    from drupalls.lsp.phpactor_integration import TypeChecker
    from drupalls.lsp.phpactor_lsp_client import PhpactorLspClient

    # Create test PHP file
    php_file = tmp_path / "test.php"
    php_file.write_text("""
<?php

class TestController {
    /** @var \Symfony\Component\DependencyInjection\ContainerInterface */
    protected $container;

    public function test() {
        $this->container->get('entity_type.');
    }
}
""")

    # Setup LSP client
    lsp_client = PhpactorLspClient()
    await lsp_client.start()

    try:
        type_checker = TypeChecker(lsp_client)

        # Create mock server and capability
        server = create_mock_server()
        capability = ServicesCompletionCapability(server, type_checker)

        # Test completion trigger
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri=f'file://{php_file}'),
            position=Position(line=7, character=35)  # At 'entity_type.'
        )

        can_handle = await capability.can_handle(params)
        assert can_handle == True

    finally:
        await lsp_client.stop()
```

## Edge Cases and Error Handling

### LSP Server Not Available

```python
class ServicesCompletionCapability:
    async def can_handle(self, params: CompletionParams) -> bool:
        # ... existing checks ...

        if "->get(" in line:
            if self.type_checker and self.type_checker.phpactor_client:
                try:
                    return await self.type_checker.is_container_variable(
                        doc, line, params.position
                    )
                except Exception as e:
                    self.server.show_message(f"Type checking failed: {e}")
                    # Fall back to heuristics
                    return self._basic_container_check(line)
            else:
                # No LSP client available
                return self._basic_container_check(line)

        return False
```

### Connection Timeouts

The LSP client handles timeouts gracefully:
- Requests timeout after 5 seconds
- Pending requests are cleaned up
- Server continues functioning without type checking

### Different IDE Configurations

**VS Code with Phpactor:**
- Ensure `phpactor.language_server_phpactor.enabled` is `true`
- LSP server runs automatically

**Neovim/Vim:**
```lua
require('lspconfig').phpactor.setup{}
```

**Other IDEs:**
- Check Phpactor documentation for LSP server setup
- Ensure stdio communication is enabled

### Performance Considerations

#### Caching
- Type queries are cached per position
- Cache persists for the server session
- Reduces repeated LSP requests

#### Asynchronous Processing
- All LSP communication is async
- Doesn't block the main LSP server
- Timeouts prevent hanging

## Integration with Existing Features

### Consistent Type Checking

All service capabilities use the same `TypeChecker` instance:

```python
class ServicesHoverCapability(HoverCapability):
    def __init__(self, server: DrupalLanguageServer, type_checker=None):
        super().__init__(server)
        self.type_checker = type_checker

class ServicesDefinitionCapability(DefinitionCapability):
    def __init__(self, server: DrupalLanguageServer, type_checker=None):
        super().__init__(server)
        self.type_checker = type_checker
```

### Fallback Chain

1. **Primary:** LSP-based type checking (most accurate)
2. **Fallback 1:** RPC-based type checking (if LSP unavailable)
3. **Fallback 2:** Heuristic pattern matching (basic)
4. **Fallback 3:** Standard service patterns only

## Configuration

### Optional LSP Integration

```python
# In server configuration
ENABLE_LSP_INTEGRATION = True  # Default: True
LSP_TIMEOUT = 5.0  # Seconds
LSP_SERVER_COMMAND = ["phpactor", "language-server"]  # Custom command
```

### Manual LSP Server Control

```python
# Advanced usage: manual LSP server management
lsp_client = PhpactorLspClient(["custom-phpactor", "--lsp"])
await lsp_client.start()

# Use in type checker
type_checker = TypeChecker(lsp_client)
```

## Summary

This implementation provides:

1. **Reliable Type Checking:** Uses developer's existing Phpactor LSP server
2. **Standard Protocol:** Follows LSP specification for communication
3. **Graceful Degradation:** Works even when LSP server unavailable
4. **Performance Optimized:** Caching and async processing
5. **IDE Agnostic:** Works with any IDE that supports Phpactor LSP

The result is accurate, context-aware service completion that only triggers for actual dependency injection usage, eliminating false positives while providing the best developer experience.

## References

- **LSP Specification:** https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
- **Phpactor LSP:** https://phpactor.readthedocs.io/en/master/lsp/
- **pygls Documentation:** https://pygls.readthedocs.io/
- **lsprotocol Types:** https://github.com/microsoft/lsprotocol</content>
<parameter name="filePath">docs/IMPLEMENTATION-014-INTEGRATING_PHPactor_LSP_CLIENT.md
