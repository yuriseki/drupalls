from unittest.mock import Mock
import pytest
from pathlib import Path
from lsprotocol.types import DidSaveTextDocumentParams, TextDocumentIdentifier

from drupalls.workspace.cache import WorkspaceCache

@pytest.mark.asyncio
async def test_services_cache_registers_hooks(tmp_path):
    """Test that ServicesCache registers text sync hooks."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Mock server with text sync manager
    server = Mock()
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    # Create workspace cache
    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    
    # Get services cache and register hooks
    cache = workspace_cache.caches['services']
    cache.register_text_sync_hooks()
    
    # Verify hook was registered
    assert len(text_sync._on_save_hooks) == 1
    assert cache._on_services_file_saved in text_sync._on_save_hooks

@pytest.mark.asyncio
async def test_services_cache_updates_on_save(tmp_path):
    """Test that cache updates when .services.yml file is saved."""
    from drupalls.workspace.services_cache import ServicesCache
    from drupalls.lsp.text_sync_manager import TextSyncManager
    
    # Setup
    server = Mock()
    text_sync = TextSyncManager(server)
    server.text_sync_manager = text_sync
    
    workspace_cache = WorkspaceCache(tmp_path, tmp_path, server=server)
    cache = workspace_cache.caches['services']
    cache.register_text_sync_hooks()
    
    # Create test services file
    services_file = tmp_path / "test.services.yml"
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\Core\\Test\\TestService
""")
    
    # Simulate save event
    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri=f'file://{services_file}')
    )
    
    # Trigger hook
    await text_sync._broadcast_on_save(params)
    
    # Verify cache was updated
    service = cache.get('test.service')
    assert service is not None
    assert service.class_name == 'Drupal\\Core\\Test\\TestService'
