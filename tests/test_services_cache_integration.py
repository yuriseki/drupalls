from unittest.mock import Mock
import pytest
from pathlib import Path
from lsprotocol.types import DidSaveTextDocumentParams, TextDocumentIdentifier

from drupalls.lsp.server import create_server
from drupalls.lsp.text_sync_manager import TextSyncManager
from drupalls.workspace.cache import WorkspaceCache


@pytest.mark.asyncio
async def test_edit_services_file_updates_cache(tmp_path):
    """Test that editing a services file updates the cache in real-time."""
    from drupalls.workspace.services_cache import ServicesCache

    # Setup full server
    server = create_server()
    text_sync = TextSyncManager(server)
    text_sync.register_handlers()
    server.text_sync_manager = text_sync

    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    await workspace_cache.initialize()

    # Initially empty
    cache = workspace_cache.caches["services"]
    assert len(cache.get_all()) == 0

    # Create services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text(
        """
services:
  initial.service:
    class: Drupal\\Core\\Initial\\InitialService
"""
    )

    # Simulate save (this would normally be triggered by LSP)
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=f"file://{services_file}")
    )
    await text_sync._broadcast_on_save(params)

    # Verify service was added
    assert cache.get("initial.service") is not None

    # Edit file to add another service
    services_file.write_text(
        """
services:
  initial.service:
    class: Drupal\\Core\\Initial\\InitialService
  new.service:
    class: Drupal\\Core\\New\\NewService
"""
    )

    # Simulate another save
    await text_sync._broadcast_on_save(params)

    # Verify both services exist
    assert cache.get("initial.service") is not None
    assert cache.get("new.service") is not None
    assert len(cache.get_all()) == 2
