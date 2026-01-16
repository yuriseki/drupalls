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


class CachedWorkspace(ABC):
    def __init__(self, workspace_cache: WorkspaceCache) -> None:
        self.workspace_cache = workspace_cache
        self.project_root = workspace_cache.project_root
        self.workspace_root = workspace_cache.workspace_root
        self.file_info = workspace_cache.file_info

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
    def load_from_disk(self) -> bool:
        pass

    @abstractmethod
    def save_to_disk(self):
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
        self, project_root: Path, workspace_root: Path, caches: dict[str, CachedWorkspace] | None = None
    ):
        from drupalls.workspace.services_cache import ServicesCache

        self.project_root = project_root
        self.workspace_root = workspace_root

        # In-memory caches
        self.file_info: dict[Path, FileInfo] = {}
        self.caches = caches or {
            "services": ServicesCache(self)
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

        # Try to load from disk cache first
        if self.enable_disk_cache and self._load_from_disk():
            self._initialized = True
            return

        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.initialize()

        # Scan workspace and build cache
        await self._scan_workspace()

        # Save to disk for next time
        if self.enable_disk_cache:
            self._save_to_disk()

        self._initialized = True
        self._last_scan = datetime.now()

    async def _scan_workspace(self):
        """Scan workspace and populate all caches."""
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                await c.scan()

    def invalidate_file(self, file_path: Path):
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                c.invalidate_file(file_path)

    # ===== Cache Persistence =====
    def _load_from_disk(self) -> bool:
        result = False
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                if c.load_from_disk():
                    result = True

        return result

    def _save_to_disk(self):
        for c in self.caches.values():
            if isinstance(c, CachedWorkspace):
                c.save_to_disk()
