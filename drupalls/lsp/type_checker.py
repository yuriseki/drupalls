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

        # TODO: Remove these lines after finish debuguing.
        var_type = await self._query_variable_type(doc, position)
        self._type_cache[cache_key] = var_type

        if not var_type:
            # Fallback heuristics
            if var_name.lower() == "container":
                return True
            return False

        return self._is_container_interface(var_type)

    async def _query_variable_type(self, doc, position: Position) -> str | None:
        """Query Phpactor for variable type at position."""
        from pathlib import Path

        file_path = Path(doc.uri.replace("file://", ""))
        offset = self._position_to_offset(doc.lines, position)
        working_dir = self._find_project_root(file_path)

        type_info = await self.phpactor.offset_info(file_path, offset, working_dir)
        if type_info:
            if type_info.type_name and type_info.type_name != "<missing>":
                var_type = type_info.type_name
            else:
                var_type = type_info.class_type
        else:
            var_type = None

        return var_type

    def _extract_variable_from_get_call(
        self, line: str, position: Position
    ) -> str | None:
        """
        Extract variable name from ->get() call context.
        """
        # Find ->get( before or at the cursor position
        # Include the current character in case cursor is on the '('
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None

        # Find variable before ->
        arrow_pos = line.rfind("->", 0, get_pos)

        if arrow_pos == -1:
            # Simple case: $var->get()
            dollar_pos = line.rfind("$", 0, get_pos)
            if dollar_pos == -1:
                return None
            var_start = dollar_pos
            var_expression = line[var_start:get_pos]
        else:
            # Find the start of the variable expression
            var_start = arrow_pos
            paren_depth = 0
            brace_depth = 0

            # Go backward, tracking parentheses and braces
            for i in range(arrow_pos - 1, -1, -1):
                char = line[i]

                if char == ")":
                    paren_depth += 1
                elif char == "}":
                    brace_depth += 1
                elif char == "{":
                    brace_depth -= 1
                elif paren_depth == 0 and brace_depth == 0:
                    # Skip whitespace
                    if char.isspace():
                        continue
                    # Check for variable start patterns
                    if char in ["$", "a-z", "A-Z", "0-9", "_"] or (
                        char == ">" and i > 0 and line[i - 1] == "-"
                    ):
                        var_start = i
                    elif char not in ["$", "a-z", "A-Z", "0-9", "_", ">", "-"]:
                        # Hit a non-variable character, stop
                        break

            var_expression = line[var_start:get_pos]

        # Extract the main variable name (handle method chains)
        # $this->container->get() -> 'container'
        # $container->get() -> 'container'
        # $this->getContainer()->get() -> 'getContainer()'

        # Simple approach: take the last identifier before any method call
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
