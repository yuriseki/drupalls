"""
Comprehensive tests for drupalls/lsp/capabilities/di_refactoring/service_interfaces.py

Covers:
- get_service_interface
- get_property_name
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    get_service_interface,
    get_property_name,
    ServiceInterfaceInfo,
)

class DummyServiceDef:
    def __init__(self, class_name):
        self.class_name = class_name

@pytest.fixture
def workspace_cache_with_renderer():
    # Simulate a workspace_cache with a 'services' cache mapping 'renderer'
    renderer_class = "\\Drupal\\Core\\Render\\RendererInterface"
    services_cache = {
        "renderer": SimpleNamespace(class_name=renderer_class)
    }
    workspace_cache = SimpleNamespace(
        caches={"services": SimpleNamespace(get=lambda sid: services_cache.get(sid))}
    )
    return workspace_cache, renderer_class

def test_get_service_interface_returns_info(workspace_cache_with_renderer):
    workspace_cache, renderer_class = workspace_cache_with_renderer
    info = get_service_interface("renderer", workspace_cache)
    assert isinstance(info, ServiceInterfaceInfo)
    assert info.interface_fqcn == renderer_class.lstrip("\\")
    assert info.interface_short == "RendererInterface"
    assert info.property_name == "renderer"
    assert info.use_statement == f"use {renderer_class.lstrip('\\')};"

def test_get_service_interface_none_workspace_cache():
    # Should not raise, just return None
    assert get_service_interface("renderer", None) is None

def test_get_service_interface_none_services_cache():
    workspace_cache = SimpleNamespace(caches={})
    assert get_service_interface("renderer", workspace_cache) is None

def test_get_service_interface_service_not_found():
    services_cache = SimpleNamespace(get=lambda sid: None)
    workspace_cache = SimpleNamespace(caches={"services": services_cache})
    assert get_service_interface("not_a_service", workspace_cache) is None

@pytest.mark.parametrize("service_id,expected", [
    ("renderer", "renderer"),
    ("entity_type.manager", "entityTypeManager"),
    ("config.factory", "configFactory"),
    ("my_module.special_service", "myModuleSpecialService"),
    ("simple", "simple"),
])
def test_get_property_name_cases(service_id, expected):
    assert get_property_name(service_id) == expected
