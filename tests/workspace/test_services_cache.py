import pytest
import asyncio
from pathlib import Path
import tempfile
from drupalls.workspace import WorkspaceCache

@pytest.mark.asyncio
async def test_services_cache_scan(tmp_path: Path = Path(tempfile.gettempdir())):
    # Create mock .services.yml
    services_file = tmp_path / "modules" / "test" / "test.services.yml"
    services_file.parent.mkdir(parents=True, exist_ok=True)
    services_file.write_text("""
services:
  test.service:
    class: Drupal\\test\\TestService
    arguments: ['@entity_type.manager']
""")
    
    # Initialize cache
    cache = WorkspaceCache(tmp_path)
    await cache.initialize()
    
    # Verify service was parsed
    services_cache = cache.caches["services"]
    service = services_cache.get('test.service')
    
    assert service is not None
    assert service.class_name == 'Drupal\\test\\TestService'
    assert len(service.arguments) == 1

@pytest.mark.asyncio
async def test_cache_invalidation(tmp_path: Path = Path(tempfile.gettempdir())):
    services_file = tmp_path / "modules" / "test" / "test.services.yml"
    services_file.parent.mkdir(parents=True, exist_ok=True)
    services_file.write_text("services: {}")
    
    cache = WorkspaceCache(tmp_path)
    await cache.initialize()
    
    # Modify file
    services_file.write_text("""
services:
  new.service:
    class: NewClass
""")
    
    # Invalidate
    cache.invalidate_file(services_file)
    await asyncio.sleep(0.1)  # Wait for async re-parse
    
    # Verify update
    services_cache = cache.caches["services"]
    assert services_cache.get('new.service') is not None
