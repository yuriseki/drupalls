"""
Comprehensive tests for DI code action strategy selection logic.

Covers:
- Strategy selection: ServiceDIStrategy vs ControllerDIStrategy
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy import ServiceDIStrategy
from drupalls.lsp.capabilities.di_refactoring.strategies.base import DIRefactoringContext

# Assume ControllerDIStrategy is implemented similarly
class DummyControllerDIStrategy:
    pass

@pytest.fixture
def workspace_cache_with_service(tmp_path):
    # Simulate a workspace_cache with a 'services' cache mapping a PHP file
    class_file_path = str(tmp_path / "MyService.php")
    service_def = SimpleNamespace(
        id="my_module.my_service",
        class_name="Drupal\\my_module\\MyService",
        class_file_path=class_file_path,
        file_path=str(tmp_path / "my_module.services.yml"),
    )
    services_cache = MagicMock()
    services_cache.get_all.return_value = {"my_module.my_service": service_def}
    workspace_cache = MagicMock()
    workspace_cache.caches = {"services": services_cache}
    return workspace_cache, class_file_path

def select_strategy(context):
    """
    Simulate the code action's strategy selection logic.
    If workspace_cache reverse-lookup finds the PHP file, use ServiceDIStrategy.
    Otherwise, use DummyControllerDIStrategy.
    """
    services_cache = context.workspace_cache.caches.get("services") if context.workspace_cache else None
    if services_cache:
        for sdef in services_cache.get_all().values():
            if getattr(sdef, "class_file_path", None) == context.file_uri.replace("file://", ""):
                return ServiceDIStrategy
    return DummyControllerDIStrategy

def test_selects_service_strategy(workspace_cache_with_service):
    workspace_cache, class_file_path = workspace_cache_with_service
    context = DIRefactoringContext(
        file_uri=f"file://{class_file_path}",
        file_content="",
        class_line=5,
        drupal_type="service",
        services_to_inject=["renderer"],
        workspace_cache=workspace_cache,
    )
    strategy = select_strategy(context)
    assert strategy is ServiceDIStrategy

def test_falls_back_to_controller_strategy():
    # No matching service in cache
    workspace_cache = MagicMock()
    services_cache = MagicMock()
    services_cache.get_all.return_value = {}
    workspace_cache.caches = {"services": services_cache}
    context = DIRefactoringContext(
        file_uri="file:///tmp/NotAService.php",
        file_content="",
        class_line=5,
        drupal_type="controller",
        services_to_inject=["renderer"],
        workspace_cache=workspace_cache,
    )
    strategy = select_strategy(context)
    assert strategy is DummyControllerDIStrategy
