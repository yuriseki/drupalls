from typing import TYPE_CHECKING
import re

from lsprotocol.types import Position
from pygls.workspace import TextDocument

from drupalls.lsp.phpactor_rpc import PhpactorRpcClient


class TypeChecker:
    """Handles type checking for variables in ->get() calls."""

    def __init__(self, phpactor_client: PhpactorRpcClient):
        self.phpactor_client = phpactor_client
        self._type_cache = {}  # simple cache for performance

    async def is_container_variable(
        self, doc: TextDocument, line: str, position: Position
    ) -> bool:
        """
        Check if the variable in ->get() call is a ContainerInterface.
        """
        # Extract variable name from ->get() context
        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False

        # Create a cache key
        cache_key = (doc.uri, position.line, position.character)

        # Check cache first
        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            # Query Phpactor for type
            var_type = await self._query_variable_type(doc, position)

        if not var_type:
            return False

        return self._is_container_interface(var_type)

    def _extract_variable_from_get_call(
        self, line: str, position: Position
    ) -> str | None:
        """
        Extract variable name from ->get() call context.
        """
        # Find ->get( before the cursor
        get_pos = line.rfind("->get(", 0, position.character)
        if get_pos == -1:
            return None

        # Find variable before ->
        arrow_pos = line.rfind("->", 0, get_pos + 2)
        if arrow_pos == -1:
            return None

        # Extract variable (handle $this->var and $var patterns)
        # Improved implementation: Parse backward from arrow_pos to find the variable
        # Handle: $var, $this->var, $obj->method()->var, etc.

        # Find the start of the variable expression
        var_start = arrow_pos
        paren_depth = 0
        brace_depth = 0

        # Go backward, tracking parentheses and braces
        for i in range(arrow_pos - 1, -1, -1):
            char = line[i]

            if char == ")":
                paren_depth += 1
            elif char == "(":
                paren_depth -= 1
            elif char == "}":
                brace_depth += 1
            elif char == "{":
                brace_depth -= 1
            elif paren_depth == 0 and brace_depth == 0:
                # Check for variable start patterns
                if char in ["$", "a-z", "A-Z", "0-9", "_"] or (
                    char == ">" and i > 0 and line[i - 1] == "-"
                ):
                    var_start = i
                elif char not in ["$", "a-z", "A-Z", "0-9", "_", ">", "-"]:
                    # Hit a non-variable character, stop
                    break

        var_expression = line[var_start:arrow_pos].strip()

        # Extract the main variable name (handle method chains)
        # $this->container->get() -> 'container'
        # $container->get() -> 'container'
        # $this->getContainer()->get() -> 'getContainer()'

        # Simple approach: take the last identifier before any method call
        parts = re.split(r"->", var_expression)
        if parts:
            # Get the last part and extract variable name
            last_part = parts[-1]
            var_match = re.search(r"^(\w+)", last_part.strip())
            if var_match:
                return var_match.group(1)

        return None

    async def _query_variable_type(self, doc: TextDocument, position: Position) -> str | None:
        """
        Query Phpactor for variable type at location.
        """
        if not self.phpactor_client:
            return None

        try:
            file_path = doc.uri.replace("file://", "")
            return await self.phpactor_client.query_type_at_position(file_path, position.line, position.character)
        except Exception:
            return None
       

    def _is_container_interface(self, type_str: str) -> bool:
        """
        Check if the type represents a ContainerInterface.
        """

        container_types = [
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "ContainerInterface",
            # Add Drupal-specific types
            "Drupal\\Core\\DependencyInjection\\Container",
            "Drupal\\Core\\DependencyInjection\\ContainerInterface",
        ]

        # Check for exact matches or inheritance
        for container_type in container_types:
            if container_type in type_str:
                return True

        return False
