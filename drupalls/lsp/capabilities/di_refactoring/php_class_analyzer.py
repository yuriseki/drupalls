"""
PHP class structure analyzer for DI refactoring.

File: drupalls/lsp/capabilities/di_refactoring/php_class_analyzer.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ConstructorInfo:
    """Information about an existing __construct() method."""

    start_line: int  # Line with "public function __construct"
    end_line: int  # Line with closing "}"
    params: list[tuple[str, str | None]]  # [(param_name, type_hint), ...]
    param_texts: list[str]  # original parameter declaration texts
    body_lines: list[str]  # Lines inside constructor body
    docblock_start: int | None  # Line where docblock starts
    docblock_end: int | None  # Line where docblock ends


@dataclass
class CreateMethodInfo:
    """Information about an existing create() method."""

    start_line: int  # Line with "public static function create"
    end_line: int  # Line with closing "}"
    container_gets: list[str]  # Service IDs from $container->get('...')
    docblock_start: int | None
    docblock_end: int | None


@dataclass
class PropertyInfo:
    """Information about an existing property."""

    name: str
    line: int
    type_hint: str | None
    has_docblock: bool
    docblock_start: int | None
    docblock_end: int | None


@dataclass
class PhpClassInfo:
    """Complete analyzed PHP class structure."""

    # Use statements
    use_statements: dict[str, int] = field(default_factory=dict)  # fqcn -> line
    use_section_start: int = 0
    use_section_end: int = 0

    # Class declaration
    class_line: int = 0
    class_name: str = ""
    extends: str | None = None
    implements: list[str] = field(default_factory=list)

    # Trait usage inside class
    trait_use_lines: list[int] = field(default_factory=list)

    # Properties
    properties: dict[str, PropertyInfo] = field(default_factory=dict)
    first_property_line: int | None = None

    # Constructor
    constructor: ConstructorInfo | None = None

    # Create method
    create_method: CreateMethodInfo | None = None


class PhpClassAnalyzer:
    """Analyzes PHP class structure for DI refactoring."""

    # Patterns
    USE_PATTERN = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+\w+)?;")
    CLASS_PATTERN = re.compile(
        r"^\s*(final\s+|abstract\s+)?(class|interface|trait)\s+(\w+)"
        r"(?:\s+extends\s+([\w\\]+))?"
        r"(?:\s+implements\s+([\w\\,\s]+))?"
    )
    TRAIT_USE_PATTERN = re.compile(r"^\s+use\s+([\w\\]+);")
    PROPERTY_PATTERN = re.compile(
        r"^\s+(protected|private|public)\s+"
        r"(?:([\w\\]+)\s+)?"
        r"\$(\w+)"
    )
    CONSTRUCTOR_PATTERN = re.compile(
        r"^\s+public\s+function\s+__construct\s*\("
    )
    CREATE_PATTERN = re.compile(
        r"^\s+public\s+static\s+function\s+create\s*\("
    )
    CONTAINER_GET_PATTERN = re.compile(
        r"\$container->get\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )
    DOCBLOCK_START = re.compile(r"^\s*/\*\*")
    DOCBLOCK_END = re.compile(r"^\s*\*/")

    def analyze(self, content: str) -> PhpClassInfo:
        """Analyze PHP file content and return class structure info."""
        info = PhpClassInfo()
        lines = content.split("\n")

        self._parse_use_statements(lines, info)
        self._parse_class_declaration(lines, info)
        self._parse_class_body(lines, info)

        return info

    def _parse_use_statements(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse use statements at file level."""
        in_use_section = False

        for i, line in enumerate(lines):
            # Skip until we find first use statement
            match = self.USE_PATTERN.match(line)
            if match:
                if not in_use_section:
                    info.use_section_start = i
                    in_use_section = True

                fqcn = match.group(1)
                info.use_statements[fqcn] = i
                info.use_section_end = i + 1

            # Stop at class declaration
            if self.CLASS_PATTERN.match(line):
                break

    def _parse_class_declaration(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse class declaration line."""
        for i, line in enumerate(lines):
            match = self.CLASS_PATTERN.match(line)
            if match:
                info.class_line = i
                info.class_name = match.group(3)
                info.extends = match.group(4)

                implements_str = match.group(5)
                if implements_str:
                    info.implements = [
                        impl.strip()
                        for impl in implements_str.split(",")
                    ]
                break

    def _parse_class_body(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse class body: traits, properties, constructor, create."""
        if info.class_line == 0:
            return

        # Track docblock for properties/methods
        current_docblock_start: int | None = None
        current_docblock_end: int | None = None

        i = info.class_line + 1
        while i < len(lines):
            line = lines[i]

            # Track docblocks
            if self.DOCBLOCK_START.match(line):
                current_docblock_start = i
                current_docblock_end = None
            elif self.DOCBLOCK_END.match(line):
                current_docblock_end = i

            # Trait use statements inside class
            trait_match = self.TRAIT_USE_PATTERN.match(line)
            if trait_match:
                info.trait_use_lines.append(i)
                i += 1
                continue

            # Properties
            prop_match = self.PROPERTY_PATTERN.match(line)
            if prop_match:
                prop_name = prop_match.group(3)
                prop_type = prop_match.group(2)

                prop_info = PropertyInfo(
                    name=prop_name,
                    line=i,
                    type_hint=prop_type,
                    has_docblock=current_docblock_end is not None,
                    docblock_start=current_docblock_start,
                    docblock_end=current_docblock_end,
                )
                info.properties[prop_name] = prop_info

                if info.first_property_line is None:
                    info.first_property_line = (
                        current_docblock_start
                        if current_docblock_start is not None
                        else i
                    )

                # Reset docblock tracking
                current_docblock_start = None
                current_docblock_end = None
                i += 1
                continue

            # Constructor
            if self.CONSTRUCTOR_PATTERN.match(line):
                info.constructor = self._parse_constructor(
                    lines, i, current_docblock_start, current_docblock_end
                )
                i = info.constructor.end_line + 1
                current_docblock_start = None
                current_docblock_end = None
                continue

            # Create method
            if self.CREATE_PATTERN.match(line):
                info.create_method = self._parse_create_method(
                    lines, i, current_docblock_start, current_docblock_end
                )
                i = info.create_method.end_line + 1
                current_docblock_start = None
                current_docblock_end = None
                continue

            # Reset docblock if we hit non-docblock, non-empty line
            if line.strip() and not line.strip().startswith("*"):
                if not self.DOCBLOCK_START.match(line):
                    current_docblock_start = None
                    current_docblock_end = None

            i += 1

    def _parse_constructor(
        self,
        lines: list[str],
        start_line: int,
        docblock_start: int | None,
        docblock_end: int | None,
    ) -> ConstructorInfo:
        """Parse __construct() method."""
        # Find method end by counting braces
        brace_count = 0
        end_line = start_line
        params: list[tuple[str, str | None]] = []
        param_texts: list[str] = []
        body_lines: list[str] = []
        in_body = False

        # Extract parameters from declaration
        param_text = ""
        i = start_line
        while i < len(lines):
            param_text += lines[i]
            if ")" in lines[i]:
                break
            i += 1

        # Parse parameters
        param_section = re.search(r"\((.*)\)", param_text, re.DOTALL)
        if param_section:
            param_str = param_section.group(1)
            for param in param_str.split(","):
                orig = param.strip()
                if not orig:
                    continue
                param_texts.append(orig)

                # Normalize promoted properties: strip visibility and readonly tokens
                norm = re.sub(r"\b(private|protected|public)\b\s*", "", orig)
                norm = re.sub(r"\breadonly\b\s*", "", norm)

                # Match: TypeHint $name or $name
                param_match = re.match(r"(?:([\w\\]+)\s+)?(\$\w+)", norm)
                if param_match:
                    type_hint = param_match.group(1)
                    name = param_match.group(2).lstrip("$")
                    params.append((name, type_hint))

        # Find method body and end
        opening_brace_line: int | None = None
        for i in range(start_line, len(lines)):
            line = lines[i]

            if "{" in line:
                brace_count += line.count("{")
                if not in_body:
                    in_body = True
                    opening_brace_line = i

            if "}" in line:
                brace_count -= line.count("}")

            if in_body and brace_count == 0:
                end_line = i
                break

            # Only add lines after the opening brace line to body_lines
            if in_body and opening_brace_line is not None and i > opening_brace_line:
                body_lines.append(line)

        return ConstructorInfo(
            start_line=start_line,
            end_line=end_line,
            params=params,
            param_texts=param_texts,
            body_lines=body_lines,
            docblock_start=docblock_start,
            docblock_end=docblock_end,
        )

    def _parse_create_method(
        self,
        lines: list[str],
        start_line: int,
        docblock_start: int | None,
        docblock_end: int | None,
    ) -> CreateMethodInfo:
        """Parse create() method."""
        brace_count = 0
        end_line = start_line
        container_gets: list[str] = []
        found_open_brace = False

        for i in range(start_line, len(lines)):
            line = lines[i]

            # Extract container->get calls
            for match in self.CONTAINER_GET_PATTERN.finditer(line):
                container_gets.append(match.group(1))

            if "{" in line:
                brace_count += line.count("{")
                found_open_brace = True

            if "}" in line:
                brace_count -= line.count("}")

            # Method ends when braces are balanced after finding opening brace
            if found_open_brace and brace_count == 0:
                end_line = i
                break

        return CreateMethodInfo(
            start_line=start_line,
            end_line=end_line,
            container_gets=container_gets,
            docblock_start=docblock_start,
            docblock_end=docblock_end,
        )

    def get_property_insert_line(self, info: PhpClassInfo) -> int:
        """
        Get the line where new properties should be inserted.

        Priority:
        1. After last trait use statement
        2. After class declaration opening brace
        3. Before first existing property
        """
        if info.trait_use_lines:
            return info.trait_use_lines[-1] + 1

        if info.first_property_line is not None:
            return info.first_property_line

        # After class declaration (find the opening brace)
        return info.class_line + 1

    def has_use_statement(self, info: PhpClassInfo, fqcn: str) -> bool:
        """Check if a use statement already exists."""
        # Normalize FQCN (remove leading backslash)
        normalized = fqcn.lstrip("\\")

        for existing in info.use_statements:
            if existing.lstrip("\\") == normalized:
                return True

        return False
