"""
Tests for PluginDIStrategy.

File: tests/lsp/capabilities/di_refactoring/test_plugin_strategy.py
"""
from __future__ import annotations

import pytest

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.plugin_strategy import (
    PluginDIStrategy,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def strategy() -> PluginDIStrategy:
    """Create a fresh PluginDIStrategy for each test."""
    return PluginDIStrategy()


@pytest.fixture
def basic_block_content() -> str:
    """Basic PHP block plugin content."""
    return """<?php

namespace Drupal\\mymodule\\Plugin\\Block;

use Drupal\\Core\\Block\\BlockBase;

/**
 * @Block(
 *   id = "my_block",
 *   admin_label = @Translation("My Block")
 * )
 */
class MyBlock extends BlockBase {

  public function build() {
    $etm = \\Drupal::entityTypeManager();
    return [];
  }

}
"""


# ============================================================================
# Tests for PluginDIStrategy properties
# ============================================================================

class TestPluginDIStrategyProperties:
    """Tests for strategy properties."""

    def test_strategy_name(self, strategy: PluginDIStrategy) -> None:
        """Test strategy name property."""
        assert strategy.name == "Plugin DI Strategy"

    def test_supported_types(self, strategy: PluginDIStrategy) -> None:
        """Test supported_types property."""
        expected = {"plugin", "block", "formatter", "widget", "queue_worker"}
        assert strategy.supported_types == expected


# ============================================================================
# Tests for generate_edits
# ============================================================================

class TestPluginDIStrategyGenerateEdits:
    """Tests for generate_edits method."""

    def test_generate_edits_returns_list(
        self, strategy: PluginDIStrategy, basic_block_content: str
    ) -> None:
        """Test that generate_edits returns a list of edits."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_block_content,
            class_line=13,
            drupal_type="block",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        
        assert isinstance(edits, list)
        assert len(edits) > 0

    def test_generate_edits_adds_interface_implementation(
        self, strategy: PluginDIStrategy, basic_block_content: str
    ) -> None:
        """Test that interface implementation edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_block_content,
            class_line=13,
            drupal_type="block",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add ContainerFactoryPluginInterface" in descriptions

    def test_generate_edits_skips_interface_if_already_present(
        self, strategy: PluginDIStrategy
    ) -> None:
        """Test that interface edit is skipped if already implemented."""
        content_with_interface = """<?php

class MyBlock extends BlockBase implements ContainerFactoryPluginInterface {

  public function build() {
    return [];
  }

}
"""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=content_with_interface,
            class_line=2,
            drupal_type="block",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add ContainerFactoryPluginInterface" not in descriptions

    def test_generate_edits_creates_use_statement_edit(
        self, strategy: PluginDIStrategy, basic_block_content: str
    ) -> None:
        """Test that use statement edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_block_content,
            class_line=13,
            drupal_type="block",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add use statements" in descriptions

    def test_generate_edits_creates_constructor_with_plugin_args(
        self, strategy: PluginDIStrategy, basic_block_content: str
    ) -> None:
        """Test that constructor includes plugin arguments."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_block_content,
            class_line=13,
            drupal_type="block",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        constructor_edit = next(
            e for e in edits if "constructor" in e.description.lower()
        )
        
        constructor_text = constructor_edit.text_edit.new_text
        assert "array $configuration" in constructor_text
        assert "$plugin_id" in constructor_text
        assert "$plugin_definition" in constructor_text
        assert "parent::__construct" in constructor_text


# ============================================================================
# Tests for helper methods
# ============================================================================

class TestPluginDIStrategyHelpers:
    """Tests for strategy helper methods."""

    def test_generate_use_statements_includes_plugin_interface(
        self, strategy: PluginDIStrategy
    ) -> None:
        """Test that use statements include plugin interface."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_use_statements(services_info)
        
        assert "ContainerFactoryPluginInterface" in result
        assert "ContainerInterface" in result
        assert "EntityTypeManagerInterface" in result

    def test_generate_constructor_with_plugin_signature(
        self, strategy: PluginDIStrategy
    ) -> None:
        """Test generating constructor with plugin signature."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_constructor(services_info)
        
        assert "array $configuration" in result
        assert "$plugin_id" in result
        assert "$plugin_definition" in result
        assert "parent::__construct($configuration, $plugin_id, $plugin_definition)" in result
        assert "$this->entityTypeManager = $entityTypeManager" in result

    def test_generate_create_method_with_plugin_signature(
        self, strategy: PluginDIStrategy
    ) -> None:
        """Test generating create() with plugin signature."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_create_method(services_info)
        
        assert "ContainerInterface $container" in result
        assert "array $configuration" in result
        assert "$plugin_id" in result
        assert "$plugin_definition" in result
        assert "$configuration," in result  # Passed to new static
        assert "$container->get('entity_type.manager')" in result
