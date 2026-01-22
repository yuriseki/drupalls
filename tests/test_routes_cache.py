"""
Comprehensive tests for drupalls/workspace/routes_cache.py

Tests all public and private functions with:
- Normal operation cases
- Edge cases and boundary conditions
- Error handling
- Type validation
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import types

from drupalls.workspace.routes_cache import (
    RouteDefinition,
    RoutesCache,
)

# --- Fixtures ---

@pytest.fixture
def sample_route_dict():
    """Sample parsed YAML route dict."""
    return {
        "example.route": {
            "path": "/example/{id}",
            "methods": ["GET", "POST"],
            "defaults": {"_controller": "Drupal\\example\\Controller::view", "_title": "Example"},
            "requirements": {"_permission": "access content"},
        },
        "simple.route": {
            "path": "/simple",
            "defaults": {"_controller": "Drupal\\simple\\Controller::main"},
            "requirements": {"_permission": "access content"},
        },
    }

@pytest.fixture
def sample_route_text():
    """YAML text for two routes."""
    return """
example.route:
  path: /example/{id}
  methods: [GET, POST]
  defaults:
    _controller: 'Drupal\\\\example\\\\Controller::view'
simple.route:
  path: /simple
  defaults:
    _controller: 'Drupal\\\\simple\\\\Controller::main'
"""

@pytest.fixture
def workspace_cache():
    """Mock WorkspaceCache with required attributes."""
    cache = Mock()
    cache.project_root = "/fake/project"
    cache.workspace_root = "/fake/project"
    cache.file_info = {}
    cache.server = None
    return cache

@pytest.fixture
def routes_cache(workspace_cache):
    """RoutesCache instance with mock workspace cache."""
    return RoutesCache(workspace_cache)

@pytest.fixture
def mock_server():
    """Mock server with window_log_message method."""
    server = Mock()
    server.window_log_message = Mock()
    return server

# --- RouteDefinition tests ---

class TestRouteDefinition:
    """Tests for RouteDefinition dataclass."""

    def test_post_init_sets_fields(self):
        rd = RouteDefinition(
            id="foo",
            description="desc",
            file_path=None,
            line_number=5,
            name="foo",
            path="/foo",
            methods=["GET"],
            defaults={"_controller": "TestController"},
            requirements={"_permission": "access content"},
            file="some/file.yml",
            line=5,
        )
        assert rd.id == "foo"
        assert rd.description == "/foo"
        assert rd.file_path == Path("some/file.yml")
        assert rd.line_number == 5
        assert rd.methods == ["GET"]
        assert rd.controller == "TestController"
        assert rd.permission == "access content"

    def test_methods_defaults_to_empty_list(self):
        rd = RouteDefinition(
            id="bar",
            description="desc",
            file_path=None,
            line_number=1,
            name="bar",
            path="/bar",
            methods=None,  # type: ignore
            defaults={},
            requirements={},
            file="",
            line=1,
        )
        assert isinstance(rd.methods, list)
        assert rd.methods == []

    def test_file_path_none_when_file_empty(self):
        rd = RouteDefinition(
            id="baz",
            description="desc",
            file_path=None,
            line_number=1,
            name="baz",
            path="/baz",
            methods=["GET"],
            defaults={},
            requirements={},
            file="",
            line=1,
        )
        assert rd.file_path is None

# --- RoutesCache core logic ---

class TestRoutesCache:
    """Tests for RoutesCache."""

    def test_init_sets_fields(self, workspace_cache):
        rc = RoutesCache(workspace_cache)
        assert rc._routes == {}
        assert rc.server == workspace_cache.server

    @patch("drupalls.workspace.routes_cache.Path.rglob")
    @patch.object(RoutesCache, "_parse_routing_file")
    @pytest.mark.asyncio
    async def test_scan_calls_parse_for_each_file(self, mock_parse, mock_rglob, routes_cache):
        mock_rglob.return_value = [Path("/fake/a.routing.yml"), Path("/fake/b.routing.yml")]
        await routes_cache.scan()
        assert mock_parse.call_count == 2
        mock_parse.assert_any_call("/fake/a.routing.yml")
        mock_parse.assert_any_call("/fake/b.routing.yml")

    @patch("drupalls.workspace.routes_cache.open", create=True)
    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_file_happy_path(self, mock_yaml, mock_open, routes_cache, sample_route_dict):
        mock_open.return_value.__enter__.return_value.read.return_value = "fake yaml"
        mock_yaml.return_value = sample_route_dict
        routes_cache._parse_routing_file("/fake/file.routing.yml")
        assert "example.route" in routes_cache._routes
        rd = routes_cache._routes["example.route"]
        assert rd.name == "example.route"
        assert rd.path == "/example/{id}"
        assert rd.methods == ["GET", "POST"]
        assert rd.controller == "Drupal\\example\\Controller::view"
        assert rd.form is None
        assert rd.title == "Example"
        assert rd.permission == "access content"
        assert rd.file == "/fake/file.routing.yml"

    @patch("drupalls.workspace.routes_cache.open", create=True)
    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_file_invalid_yaml(self, mock_yaml, mock_open, routes_cache):
        mock_open.return_value.__enter__.return_value.read.return_value = "bad yaml"
        mock_yaml.return_value = None
        routes_cache._parse_routing_file("/fake/invalid.routing.yml")
        assert routes_cache._routes == {}

    @patch("drupalls.workspace.routes_cache.open", create=True)
    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_file_handles_exception_and_logs(self, mock_yaml, mock_open, workspace_cache, mock_server):
        workspace_cache.server = mock_server
        routes_cache = RoutesCache(workspace_cache)
        mock_open.side_effect = Exception("fail open")
        routes_cache._parse_routing_file("/fail/file.routing.yml")
        assert mock_server.window_log_message.called
        args = mock_server.window_log_message.call_args[0][0]
        assert "Error parsing" in args.message

    def test_find_route_line_finds_correct_line(self, routes_cache):
        content = "foo.route:\n  path: /foo\nbar.route:\n  path: /bar"
        assert routes_cache._find_route_line(content, "bar.route") == 3
        assert routes_cache._find_route_line(content, "foo.route") == 1
        assert routes_cache._find_route_line(content, "baz.route") == 1

    def test_get_and_get_all(self, routes_cache, sample_route_dict):
        # Populate manually
        for name, info in sample_route_dict.items():
            routes_cache._routes[name] = RouteDefinition(
                id=name,
                description=info["path"],
                file_path=Path("/fake/file.yml"),
                line_number=1,
                name=name,
                path=info["path"],
                methods=info.get("methods", ["GET"]),
                defaults=info.get("defaults", {}),
                requirements=info.get("requirements", {}),
                file="/fake/file.yml",
                line=1,
            )
        assert routes_cache.get("example.route").name == "example.route"
        assert routes_cache.get("notfound") is None
        all_routes = routes_cache.get_all()
        assert isinstance(all_routes, dict)
        assert len(all_routes) == 2

    def test_search_and_sorting(self, routes_cache, sample_route_dict):
        for name, info in sample_route_dict.items():
            routes_cache._routes[name] = RouteDefinition(
                id=name,
                description=info["path"],
                file_path=Path("/fake/file.yml"),
                line_number=1,
                name=name,
                path=info["path"],
                methods=info.get("methods", ["GET"]),
                defaults=info.get("defaults", {}),
                requirements=info.get("requirements", {}),
                file="/fake/file.yml",
                line=1,
            )
        results = routes_cache.search("example")
        assert len(results) == 1
        assert results[0].name == "example.route"
        results = routes_cache.search("/")
        assert len(results) == 2
        # Test limit
        results = routes_cache.search("/", limit=1)
        assert len(results) == 1

    def test_get_route_and_get_all_routes(self, routes_cache, sample_route_dict):
        for name, info in sample_route_dict.items():
            routes_cache._routes[name] = RouteDefinition(
                id=name,
                description=info["path"],
                file_path=Path("/fake/file.yml"),
                line_number=1,
                name=name,
                path=info["path"],
                methods=info.get("methods", ["GET"]),
                defaults=info.get("defaults", {}),
                requirements=info.get("requirements", {}),
                file="/fake/file.yml",
                line=1,
            )
        assert routes_cache.get_route("simple.route").name == "simple.route"
        assert routes_cache.get_route("notfound") is None
        all_routes = routes_cache.get_all_routes()
        assert isinstance(all_routes, list)
        assert len(all_routes) == 2

    def test_update_from_text_sync_calls_parse(self, routes_cache):
        with patch.object(routes_cache, "_parse_routing_text") as mock_parse:
            routes_cache.update_from_text_sync("foo.routing.yml", "text")
            mock_parse.assert_called_once_with("foo.routing.yml", "text")
            routes_cache.update_from_text_sync("foo.txt", "text")
            # Should not call for non-routing.yml

    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_text_happy_path(self, mock_yaml, routes_cache, sample_route_dict):
        mock_yaml.return_value = sample_route_dict
        routes_cache._parse_routing_text("uri.routing.yml", "text")
        assert "example.route" in routes_cache._routes
        rd = routes_cache._routes["example.route"]
        assert rd.name == "example.route"
        assert rd.file == "uri.routing.yml"

    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_text_invalid_yaml(self, mock_yaml, routes_cache):
        mock_yaml.return_value = None
        routes_cache._parse_routing_text("uri.routing.yml", "text")
        assert routes_cache._routes == {}

    @patch("drupalls.workspace.routes_cache.yaml.safe_load")
    def test_parse_routing_text_handles_exception_and_logs(self, mock_yaml, workspace_cache, mock_server):
        workspace_cache.server = mock_server
        routes_cache = RoutesCache(workspace_cache)
        mock_yaml.side_effect = Exception("fail parse")
        routes_cache._parse_routing_text("uri.routing.yml", "text")
        assert mock_server.window_log_message.called
        args = mock_server.window_log_message.call_args[0][0]
        assert "Error parsing routing text" in args.message

    def test_invalidate_file_removes_routes(self, routes_cache, sample_route_dict):
        # Add two routes, one in /a.yml, one in /b.yml
        routes_cache._routes["a"] = RouteDefinition(
            id="a", description="/a", file_path=Path("/a.yml"), line_number=1,
            name="a", path="/a", methods=["GET"], defaults={}, requirements={}, file="/a.yml", line=1
        )
        routes_cache._routes["b"] = RouteDefinition(
            id="b", description="/b", file_path=Path("/b.yml"), line_number=1,
            name="b", path="/b", methods=["GET"], defaults={}, requirements={}, file="/b.yml", line=1
        )
        routes_cache.invalidate_file(Path("/a.yml"))
        assert "a" not in routes_cache._routes
        assert "b" in routes_cache._routes

    def test_register_text_sync_hooks_no_server(self, routes_cache):
        routes_cache.server = None
        routes_cache.register_text_sync_hooks()  # Should not error

    def test_register_text_sync_hooks_with_manager(self, routes_cache):
        text_sync = Mock()
        server = Mock()
        server.text_sync_manager = text_sync
        routes_cache.server = server
        routes_cache.register_text_sync_hooks()
        assert text_sync.add_on_save_hook.called
        assert text_sync.add_on_change_hook.called

    @pytest.mark.asyncio
    async def test_on_routing_file_change_and_save(self, routes_cache, mock_server):
        # Setup
        routes_cache.server = mock_server
        params = types.SimpleNamespace()
        params.text_document = types.SimpleNamespace(uri="foo.routing.yml")
        params.content_changes = [types.SimpleNamespace(text="route:\n  path: /foo")]
        # Patch update_from_text_sync
        with patch.object(routes_cache, "update_from_text_sync") as mock_update:
            await routes_cache._on_routing_file_change(params)
            mock_update.assert_called_once()
            assert mock_server.window_log_message.called

        # Test _on_routing_file_saved
        with patch.object(routes_cache, "invalidate_file") as mock_invalidate, \
             patch.object(routes_cache, "_parse_routing_file") as mock_parse:
            mock_invalidate.return_value = None
            mock_parse.return_value = None
            await routes_cache._on_routing_file_saved(params)
            assert mock_invalidate.called
            assert mock_parse.called
            assert mock_server.window_log_message.called

    @pytest.mark.asyncio
    async def test_on_routing_file_saved_handles_exception(self, routes_cache, mock_server):
        routes_cache.server = mock_server
        params = types.SimpleNamespace()
        params.text_document = types.SimpleNamespace(uri="foo.routing.yml")
        with patch.object(routes_cache, "invalidate_file", side_effect=Exception("fail")), \
             patch.object(routes_cache, "_parse_routing_file"):
            await routes_cache._on_routing_file_saved(params)
            assert mock_server.window_log_message.called
            args = mock_server.window_log_message.call_args[0][0]
            assert "Error updating routes cache" in args.message

    @pytest.mark.asyncio
    async def test_initialize_and_scan_files(self, routes_cache):
        with patch.object(routes_cache, "scan") as mock_scan:
            await routes_cache.initialize()
            mock_scan.assert_called_once()
            await routes_cache.scan_files()
            assert mock_scan.call_count == 2

    @pytest.mark.asyncio
    async def test_load_from_disk_and_save_to_disk(self, routes_cache, tmp_path):
        # Test save to disk
        routes_cache._routes["test.route"] = RouteDefinition(
            id="test.route", description="/test", file_path=Path("/test.yml"), line_number=1,
            name="test.route", path="/test", methods=["GET"], defaults={"_controller": "TestController"},
            requirements={"_permission": "access content"}, file="/test.yml", line=1
        )

        # Mock the cache_dir
        routes_cache.workspace_cache.cache_dir = tmp_path / ".drupalls" / "cache"

        await routes_cache.save_to_disk()

        # Check file was created
        cache_file = routes_cache.workspace_cache.cache_dir / "routes.json"
        assert cache_file.exists()

        # Clear routes and test load from disk
        routes_cache._routes.clear()
        result = await routes_cache.load_from_disk()
        assert result is True
        assert "test.route" in routes_cache._routes
        assert routes_cache._routes["test.route"].controller == "TestController"