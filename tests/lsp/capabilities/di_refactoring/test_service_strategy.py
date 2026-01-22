"""
Comprehensive tests for drupalls/lsp/capabilities/di_refactoring/strategies/service_strategy.py

Covers:
- ServiceDIStrategy.generate_edits
- YAML normalization and merging
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy import (
    ServiceDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)
from drupalls.workspace.services_cache import ServiceDefinition
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    ServiceInterfaceInfo,
)

# --- Fixtures ---

@pytest.fixture
def php_service_class_source():
    # PHP class with a static call and no constructor
    return """<?php

namespace Drupal\\my_module;

use Drupal\\Core\\Render\\RendererInterface;

class MyService {
  public function doSomething() {
    $renderer = \\Drupal::service('renderer');
    $renderer->render();
  }
}
"""

@pytest.fixture
def services_yml_content(tmp_path):
    # Write a services.yml file to disk for the test
    yml = """services:
  my_module.my_service:
    class: Drupal\\my_module\\MyService
    arguments: []
"""
    file_path = tmp_path / "my_module.services.yml"
    file_path.write_text(yml)
    return str(file_path), yml

@pytest.fixture
def workspace_cache_mock(tmp_path, services_yml_content):
    # Simulate a WorkspaceCache with a ServicesCache containing the service definition
    services_file_path, _ = services_yml_content
    class_file_path = str(tmp_path / "MyService.php")
    service_def = ServiceDefinition(
        id="my_module.my_service",
        class_name="Drupal\\my_module\\MyService",
        class_file_path=class_file_path,
        description="Drupal\\my_module\\MyService",
        arguments=[],
        tags=[],
        file_path=services_file_path,
        line_number=2,
    )
    services_cache = MagicMock()
    services_cache.get_all.return_value = {"my_module.my_service": service_def}
    services_cache.get.return_value = service_def
    workspace_cache = MagicMock()
    workspace_cache.caches = {"services": services_cache}
    return workspace_cache, class_file_path, services_file_path

@pytest.fixture
def di_context(php_service_class_source, workspace_cache_mock):
    workspace_cache, class_file_path, _ = workspace_cache_mock
    return DIRefactoringContext(
        file_uri=f"file://{class_file_path}",
        file_content=php_service_class_source,
        class_line=5,
        drupal_type="service",
        services_to_inject=["renderer"],
        workspace_cache=workspace_cache,
    )

# --- Tests ---

@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.open")
@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.yaml.safe_load")
@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.get_service_interface")
def test_generate_edits_inserts_property_and_yaml(
    mock_get_service_interface, mock_yaml_load, mock_open, di_context, services_yml_content
):
    # Setup YAML loader to return the parsed dict
    services_file_path, yml = services_yml_content
    mock_yaml_load.return_value = {
        "services": {
            "my_module.my_service": {
                "class": "Drupal\\my_module\\MyService",
                "arguments": [],
            }
        }
    }
    # Simulate reading the services.yml file
    mock_open.return_value.__enter__.return_value.read.return_value = yml
    # Mock get_service_interface to return RendererInterface for 'renderer'
    def _gsi(sid, workspace_cache=None):
        if sid == "renderer":
            return ServiceInterfaceInfo(
                interface_fqcn="Drupal\\Core\\Render\\RendererInterface",
                interface_short="RendererInterface",
                property_name="renderer",
                use_statement="use Drupal\\Core\\Render\\RendererInterface;",
            )
        return None

    mock_get_service_interface.side_effect = _gsi

    strategy = ServiceDIStrategy()
    edits = strategy.generate_edits(di_context)

    # There should be at least one edit for PHP and one for YAML
    php_edits = [e for e in edits if not e.target_uri]
    yaml_edits = [e for e in edits if e.target_uri and e.target_uri.endswith(".services.yml")]

    assert any("Add properties" in e.description for e in php_edits)
    assert any("constructor" in e.description.lower() for e in php_edits)
    assert any("Update services.yml" in e.description for e in yaml_edits)

    # Check YAML normalization: arguments should be prefixed with '@'
    yaml_edit = yaml_edits[0]
    assert "@renderer" in yaml_edit.text_edit.new_text

    # Check property declaration in PHP edit
    property_edit = next(e for e in php_edits if "Add properties" in e.description)
    assert "$renderer;" in property_edit.text_edit.new_text
    assert "@var \\Drupal\\Core\\Render\\RendererInterface" in property_edit.text_edit.new_text

    # Check constructor param in PHP edit
    constructor_edit = next(e for e in php_edits if "constructor" in e.description.lower())
    assert "RendererInterface $renderer" in constructor_edit.text_edit.new_text

@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.open")
@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.yaml.safe_load")
@patch("drupalls.lsp.capabilities.di_refactoring.strategies.service_strategy.get_service_interface")
def test_generate_edits_preserves_existing_arguments(
    mock_get_service_interface, mock_yaml_load, mock_open, di_context, services_yml_content
):
    # Existing arguments in YAML (already has @logger)
    services_file_path, yml = services_yml_content
    mock_yaml_load.return_value = {
        "services": {
            "my_module.my_service": {
                "class": "Drupal\\my_module\\MyService",
                "arguments": ["@logger"],
            }
        }
    }
    mock_open.return_value.__enter__.return_value.read.return_value = yml
    # Mock get_service_interface to return RendererInterface for 'renderer'
    def _gsi(sid, workspace_cache=None):
        if sid == "renderer":
            return ServiceInterfaceInfo(
                interface_fqcn="Drupal\\Core\\Render\\RendererInterface",
                interface_short="RendererInterface",
                property_name="renderer",
                use_statement="use Drupal\\Core\\Render\\RendererInterface;",
            )
        return None

    mock_get_service_interface.side_effect = _gsi

    strategy = ServiceDIStrategy()
    edits = strategy.generate_edits(di_context)

    yaml_edits = [e for e in edits if e.target_uri and e.target_uri.endswith(".services.yml")]
    assert yaml_edits
    yaml_edit = yaml_edits[0]
    # Both @logger and @renderer should be present, normalized
    assert "@logger" in yaml_edit.text_edit.new_text
    assert "@renderer" in yaml_edit.text_edit.new_text

def test_generate_edits_no_services_to_inject(di_context):
    di_context.services_to_inject = []
    strategy = ServiceDIStrategy()
    edits = strategy.generate_edits(di_context)
    assert edits == []

def test_generate_edits_no_services_cache(di_context):
    # Remove services cache
    di_context.workspace_cache.caches = {}
    strategy = ServiceDIStrategy()
    edits = strategy.generate_edits(di_context)
    # Should not raise, but no YAML edit
    assert all(not (e.target_uri and e.target_uri.endswith(".services.yml")) for e in edits)
