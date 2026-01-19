#!/usr/bin/env python3
"""
Test script to implement and test the PhpactorLspClient from IMPLEMENTATION-014.
Starts its own LSP server and queries variable types.
"""

import asyncio
import json
import sys
from pathlib import Path


class PhpactorLspClient:
    """LSP client for connecting to a running Phpactor LSP server."""

    def __init__(self, server_command: list[str] | None = None):
        self.server_command = server_command or ["phpactor", "language-server"]
        self._server_process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}

    async def start(self) -> None:
        """Start the Phpactor LSP server process."""
        if self._server_process is not None:
            return  # Already started

        print("🚀 Starting Phpactor LSP server...")
        self._server_process = await asyncio.create_subprocess_exec(
            *self.server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Start message handling task
        asyncio.create_task(self._handle_messages())

        # Initialize LSP handshake
        await self._initialize()
        print("✅ LSP server initialized")

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
                "text": content,
            }
        }

        await self._send_notification("textDocument/didOpen", params)

    async def _send_notification(self, method: str, params: object) -> None:
        """Send LSP notification (no response expected)."""
        if not self._server_process or not self._server_process.stdin:
            return

        notification = {"jsonrpc": "2.0", "method": method, "params": params}

        # Send notification
        notification_json = json.dumps(notification) + "\n"
        headers = f"Content-Length: {len(notification_json)}\r\n\r\n"
        message = headers + notification_json

        self._server_process.stdin.write(message.encode())
        await self._server_process.stdin.drain()

    async def query_type(self, uri: str, line: int, character: int) -> str | None:
        """Query type information at position using LSP hover request."""
        if not self._server_process:
            return None

        print(f"🔍 Querying type at {uri}:{line + 1}:{character + 1}")

        # Use dict for JSON serialization
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        }

        try:
            response = await self._send_request("textDocument/hover", params)
            if response and isinstance(response, dict) and "contents" in response:
                # Extract type from hover content
                return self._extract_type_from_hover(response["contents"])
        except Exception as e:
            print(f"❌ Error querying type: {e}")
            return None

        return None

    async def _initialize(self) -> None:
        """Perform LSP initialize handshake."""
        # Use dict for JSON serialization
        params = {
            "processId": None,
            "rootUri": "file:///home/yuri/ssd2/project-files/Kalamuna/projects/mtcno/mtcno",  # Project root
            "capabilities": {},
        }

        await self._send_request("initialize", params)

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
            "params": params,
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
            print("⏰ Request timed out")
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

                    body = buffer[body_start : body_start + content_length]
                    buffer = buffer[body_start + content_length :]

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
                    future.set_exception(
                        Exception(message["error"].get("message", "LSP error"))
                    )
                else:
                    future.set_result(message.get("result"))

    def _extract_type_from_hover(self, contents) -> str | None:
        """Extract type information from LSP hover response."""
        print(
            f"📄 Raw hover contents: {contents}"
        )  # Handle the structured response format from Phpactor

        if isinstance(contents, dict):
            if contents.get("kind") == "markdown":
                value = contents.get("value", "")
            else:
                value = str(contents)
        elif isinstance(contents, str):
            value = contents
        elif isinstance(contents, list) and contents:
            # Handle list format
            first_item = contents[0]
            if isinstance(first_item, dict) and first_item.get("kind") == "markdown":
                value = first_item.get("value", "")
            else:
                value = str(first_item)
        else:
            value = str(contents)

        # Skip generic language constructs that aren't types
        skip_values = ["assignment", "expression", "statement", "declaration"]
        if value.strip().lower() in skip_values:
            return None

        # Look for variable type patterns in the markdown content
        lines = value.split("\n")
        for line in lines:
            line = line.strip()

            # Pattern 1: variable container: `Ⓘ ContainerInterface`
            if "variable" in line and "`" in line:
                # Extract the type from backticks
                parts = line.split("`")
                if len(parts) >= 3:
                    type_part = parts[1]
                    # Remove the icon prefix if present
                    if type_part.startswith("Ⓘ "):
                        return type_part[2:].strip()
                    return type_part.strip()

            # Pattern 2: **Type**: description format
            if line.startswith("**") and "**" in line:
                type_part = line.split("**")[1]
                if ":" in type_part:
                    return type_part.split(":", 1)[1].strip()

        # Return None if we can't parse it specifically
        return None

    def is_available(self) -> bool:
        """Check if LSP server is running."""
        return (
            self._server_process is not None and self._server_process.returncode is None
        )


async def test_lsp_client():
    """Test the LSP client with the specified file."""
    file_path = "/home/yuri/ssd2/project-files/Kalamuna/projects/mtcno/mtcno/web/modules/common/ocr_api/modules/ocr_api_substitute_service/src/Form/SettingsForm.php"

    if not Path(file_path).exists():
        print(f"❌ File not found: {file_path}")
        return

    client = PhpactorLspClient()

    try:
        await client.start()

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        # Open the document in LSP server
        uri = f"file://{file_path}"
        await client.open_document(uri, file_content)
        print("📄 Document opened in LSP server")

        # Query type at line 109, character position of $container
        line = 108  # 0-indexed (line 109 in 1-indexed)
        character = 6  # Position of '$' in '$container'

        var_type = await client.query_type(uri, line, character)

        if var_type:
            print(f"✅ Variable type: {var_type}")

            # Check if it's a ContainerInterface
            if "ContainerInterface" in var_type:
                print(
                    "🎯 SUCCESS: Variable is correctly identified as ContainerInterface!"
                )
                print("IMPLEMENTATION-014 approach works!")
            else:
                print(f"⚠️ Type found but not ContainerInterface: {var_type}")
        else:
            print("❌ No type information returned")

            # Try a few different positions
            print("🔄 Trying different positions...")
            for char_pos in [
                0,
                6,
                10,
                15,
            ]:  # Start of line, $ position, after container
                try:
                    alt_type = await client.query_type(uri, line, char_pos)
                    print(f"  Position {char_pos}: {alt_type or 'None'}")
                except Exception as e:
                    print(f"  Position {char_pos}: Error - {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.stop()
        print("🛑 LSP server stopped")


if __name__ == "__main__":
    asyncio.run(test_lsp_client())
