"""
Workspace Cache Manager for DrupalLS

This module manages all parsed data for the workspace in memory.
It provides fast access to services, hooks, config schemas, etc.

Design Principles:
1. In-memory first (fast access)
2. Lazy loading (parse only what's needed)
3. Incremental updates (re-parse only changed files)
4. Optional disk persistence (speed up restarts)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer


@dataclass
class FileInfo:
    """Track file state for cache invalidation."""

    path: Path
    hash: str
    last_modified: datetime


@dataclass
class CachedDataBase:
    id: str
    description: str
    file_path: Path | None
    line_number: int


class CachedWorkspace(ABC):
    """Abstract base class for workspace caches."""

    def __init__(
        self,
        workspace_cache: WorkspaceCache,
        server: DrupalLanguageServer | None = None
    ) -> None:
        self.workspace_cache = workspace_cache
        self.server = server
        self.project_root = workspace_cache.project_root
        self.workspace_root = workspace_cache.workspace_root
        self.file_info = workspace_cache.file_info

    def register_text_sync_hooks(self) -> None:
        """
        Register text sync hooks to keep cache up-to-date.

        Override in subclasses to register hooks with TextSyncManager
        that update the cache when relevant files change.
        """
        pass

    @abstractmethod
    async def initialize(self):
        pass

    @abstractmethod
    def get(self, id: str) -> CachedDataBase | None:
        pass

    @abstractmethod
    def get_all(self) -> Mapping[str, CachedDataBase]:
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 50) -> Sequence[CachedDataBase]:
        pass

    # ===== Cache Persistence =====
    @abstractmethod
    async def load_from_disk(self) -> bool:
        pass

    @abstractmethod
    async def save_to_disk(self):
        pass

    @abstractmethod
    async def scan(self):
        pass

    @abstractmethod
    def invalidate_file(self, file_path: Path):
        """
        Invalidate cache for a specific file.

        Call this when a file changes (from didChange notification).
        """
        pass


class WorkspaceCache:
    """
    Central cache for all parsed workspace data.

    This is a singleton that stores:
    - Services from *.services.yml files
    - Hooks from core API files
    - Config schemas
    - Entity types
    - Plugin definitions

    Usage:
        cache = WorkspaceCache(workspace_root)
        await cache.initialize()

        # Get services
        services = cache.get_services()

        # Get specific service
        service = cache.get_service('entity_type.manager')

        # Invalidate when file changes
        cache.invalidate_file(file_path)
    """

    def __init__(
        self,
        project_root: Path,
        workspace_root: Path,
        caches: dict[str, CachedWorkspace] | None = None,
        server: DrupalLanguageServer | None = None,
    ):
        from drupalls.workspace.services_cache import ServicesCache
        from drupalls.workspace.routes_cache import RoutesCache

        self.project_root = project_root
        self.workspace_root = workspace_root # Drupal root directory
        self.server = server

        # In-memory caches
        self.file_info: dict[Path, FileInfo] = {}
        self.caches = caches or {
            "services": ServicesCache(self),
            "routes": RoutesCache(self)
        }

        # State
        self._initialized = False
        self._last_scan: datetime | None = None

        # Configuration
        self.cache_dir = project_root / ".drupalls" / "cache"
        self.enable_disk_cache = True  # Optional: persist to disk

    async def initialize(self):
        """
        Initialize the cache by scanning the workspace.

        This is called once when the workspace is opened.
        """
        if self._initialized:
            return

        # Register hooks for all caches
        self._register_text_sync_hooks()

        # Try to load from disk cache first
        if self.enable_disk_cache and await self._load_from_disk():
            self._initialized = True
            return

        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.initialize()

        # Scan workspace and build cache
        await self._scan_workspace()

        # Save to disk for next time
        if self.enable_disk_cache:
            await self._save_to_disk()

        self._initialized = True
        self._last_scan = datetime.now()

    async def _scan_workspace(self):
        """Scan workspace and populate all caches."""
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.scan()

    def _register_text_sync_hooks(self) -> None:
        """Register text sync hooks for all caches."""
        for cache in self.caches.values():
            if isinstance(cache, CachedWorkspace):
                cache.register_text_sync_hooks()

    def invalidate_file(self, file_path: Path):
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                c.invalidate_file(file_path)

    # ===== Cache Persistence =====
    async def _load_from_disk(self) -> bool:
        result = False
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                if await c.load_from_disk():
                    result = True

        return result

    async def _save_to_disk(self):
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.save_to_disk()
