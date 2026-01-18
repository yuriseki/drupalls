from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from lsprotocol.types import DidChangeTextDocumentParams, DidSaveTextDocumentParams, LogMessageParams, MessageType
import yaml
import json

from drupalls.utils.resolve_class_file import resolve_class_file
from drupalls.workspace.cache import (
    CachedDataBase,
    CachedWorkspace,
    FileInfo,
    WorkspaceCache,
)
from drupalls.workspace.utils import calculate_file_hash


@dataclass
class ServiceDefinition(CachedDataBase):
    """Represents a parsed Drupal service definition."""

    class_name: str
    class_file_path: str
    arguments: list[str] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)

    @property
    def short_description(self) -> str:
        """Get a short description for completion."""
        if self.description:
            return self.description
        if self.class_name:
            # Extract class name from FQCN (Fully Qualified Class Name)
            return self.class_name.split("\\")[-1]
        return self.id


class ServicesCache(CachedWorkspace):
    """Cache for Drupal service definitions with self-updating hooks."""

    def __init__(self, workspace_cache: WorkspaceCache) -> None:
        super().__init__(workspace_cache)
        self._services: dict[str, ServiceDefinition] = {}
        self.server = workspace_cache.server

    async def initialize(self):
        await self.scan()

    async def scan(self):
        """
        Scan all *.services.yml files and parse service definitions.

        Looks in:
        - core/core.services.yml
        - core/modules/*/[module].services.yml
        - modules/*/[module].services.yml
        - modules/contrib/*/[module].services.yml
        - modules/custom/*/[module].services.yml
        """
        base_dirs = ["core", "modules", "profiles", "themes"]

        for base_name in base_dirs:
            # Get the actual directory object (e.g., /root/core)
            base_path = self.workspace_root / base_name

            if not base_path.is_dir():
                continue

            # rglob handles the recursion automatically
            # It will find core/core.services.yml AND core/subdir/other.services.yml
            for services_file in base_path.rglob("*.services.yml"):
                if services_file.is_file():
                    await self.parse_services_file(services_file)

    async def parse_services_file(self, file_path: Path) -> None:
        """
        Parse a single .services.yml file and update cache.
        
        This method handles both initial scanning and incremental updates.
        """
        # Calculate file hash for change detection
        file_hash = calculate_file_hash(file_path)

        # Add constructors used in Drupal core services.
        def construct_ref(loader, node):
            # This simple constructor just returns the value as a string/scalar
            return loader.construct_scalar(node)
    
        custom_tags = ["!tagged_iterator", "!Ref", "!Sub", "!GetAtt", "!Base64"]
        for custom_tag in custom_tags:
            yaml.SafeLoader.add_constructor(custom_tag, construct_ref)

        # Load and parse YAML
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Extract services
        services = data.get('services', {}) if data else {}
        
        # Remove existing services from this file (for updates)
        self._services = {
            sid: sdef for sid, sdef in self._services.items()
            if sdef.file_path != file_path
        }
        
        # Add/update services from this file
        for service_id, service_data in services.items():
            if not isinstance(service_data, dict):
                    continue

            class_file_path = resolve_class_file(
                service_data.get('class', ''), self.workspace_cache.workspace_root
            )

            service_def = ServiceDefinition(
                id=service_id,
                class_name=service_data.get('class', ''),
                class_file_path=str(class_file_path) or "",
                description=service_data.get('class', ''),
                arguments=service_data.get('arguments', []),
                tags=service_data.get('tags', []),
                file_path=file_path,
                line_number=self._find_service_line(file_path, service_id),
            )
            self._services[service_id] = service_def
        
        # Track file for future updates
        self.file_info[file_path] = FileInfo(
            path=file_path,
            hash=file_hash,
            last_modified=datetime.fromtimestamp(file_path.stat().st_mtime)
        )

    def _find_service_line(self, file_path: Path, service_id: str) -> int:
        """Find the line number where a service is defined."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                if f'{service_id}:' in line:
                    return i + 1 # Index base 0, so we need to add 1
        except Exception:
            pass
        
        return 0


    async def parse_services_file_OLD(self, file_path: Path):
        """
        Parse a single .services.yml file and update cache.
        
        This method handles both initial scanning and incremental updates.
        """
        try:
            # Calculate file hash for cache invalidation
            file_hash = calculate_file_hash(file_path)

            # First pass: Find line numbers for each service ID
            service_line_numbers = {}
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                in_services_section = False

                for line_num, line in enumerate(lines, start=1):
                    # Check if we entered the services section
                    if line.strip().startswith("services:"):
                        in_services_section = True
                        continue

                    # Exit services section if we hit another root-level key
                    if (
                        in_services_section
                        and line.strip()
                        and not line.startswith(" ")
                    ):
                        in_services_section = False

                    # Service IDs are indented with 2 spaces and followed by ':'
                    if in_services_section and line.startswith("  ") and ":" in line:
                        # Make sure it's not a property (properties have 4+ spaces)
                        if not line.startswith("    "):
                            service_id = line.strip().split(":")[0].strip()
                            if service_id:
                                service_line_numbers[service_id] = line_num

            # Add constructors used in Drupal core services.
            def construct_ref(loader, node):
                # This simple constructor just returns the value as a string/scalar
                return loader.construct_scalar(node)

            custom_tags = ["!tagged_iterator", "!Ref", "!Sub", "!GetAtt", "!Base64"]
            for custom_tag in custom_tags:
                yaml.SafeLoader.add_constructor(custom_tag, construct_ref)

            # Second pass: Parse YAML
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "services" not in data:
                return

            # Parse each service definition
            for id, service_def in data["services"].items():
                if not isinstance(service_def, dict):
                    continue

                # Extract service information
                class_name = service_def.get("class", "")
                class_file_path = resolve_class_file(
                    class_name, self.workspace_cache.workspace_root
                )
                arguments = service_def.get("arguments", [])
                tags = service_def.get("tags", [])

                # Create service definition
                if class_name:
                    self._services[id] = ServiceDefinition(
                        id=id,
                        description=class_name,
                        class_name=class_name,
                        class_file_path=str(class_file_path) or "",
                        arguments=arguments,
                        tags=tags,
                        file_path=file_path,
                        line_number=service_line_numbers.get(id, 0),
                    )

            # Track file info for invalidation
            self.file_info[file_path] = FileInfo(
                path=file_path,
                hash=file_hash,
                last_modified=datetime.fromtimestamp(file_path.stat().st_mtime),
            )

        except Exception as e:
            # Log error but don't fail
            print(f"Error parsing {file_path}: {e}")

    def get_all(self) -> dict[str, ServiceDefinition]:
        """Get all services."""
        return self._services

    def get(self, id: str) -> ServiceDefinition | None:
        """Get a specific service by ID."""
        return self._services.get(id)

    def search(self, query: str, limit: int = 50) -> list[ServiceDefinition]:
        """
        Search services by ID or class name.

        Returns services matching the query, sorted by relevance.
        """
        query_lower = query.lower()
        results = []

        for id, service_def in self._services.items():
            # Check if query matches service ID or class name
            if query_lower in id.lower():
                results.append(service_def)
            elif query_lower in service_def.class_name.lower():
                results.append(service_def)

        # Sort by relevance (starts with query first)
        results.sort(
            key=lambda s: (
                not s.id.lower().startswith(query_lower),
                s.id,
            )
        )

        return results[:limit]

    # ===== Cache Persistence =====

    async def load_from_disk(self) -> bool:
        """
        Load cache from disk.

        Returns True if successful, False otherwise.
        """
        cache_file = self.workspace_cache.cache_dir / "services.json"

        if not cache_file.exists():
            return False

        try:
            with open(cache_file, "r") as f:
                data = json.load(f)

            # Check if cache is still valid
            cache_version = data.get("version", 0)
            if cache_version != 1:
                return False

            # Load services
            services_data = data.get("services", {})
            for id, service_dict in services_data.items():
                # Convert dict back to ServiceDefinition
                self._services[id] = ServiceDefinition(
                    id=service_dict["id"],
                    class_name=service_dict["class_name"],
                    class_file_path=service_dict["class_file_path"],
                    description=service_dict.get("description", ""),
                    arguments=service_dict.get("arguments", []),
                    tags=service_dict.get("tags", []),
                    file_path=(
                        Path(service_dict["file_path"])
                        if service_dict.get("file_path")
                        else None
                    ),
                    line_number=service_dict["line_number"],
                )

            return True

        except Exception as e:
            print(f"Error loading cache from disk: {e}")
            return False

    async def save_to_disk(self):
        """Save cache to disk."""
        self.workspace_cache.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.workspace_cache.cache_dir / "services.json"

        try:
            data = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "services": {
                    id: {
                        "id": service_def.id,
                        "class_name": service_def.class_name,
                        "description": service_def.description,
                        "class_file_path": service_def.class_file_path,
                        "arguments": service_def.arguments,
                        "tags": service_def.tags,
                        "file_path": (
                            str(service_def.file_path)
                            if service_def.file_path
                            else None
                        ),
                        "line_number": service_def.line_number,
                    }
                    for id, service_def in self._services.items()
                },
            }

            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Error saving cache to disk: {e}")

    def invalidate_file(self, file_path: Path):
        """
        Invalidate cache for a specific file.

        Call this when a file changes (from didChange notification).
        """
        if not file_path.exists():
            # File deleted - remove from cache
            if file_path in self.file_info:
                del self.file_info[file_path]

            # Remove services from this file
            self._services = {
                sid: sdef
                for sid, sdef in self._services.items()
                if sdef.file_path != file_path
            }
            return

        # Check if file actually changed
        new_hash = calculate_file_hash(file_path)
        old_info = self.file_info.get(file_path)

        if old_info and old_info.hash == new_hash:
            # File hasn't changed, no need to re-parse
            return

        # Re-parse the file
        if file_path.name.endswith(".services.yml"):
            # Run in sync for simplicity (can be async if needed)
            import asyncio

            asyncio.create_task(self.parse_services_file(file_path))


    def register_text_sync_hooks(self) -> None:
        """
        Register hooks to keep services cache up-to-date.

        Registers a save hook that updates the cache when .services.yml files
        are saved.
        """
        if not self.server or not hasattr(self.server, "text_sync_manager"):
            return
        
        text_sync = self.server.text_sync_manager
        if text_sync:
            text_sync.add_on_save_hook(self._on_services_file_saved)
            text_sync.add_on_change_hook(self._on_services_file_change)
        
    async def _on_services_file_change(
        self,
        params: DidChangeTextDocumentParams
    ) -> None:
        """
        Update cache when a .services.yml file is changed.
        
        This method is called automatically by TextSyncManager
        when any file is saved. We filter for .services.yml files
        and update the cache incrementally.
        """
        uri = params.text_document.uri
        
        # Filter: Only handle .services.yml files
        if not uri.endswith('.services.yml'):
            return
        
        try:
            # Convert URI to file path
            file_path = Path(uri.replace('file://', ''))
            if not file_path:
                return

            self.invalidate_file(file_path)
           
            # Log success
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated services cache: {file_path.name}"
                    )
                )
        
        except FileNotFoundError:
            # File was deleted - remove services from cache
            self._remove_services_from_file(file_path)
            
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Services file deleted: {file_path.name}"
                    )
                )
        
        except Exception as e:
            # Log errors but don't crash
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating services cache: {type(e).__name__}: {e}"
                    )
                )


    async def _on_services_file_saved(
        self, 
        params: DidSaveTextDocumentParams
    ) -> None:
        """
        Update cache when a .services.yml file is saved.
        
        This method is called automatically by TextSyncManager
        when any file is saved. We filter for .services.yml files
        and update the cache incrementally.
        """
        uri = params.text_document.uri
        
        # Filter: Only handle .services.yml files
        if not uri.endswith('.services.yml'):
            return
        
        try:
            # Convert URI to file path
            file_path = Path(uri.replace('file://', ''))
            if not file_path:
                return

            # Check if file is within our workspace
            if not self._is_in_workspace(file_path):
                return
            
            # Re-parse this specific file (incremental update)
            await self.parse_services_file(file_path)

            await self.save_to_disk()
            
            # Log success
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Info,
                        message=f"✓ Updated services cache: {file_path.name}"
                    )
                )
        
        except FileNotFoundError:
            # File was deleted - remove services from cache
            self._remove_services_from_file(file_path)
            
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Services file deleted: {file_path.name}"
                    )
                )
        
        except Exception as e:
            # Log errors but don't crash
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Error updating services cache: {type(e).__name__}: {e}"
                    )
                )

    def _is_in_workspace(self, file_path: Path) -> bool:
        """Check if file path is within workspace root."""
        try:
            file_path.relative_to(self.workspace_cache.workspace_root)
            return True
        except ValueError:
            return False
    
    def _remove_services_from_file(self, file_path: Path) -> None:
        """Remove all services defined in a specific file."""
        # Remove services that came from this file
        self._services = {
            service_id: service_def
            for service_id, service_def in self._services.items()
            if service_def.file_path != file_path
        }
        
        # Remove file from tracking
        if file_path in self.file_info:
            del self.file_info[file_path]
