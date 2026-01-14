"""
Main entry point for the Drupal Language Server.

This file is executed when running: python -m drupalls

The server communicates with editors via stdin/stdout using JSON-RPC.
"""
from drupalls.lsp.server import create_server

def main():
    """Start the language server on stdin/stdout."""
    server = create_server()
    
    # Start the server - it will listen on stdin/stdout for LSP messages
    # from the editor client
    server.start_io()

if __name__ == "__main__":
    main()
