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


@pytest.fixture
def php_with_existing_constructor() -> str:
    """PHP controller content with existing constructor."""
    return """<?php

namespace Drupal\\mymodule\\Controller;

use Drupal\\Core\\Controller\\ControllerBase;
use Symfony\\Component\\DependencyInjection\\ContainerInterface;
use Drupal\\Core\\Config\\ConfigFactoryInterface;

class MyController extends ControllerBase {

  protected ConfigFactoryInterface $configFactory;

  public function __construct(ConfigFactoryInterface $configFactory) {
    $this->configFactory = $configFactory;
  }

  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('config.factory')
    );
  }

  public function index() {
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
        
        assert "Add properties with docstrings" in descriptions

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
        
        assert "Add constructor" in descriptions

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
        
        assert "Add create() method" in descriptions

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
# Tests for merge functionality
# ============================================================================

class TestControllerDIStrategyMerge:
    """Tests for merging with existing constructor/create."""

    def test_merge_constructor_with_existing(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that new services are merged into existing constructor."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        # Should merge, not add new
        assert "Merge constructor with new services" in descriptions

    def test_merge_create_method_with_existing(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that new container gets are merged into existing create()."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        descriptions = [e.description for e in edits]
        
        # Should merge, not add new
        assert "Merge create() with new container gets" in descriptions

    def test_merged_constructor_contains_both_params(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that merged constructor contains existing and new params."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        
        constructor_edit = next(
            (e for e in edits if "constructor" in e.description.lower()), None
        )
        assert constructor_edit is not None
        
        new_text = constructor_edit.text_edit.new_text
        assert "$configFactory" in new_text
        assert "EntityTypeManagerInterface" in new_text or "$entityTypeManager" in new_text

    def test_merged_create_contains_both_gets(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that merged create() contains existing and new container gets."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        edits = strategy.generate_edits(context)
        
        create_edit = next(
            (e for e in edits if "create" in e.description.lower()), None
        )
        assert create_edit is not None
        
        new_text = create_edit.text_edit.new_text
        assert "config.factory" in new_text
        assert "entity_type.manager" in new_text

    def test_skips_already_injected_service(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that already injected services are skipped."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["config.factory"],  # Already exists
        )
        
        edits = strategy.generate_edits(context)
        
        # No edits needed as service already exists
        assert len(edits) == 0


# ============================================================================
# Tests for class_info population
# ============================================================================

class TestControllerDIStrategyClassInfo:
    """Tests for class_info population in context."""

    def test_class_info_set_after_generate_edits(
        self, strategy: ControllerDIStrategy, basic_php_content: str
    ) -> None:
        """Test that class_info is set after generate_edits."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=basic_php_content,
            class_line=6,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        strategy.generate_edits(context)
        
        assert context.class_info is not None

    def test_class_info_has_use_statements(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that class_info contains use statements."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        strategy.generate_edits(context)
        
        assert context.class_info is not None
        assert len(context.class_info.use_statements) > 0

    def test_class_info_has_constructor(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that class_info contains constructor info."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        strategy.generate_edits(context)
        
        assert context.class_info is not None
        assert context.class_info.constructor is not None

    def test_class_info_has_create_method(
        self, strategy: ControllerDIStrategy, php_with_existing_constructor: str
    ) -> None:
        """Test that class_info contains create method info."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content=php_with_existing_constructor,
            class_line=9,
            drupal_type="controller",
            services_to_inject=["entity_type.manager"],
        )
        
        strategy.generate_edits(context)
        
        assert context.class_info is not None
        assert context.class_info.create_method is not None
