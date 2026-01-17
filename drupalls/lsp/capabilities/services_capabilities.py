"""
Services-related LSP capabilities.

Provides completion, hover, and definition for Drupal services.
"""

from pathlib import Path
import re
from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    FileOperationClientCapabilities,
    Hover,
    HoverParams,
    Location,
    LogMessageParams,
    MarkupContent,
    MarkupKind,
    MessageType,
    Position,
    Range,
)
from pygls import workspace
from drupalls.lsp.capabilities.capabilities import (
    CompletionCapability,
    DefinitionCapability,
    HoverCapability,
)

from drupalls.workspace.services_cache import ServiceDefinition, ServicesCache


# Check for service patterns
SERVICE_PATTERN = re.compile(r'::service\([\'"]?|getContainer\(\)->get\([\'"]?')


class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""

    @property
    def name(self) -> str:
        return "service_completion"

    @property
    def description(self) -> str:
        return "Autopcomplete Drupal service names in ::serivice() and getContainer()->get() calls"

    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor in in a service context."""
        if not self.workspace_cache:
            return False

        # Get the document and line
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide service name completions."""
        if not self.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])

        # Get services cache
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])

        # Get all services
        all_services: dict[str, ServiceDefinition] = (
            services_cache.get_all()
        )  # pyright: ignore

        # Build completion items
        items = []
        for service_id, service_def in all_services.items():
            # Get relative path for display
            file_path_str = "unknown"
            if service_def.file_path:
                try:
                    relative = service_def.file_path.relative_to(
                        self.workspace_cache.workspace_root
                    )
                    file_path_str = str(relative)
                except ValueError:
                    file_path_str = str(service_def.file_path)

            items.append(
                CompletionItem(
                    label=service_id,
                    kind=CompletionItemKind.Value,
                    detail=service_def.class_name,
                    documentation=f"Defined in: {file_path_str}",
                    insert_text=service_id,
                )
            )

        return CompletionList(is_incomplete=False, items=items)


class ServicesHoverCapability(HoverCapability):
    """Provides hover information for Drupal services."""

    @property
    def name(self) -> str:
        return "services_hover"

    @property
    def description(self) -> str:
        return "Suow information about Drupal services on hover"

    async def can_handle(self, params: HoverParams) -> bool:
        """Check if hovering over a service identifier."""
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def hover(self, params: HoverParams) -> Hover | None:
        """Provide hover information for services"""
        if not self.workspace_cache:
            return None

        # Get word under cursor using LSP's built in word_at_position
        doc = self.server.workspace.get_text_document(params.text_document.uri)

        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None

        service_def = services_cache.get(word)
        if service_def:
            # Found the service
            relative_path = "unknown"
            if service_def.file_path:
                try:
                    relative_path = str(
                        service_def.file_path.relative_to(
                            self.workspace_cache.workspace_root
                        )
                    )
                except ValueError:
                    relative_path = str(service_def.file_path)

            content = (
                f"**Drupal Service:** `{word}`{chr(10)}"
                f"**Class:** {service_def.class_name}{chr(10)}"
                f"**Defined in:** {relative_path}"
            )

            if service_def.arguments:
                content += f"{chr(10)}**Arguments:** ({service_def.arguments})"

            if service_def.tags:
                content += f"{chr(10)}**Tags:** {service_def.tags}"

            return Hover(
                contents=MarkupContent(kind=MarkupKind.Markdown, value=content)
            )

        return None


class ServicesDefinitionCapability(DefinitionCapability):
    """Provides go-to-definition for Drupal services."""

    @property
    def name(self) -> str:
        return "services_definition"

    @property
    def description(self) -> str:
        return "Navigate to service definition in .services.yml files"

    async def can_handle(self, params: DefinitionParams) -> bool:
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]

        return True if SERVICE_PATTERN.search(line) else False

    async def definition(self, params: DefinitionParams) -> Location | None:
        """Provide definition location for services."""
        if not self.workspace_cache:
            return None

        # Get service ID under cursor
        doc = self.server.workspace.get_text_document(params.text_document.uri)

        # Extract service ID with custom pattern for dots
        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None

        # Look up the service definition
        service_def = services_cache.get(word)
        if service_def and service_def.file_path:
            # Get the exact line number from the service definition
            # ServiceDefinition stores the line number where it was defined.
            line_number = (
                service_def.line_number - 1
                if hasattr(service_def, "line_number")
                else 0
            )

            # Return the location pointing to the service definition in .services.yml
            return Location(
                uri=service_def.file_path.as_uri(),
                range=Range(
                    start=Position(line=line_number, character=0),
                    end=Position(line=line_number, character=0),
                ),
            )

        return None


class ServicesYamlDefinitionCapability(DefinitionCapability):
    r"""
    Provides go-to-definition from .services.yml files to PHP class definitions.
    
    Navigates from:
        services:
          logger.factory:
            class: Drupal\Core\Logger\LoggerChannelFactory
    
    To:
        core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
    """
    
    @property
    def name(self) -> str:
        return "services_yaml_to_class_definition"

    @property
    def description(self) -> str:
        return "Navigate from services class in YAML file to PHP class definition"

    async def can_handle(self, params: DefinitionParams) -> bool:
        """
        Check if we should handle this definition request.

        Returns True if:
        1. File is a .services.yml file
        2. Cursor is on a line containing "class:" property
        3. Line contains a valid PHP class name
        """
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)

        # Check if  file is a services YAML file
        if not doc.uri.endswith(".services.yml"):
            return False

        # Get the current line
        try:
            line = doc.lines[params.position.line]
        except IndexError:
            return False

        # Check if line contains "class:" property
        # Format: "class: Drupal\Core\Logger\LoggerChannelFactory"
        if "class:" not in line:
            return False

        # Check if line has a PHP namespace (contains backslash)
        if "\\" not in line:
            return False

        return True

    async def definition(
        self, params: DefinitionParams
    ) -> Location | list[Location] | None:
        """
        Provide definition location for the PHP class.

        Process:
        1. Extract FQCN from the current line
        2. Convert FQCN to file path
        3. Find the class definition line in the file
        4. Return Location pointing to class declaration
        """
        if not self.workspace_cache:
            return None

        doc = self.server.workspace.get_text_document(params.text_document.uri)

        try:
            line = doc.lines[params.position.line]
        except IndexError:
            return None

        # Extract the fully qualified class name
        class_name = self._extract_class_name(line)
        if not class_name:
            return None

        # Resolve FQCN to file_path
        class_file = self._resolve_class_file(class_name)
        if not class_file or not class_file.exists():
            return None

        # Find the class definition line
        class_line = self._find_class_definition_line(class_file, class_name)

        # Return location
        return Location(
            uri=class_file.as_uri(),
            range=Range(
                start=Position(line=class_line, character=0),
                end=Position(line=class_line, character=0),
            ),
        )

    def _extract_class_name(self, line: str) -> str | None:
        r"""
        Extract fully qualified class name from YAML line.

        Examples:
            "    class: Drupal\\Core\\Logger\\LoggerChannelFactory"
            "    class: 'Drupal\\Core\\Logger\\LoggerChannelFactory'"
            "    class: \"Drupal\\Core\\Logger\\LoggerChannelFactory\""

        Returns:
            "Drupal\\Core\\Logger\\LoggerChannelFactory"
        """
        # Pattern: class: optionally quoted PHP namespace
        pattern = re.compile(r'class:\s*["\']?([A-Za-z0-9\\_]+)["\']?')
        match = pattern.search(line)

        if match:
            return match.group(1).strip()

        return None

    def _resolve_class_file(self, fqcn: str) -> Path | None:
        r"""
        Convert fully qualified class name to file path.

        Uses Drupal's PSR-4 autoloading conventions:
        - Drupal\\Core\\...       → core/lib/Drupal/Core/...
        - Drupal\\[module]\\...   → modules/.../src/...

        Args:
            fqcn: Fully qualified class name (e.g., "Drupal\\Core\\Logger\\LoggerChannelFactory")

        Returns:
            Path to PHP file, or None if cannot resolve
        """
        if not self.workspace_cache:
            return None

        workspace_root = self.workspace_cache.workspace_root

        # Split namespace into parts
        parts = fqcn.split("\\")

        if len(parts) < 2:
            return None

        # Handle Drupal\Core* classes
        if parts[0] == "Drupal" and parts[1] == "Core":
            # Drupal\Core\Logger\LoggerChannelFactory
            # -> core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
            relative_path = Path("core/lib") / "/".join(parts)
            class_file = workspace_root / f"{relative_path}.php"
            return class_file

        # Handle Drupal\[module]\* classes
        if parts[0] == "Drupal" and len(parts) >= 2:
            # Drupal\mymodule\Controller\MyController
            # -> modules/.../mymodule/src/Controller/MyController.php
            module_name = parts[1].lower()  # Module names are lowercase

            # Remaining namespace parts after "Drupal\[module]\"
            relative_parts = parts[2:]  # Skip "Drupal" and module name

            # Build the relative path within the module's src/ directory
            if relative_parts:
                class_relative_path = Path("/".join(relative_parts)).with_suffix(".php")
            else:
                return None

            # Search for module recursively in common base directories
            # This handles nested directories like modules/custom/vendor/mymodule
            search_base_dirs = [
                workspace_root / "modules",
                workspace_root / "core" / "modules",
                workspace_root / "profiles",
            ]

            for base_dir in search_base_dirs:
                if not base_dir.exists():
                    continue

                # Use rglob to search recursively for module directories
                # Look for any directory matching the module name that contains a src/ folder
                for module_dir in base_dir.rglob(module_name):
                    if module_dir.is_dir():
                        src_dir = module_dir / "src"
                        if src_dir.exists() and src_dir.is_dir():
                            class_file = src_dir / class_relative_path
                            if class_file.exists():
                                return class_file

        return None

    def _find_class_definition_line(self, file_path: Path, fqcn: str) -> int:
        """
        Find the line number where the class is declared.

        Searches for patterns like:
        - class LoggerChannelFactory
        - final class LoggerChannelFactory
        - abstract class LoggerChannelFactory
        - interface LoggerChannelFactoryInterface
        - trait LoggerChannelFactoryTrait

        Args:
            file_path: Path to PHP file
            fqcn: Fully qualified class name

        Returns:
            Line number (0-indexed) where class is declared, or 0 if not found
        """
        # Extract simple class name (last part after backslash)
        class_name = fqcn.split("\\")[-1]

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Pattern for class/interface/trait declaration
            # Matches: class ClassName, final class ClassName, etc.
            pattern = re.compile(
                rf"^\s*(final|abstract)?\s*(class|interface|trait)\s+{re.escape(class_name)}\b"
            )

            for line_num, line in enumerate(lines):
                if pattern.search(line):
                    return line_num

        except Exception:
            # If file read fails, return 0
            pass

        return 0
