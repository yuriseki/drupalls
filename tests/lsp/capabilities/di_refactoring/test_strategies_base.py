"""
Tests for DI strategy base class.

File: tests/lsp/capabilities/di_refactoring/test_strategies_base.py
"""
from __future__ import annotations

import pytest
from lsprotocol.types import TextEdit, Range, Position

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
    RefactoringEdit,
    DIStrategy,
)


# ============================================================================
# Tests for DIRefactoringContext
# ============================================================================

class TestDIRefactoringContext:
    """Tests for DIRefactoringContext dataclass."""

    def test_create_context(self) -> None:
        """Test creating a DIRefactoringContext."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content="<?php class Test {}",
            class_line=5,
            drupal_type="controller",
        )
        
        assert context.file_uri == "file:///test.php"
        assert context.file_content == "<?php class Test {}"
        assert context.class_line == 5
        assert context.drupal_type == "controller"
        assert context.services_to_inject == []

    def test_create_context_with_services(self) -> None:
        """Test creating context with services to inject."""
        context = DIRefactoringContext(
            file_uri="file:///test.php",
            file_content="<?php class Test {}",
            class_line=5,
            drupal_type="controller",
            services_to_inject=["entity_type.manager", "messenger"],
        )
        
        assert context.services_to_inject == ["entity_type.manager", "messenger"]


# ============================================================================
# Tests for RefactoringEdit
# ============================================================================

class TestRefactoringEdit:
    """Tests for RefactoringEdit dataclass."""

    def test_create_refactoring_edit(self) -> None:
        """Test creating a RefactoringEdit."""
        text_edit = TextEdit(
            range=Range(
                start=Position(line=0, character=0),
                end=Position(line=0, character=10),
            ),
            new_text="new content",
        )
        
        edit = RefactoringEdit(
            description="Add use statement",
            text_edit=text_edit,
        )
        
        assert edit.description == "Add use statement"
        assert edit.text_edit == text_edit
        assert edit.text_edit.new_text == "new content"


# ============================================================================
# Tests for DIStrategy base class helpers
# ============================================================================

class ConcreteDIStrategy(DIStrategy):
    """Concrete implementation for testing abstract base class."""
    
    @property
    def name(self) -> str:
        return "Test Strategy"
    
    @property
    def supported_types(self) -> set[str]:
        return {"test"}
    
    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        return []


class TestDIStrategyHelpers:
    """Tests for DIStrategy helper methods."""

    @pytest.fixture
    def strategy(self) -> ConcreteDIStrategy:
        """Create a concrete strategy for testing."""
        return ConcreteDIStrategy()

    def test_create_text_edit(self, strategy: ConcreteDIStrategy) -> None:
        """Test _create_text_edit helper."""
        edit = strategy._create_text_edit(
            line=5,
            character=10,
            end_line=5,
            end_character=20,
            new_text="replacement",
        )
        
        assert isinstance(edit, TextEdit)
        assert edit.range.start.line == 5
        assert edit.range.start.character == 10
        assert edit.range.end.line == 5
        assert edit.range.end.character == 20
        assert edit.new_text == "replacement"

    def test_insert_at(self, strategy: ConcreteDIStrategy) -> None:
        """Test _insert_at helper creates zero-width range."""
        edit = strategy._insert_at(line=10, character=5, text="inserted")
        
        assert isinstance(edit, TextEdit)
        assert edit.range.start.line == 10
        assert edit.range.start.character == 5
        assert edit.range.end.line == 10
        assert edit.range.end.character == 5  # Same as start = insert
        assert edit.new_text == "inserted"

    def test_strategy_name_property(self, strategy: ConcreteDIStrategy) -> None:
        """Test that name property is accessible."""
        assert strategy.name == "Test Strategy"

    def test_strategy_supported_types_property(
        self, strategy: ConcreteDIStrategy
    ) -> None:
        """Test that supported_types property is accessible."""
        assert strategy.supported_types == {"test"}
