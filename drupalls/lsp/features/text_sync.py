"""
Text document synchronization handlers.

These handlers track the state of documents (files) that are open in the editor.
This is crucial because the language server needs to know what content the user
is currently working with.
"""

from lsprotocol.types import (
    DidOpenTextDocumentParams,
    DidChangeTextDocumentParams,
    DidSaveTextDocumentParams,
    DidCloseTextDocumentParams,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_SAVE,
    TEXT_DOCUMENT_DID_CLOSE,
)
from pygls.lsp.server import LanguageServer


def register_text_sync_handlers(server: LanguageServer):
    """
    Register handlers for document synchronization events.
    
    These are NOTIFICATIONS (not requests) - the client sends them
    but doesn't expect a response.
    """
    
    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
        """
        Called when a document is opened in the editor.
        
        params.text_document contains:
        - uri: The file URI (e.g., "file:///path/to/file.php")
        - language_id: Language identifier (e.g., "php")
        - version: Document version number
        - text: The full content of the document
        """
        ls.show_message_log(f"Document opened: {params.text_document.uri}")
        
        # The document is automatically added to ls.workspace.text_documents
        # You can access it later with: ls.workspace.get_text_document(uri)
    
    @server.feature(TEXT_DOCUMENT_DID_CHANGE)
    def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
        """
        Called when the document content changes.
        
        params.content_changes contains the changes made.
        In full sync mode (default), you get the entire new content.
        In incremental mode, you get only the changed parts.
        """
        ls.show_message_log(f"Document changed: {params.text_document.uri}")
        
        # The workspace automatically updates the document content
        # This is a good place to trigger diagnostics (error checking)
    
    @server.feature(TEXT_DOCUMENT_DID_SAVE)
    def did_save(ls: LanguageServer, params: DidSaveTextDocumentParams):
        """
        Called when the document is saved.
        
        This is a good place to run more expensive operations like:
        - Full code analysis
        - Linting
        - Code formatting
        """
        ls.show_message_log(f"Document saved: {params.text_document.uri}")
    
    @server.feature(TEXT_DOCUMENT_DID_CLOSE)
    def did_close(ls: LanguageServer, params: DidCloseTextDocumentParams):
        """
        Called when the document is closed in the editor.
        
        You might want to clean up any resources associated with this document.
        """
        ls.show_message_log(f"Document closed: {params.text_document.uri}")
