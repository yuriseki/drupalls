from pathlib import (
    Path,
)
import re
from lsprotocol.types import Position

from drupalls.context.class_context_detector import ClassContextDetector
from drupalls.context.drupal_classifier import DrupalContextClassifier
from drupalls.context.class_context import ClassContext
from drupalls.phpactor.client import PhpactorClient


class TypeChecker:
    """
    Unified type checker using context-aware Phpactor integration.

    This refactored class delegates to specialized components
    for cleaner separation of concerns.
    """

    def __init__(self, phpactor_client: PhpactorClient | None = None):
        """
        Initialize TypeChecker.

        Args:
            phpactor_client: Optional PhpactorClient instance.
                           Creates one if not provided.
        """
        if phpactor_client is None:
            phpactor_client = PhpactorClient()

        self.phpactor = phpactor_client
        self.context_detector = ClassContextDetector(phpactor_client)
        self.classifier = DrupalContextClassifier()

        # Cache for variable type lookups
        self._type_cache: dict[tuple, str | None] = {}

    async def get_class_context(
        self, uri: str, position: Position, doc_lines: list[str] | None = None
    ) -> ClassContext | None:
        """
        Get the classified class context at a position.

        Args:
            uri: Document URI
            position: Cursor position
            doc_lines: Optional document lines

        Returns:
            ClassContext with drupal_type set, or None
        """
        context = await self.context_detector.get_class_at_position(
            uri, position, doc_lines
        )

        if context:
            self.classifier.classify(context)

        return context

    async def is_container_variable(self, doc, line: str, position: Position) -> bool:
        """
        Check if the variable in ->get() call is a ContainerInterface.

        Maintains backward compatibility with existing capability code.

        Args:
            doc: Document object with uri and lines
            line: Current line text
            position: Cursor position

        Returns:
            True if variable is ContainerInterface type
        """
        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False

        cache_key = (doc.uri, position.line, var_name)

        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            var_type = await self._query_variable_type(doc, position)
            self._type_cache[cache_key] = var_type

        if not var_type:
            # Fallback heuristics
            if var_name.lower() == "container":
                return True
            return False

        return self._is_container_interface(var_type)

    async def _query_variable_type(self, doc, position: Position) -> str | None:
        """Query Phpactor for variable type at position.
        
        This method finds the variable before ->get() and queries its type.
        For a line like `$a->get("service")`, we need to query the type of $a,
        not the type at the cursor position (which might be inside the string).
        """
        from pathlib import Path

        file_path = Path(doc.uri.replace("file://", ""))
        working_dir = self._find_project_root(file_path)
        
        # Get the current line
        line = doc.lines[position.line].rstrip('\n') if position.line < len(doc.lines) else ""
        
        # Find the variable position (before ->get()
        var_offset = self._find_variable_offset_before_get(doc.lines, line, position)
        
        if var_offset is None:
            # Fallback to cursor position
            var_offset = self._position_to_offset(doc.lines, position)

        type_info = await self.phpactor.offset_info(file_path, var_offset, working_dir)
        if type_info:
            if type_info.type_name and type_info.type_name != "<missing>":
                var_type = type_info.type_name
            else:
                var_type = type_info.class_type
        else:
            var_type = None

        return var_type
    
    def _find_variable_offset_before_get(
        self, lines: list[str], line: str, position: Position
    ) -> int | None:
        """
        Find the byte offset of the variable before ->get() call.
        
        For a line like `$a->get("service")` with cursor inside the string,
        we need to find the position of $a to query its type.
        
        Args:
            lines: All document lines
            line: Current line text
            position: Cursor position
            
        Returns:
            Byte offset of the variable, or None if not found
        """
        # Find ->get( before or at the cursor position
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None
        
        # Find the $ sign before ->get(
        # We look for the variable pattern like $var or $this->var
        arrow_pos = get_pos  # Position of '->' in '->get('
        
        # Search backward for the variable start ($)
        dollar_pos = line.rfind("$", 0, arrow_pos)
        if dollar_pos == -1:
            return None
        
        # The variable starts at dollar_pos
        # Calculate the byte offset for this position
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip("\n")) + 1
        
        # Add the character position of the variable (after $)
        # We want to point to a character within the variable name
        # so Phpactor can identify it. Let's point to the char after $
        var_name_start = dollar_pos + 1  # Skip the $
        offset += var_name_start
        
        return offset

    def _extract_variable_from_get_call(
        self, line: str, position: Position
    ) -> str | None:
        """
        Extract variable name from ->get() call context.
        
        Examples:
            $container->get('service') -> 'container'
            $this->container->get('service') -> 'container'
            $this->getContainer()->get('service') -> 'getContainer'
        """
        # Find ->get( before or at the cursor position
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None

        # Find the $ that starts the variable expression for THIS ->get() call
        # We need to find the $ between any preceding ; or statement boundary and get_pos
        
        # Look for statement boundaries before get_pos
        # Common boundaries: ; { } 
        last_boundary = -1
        for boundary_char in [';', '{', '}', '=']:
            pos = line.rfind(boundary_char, 0, get_pos)
            if pos > last_boundary:
                last_boundary = pos
        
        # Find $ after the boundary (or from start if no boundary)
        search_start = last_boundary + 1 if last_boundary >= 0 else 0
        dollar_pos = line.find("$", search_start, get_pos)
        
        if dollar_pos == -1:
            return None
        
        # Extract the variable expression from $ to ->get(
        var_expression = line[dollar_pos:get_pos]
        
        # Extract the main variable name (handle method chains)
        # $this->container->get() -> 'container'
        # $container->get() -> 'container'
        # $this->getContainer()->get() -> 'getContainer'

        # Split by -> and take the last identifier
        parts = re.split(r"->", var_expression)
        # Remove empty parts
        parts = [p for p in parts if p.strip()]
        if parts:
            # Get the last part and extract variable name
            last_part = parts[-1].strip().lstrip("$")
            var_match = re.search(r"^(\w+)", last_part)
            if var_match:
                return var_match.group(1)

        return None

    def _is_container_interface(self, type_str: str) -> bool:
        """Check if type represents a ContainerInterface."""
        container_types = [
            "ContainerInterface",
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "Drupal\\Core\\DependencyInjection\\ContainerInterface",
        ]

        type_lower = type_str.lower()
        return any(ct.lower() in type_lower for ct in container_types)

    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert Position to byte offset."""
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip("\n")) + 1

        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line].rstrip("\n")))

        return offset

    def _find_project_root(self, file_path) -> Path:
        """Find project root containing composer.json."""
        current = (
            file_path.parent if hasattr(file_path, "parent") else Path(file_path).parent
        )

        for _ in range(10):
            if (current / "composer.json").exists():
                return current
            if current.parent == current:
                break
            current = current.parent

        return (
            file_path.parent if hasattr(file_path, "parent") else Path(file_path).parent
        )

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._type_cache.clear()
        self.context_detector.clear_cache()
