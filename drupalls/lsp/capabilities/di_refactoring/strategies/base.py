"""
DI refactoring strategy base class.

File: drupalls/lsp/capabilities/di_refactoring/strategies/base.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from lsprotocol.types import TextEdit, Range, Position


@dataclass
class DIRefactoringContext:
    """Context for DI refactoring."""

    file_uri: str
    file_content: str
    class_line: int
    drupal_type: str
    services_to_inject: list[str] = field(default_factory=list)


@dataclass
class RefactoringEdit:
    """A single refactoring edit."""

    description: str
    text_edit: TextEdit


class DIStrategy(ABC):
    """Base class for DI refactoring strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for display."""
        pass

    @property
    @abstractmethod
    def supported_types(self) -> set[str]:
        """DrupalClassType values this strategy handles."""
        pass

    @abstractmethod
    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits to convert static calls to DI."""
        pass

    def _create_text_edit(
        self,
        line: int,
        character: int,
        end_line: int,
        end_character: int,
        new_text: str,
    ) -> TextEdit:
        """Helper to create a TextEdit."""
        return TextEdit(
            range=Range(
                start=Position(line=line, character=character),
                end=Position(line=end_line, character=end_character),
            ),
            new_text=new_text,
        )

    def _insert_at(self, line: int, character: int, text: str) -> TextEdit:
        """Create an insert edit at position."""
        return self._create_text_edit(line, character, line, character, text)
