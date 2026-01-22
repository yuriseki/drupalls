"""
RoutesCache: In-memory cache for Drupal route definitions.

This module provides fast lookups of route names, paths, and controllers
by scanning and parsing all *.routing.yml files in the workspace.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence
import yaml
import json
from datetime import datetime

from drupalls.workspace.cache import (
    CachedWorkspace,
    WorkspaceCache,
    CachedDataBase,
    FileInfo,
)
from drupalls.workspace.utils import calculate_file_hash

@dataclass
class RouteDefinition(CachedDataBase):
    id: str
    description: str
    file_path: Path | None
    line_number: int
    name: str
    path: str
    methods: list[str] = field(default_factory=list)
    defaults: dict[str, str] = field(default_factory=dict)
    requirements: dict[str, str] = field(default_factory=dict)
    file: str = ""
    line: int = 1

    def __post_init__(self):
        # Defensive: Ensure collections are always proper types
        if self.methods is None:
            object.__setattr__(self, 'methods', [])
        if self.defaults is None:
            object.__setattr__(self, 'defaults', {})
        if self.requirements is None:
            object.__setattr__(self, 'requirements', {})
        # Set base fields for CachedDataBase compatibility
        object.__setattr__(self, 'id', self.name)
        object.__setattr__(self, 'description', self.path)
        object.__setattr__(self, 'file_path', Path(self.file) if self.file else None)
        object.__setattr__(self, 'line_number', self.line)

    @property
    def controller(self) -> str | None:
        """Get the controller if this route has one."""
        return self.defaults.get('_controller')

    @property
    def form(self) -> str | None:
        """Get the form class if this route has one."""
        return self.defaults.get('_form')

    @property
    def title(self) -> str | None:
        """Get the title (static or callback)."""
        return self.defaults.get('_title') or self.defaults.get('_title_callback')

    @property
    def permission(self) -> str | None:
        """Get the required permission if any."""
        return self.requirements.get('_permission')

    @property
    def handler_class(self) -> str | None:
        """Get the primary handler class (controller or form)."""
        return self.controller or self.form

class RoutesCache(CachedWorkspace):
    """
    Cache for Drupal route definitions with real-time update hooks.
    """
    def __init__(self, workspace_cache: WorkspaceCache) -> None:
        super().__init__(workspace_cache)
        self._routes: dict[str, RouteDefinition] = {}
        self.server = workspace_cache.server

    async def initialize(self):
        await self.scan()

    async def scan(self):
        self._routes.clear()
        for yml_path in Path(self.workspace_root).rglob("*.routing.yml"):
            self._parse_routing_file(str(yml_path))

    def _parse_routing_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                return  # Defensive: skip invalid files
            for i, (route_name, route_info) in enumerate(data.items()):
                path = route_info.get("path", "")
                methods = route_info.get("methods", ["GET"])
                if isinstance(methods, str):
                    methods = [methods]
                defaults = route_info.get("defaults", {})
                requirements = route_info.get("requirements", {})
                line = self._find_route_line(content, route_name)
                self._routes[route_name] = RouteDefinition(
                    id=route_name,
                    description=path,
                    file_path=Path(file_path),
                    line_number=line,
                    name=route_name,
                    path=path,
                    methods=methods,
                    defaults=defaults,
                    requirements=requirements,
                    file=file_path,
                    line=line,
                )
        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error parsing {file_path}: {e}"
                    )
                )

    def _find_route_line(self, content: str, route_name: str) -> int:
        for idx, line in enumerate(content.splitlines(), 1):
            if line.strip().startswith(f"{route_name}:"):
                return idx
        return 1

    def get(self, id: str) -> RouteDefinition | None:
        return self._routes.get(id)

    def get_all(self) -> Mapping[str, RouteDefinition]:
        return self._routes

    def search(self, query: str, limit: int = 50) -> Sequence[RouteDefinition]:
        query_lower = query.lower()
        results = []
        for name, route in self._routes.items():
            if query_lower in name.lower() or query_lower in route.path.lower():
                results.append(route)
        results.sort(key=lambda r: (not r.name.lower().startswith(query_lower), r.name))
        return results[:limit]

    def get_route(self, name: str) -> RouteDefinition | None:
        return self._routes.get(name)

    def get_all_routes(self) -> list[RouteDefinition]:
        return list(self._routes.values())

    def update_from_text_sync(self, uri: str, text: str) -> None:
        if uri.endswith(".routing.yml"):
            self._parse_routing_text(uri, text)

    def _parse_routing_text(self, uri: str, text: str) -> None:
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                return
            for route_name, route_info in data.items():
                path = route_info.get("path", "")
                methods = route_info.get("methods", ["GET"])
                if isinstance(methods, str):
                    methods = [methods]
                defaults = route_info.get("defaults", {})
                requirements = route_info.get("requirements", {})
                self._routes[route_name] = RouteDefinition(
                    id=route_name,
                    description=path,
                    file_path=Path(uri),
                    line_number=1,
                    name=route_name,
                    path=path,
                    methods=methods,
                    defaults=defaults,
                    requirements=requirements,
                    file=uri,
                    line=1,
                )
        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error parsing routing text from {uri}: {e}"
                    )
                )

    def invalidate_file(self, file_path: Path):
        file_path_str = str(file_path)
        self._routes = {
            name: route for name, route in self._routes.items()
            if route.file != file_path_str
        }

    def register_text_sync_hooks(self) -> None:
        if not self.server or not hasattr(self.server, "text_sync_manager"):
            return
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_routing_file_saved)
            text_sync.add_on_change_hook(self._on_routing_file_change)

    async def _on_routing_file_change(self, params):
        uri = params.text_document.uri
        if not uri.endswith(".routing.yml"):
            return
        text = None
        if hasattr(params, "content_changes") and params.content_changes:
            text = params.content_changes[-1].text
        if text:
            self.update_from_text_sync(uri, text)
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated routes cache (change): {os.path.basename(uri)}"
                    )
                )

    async def _on_routing_file_saved(self, params):
        uri = params.text_document.uri
        if not uri.endswith(".routing.yml"):
            return
        file_path = Path(uri.replace("file://", ""))
        try:
            self.invalidate_file(file_path)
            self._parse_routing_file(str(file_path))
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated routes cache (save): {file_path.name}"
                    )
                )
        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating routes cache: {type(e).__name__}: {e}"
                    )
                )

    async def load_from_disk(self) -> bool:
        """
        Load cache from disk.

        Returns True if successful, False otherwise.
        """
        cache_file = self.workspace_cache.cache_dir / "routes.json"

        if not cache_file.exists():
            return False

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            # Check if cache is still valid
            cache_version = data.get("version", 0)
            if cache_version != 1:
                return False

            # Load routes
            routes_data = data.get("routes", {})
            for name, route_dict in routes_data.items():
                # Convert dict back to RouteDefinition
                self._routes[name] = RouteDefinition(
                    id=route_dict["id"],
                    description=route_dict["description"],
                    file_path=(
                        Path(route_dict["file_path"])
                        if route_dict.get("file_path")
                        else None
                    ),
                    line_number=route_dict["line_number"],
                    name=route_dict["name"],
                    path=route_dict["path"],
                    methods=route_dict.get("methods", []),
                    defaults=route_dict.get("defaults", {}),
                    requirements=route_dict.get("requirements", {}),
                    file=route_dict.get("file", ""),
                    line=route_dict.get("line", 1),
                )

            return True

        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error loading routes cache from disk: {e}"
                    )
                )
            return False

    async def save_to_disk(self):
        """Save cache to disk."""
        self.workspace_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.workspace_cache.cache_dir / "routes.json"

        try:
            data = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "routes": {
                    name: {
                        "id": route_def.id,
                        "description": route_def.description,
                        "file_path": (
                            str(route_def.file_path)
                            if route_def.file_path
                            else None
                        ),
                        "line_number": route_def.line_number,
                        "name": route_def.name,
                        "path": route_def.path,
                        "methods": route_def.methods,
                        "defaults": route_def.defaults,
                        "requirements": route_def.requirements,
                        "file": route_def.file,
                        "line": route_def.line,
                    }
                    for name, route_def in self._routes.items()
                },
            }

            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error saving routes cache to disk: {e}"
                    )
                )

    async def scan_files(self):
        await self.scan()
