"""
Tests for routing-related LSP capabilities.

Tests completion, hover, and definition for Drupal routes.
"""

import pytest
from unittest.mock import Mock, patch
from lsprotocol.types import (
    CompletionParams,
    CompletionItem,
    CompletionItemKind,
    HoverParams,
    DefinitionParams,
    Position,
    TextDocumentIdentifier,
)

from drupalls.lsp.capabilities.routing_capabilities import (
    RoutesCompletionCapability,
    RouteHandlerCompletionCapability,
    RouteMethodCompletionCapability,
    RoutesHoverCapability,
    RoutesDefinitionCapability,
)
from drupalls.workspace.routes_cache import RouteDefinition


@pytest.fixture
def mock_server():
    """Mock DrupalLanguageServer."""
    server = Mock()
    server.workspace = Mock()
    server.workspace.get_text_document = Mock()
    return server


@pytest.fixture
def workspace_cache():
    """Mock WorkspaceCache with routes and classes."""
    cache = Mock()
    routes_cache = Mock()
    classes_cache = Mock()

    # Create mock route definitions
    route1 = RouteDefinition(
        id="user.login",
        description="/user/login",
        file_path=Mock(),
        line_number=1,
        name="user.login",
        path="/user/login",
        methods=["GET", "POST"],
        defaults={"_controller": "Drupal\\User\\Controller::login"},
        requirements={"_permission": "access content"},
        file="/path/to/user.routing.yml",
        line=1,
    )

    route2 = RouteDefinition(
        id="admin.settings",
        description="/admin/config",
        file_path=Mock(),
        line_number=1,
        name="admin.settings",
        path="/admin/config",
        methods=["GET"],
        defaults={"_form": "Drupal\\Admin\\Form\\SettingsForm"},
        requirements={"_permission": "administer site configuration"},
        file="/path/to/admin.routing.yml",
        line=1,
    )

    routes_cache.get_all.return_value = {"user.login": route1, "admin.settings": route2}
    routes_cache.get.return_value = route1
    routes_cache.search.return_value = [route1]

    # Create mock class definitions
    from drupalls.workspace.classes_cache import ClassDefinition
    class1 = ClassDefinition(
        id="\\Drupal\\Test\\Controller",
        description="\\Drupal\\Test\\Controller",
        file_path=Mock(),
        line_number=1,
        namespace="\\Drupal\\Test",
        class_name="Controller",
        full_name="\\Drupal\\Test\\Controller",
        methods=["build", "create", "__invoke"],
    )

    classes_cache.get_all.return_value = {"\\Drupal\\Test\\Controller": class1}
    classes_cache.get_methods.return_value = ["build", "create", "__invoke"]

    cache.caches = {"routes": routes_cache, "classes": classes_cache}
    cache.workspace_root = "/workspace"
    return cache


@pytest.fixture
def routes_completion_capability(mock_server, workspace_cache):
    """RoutesCompletionCapability instance."""
    mock_server.workspace_cache = workspace_cache
    capability = RoutesCompletionCapability(mock_server)
    return capability


@pytest.fixture
def route_handler_completion_capability(mock_server, workspace_cache):
    """RouteHandlerCompletionCapability instance."""
    mock_server.workspace_cache = workspace_cache
    capability = RouteHandlerCompletionCapability(mock_server)
    return capability


@pytest.fixture
def route_method_completion_capability(mock_server, workspace_cache):
    """RouteMethodCompletionCapability instance."""
    mock_server.workspace_cache = workspace_cache
    capability = RouteMethodCompletionCapability(mock_server)
    return capability


@pytest.fixture
def routes_hover_capability(mock_server, workspace_cache):
    """RoutesHoverCapability instance."""
    mock_server.workspace_cache = workspace_cache
    capability = RoutesHoverCapability(mock_server)
    return capability


@pytest.fixture
def routes_definition_capability(mock_server, workspace_cache):
    """RoutesDefinitionCapability instance."""
    mock_server.workspace_cache = workspace_cache
    capability = RoutesDefinitionCapability(mock_server)
    return capability


class TestRoutesCompletionCapability:
    """Tests for RoutesCompletionCapability."""

    @pytest.mark.asyncio
    async def test_can_handle_route_patterns(self, routes_completion_capability):
        """Test context detection for route name completion."""
        # Mock document
        mock_doc = Mock()
        routes_completion_capability.server.workspace.get_text_document.return_value = mock_doc

        # Test various route patterns
        test_cases = [
            ("Url::fromRoute('", True),
            ("setRedirect('", True),
            ("router->match(", True),
            ("someOtherCall('", False),
            ("not a route call", False),
        ]

        for line_content, expected in test_cases:
            mock_doc.lines = [line_content]
            params = CompletionParams(
                text_document=TextDocumentIdentifier(uri="file.php"),
                position=Position(line=0, character=10)
            )

            result = await routes_completion_capability.can_handle(params)
            assert result == expected

    @pytest.mark.asyncio
    async def test_can_handle_skips_yaml_files(self, routes_completion_capability):
        """Test that YAML files are not handled by route name completion."""
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="routes.routing.yml"),
            position=Position(line=0, character=10)
        )

        result = await routes_completion_capability.can_handle(params)
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_provides_route_names(self, routes_completion_capability):
        """Test that completion provides route names with details."""
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=10)
        )

        result = await routes_completion_capability.complete(params)

        assert len(result.items) == 2
        assert result.items[0].label == "user.login"
        assert result.items[0].detail == "/user/login"
        assert "Handler:" in result.items[0].documentation
        assert result.items[1].label == "admin.settings"


class TestRouteHandlerCompletionCapability:
    """Tests for RouteHandlerCompletionCapability."""

    @pytest.mark.asyncio
    async def test_can_handle_yaml_handler_keys(self, route_handler_completion_capability):
        """Test context detection for handler completion in YAML."""
        mock_doc = Mock()
        route_handler_completion_capability.server.workspace.get_text_document.return_value = mock_doc

        test_cases = [
            ("  _controller: '\\Drupal\\", True),
            ("  _form: '\\Drupal\\", True),
            ("  _title_callback: '\\Drupal\\", True),
            ("  path: '/some/path'", False),
            ("  requirements:", False),
        ]

        for line_content, expected in test_cases:
            mock_doc.lines = [line_content]
            params = CompletionParams(
                text_document=TextDocumentIdentifier(uri="routes.routing.yml"),
                position=Position(line=0, character=10)
            )

            result = await route_handler_completion_capability.can_handle(params)
            assert result == expected

    @pytest.mark.asyncio
    async def test_can_handle_requires_yaml_files(self, route_handler_completion_capability):
        """Test that only YAML files are handled."""
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=10)
        )

        result = await route_handler_completion_capability.can_handle(params)
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_provides_namespace_suggestions(self, route_handler_completion_capability):
        """Test that completion provides Drupal namespace suggestions."""
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="routes.routing.yml"),
            position=Position(line=0, character=10)
        )

        result = await route_handler_completion_capability.complete(params)

        assert len(result.items) > 0
        # Check that we get namespace and class suggestions
        labels = [item.label for item in result.items]
        assert any("\\Drupal" in label for label in labels)


class TestRouteMethodCompletionCapability:
    """Tests for RouteMethodCompletionCapability."""

    @pytest.mark.asyncio
    async def test_can_handle_after_double_colon(self, route_method_completion_capability):
        """Test context detection for method completion after ::."""
        mock_doc = Mock()
        route_method_completion_capability.server.workspace.get_text_document.return_value = mock_doc

        test_cases = [
            ("  _controller: '\\Drupal\\Controller::", True),
            ("  _form: '\\Drupal\\Form::", True),
            ("  _title_callback: '\\Drupal\\Utils::", True),
            ("  _controller: '\\Drupal\\Controller'", False),
            ("  path: '/some/path'", False),
        ]

        for line_content, expected in test_cases:
            mock_doc.lines = [line_content]
            params = CompletionParams(
                text_document=TextDocumentIdentifier(uri="routes.routing.yml"),
                position=Position(line=0, character=10)
            )

            result = await route_method_completion_capability.can_handle(params)
            assert result == expected

    @pytest.mark.asyncio
    async def test_complete_provides_method_suggestions(self, route_method_completion_capability):
        """Test that completion provides common method names."""
        # Mock document with a line containing ::
        mock_doc = Mock()
        mock_doc.lines = ["  _controller: '\\Drupal\\Test\\Controller::'"]
        route_method_completion_capability.server.workspace.get_text_document.return_value = mock_doc

        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="routes.routing.yml"),
            position=Position(line=0, character=40)  # After ::
        )

        result = await route_method_completion_capability.complete(params)

        assert len(result.items) > 0
        method_names = [item.label for item in result.items]
        assert "build" in method_names
        assert "__invoke" in method_names
        assert all(item.kind == CompletionItemKind.Method for item in result.items)


class TestRoutesHoverCapability:
    """Tests for RoutesHoverCapability."""

    @pytest.mark.asyncio
    async def test_can_handle_route_names_in_quotes(self, routes_hover_capability):
        """Test hover detection for route names in quotes."""
        mock_doc = Mock()
        mock_doc.lines = ["Url::fromRoute('user.login')"]
        routes_hover_capability.server.workspace.get_text_document.return_value = mock_doc

        params = HoverParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=20)  # On 'user.login'
        )

        result = await routes_hover_capability.can_handle(params)
        assert result is True

    @pytest.mark.asyncio
    async def test_hover_provides_route_info(self, routes_hover_capability):
        """Test that hover provides detailed route information."""
        mock_doc = Mock()
        mock_doc.lines = ["Url::fromRoute('user.login')"]
        routes_hover_capability.server.workspace.get_text_document.return_value = mock_doc

        params = HoverParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=20)
        )

        result = await routes_hover_capability.hover(params)

        assert result is not None
        content = result.contents
        assert "**Route:** user.login" in content.value
        assert "**Path:** /user/login" in content.value
        assert "**Handler:**" in content.value


class TestRoutesDefinitionCapability:
    """Tests for RoutesDefinitionCapability."""

    @pytest.mark.asyncio
    async def test_can_handle_route_references(self, routes_definition_capability):
        """Test definition detection for route references."""
        mock_doc = Mock()
        mock_doc.lines = ["Url::fromRoute('user.login')"]
        routes_definition_capability.server.workspace.get_text_document.return_value = mock_doc

        params = DefinitionParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=20)
        )

        result = await routes_definition_capability.can_handle(params)
        assert result is True

    @pytest.mark.asyncio
    async def test_definition_navigates_to_yaml(self, routes_definition_capability):
        """Test that definition navigates to the YAML route definition."""
        mock_doc = Mock()
        mock_doc.lines = ["Url::fromRoute('user.login')"]
        routes_definition_capability.server.workspace.get_text_document.return_value = mock_doc

        params = DefinitionParams(
            text_document=TextDocumentIdentifier(uri="file.php"),
            position=Position(line=0, character=20)
        )

        result = await routes_definition_capability.definition(params)

        assert result is not None
        assert result.uri.startswith("file://")
        assert result.range.start.line >= 0