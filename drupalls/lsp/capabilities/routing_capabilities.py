"""
Routing-related LSP capabilities.

Provides completion, hover, and definition for Drupal routes and route handlers.
"""

import os
import re
from pathlib import Path
from typing import cast
from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    Hover,
    HoverParams,
    Location,
    LogMessageParams,
    MarkupContent,
    MarkupKind,
    MessageType,
    Position,
    Range,
    ReferenceParams,
)
from pygls import workspace

from drupalls.lsp.capabilities.capabilities import (
    CompletionCapability,
    DefinitionCapability,
    HoverCapability,
    ReferencesCapability,
)
from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.workspace.routes_cache import RouteDefinition, RoutesCache


# Route name completion patterns (in PHP code)
ROUTE_NAME_PATTERNS = [
    re.compile(r"fromRoute\(['\"]"),
    re.compile(r"setRedirect\(['\"]"),
    re.compile(r"redirect\(['\"]"),
    re.compile(r"Url::fromRoute\(['\"]"),
    re.compile(r"router.*match\("),
]

# Route handler patterns (in YAML)
ROUTE_HANDLER_KEYS = ['_controller:', '_form:', '_title_callback:']


class RoutesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal route names in PHP code."""

    @property
    def name(self) -> str:
        return "routes_completion"

    @property
    def description(self) -> str:
        return "Autocomplete Drupal route names in PHP routing calls"

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is in a route name context in PHP code."""
        # Skip YAML files (handled by other capabilities)
        if params.text_document.uri.endswith('.routing.yml'):
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line: str = doc.lines[params.position.line]

        # Check for route name patterns
        return any(pattern.search(line) for pattern in ROUTE_NAME_PATTERNS)

    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide route name completions."""
        if not self.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])

        routes_cache = self.workspace_cache.caches.get("routes")
        if not routes_cache:
            return CompletionList(is_incomplete=False, items=[])

        all_routes: dict[str, RouteDefinition] = routes_cache.get_all()  # type: ignore

        items = []
        for route_name, route_def_base in all_routes.items():
            # Cast to RouteDefinition to access specific attributes
            route_def = cast(RouteDefinition, route_def_base)

            # Get relative path for display
            file_path_str = "unknown"
            if route_def.file_path:
                try:
                    relative = route_def.file_path.relative_to(
                        self.workspace_cache.workspace_root
                    )
                    file_path_str = str(relative)
                except ValueError:
                    file_path_str = str(route_def.file_path)

            # Create documentation with route details
            doc_lines = [f"**Path:** {route_def.path}"]  # type: ignore[attr]
            if route_def.handler_class:  # type: ignore[attr]
                doc_lines.append(f"**Handler:** {route_def.handler_class}")  # type: ignore[attr]
            if route_def.permission:  # type: ignore[attr]
                doc_lines.append(f"**Permission:** {route_def.permission}")  # type: ignore[attr]
            if route_def.methods != ["GET"]:  # type: ignore[attr]
                doc_lines.append(f"**Methods:** {', '.join(route_def.methods)}")  # type: ignore[attr]
            doc_lines.append(f"**Defined in:** {file_path_str}")

            items.append(
                CompletionItem(
                    label=route_def.name,  # type: ignore
                    kind=CompletionItemKind.Value,
                    detail=route_def.path,  # type: ignore
                    documentation="\n".join(doc_lines),
                    insert_text=route_name,
                )
            )

        return CompletionList(is_incomplete=False, items=items)


class RouteHandlerCompletionCapability(CompletionCapability):
    """Provides completion for PHP namespaces/classes in route handlers (YAML)."""

    @property
    def name(self) -> str:
        return "route_handler_completion"

    @property
    def description(self) -> str:
        return "Autocomplete PHP namespaces in routing.yml handler definitions"

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is in a route handler context in YAML."""
        if not params.text_document.uri.endswith('.routing.yml'):
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line: str = doc.lines[params.position.line]

        # Check if line contains handler keys
        return any(key in line for key in ROUTE_HANDLER_KEYS)

    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide PHP namespace/class completions for route handlers."""
        # For now, provide basic Drupal namespace suggestions
        # TODO: Integrate with Phpactor for full class completion
        drupal_namespaces = [
            "\\Drupal\\",
            "\\Drupal\\Core\\",
            "\\Drupal\\Component\\",
            "\\Symfony\\Component\\",
        ]

        items = []
        for ns in drupal_namespaces:
            items.append(
                CompletionItem(
                    label=ns,
                    kind=CompletionItemKind.Module,
                    detail="PHP namespace",
                    insert_text=ns,
                )
            )

        return CompletionList(is_incomplete=False, items=items)


class RouteMethodCompletionCapability(CompletionCapability):
    """Provides completion for method names after :: in route handlers."""

    @property
    def name(self) -> str:
        return "route_method_completion"

    @property
    def description(self) -> str:
        return "Autocomplete method names in routing.yml handler definitions"

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is after :: in a route handler."""
        if not params.text_document.uri.endswith('.routing.yml'):
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line: str = doc.lines[params.position.line]

        # Check if after :: and in handler context
        return ('::' in line and
                any(key in line for key in ROUTE_HANDLER_KEYS))

    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide method name completions after ::."""
        # For now, provide common Drupal controller method names
        # TODO: Integrate with Phpactor for actual class method introspection
        common_methods = [
            "build",
            "content",
            "__invoke",
            "create",
            "edit",
            "delete",
            "view",
            "list",
            "overview",
            "settings",
            "configure",
        ]

        items = []
        for method in common_methods:
            items.append(
                CompletionItem(
                    label=method,
                    kind=CompletionItemKind.Method,
                    detail="Controller method",
                    insert_text=method,
                )
            )

        return CompletionList(is_incomplete=False, items=items)


class RoutesHoverCapability(HoverCapability):
    """Provides hover information for Drupal routes."""

    @property
    def name(self) -> str:
        return "routes_hover"

    @property
    def description(self) -> str:
        return "Show information about Drupal routes on hover"

    async def can_handle(self, params: HoverParams) -> bool:
        """Check if hovering over a route reference."""
        if not self.workspace_cache:
            return False

        routes_cache = self.workspace_cache.caches.get("routes")
        if not routes_cache:
            return False

        # Check if hovering over route name in quotes
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        # Extract word at cursor position
        word = self._get_word_at_position(doc, params.position)
        if not word:
            return False

        # Check if it's a route name
        return routes_cache.get(word) is not None

    async def hover(self, params: HoverParams) -> Hover | None:
        """Provide hover information for routes."""
        if not self.workspace_cache:
            return None

        routes_cache = self.workspace_cache.caches.get("routes")
        if not routes_cache:
            return None

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        word = self._get_word_at_position(doc, params.position)
        if not word:
            return None

        route_def = routes_cache.get(word)
        if not route_def:
            return None

        # Build hover content
        lines = [f"**Route:** {route_def.name}", f"**Path:** {route_def.path}"]

        if route_def.handler_class:
            lines.append(f"**Handler:** `{route_def.handler_class}`")

        if route_def.permission:
            lines.append(f"**Permission:** {route_def.permission}")

        if route_def.methods != ["GET"]:
            lines.append(f"**Methods:** {', '.join(route_def.methods)}")

        if route_def.file_path:
            try:
                relative = route_def.file_path.relative_to(
                    self.workspace_cache.workspace_root
                )
                lines.append(f"**Defined in:** {relative}")
            except ValueError:
                lines.append(f"**Defined in:** {route_def.file_path}")

        return Hover(
            contents=MarkupContent(
                kind=MarkupKind.Markdown,
                value="\n".join(lines)
            )
        )

    def _get_word_at_position(self, doc, position: Position) -> str | None:
        """Extract the word at the given position."""
        line = doc.lines[position.line]
        # Simple word extraction (could be improved)
        words = re.findall(r"'([^']*)'|\"([^\"]*)\"", line)
        for word_tuple in words:
            word = word_tuple[0] or word_tuple[1]
            if word:
                return word
        return None


class RoutesDefinitionCapability(DefinitionCapability):
    """Provides go-to-definition for Drupal routes."""

    @property
    def name(self) -> str:
        return "routes_definition"

    @property
    def description(self) -> str:
        return "Navigate to Drupal route definitions"

    async def can_handle(self, params: DefinitionParams) -> bool:
        """Check if cursor is on a route reference that can be navigated to."""
        if not self.workspace_cache:
            return False

        routes_cache = self.workspace_cache.caches.get("routes")
        if not routes_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        word = self._get_word_at_position(doc, params.position)
        if not word:
            return False

        route_def = routes_cache.get(word)
        return route_def is not None

    async def definition(self, params: DefinitionParams) -> Location | None:
        """Navigate to route definition in YAML file."""
        if not self.workspace_cache:
            return None

        routes_cache = self.workspace_cache.caches.get("routes")
        if not routes_cache:
            return None

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        word = self._get_word_at_position(doc, params.position)
        if not word:
            return None

        route_def = routes_cache.get(word)
        if not route_def or not route_def.file_path:
            return None

        return Location(
            uri=f"file://{route_def.file_path}",
            range=Range(
                start=Position(line=route_def.line_number - 1, character=0),
                end=Position(line=route_def.line_number - 1, character=100)  # Rough estimate
            )
        )

    def _get_word_at_position(self, doc, position: Position) -> str | None:
        """Extract the word at the given position."""
        line = doc.lines[position.line]
        # Simple word extraction (could be improved)
        words = re.findall(r"'([^']*)'|\"([^\"]*)\"", line)
        for word_tuple in words:
            word = word_tuple[0] or word_tuple[1]
            if word:
                return word
        return None