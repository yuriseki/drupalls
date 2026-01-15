"""
Main entry point for the Drupal Language Server.

This file is executed when running: python -m drupalls

The server communicates with editors via stdin/stdout using JSON-RPC.
"""
import os

from drupalls.lsp.server import create_server


def main():
    """Start the language server on stdin/stdout."""

    # Check if we're in debug mode
    if os.getenv("DEBUG"):
        print("🔧 DRUPAL Server starting in DEBUG mode")
        print("📡 Waiting for debugger to attach on port 5678...")
        # Enable debugpy if in debug mode
        try:
            import debugpy  # type: ignore
            debugpy.listen(("127.0.0.1", 5678))
            debugpy.wait_for_client()
            print("🎯 Debugger attached! Continuing...")
        except ImportError:
            print("❌ debugpy not available - install with: poetry install --with dev")

    server = create_server()
    
    # Start the server - it will listen on stdin/stdout for LSP messages
    # from the editor client
    server.start_io()

if __name__ == "__main__":
    main()
