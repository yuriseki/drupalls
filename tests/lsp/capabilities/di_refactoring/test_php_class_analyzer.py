"""
Tests for PhpClassAnalyzer.

File: tests/lsp/capabilities/di_refactoring/test_php_class_analyzer.py
"""
from __future__ import annotations

import pytest

from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
    PhpClassInfo,
    ConstructorInfo,
    CreateMethodInfo,
    PropertyInfo,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def analyzer() -> PhpClassAnalyzer:
    """Create a fresh PhpClassAnalyzer for each test."""
    return PhpClassAnalyzer()


@pytest.fixture
def basic_php_content() -> str:
    """Basic PHP class content."""
    return """<?php
namespace Test;

use Drupal\\Core\\Controller\\ControllerBase;
use Symfony\\Component\\DependencyInjection\\ContainerInterface;

class MyController extends ControllerBase {
}
"""


@pytest.fixture
def php_with_constructor() -> str:
    """PHP class with constructor."""
    return """<?php
class MyController {
  public function __construct(
    DateFormatter $dateFormatter,
    EntityTypeManager $entityTypeManager
  ) {
    $this->dateFormatter = $dateFormatter;
    $this->entityTypeManager = $entityTypeManager;
  }
}
"""


@pytest.fixture
def php_with_create() -> str:
    """PHP class with create method."""
    return """<?php
class MyController {
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('date.formatter'),
      $container->get('entity_type.manager')
    );
  }
}
"""


@pytest.fixture
def php_with_properties() -> str:
    """PHP class with properties and docstrings."""
    return """<?php
class MyController {

  /**
   * The date formatter service.
   *
   * @var \\Drupal\\Core\\Datetime\\DateFormatter
   */
  protected $dateFormatter;

  /**
   * The entity type manager.
   *
   * @var \\Drupal\\Core\\Entity\\EntityTypeManagerInterface
   */
  protected EntityTypeManagerInterface $entityTypeManager;

}
"""


@pytest.fixture
def php_with_traits() -> str:
    """PHP class with trait uses."""
    return """<?php
class MyController {
  use SomeTrait;
  use AnotherTrait;
  
  protected $existingProp;
}
"""


@pytest.fixture
def full_php_class() -> str:
    """Full PHP class with all elements."""
    return """<?php

namespace Drupal\\mymodule\\Controller;

use Drupal\\Core\\Controller\\ControllerBase;
use Drupal\\Core\\DependencyInjection\\ContainerInjectionInterface;
use Drupal\\Core\\Datetime\\DateFormatter;
use Symfony\\Component\\DependencyInjection\\ContainerInterface;

/**
 * Returns responses for routes.
 */
class UserController extends ControllerBase implements ContainerInjectionInterface {

  /**
   * The date formatter service.
   *
   * @var \\Drupal\\Core\\Datetime\\DateFormatter
   */
  protected $dateFormatter;

  /**
   * Constructs a UserController object.
   *
   * @param \\Drupal\\Core\\Datetime\\DateFormatter $date_formatter
   *   The date formatter service.
   */
  public function __construct(DateFormatter $date_formatter) {
    $this->dateFormatter = $date_formatter;
  }

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('date.formatter')
    );
  }

  public function index() {
    return [];
  }
}
"""


# ============================================================================
# Tests for analyze method
# ============================================================================

class TestPhpClassAnalyzerAnalyze:
    """Tests for the analyze method."""

    def test_analyze_returns_php_class_info(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test that analyze returns a PhpClassInfo object."""
        result = analyzer.analyze(basic_php_content)
        
        assert isinstance(result, PhpClassInfo)

    def test_analyze_empty_content(self, analyzer: PhpClassAnalyzer) -> None:
        """Test analyzing empty content."""
        result = analyzer.analyze("")
        
        assert result.class_line == 0
        assert result.class_name == ""


# ============================================================================
# Tests for use statement parsing
# ============================================================================

class TestPhpClassAnalyzerUseStatements:
    """Tests for use statement parsing."""

    def test_parse_use_statements(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test parsing use statements."""
        info = analyzer.analyze(basic_php_content)
        
        assert len(info.use_statements) == 2
        assert "Drupal\\Core\\Controller\\ControllerBase" in info.use_statements
        assert "Symfony\\Component\\DependencyInjection\\ContainerInterface" in info.use_statements

    def test_use_section_boundaries(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test use section start and end are set correctly."""
        info = analyzer.analyze(basic_php_content)
        
        assert info.use_section_start > 0
        assert info.use_section_end > info.use_section_start

    def test_has_use_statement_exists(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test has_use_statement returns True for existing use."""
        info = analyzer.analyze(basic_php_content)
        
        assert analyzer.has_use_statement(
            info, "Drupal\\Core\\Controller\\ControllerBase"
        )

    def test_has_use_statement_not_exists(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test has_use_statement returns False for non-existing use."""
        info = analyzer.analyze(basic_php_content)
        
        assert not analyzer.has_use_statement(
            info, "Drupal\\Core\\Render\\RendererInterface"
        )

    def test_has_use_statement_leading_backslash(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test has_use_statement handles leading backslash."""
        info = analyzer.analyze(basic_php_content)
        
        # Should match even with leading backslash
        assert analyzer.has_use_statement(
            info, "\\Drupal\\Core\\Controller\\ControllerBase"
        )


# ============================================================================
# Tests for class declaration parsing
# ============================================================================

class TestPhpClassAnalyzerClassDeclaration:
    """Tests for class declaration parsing."""

    def test_parse_class_line(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test parsing class declaration line."""
        info = analyzer.analyze(basic_php_content)
        
        assert info.class_line > 0
        assert info.class_name == "MyController"

    def test_parse_extends(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test parsing extends clause."""
        info = analyzer.analyze(basic_php_content)
        
        assert info.extends == "ControllerBase"

    def test_parse_implements(
        self, analyzer: PhpClassAnalyzer, full_php_class: str
    ) -> None:
        """Test parsing implements clause."""
        info = analyzer.analyze(full_php_class)
        
        assert "ContainerInjectionInterface" in info.implements


# ============================================================================
# Tests for constructor parsing
# ============================================================================

class TestPhpClassAnalyzerConstructor:
    """Tests for constructor parsing."""

    def test_parse_constructor(
        self, analyzer: PhpClassAnalyzer, php_with_constructor: str
    ) -> None:
        """Test parsing __construct() method."""
        info = analyzer.analyze(php_with_constructor)
        
        assert info.constructor is not None
        assert isinstance(info.constructor, ConstructorInfo)

    def test_parse_constructor_params(
        self, analyzer: PhpClassAnalyzer, php_with_constructor: str
    ) -> None:
        """Test parsing constructor parameters."""
        info = analyzer.analyze(php_with_constructor)
        
        assert info.constructor is not None
        assert len(info.constructor.params) == 2
        assert info.constructor.params[0] == ("dateFormatter", "DateFormatter")
        assert info.constructor.params[1] == ("entityTypeManager", "EntityTypeManager")

    def test_parse_constructor_lines(
        self, analyzer: PhpClassAnalyzer, php_with_constructor: str
    ) -> None:
        """Test constructor start and end lines."""
        info = analyzer.analyze(php_with_constructor)
        
        assert info.constructor is not None
        assert info.constructor.start_line < info.constructor.end_line

    def test_no_constructor(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test that constructor is None when not present."""
        info = analyzer.analyze(basic_php_content)
        
        assert info.constructor is None


# ============================================================================
# Tests for create method parsing
# ============================================================================

class TestPhpClassAnalyzerCreateMethod:
    """Tests for create() method parsing."""

    def test_parse_create_method(
        self, analyzer: PhpClassAnalyzer, php_with_create: str
    ) -> None:
        """Test parsing create() method."""
        info = analyzer.analyze(php_with_create)
        
        assert info.create_method is not None
        assert isinstance(info.create_method, CreateMethodInfo)

    def test_parse_create_container_gets(
        self, analyzer: PhpClassAnalyzer, php_with_create: str
    ) -> None:
        """Test parsing container->get calls from create()."""
        info = analyzer.analyze(php_with_create)
        
        assert info.create_method is not None
        assert len(info.create_method.container_gets) == 2
        assert "date.formatter" in info.create_method.container_gets
        assert "entity_type.manager" in info.create_method.container_gets

    def test_no_create_method(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test that create_method is None when not present."""
        info = analyzer.analyze(basic_php_content)
        
        assert info.create_method is None


# ============================================================================
# Tests for property parsing
# ============================================================================

class TestPhpClassAnalyzerProperties:
    """Tests for property parsing."""

    def test_parse_properties(
        self, analyzer: PhpClassAnalyzer, php_with_properties: str
    ) -> None:
        """Test parsing property declarations."""
        info = analyzer.analyze(php_with_properties)
        
        assert len(info.properties) == 2
        assert "dateFormatter" in info.properties
        assert "entityTypeManager" in info.properties

    def test_property_type_hints(
        self, analyzer: PhpClassAnalyzer, php_with_properties: str
    ) -> None:
        """Test parsing property type hints."""
        info = analyzer.analyze(php_with_properties)
        
        # Second property has type hint
        assert info.properties["entityTypeManager"].type_hint == "EntityTypeManagerInterface"
        # First property has no inline type hint
        assert info.properties["dateFormatter"].type_hint is None

    def test_property_docblocks(
        self, analyzer: PhpClassAnalyzer, php_with_properties: str
    ) -> None:
        """Test parsing property docblocks."""
        info = analyzer.analyze(php_with_properties)
        
        assert info.properties["dateFormatter"].has_docblock
        assert info.properties["entityTypeManager"].has_docblock

    def test_first_property_line(
        self, analyzer: PhpClassAnalyzer, php_with_properties: str
    ) -> None:
        """Test first_property_line is set correctly."""
        info = analyzer.analyze(php_with_properties)
        
        assert info.first_property_line is not None
        assert info.first_property_line > 0


# ============================================================================
# Tests for trait parsing
# ============================================================================

class TestPhpClassAnalyzerTraits:
    """Tests for trait use parsing."""

    def test_parse_traits(
        self, analyzer: PhpClassAnalyzer, php_with_traits: str
    ) -> None:
        """Test parsing trait use statements."""
        info = analyzer.analyze(php_with_traits)
        
        assert len(info.trait_use_lines) == 2


# ============================================================================
# Tests for get_property_insert_line
# ============================================================================

class TestPhpClassAnalyzerPropertyInsertLine:
    """Tests for get_property_insert_line method."""

    def test_insert_after_traits(
        self, analyzer: PhpClassAnalyzer, php_with_traits: str
    ) -> None:
        """Test that insert line is after traits."""
        info = analyzer.analyze(php_with_traits)
        
        insert_line = analyzer.get_property_insert_line(info)
        assert insert_line > max(info.trait_use_lines)

    def test_insert_before_first_property(
        self, analyzer: PhpClassAnalyzer, php_with_properties: str
    ) -> None:
        """Test that insert line is at or before first property."""
        info = analyzer.analyze(php_with_properties)
        
        insert_line = analyzer.get_property_insert_line(info)
        assert insert_line <= info.first_property_line

    def test_insert_after_class_when_empty(
        self, analyzer: PhpClassAnalyzer, basic_php_content: str
    ) -> None:
        """Test that insert line is after class when no traits/properties."""
        info = analyzer.analyze(basic_php_content)
        
        insert_line = analyzer.get_property_insert_line(info)
        assert insert_line == info.class_line + 1


# ============================================================================
# Tests for full class parsing
# ============================================================================

class TestPhpClassAnalyzerFullClass:
    """Tests for parsing a full PHP class."""

    def test_full_class_all_components(
        self, analyzer: PhpClassAnalyzer, full_php_class: str
    ) -> None:
        """Test that all components are parsed from full class."""
        info = analyzer.analyze(full_php_class)
        
        # Has use statements
        assert len(info.use_statements) >= 3
        
        # Has class info
        assert info.class_name == "UserController"
        assert info.extends == "ControllerBase"
        
        # Has property
        assert len(info.properties) >= 1
        
        # Has constructor
        assert info.constructor is not None
        assert len(info.constructor.params) >= 1
        
        # Has create method
        assert info.create_method is not None
        assert len(info.create_method.container_gets) >= 1
