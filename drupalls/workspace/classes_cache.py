"""
ClassesCache: In-memory cache for Drupal PHP class definitions.

This module provides fast lookups of PHP classes, methods, and namespaces
by scanning and parsing all PHP files in the workspace.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Mapping, Sequence
import json

from drupalls.workspace.cache import (
    CachedDataBase,
    CachedWorkspace,
    FileInfo,
    WorkspaceCache,
)
from drupalls.workspace.utils import calculate_file_hash


@dataclass
class ClassDefinition(CachedDataBase):
    """Represents a parsed PHP class definition."""

    id: str
    description: str
    file_path: Path | None
    line_number: int
    namespace: str = ""
    class_name: str = ""
    full_name: str = ""  # namespace + class_name
    methods: list[str] = field(default_factory=list)

    def __post_init__(self):
        # Set base fields for CachedDataBase compatibility
        object.__setattr__(self, 'id', self.full_name or self.class_name)
        object.__setattr__(self, 'description', f"{self.namespace}\\{self.class_name}" if self.namespace else self.class_name)
        object.__setattr__(self, 'file_path', self.file_path)
        object.__setattr__(self, 'line_number', self.line_number)


class ClassesCache(CachedWorkspace):
    """Cache for PHP class definitions with method information."""

    def __init__(self, workspace_cache: WorkspaceCache) -> None:
        super().__init__(workspace_cache)
        self._classes: dict[str, ClassDefinition] = {}
        self.server = workspace_cache.server

        # PHP parsing patterns - simplified and more reliable
        self._namespace_pattern = re.compile(r'namespace\s+([^;]+);', re.IGNORECASE)
        self._class_pattern = re.compile(
            r'(?:abstract\s+|final\s+)?\s*'       # optional modifiers
            r'class\s+(\w+)'                      # class name
            r'(?:\s+extends\s+[^{\s]+)?'          # optional extends
            r'(?:\s+implements\s+[^}]+)?'         # optional implements
            r'\s*{',                              # opening brace
            re.IGNORECASE | re.DOTALL
        )

        self._method_pattern = re.compile(
            r'(public|protected|private)?\s*'      # visibility (captured)
            r'(?:static\s+)?'                      # static modifier
            r'(?:function\s+)(\w+)\s*\(',          # function name
            re.IGNORECASE
        )

    async def initialize(self):
        """Initialize the classes cache."""
        await self.scan()

    async def scan(self):
        """Scan all PHP files in Drupal-specific directories and populate the cache."""
        self._classes.clear()

        # Only scan Drupal-specific base directories
        base_dirs = ["core", "modules", "profiles", "themes"]

        # Find all PHP files
        php_files = []

        # Check if any of the base directories exist (indicates this is a real Drupal project)
        has_drupal_structure = any((self.workspace_root / base_dir).exists() for base_dir in base_dirs)

        if has_drupal_structure:
            # Scan only Drupal-specific directories
            for base_dir in base_dirs:
                base_path = self.workspace_root / base_dir
                if not base_path.exists():
                    continue

                # Special handling for core: scan core/modules and core/lib
                if base_dir == "core":
                    for sub_dir in ["modules", "lib"]:
                        core_path = base_path / sub_dir
                        if core_path.exists():
                            for root, dirs, files in os.walk(core_path):
                                # Skip common directories that don't contain classes
                                dirs[:] = [d for d in dirs if d not in {
                                    '.git', 'node_modules', 'vendor', 'sites', 'files',
                                    '.drupalls', 'css', 'js', 'images', 'libraries'
                                }]

                                for file in files:
                                    if file.endswith('.php'):
                                        php_files.append(Path(root) / file)
                else:
                    # For modules, profiles, themes: scan all subdirectories
                    for root, dirs, files in os.walk(base_path):
                        # Skip common directories that don't contain classes
                        dirs[:] = [d for d in dirs if d not in {
                            '.git', 'node_modules', 'vendor', 'sites', 'files',
                            '.drupalls', 'css', 'js', 'images', 'libraries'
                        }]

                        for file in files:
                            if file.endswith('.php'):
                                php_files.append(Path(root) / file)
        else:
            # Fallback for test environments: scan entire workspace
            for root, dirs, files in os.walk(self.workspace_root):
                # Skip common directories that don't contain classes
                dirs[:] = [d for d in dirs if d not in {
                    '.git', 'node_modules', 'vendor', 'sites', 'files',
                    '.drupalls', 'css', 'js', 'images', 'libraries'
                }]

                for file in files:
                    if file.endswith('.php'):
                        php_files.append(Path(root) / file)

        # Parse each PHP file
        for php_file in php_files:
            self._parse_php_file(php_file)

    def _parse_php_file(self, file_path: Path):
        """Parse a single PHP file for class definitions."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Find namespace first
            namespace = ""
            namespace_match = self._namespace_pattern.search(content)
            if namespace_match:
                namespace = namespace_match.group(1).strip()

            # Find all class definitions in the file
            for match in self._class_pattern.finditer(content):
                class_name = match.group(1)

                # Build full class name
                full_name = f"{namespace}\\{class_name}" if namespace else class_name

                # Find methods in this class
                methods = self._extract_methods(content, match.end())

                # Calculate line number
                line_number = content[:match.start()].count('\n') + 1

                # Create class definition
                class_def = ClassDefinition(
                    id=full_name,
                    description=f"{namespace}\\{class_name}" if namespace else class_name,
                    file_path=file_path,
                    line_number=line_number,
                    namespace=namespace,
                    class_name=class_name,
                    full_name=full_name,
                    methods=methods,
                )

                self._classes[full_name] = class_def

        except Exception as e:
            # Log error but continue
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error parsing PHP file {file_path}: {e}"
                    )
                )

    def _extract_methods(self, content: str, start_pos: int) -> list[str]:
        """Extract method names from a class definition."""
        methods = []

        # Find the class body (between start_pos and matching closing brace)
        # Start with brace_count = 1 because we're already inside the class opening brace
        brace_count = 1
        end_pos = start_pos

        for i, char in enumerate(content[start_pos:], start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i
                    break

        # Extract methods from the class body
        class_body = content[start_pos:end_pos]
        for match in self._method_pattern.finditer(class_body):
            visibility = match.group(1)
            method_name = match.group(2)

            # Skip constructors, destructors, private/protected methods, and internal methods
            # But allow magic methods like __invoke that are commonly used
            allowed_magic_methods = {'__invoke', '__toString', '__call', '__get', '__set'}
            if (method_name not in {'__construct', '__destruct'} and
                (not method_name.startswith('_') or method_name in allowed_magic_methods) and
                visibility != 'protected' and visibility != 'private'):
                methods.append(method_name)

        return methods

    def get(self, id: str) -> ClassDefinition | None:
        """Get a class definition by full name."""
        return self._classes.get(id)

    def get_all(self) -> Mapping[str, ClassDefinition]:
        """Get all class definitions."""
        return self._classes

    def search(self, query: str, limit: int = 50) -> Sequence[ClassDefinition]:
        """Search for classes by name or namespace."""
        query_lower = query.lower()
        results = []

        for class_def in self._classes.values():
            if (query_lower in class_def.full_name.lower() or
                query_lower in class_def.class_name.lower() or
                query_lower in class_def.namespace.lower()):
                results.append(class_def)

        # Sort by relevance (exact matches first)
        results.sort(key=lambda c: (
            not c.class_name.lower().startswith(query_lower),
            not c.full_name.lower().startswith(query_lower),
            c.class_name
        ))

        return results[:limit]

    def get_methods(self, class_name: str) -> list[str]:
        """Get methods for a specific class."""
        class_def = self.get(class_name)
        return class_def.methods if class_def else []

    def search_methods(self, class_name: str, query: str, limit: int = 20) -> list[str]:
        """Search for methods in a specific class."""
        methods = self.get_methods(class_name)
        query_lower = query.lower()

        matching_methods = [
            method for method in methods
            if query_lower in method.lower()
        ]

        # Sort by relevance
        matching_methods.sort(key=lambda m: (
            not m.lower().startswith(query_lower),
            m
        ))

        return matching_methods[:limit]

    async def load_from_disk(self) -> bool:
        """
        Load cache from disk.

        Returns True if successful, False otherwise.
        """
        cache_file = self.workspace_cache.cache_dir / "classes.json"

        if not cache_file.exists():
            return False

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            # Check if cache is still valid
            cache_version = data.get("version", 0)
            if cache_version != 1:
                return False

            # Load classes
            classes_data = data.get("classes", {})
            for full_name, class_dict in classes_data.items():
                # Convert dict back to ClassDefinition
                self._classes[full_name] = ClassDefinition(
                    id=class_dict["full_name"],
                    description=f"{class_dict['namespace']}\\{class_dict['class_name']}" if class_dict["namespace"] else class_dict["class_name"],
                    file_path=Path(class_dict["file_path"]),
                    line_number=class_dict["line_number"],
                    namespace=class_dict["namespace"],
                    class_name=class_dict["class_name"],
                    full_name=class_dict["full_name"],
                    methods=class_dict.get("methods", []),
                )

            return True

        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error loading classes cache from disk: {e}"
                    )
                )
            return False

    async def save_to_disk(self):
        """Save cache to disk."""
        self.workspace_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.workspace_cache.cache_dir / "classes.json"

        try:
            data = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "classes": {
                    full_name: {
                        "namespace": class_def.namespace,
                        "class_name": class_def.class_name,
                        "full_name": class_def.full_name,
                        "methods": class_def.methods,
                        "file_path": str(class_def.file_path),
                        "line_number": class_def.line_number,
                    }
                    for full_name, class_def in self._classes.items()
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
                        message=f"Error saving classes cache to disk: {e}"
                    )
                )

    def invalidate_file(self, file_path: Path):
        """Invalidate cache entries for a specific file."""
        file_path_str = str(file_path)
        self._classes = {
            name: class_def for name, class_def in self._classes.items()
            if str(class_def.file_path) != file_path_str
        }

        # Re-parse the file if it still exists
        if file_path.exists():
            self._parse_php_file(file_path)

    def register_text_sync_hooks(self) -> None:
        """Register text sync hooks for real-time updates."""
        if not self.server or not hasattr(self.server, "text_sync_manager"):
            return

        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_php_file_saved)
            text_sync.add_on_change_hook(self._on_php_file_change)

    async def _on_php_file_change(self, params):
        """Handle PHP file changes."""
        uri = params.text_document.uri
        if not uri.endswith('.php'):
            return

        # For changes, we could do incremental parsing, but for simplicity
        # we'll just invalidate and re-parse on save
        pass

    async def _on_php_file_saved(self, params):
        """Handle PHP file saves."""
        uri = params.text_document.uri
        if not uri.endswith('.php'):
            return

        file_path = Path(uri.replace("file://", ""))

        try:
            # Invalidate and re-parse
            self.invalidate_file(file_path)

            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated classes cache: {file_path.name}"
                    )
                )
        except Exception as e:
            if self.server:
                from lsprotocol.types import LogMessageParams, MessageType
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating classes cache: {type(e).__name__}: {e}"
                    )
                )