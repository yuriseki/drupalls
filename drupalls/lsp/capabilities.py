"""
LSP Capabilities - What features the server can provide to clients.

In LSP, capabilities are announced during initialization so the client knows
what features are supported. Common capabilities include:

1. TEXT SYNCHRONIZATION:
   - text_document/didOpen: Notified when a file is opened
   - text_document/didChange: Notified when file content changes
   - text_document/didSave: Notified when a file is saved
   - text_document/didClose: Notified when a file is closed

2. LANGUAGE FEATURES:
   - textDocument/completion: Autocomplete suggestions
   - textDocument/hover: Show information on hover
   - textDocument/signatureHelp: Show function signatures while typing
   - textDocument/definition: Go to definition
   - textDocument/references: Find all references
   - textDocument/documentSymbol: Outline/symbol tree of the document
   - textDocument/formatting: Format the entire document
   - textDocument/rangeFormatting: Format a selected range

3. DIAGNOSTICS:
   - textDocument/publishDiagnostics: Send errors/warnings to the client

For Drupal specifically, we might want:
- Completion for Drupal hooks, services, configs
- Hover information for Drupal APIs
- Go to definition for services, plugins
- Diagnostics for deprecated functions, syntax errors
"""

from lsprotocol.types import (
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_HOVER,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CLOSE,
)

# Capabilities we'll implement for Drupal
DRUPAL_CAPABILITIES = [
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CLOSE,
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_HOVER,
]
