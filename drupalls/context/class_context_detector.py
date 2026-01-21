import re
from pathlib import Path

from lsprotocol.types import Position

from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType
from drupalls.phpactor.client import PhpactorClient


class ClassContextDetector:
    """
    Detects PHP class context at a given cursor position.
    
    This class is responsible for determining what class the cursor
    is currently inside, and gathering all relevant information about
    that class including parent classes and interfaces.
    """
    
    def __init__(self, phpactor_client: PhpactorClient):
        """
        Initialize detector with Phpactor client.
        
        Args:
            phpactor_client: Configured PhpactorClient instance
        """
        self.phpactor = phpactor_client
        self._context_cache: dict[tuple[str, int], ClassContext] = {}
    
    async def get_class_at_position(
        self,
        uri: str,
        position: Position,
        doc_lines: list[str] | None = None
    ) -> ClassContext | None:
        """
        Get the class context at a specific cursor position.
        
        Args:
            uri: Document URI (file://...)
            position: Cursor position (line, character)
            doc_lines: Optional document lines for offset calculation
        
        Returns:
            ClassContext if cursor is inside a class, None otherwise
        """
        file_path = Path(uri.replace("file://", ""))
        
        if not file_path.exists() or not file_path.suffix == ".php":
            return None
        
        # Check cache
        cache_key = (uri, position.line)
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
        
        # Read file if lines not provided
        if doc_lines is None:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    doc_lines = f.readlines()
            except Exception:
                return None
        
        # First, find if we're inside a class using regex
        class_info = self._find_enclosing_class(doc_lines, position.line)
        if class_info is None:
            return None
        
        class_name, class_line = class_info
        
        # Calculate offset to class declaration
        offset = self._position_to_offset(doc_lines, Position(line=class_line, character=0))
        
        # Find project root
        working_dir = self._find_project_root(file_path)
        
        # Get class reflection from Phpactor
        reflection = await self.phpactor.class_reflect(
            file_path, offset, working_dir
        )
        
        if reflection is None:
            # Fallback: create basic context from regex parsing
            context = self._create_context_from_regex(
                file_path, doc_lines, class_line, class_name
            )
        else:
            # Get full hierarchy
            hierarchy = await self.phpactor.get_class_hierarchy(
                reflection.fqcn, working_dir
            )
            
            context = ClassContext(
                fqcn=reflection.fqcn,
                short_name=reflection.short_name,
                file_path=file_path,
                class_line=class_line,
                parent_classes=hierarchy,
                interfaces=reflection.interfaces,
                traits=reflection.traits,
                methods=reflection.methods,
                properties=reflection.properties
            )
        
        # Check for ContainerInjectionInterface
        context.has_container_injection = any(
            "ContainerInjectionInterface" in iface
            for iface in context.interfaces
        )
        
        # Cache the result
        self._context_cache[cache_key] = context
        
        return context
    
    def _find_enclosing_class(
        self,
        lines: list[str],
        cursor_line: int
    ) -> tuple[str, int] | None:
        """
        Find the class declaration that encloses the cursor position.
        
        Uses bracket counting to determine class boundaries.
        
        Args:
            lines: Document lines
            cursor_line: Current cursor line (0-indexed)
        
        Returns:
            Tuple of (class_name, class_declaration_line) or None
        """
        # Pattern for class/interface/trait declaration
        class_pattern = re.compile(
            r"^\s*(final\s+|abstract\s+)?"
            r"(class|interface|trait)\s+"
            r"(\w+)"
        )
        
        # Search backwards from cursor to find class declaration
        brace_count = 0
        in_string = False
        
        for line_num in range(cursor_line, -1, -1):
            line = lines[line_num] if line_num < len(lines) else ""
            
            # Skip counting in strings (simplified)
            for char in reversed(line):
                if char == '}' and not in_string:
                    brace_count += 1
                elif char == '{' and not in_string:
                    brace_count -= 1
            
            # Check for class declaration
            match = class_pattern.search(line)
            if match:
                # If brace_count <= 0, we're inside this class
                if brace_count <= 0:
                    return (match.group(3), line_num)
                # Otherwise, continue searching (nested class case)
                brace_count = 0  # Reset for outer class
        
        return None
    
    def _create_context_from_regex(
        self,
        file_path: Path,
        lines: list[str],
        class_line: int,
        class_name: str
    ) -> ClassContext:
        """
        Create ClassContext using regex parsing when Phpactor fails.
        
        This is a fallback that provides basic information.
        """
        # Try to extract extends/implements from declaration
        declaration = ""
        for i in range(class_line, min(class_line + 5, len(lines))):
            declaration += lines[i]
            if "{" in lines[i]:
                break
        
        # Extract parent class
        extends_match = re.search(r"extends\s+([\w\\]+)", declaration)
        parent = [extends_match.group(1)] if extends_match else []
        
        # Extract interfaces
        implements_match = re.search(r"implements\s+([\w\\,\s]+)", declaration)
        interfaces: list[str] = []
        if implements_match:
            interfaces = [
                i.strip() 
                for i in implements_match.group(1).split(",")
            ]
        
        # Try to determine FQCN from namespace
        namespace = ""
        for line in lines[:class_line]:
            ns_match = re.search(r"namespace\s+([\w\\]+)", line)
            if ns_match:
                namespace = ns_match.group(1)
                break
        
        fqcn = f"{namespace}\\{class_name}" if namespace else class_name
        
        return ClassContext(
            fqcn=fqcn,
            short_name=class_name,
            file_path=file_path,
            class_line=class_line,
            parent_classes=parent,
            interfaces=interfaces
        )
    
    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert LSP Position to byte offset."""
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip('\n')) + 1
        
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line].rstrip('\n')))
        
        return offset
    
    def _find_project_root(self, file_path: Path) -> Path:
        """Find project root by looking for composer.json."""
        current = file_path.parent
        
        for _ in range(10):
            if (current / "composer.json").exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        
        return file_path.parent
    
    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._context_cache.clear()

