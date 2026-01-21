"""
Tests for ControllerDIStrategy.

File: tests/lsp/capabilities/di_refactoring/test_controller_strategy.py
"""
from __future__ import annotations

import pytest

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def strategy() -> ControllerDIStrategy:
    """Create a fresh ControllerDIStrategy for each test."""
    return ControllerDIStrategy()


@pytest.fixture
def basic_php_content() -> str:
    """Basic PHP controller content."""
    return """<?php

namespace Drupal\\mymodule\\Controller;

use Drupal\\Core\\Controller\\ControllerBase;

class MyController extends ControllerBase {

  public function index() {
    $etm = \\Drupal::entityTypeManager();
    return [];
  }

}
"""


# ============================================================================
# Tests for ControllerDIStrategy properties
# ============================================================================

class TestControllerDIStrategyProperties:
    """Tests for strategy properties."""

    def test_strategy_name(self, strategy: ControllerDIStrategy) -> None:
        """Test strategy name property."""
        assert strategy.name == "Controller/Form DI Strategy"

    def test_supported_types(self, strategy: ControllerDIStrategy) -> None:
        """Test supported_types property."""
        assert strategy.supported_types == {"controller", "form"}


# ============================================================================
# Tests for generate_edits
# ============================================================================

class TestControllerDIStrategyGenerateEdits:
    """Tests for generate_edits method."""

    def test_generate_edits_returns_list(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that generate_edits returns a list of edits."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        
        assert isinstance(edits, list)
        assert len(edits) > 0

    def test_generate_edits_creates_use_statement_edit(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that use statement edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add use statements" in descriptions

    def test_generate_edits_creates_properties_edit(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that properties edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add properties" in descriptions

    def test_generate_edits_creates_constructor_edit(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that constructor edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add/modify constructor" in descriptions

    def test_generate_edits_creates_create_method_edit(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that create() method edit is generated."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        assert "Add/modify create() method" in descriptions

    def test_generate_edits_multiple_services(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test generating edits for multiple services."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager", "messenger", "current_user"],
        )
        
        edits = strategy.generate_edits(context)
        
        # Should have all required edits
        assert len(edits) == 4

    def test_generate_edits_unknown_service(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test generating edits for unknown service."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["unknown.custom.service"],
        )
        
        edits = strategy.generate_edits(context)
        
        # Should still generate edits, just without type hints
        assert len(edits) > 0


# ============================================================================
# Tests for helper methods
# ============================================================================

class TestControllerDIStrategyHelpers:
    """Tests for strategy helper methods."""

    def test_find_use_insert_line(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test finding the line to insert use statements."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
        )
        
        line = strategy._find_use_insert_line(context)
        
        # Should be at the class line (before it)
        assert line == 6

    def test_generate_use_statements(
        self, strategy: ControllerDIStrategy
    ) -> None:
        """Test generating use statements."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
            ("messenger", get_service_interface("messenger")),
        ]
        
        result = strategy._generate_use_statements(services_info)
        
        assert "EntityTypeManagerInterface" in result
        assert "MessengerInterface" in result
        assert "ContainerInterface" in result

    def test_generate_properties(
        self, strategy: ControllerDIStrategy
    ) -> None:
        """Test generating property declarations."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_properties(services_info)
        
        assert "protected EntityTypeManagerInterface $entityTypeManager" in result

    def test_generate_constructor(
        self, strategy: ControllerDIStrategy
    ) -> None:
        """Test generating constructor."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_constructor(services_info)
        
        assert "__construct" in result
        assert "EntityTypeManagerInterface $entityTypeManager" in result
        assert "$this->entityTypeManager = $entityTypeManager" in result

    def test_generate_create_method(
        self, strategy: ControllerDIStrategy
    ) -> None:
        """Test generating create() method."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_service_interface,
        )
        
        services_info = [
            ("entity_type.manager", get_service_interface("entity_type.manager")),
        ]
        
        result = strategy._generate_create_method(services_info)
        
        assert "public static function create" in result
        assert "ContainerInterface $container" in result
        assert "$container->get('entity_type.manager')" in result
        assert "return new static(" in result
