from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import yaml
import json

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
    def __init__(self, workspace_cache: WorkspaceCache) -> None:
        super().__init__(workspace_cache)
        self._services: dict[str, ServiceDefinition] = {}

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

    async def parse_services_file(self, file_path: Path):
        """Parse a single .services.yml file."""
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
                    if line.strip().startswith('services:'):
                        in_services_section = True
                        continue
                    
                    # Exit services section if we hit another root-level key
                    if in_services_section and line.strip() and not line.startswith(' '):
                        in_services_section = False
                    
                    # Service IDs are indented with 2 spaces and followed by ':'
                    if in_services_section and line.startswith('  ') and ':' in line:
                        # Make sure it's not a property (properties have 4+ spaces)
                        if not line.startswith('    '):
                            service_id = line.strip().split(':')[0].strip()
                            if service_id:
                                service_line_numbers[service_id] = line_num

            # Add constructors used in Drupal core services.
            def construct_ref(loader, node):
                # This simple constructor just returns the value as a string/scalar
                return loader.construct_scalar(node)

            custom_tags = ['!tagged_iterator', '!Ref', '!Sub', '!GetAtt', '!Base64']
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
                arguments = service_def.get("arguments", [])
                tags = service_def.get("tags", [])

                # Create service definition
                if (class_name):
                    self._services[id] = ServiceDefinition(
                        id=id,
                        description=class_name,
                        class_name=class_name,
                        arguments=arguments,
                        tags=tags,
                        file_path=file_path,
                        line_number=service_line_numbers.get(id, 0)
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

    def load_from_disk(self) -> bool:
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
                    description=service_dict.get("description", ""),
                    arguments=service_dict.get("arguments", []),
                    tags=service_dict.get("tags", []),
                    file_path=(
                        Path(service_dict["file_path"])
                        if service_dict.get("file_path")
                        else None
                    ),
                    line_number=service_dict["line_number"]
                )

            return True

        except Exception as e:
            print(f"Error loading cache from disk: {e}")
            return False

    def save_to_disk(self):
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
