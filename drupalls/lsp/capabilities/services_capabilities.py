"""
Services-related LSP capabilities.

Provides completion, hover, and definition for Drupal services.
"""

import os
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
    ReferenceParams,
)
from pygls import workspace
from pygls.workspace.text_document import TextDocument
from drupalls.lsp.capabilities.capabilities import (
    CompletionCapability,
    DefinitionCapability,
    HoverCapability,
    ReferencesCapability,
)

from drupalls.utils.resolve_class_file import resolve_class_file
from drupalls.workspace.services_cache import ServiceDefinition, ServicesCache


# Check for service patterns
# TODO: Include variables of type container for dependency injection.
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
                f"**Class:** {service_def.class_name}{chr(10)}"  # type: ignore
                f"**Defined in:** {relative_path}"
            )

            if service_def.arguments:  # type: ignore
                content += f"{chr(10)}**Arguments:** ({service_def.arguments})"  # type: ignore

            if service_def.tags:  # type: ignore
                content += f"{chr(10)}**Tags:** {service_def.tags}"  # type: ignore

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

        services_cache = self.workspace_cache.caches.get("services")
        if services_cache:
            # Look up the service definition
            service_def = services_cache.get(class_name)
            if service_def and service_def.class_file_path:  # type: ignore
                class_file = Path(service_def.class_file_path)  # type: ignore
                if class_file.exists():
                    class_line = self._find_class_definition_line(
                        class_file,
                        service_def.class_name,  # type: ignore
                    )

                    return Location(
                        uri=class_file.as_uri(),
                        range=Range(
                            start=Position(line=class_line, character=0),
                            end=Position(line=class_line, character=0),
                        ),
                    )

        # Fallback: Dynamic resolution if cache lookup fails.
        # Resolve FQCN to file_path
        class_file = resolve_class_file(class_name, self.workspace_cache.workspace_root)
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


class ServicesReferencesCapability(ReferencesCapability):
    """Find all references to Drupal services."""

    @property
    def name(self) -> str:
        return "services_references"

    @property
    def description(self) -> str:
        return "Find all usages of a Drupal service"

    async def can_handle(self, params: ReferenceParams) -> bool:
        """Check if cursor is on a service identifier."""
        if not self.workspace_cache:
            return False

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        
        # Handle YAML files (.services.yml)
        if doc.uri.endswith('.services.yml'):
            return await self._can_handle_yaml_file(params, doc)

        # Handle PHP files
        line = doc.lines[params.position.line]

        return bool(SERVICE_PATTERN.search(line))

    async def _can_handle_yaml_file(self, params: ReferenceParams, doc: TextDocument) -> bool:
        """Check if cursor in on an service ID in a YAML file."""
        if not self.workspace_cache:
            return False

        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        if not word:
            return False

        # Check if this word is a valid service ID
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return False

        return services_cache.get(word) is not None

    async def find_references(self, params: ReferenceParams) -> list[Location]:
        """Find all references to the search under cursor."""
        if not self.workspace_cache:
            return []

        # Get service ID under cursor
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        word = doc.word_at_position(
            params.position,
            re_start_word=re.compile(r"[A-Za-z_][A-Za-z0-9_.]*$"),
            re_end_word=re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*"),
        )

        if not word:
            return []

        # Get services cache to verify this is a valid service
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache or not services_cache.get(word):
            return []

        # Search all PHP files for service usage
        locations = []
        await self._search_files_for_service(word, locations)

        return locations

    async def _search_files_for_service(
        self, service_id: str, locations: list[Location]
    ):
        """Search all PHP files for usage of the service."""
        if not self.workspace_cache:
            return []

        # Search patterns for service usage
        # TODO: Include dependency injection in the patterns.
        patterns = [
            rf'\\Drupal::service\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)',
            rf'\\Drupal::getContainer\(\)->get\(\s*[\'"]({re.escape(service_id)})[\'"]\s*\)',
        ]

        # Get all files in the workspace
        php_files = []
        for root, dirs, files in os.walk(self.workspace_cache.workspace_root):
            for file in files:
                if file.endswith((".php", ".module", ".inc", ".install")):
                    php_files.append(Path(root) / file)

        for php_file in php_files:
            await self._search_file_for_service(
                php_file, service_id, patterns, locations
            )

    async def _search_file_for_service(
        self,
        file_path: Path,
        service_id: str,
        patterns: list[str],
        locations: list[Location],
    ):
        """Search a single file for service references."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.splitlines()

            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    # Get line number
                    line_num = content[: match.start()].count("\n")

                    # Get column position of service ID with the line
                    line_start = content.rfind("\n", 0, match.start()) + 1
                    col_start = match.start() - line_start

                    # Find the actual service ID within the match
                    service_match = re.search(
                        rf"['\"]({re.escape(service_id)})['\"]", match.group()
                    )
                    if service_match:
                        service_col = col_start + service_match.start(1)

                        locations.append(
                            Location(
                                uri=file_path.as_uri(),
                                range=Range(
                                    start=Position(
                                        line=line_num, character=service_col
                                    ),
                                    end=Position(
                                        line=line_num,
                                        character=service_col + len(service_id),
                                    ),
                                ),
                            )
                        )

        except Exception as e:
            # Log and continue with other files
            if self.server:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Warning,
                        message=f"Error searching {file_path}: {e}",
                    )
                )
