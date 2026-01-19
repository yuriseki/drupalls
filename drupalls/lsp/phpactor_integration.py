import asyncio
import re
from pathlib import Path
from lsprotocol.types import Position


class TypeChecker:
    """Handles type checking for variables in ->get() calls using Phpactor CLI."""

    def __init__(self):
        self._type_cache: dict[tuple, str | None] = {}

    def clear_cache(self):
        """Clear the type cache."""
        self._type_cache.clear()

    async def is_container_variable(self, doc, line: str, position: Position) -> bool:
        """Check if the variable in ->get() call is a ContainerInterface."""

        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False

        # Create cache key - include var_name for specificity
        cache_key = (doc.uri, position.line, var_name)

        # Check cache first
        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            # Query type using CLI approach
            var_type = await self._query_variable_type(doc, line, position)
            self._type_cache[cache_key] = var_type

        if not var_type:
            # Fallback: assume 'container' variables are ContainerInterface
            if var_name == "container":
                return True
            return False

        return self._is_container_interface(var_type)

    async def _query_variable_type(
        self, doc, line: str, position: Position
    ) -> str | None:
        """Query Phpactor CLI for variable type at position."""
        try:
            # Find the variable position to query for type
            var_position = self._find_variable_position(line, position)
            if var_position is None:
                return None

            # Convert position to byte offset
            offset = self._position_to_offset(doc.lines, var_position)

            # Find project root directory
            working_dir = self._find_project_root(doc.uri)

            # Run phpactor offset:info CLI command
            cmd = [
                "phpactor",
                "offset:info",
                "--working-dir",
                working_dir,
                doc.uri.replace("file://", ""),  # Remove file:// prefix
                str(offset),
            ]

            # Execute CLI command asynchronously
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                # Parse the CLI output for type information
                output = stdout.decode().strip()
                type_info = self._parse_cli_output(output)
                return type_info.get("type")
            else:
                return None

        except Exception:
            return None

    def _parse_cli_output(self, output: str) -> dict[str, str]:
        """Parse phpactor offset:info CLI output into key-value pairs."""
        lines = output.strip().split("\n")
        type_info = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                type_info[key.strip()] = value.strip()

        return type_info

    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert Position to byte offset in file."""
        # Calculate offset up to the target line
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i]) + 1  # +1 for newline

        # Add character offset within the line
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line]))

        return offset

    def _find_project_root(self, uri: str) -> str:
        """Find the project root directory containing composer.json."""
        file_path = Path(uri.replace("file://", ""))

        # Start from file directory and go up looking for composer.json
        current = file_path.parent
        for _ in range(10):  # Don't go up more than 10 levels
            if (current / "composer.json").exists():
                return str(current)
            current = current.parent

        # Fallback to file directory
        return str(file_path.parent)

    def _find_variable_position(self, line: str, position: Position) -> Position | None:
        """Find the position of the variable in a ->get() call."""
        # Find ->get( before the cursor
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

            # Return position at the start of the variable name
            return Position(line=position.line, character=dollar_pos + 1)
        else:
            # Complex case: find the variable before the last ->
            # For $this->container->get(), we want position at 'c' in 'container'
            var_end = arrow_pos

            # Go backward to find variable start
            for i in range(arrow_pos - 1, -1, -1):
                char = line[i]
                if char in ["$", ">", "-"]:
                    continue
                elif char in [" ", "\t"]:
                    # Found variable start
                    var_start = i + 1
                    # Return position in the middle of the variable
                    var_middle = var_start + (var_end - var_start) // 2
                    return Position(line=position.line, character=var_middle)
                elif not char.isalnum() and char not in ["_"]:
                    # Hit a non-variable character
                    var_start = i + 1
                    var_middle = var_start + (var_end - var_start) // 2
                    return Position(line=position.line, character=var_middle)

            # Fallback: return position near the arrow
            return Position(line=position.line, character=arrow_pos - 1)

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
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "ContainerInterface",
            "Drupal\\Core\\DependencyInjection\\Container",
            "Drupal\\Core\\DependencyInjection\\ContainerInterface",
        ]

        type_str_lower = type_str.lower()
        for container_type in container_types:
            if container_type.lower() in type_str_lower:
                return True

        return False
