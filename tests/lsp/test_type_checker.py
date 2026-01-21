"""
Comprehensive tests for drupalls/lsp/type_checker.py

Tests all public and private methods of the TypeChecker class:
- __init__: Constructor with optional PhpactorClient
- get_class_context: Get classified class context at position
- is_container_variable: Check if variable is ContainerInterface
- _query_variable_type: Query Phpactor for variable type
- _extract_variable_from_get_call: Extract variable name from ->get() call
- _is_container_interface: Check if type is ContainerInterface
- _position_to_offset: Convert LSP Position to byte offset
- _find_project_root: Find project root with composer.json
- clear_cache: Clear all caches

Mocked Dependencies:
- PhpactorClient.offset_info() - External subprocess call
- PhpactorClient.class_reflect() - External subprocess call
- PhpactorClient.get_class_hierarchy() - External subprocess call
- Path.exists() - File system access (for _find_project_root tests)

Not Mocked (Internal):
- DrupalContextClassifier - Pure Python logic, tested through integration
- ClassContextDetector - Tested through TypeChecker with mocked PhpactorClient
- ClassContext - Pure dataclass
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from lsprotocol.types import Position

from drupalls.lsp.type_checker import TypeChecker
from drupalls.phpactor.client import PhpactorClient, TypeInfo, ClassReflection
from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


# ============================================================================
# Test Fixtures
# ============================================================================


class MockDoc:
    """Simple mock document following project patterns."""
    
    def __init__(
        self,
        uri: str = "file:///test/project/src/Controller/TestController.php",
        lines: list[str] | None = None
    ):
        self.uri = uri
        self.lines = lines or ["<?php", "$container->get('service');"]


@pytest.fixture
def mock_phpactor():
    """Create a mock PhpactorClient with all async methods."""
    client = Mock(spec=PhpactorClient)
    client.offset_info = AsyncMock(return_value=None)
    client.class_reflect = AsyncMock(return_value=None)
    client.get_class_hierarchy = AsyncMock(return_value=[])
    client.clear_cache = Mock()
    return client


@pytest.fixture
def type_checker(mock_phpactor):
    """Create TypeChecker with mocked PhpactorClient."""
    return TypeChecker(phpactor_client=mock_phpactor)


@pytest.fixture
def sample_type_info():
    """Provide sample TypeInfo for testing."""
    return TypeInfo(
        type_name="Symfony\\Component\\DependencyInjection\\ContainerInterface",
        symbol_type="variable",
        fqcn="Symfony\\Component\\DependencyInjection\\ContainerInterface",
        offset=100,
        class_type="Symfony\\Component\\DependencyInjection\\ContainerInterface"
    )


@pytest.fixture
def sample_class_reflection():
    """Provide sample ClassReflection for testing."""
    return ClassReflection(
        fqcn="Drupal\\mymodule\\Controller\\TestController",
        short_name="TestController",
        parent_class="Drupal\\Core\\Controller\\ControllerBase",
        interfaces=["Drupal\\Core\\DependencyInjection\\ContainerInjectionInterface"],
        traits=[],
        methods=["create", "index", "__construct"],
        properties=["entityTypeManager"],
        is_abstract=False,
        is_final=False
    )


# ============================================================================
# Tests for __init__
# ============================================================================


class TestTypeCheckerInit:
    """Tests for TypeChecker.__init__ method."""

    def test_init_with_provided_phpactor_client(self, mock_phpactor):
        """Test initialization with a provided PhpactorClient."""
        checker = TypeChecker(phpactor_client=mock_phpactor)
        
        assert checker.phpactor is mock_phpactor
        assert checker.context_detector is not None
        assert checker.classifier is not None
        assert checker._type_cache == {}

    def test_init_without_phpactor_client(self):
        """Test initialization creates default PhpactorClient."""
        checker = TypeChecker(phpactor_client=None)
        
        assert isinstance(checker.phpactor, PhpactorClient)
        assert checker.context_detector is not None
        assert checker.classifier is not None

    def test_init_creates_empty_cache(self, mock_phpactor):
        """Test that type cache is initialized as empty dict."""
        checker = TypeChecker(phpactor_client=mock_phpactor)
        
        assert isinstance(checker._type_cache, dict)
        assert len(checker._type_cache) == 0


# ============================================================================
# Tests for _extract_variable_from_get_call (Pure Logic - No Mocking)
# ============================================================================


class TestExtractVariableFromGetCall:
    """Tests for _extract_variable_from_get_call method."""

    def test_simple_variable_container(self, type_checker):
        """Test extracting $container from $container->get('service')."""
        line = "$container->get('service');"
        position = Position(line=0, character=20)  # Inside get('')
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "container"

    def test_this_container_property(self, type_checker):
        """Test extracting container from $this->container->get('service')."""
        line = "$this->container->get('service');"
        position = Position(line=0, character=25)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "container"

    def test_method_call_get_container(self, type_checker):
        """Test extracting getContainer from $this->getContainer()->get('service').
        
        Note: Bare function calls like getContainer() without $ are rare in 
        Drupal container access patterns. The typical pattern is $this->getContainer().
        """
        line = "$this->getContainer()->get('service');"
        position = Position(line=0, character=30)  # Inside get('')
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        # The function extracts the last identifier before ->get(, which is getContainer
        assert result == "getContainer"

    def test_this_method_call(self, type_checker):
        """Test extracting getContainer from $this->getContainer()->get('service')."""
        line = "$this->getContainer()->get('service');"
        position = Position(line=0, character=30)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "getContainer"

    def test_no_get_call_in_line(self, type_checker):
        """Test returns None when no ->get() in line."""
        line = "$service = $container->has('service');"
        position = Position(line=0, character=30)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result is None

    def test_cursor_before_get_call(self, type_checker):
        """Test returns None when cursor is before ->get(."""
        line = "$container->get('service');"
        position = Position(line=0, character=5)  # Before ->get(
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result is None

    def test_multiple_get_calls_selects_correct_one(self, type_checker):
        """Test selects the correct ->get() when multiple exist."""
        line = "$a->get('first'); $container->get('second');"
        position = Position(line=0, character=38)  # Inside second get('')
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "container"

    def test_empty_line(self, type_checker):
        """Test returns None for empty line."""
        line = ""
        position = Position(line=0, character=0)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result is None

    def test_variable_with_underscore(self, type_checker):
        """Test extracting variable with underscores."""
        line = "$my_container->get('service');"
        position = Position(line=0, character=22)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "my_container"

    def test_variable_with_numbers(self, type_checker):
        """Test extracting variable with numbers."""
        line = "$container2->get('service');"
        position = Position(line=0, character=20)
        
        result = type_checker._extract_variable_from_get_call(line, position)
        
        assert result == "container2"


# ============================================================================
# Tests for _is_container_interface (Pure Logic - No Mocking)
# ============================================================================


class TestIsContainerInterface:
    """Tests for _is_container_interface method."""

    def test_full_symfony_container_interface(self, type_checker):
        """Test full FQCN Symfony ContainerInterface."""
        result = type_checker._is_container_interface(
            "Symfony\\Component\\DependencyInjection\\ContainerInterface"
        )
        assert result is True

    def test_short_container_interface(self, type_checker):
        """Test short name ContainerInterface."""
        result = type_checker._is_container_interface("ContainerInterface")
        assert result is True

    def test_psr_container_interface(self, type_checker):
        """Test PSR ContainerInterface."""
        result = type_checker._is_container_interface(
            "Psr\\Container\\ContainerInterface"
        )
        assert result is True

    def test_drupal_container_interface(self, type_checker):
        """Test Drupal ContainerInterface."""
        result = type_checker._is_container_interface(
            "Drupal\\Core\\DependencyInjection\\ContainerInterface"
        )
        assert result is True

    def test_non_container_type(self, type_checker):
        """Test non-container type returns False."""
        result = type_checker._is_container_interface("EntityTypeManager")
        assert result is False

    def test_case_insensitivity(self, type_checker):
        """Test case insensitivity of container interface check."""
        result = type_checker._is_container_interface("containerinterface")
        assert result is True

    def test_partial_match_in_fqcn(self, type_checker):
        """Test partial match within FQCN."""
        result = type_checker._is_container_interface(
            "SomeBundle\\ContainerInterface\\SomeClass"
        )
        assert result is True

    def test_similar_but_not_container(self, type_checker):
        """Test similar names that are not ContainerInterface."""
        result = type_checker._is_container_interface("Container")
        assert result is False

    def test_empty_string(self, type_checker):
        """Test empty string returns False."""
        result = type_checker._is_container_interface("")
        assert result is False


# ============================================================================
# Tests for _position_to_offset (Pure Logic - No Mocking)
# ============================================================================


class TestPositionToOffset:
    """Tests for _position_to_offset method."""

    def test_first_position(self, type_checker):
        """Test line 0, char 0 returns 0."""
        lines = ["<?php", "class Test {}", "}"]
        position = Position(line=0, character=0)
        
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 0

    def test_second_line_start(self, type_checker):
        """Test line 1, char 0 returns length of line 0 + 1."""
        lines = ["<?php", "class Test {}", "}"]
        position = Position(line=1, character=0)
        
        # "<?php" is 5 chars + 1 newline = 6
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 6

    def test_middle_of_line(self, type_checker):
        """Test position in middle of a line."""
        lines = ["<?php", "class Test {}", "}"]
        position = Position(line=1, character=6)  # On "Test"
        
        # Line 0: "<?php" = 5 + 1 newline = 6
        # Line 1: character 6
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 12

    def test_multiple_lines(self, type_checker):
        """Test offset calculation across multiple lines."""
        lines = ["abc", "def", "ghi"]
        position = Position(line=2, character=1)
        
        # Line 0: 3 + 1 = 4
        # Line 1: 3 + 1 = 4
        # Line 2: 1 char
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 9

    def test_character_past_line_length_caps_at_line_end(self, type_checker):
        """Test character position past line length caps at line end."""
        lines = ["abc", "de", "f"]
        position = Position(line=1, character=10)  # Past "de" length
        
        # Line 0: 3 + 1 = 4
        # Line 1: capped at 2 (length of "de")
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 6

    def test_empty_lines(self, type_checker):
        """Test with empty lines."""
        lines = ["", "", "test"]
        position = Position(line=2, character=2)
        
        # Line 0: 0 + 1 = 1
        # Line 1: 0 + 1 = 1
        # Line 2: 2 chars
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 4

    def test_single_line(self, type_checker):
        """Test with single line."""
        lines = ["hello world"]
        position = Position(line=0, character=5)
        
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 5

    def test_empty_lines_list(self, type_checker):
        """Test with empty lines list."""
        lines = []
        position = Position(line=0, character=0)
        
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 0

    def test_line_beyond_lines_list(self, type_checker):
        """Test with line number beyond available lines."""
        lines = ["abc", "def"]
        position = Position(line=5, character=0)
        
        # Should sum all available lines
        # Line 0: 3 + 1 = 4
        # Line 1: 3 + 1 = 4
        result = type_checker._position_to_offset(lines, position)
        
        assert result == 8


# ============================================================================
# Tests for _find_project_root (File System Access - Uses tmp_path)
# ============================================================================


class TestFindProjectRoot:
    """Tests for _find_project_root method."""

    def test_finds_composer_json_in_parent(self, type_checker, tmp_path):
        """Test finding composer.json in parent directory."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "composer.json").touch()
        
        src_dir = project_root / "src" / "Controller"
        src_dir.mkdir(parents=True)
        php_file = src_dir / "TestController.php"
        php_file.touch()
        
        result = type_checker._find_project_root(php_file)
        
        assert result == project_root

    def test_finds_composer_json_in_same_directory(self, type_checker, tmp_path):
        """Test finding composer.json in same directory as file."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "composer.json").touch()
        php_file = project_root / "test.php"
        php_file.touch()
        
        result = type_checker._find_project_root(php_file)
        
        assert result == project_root

    def test_returns_file_parent_if_not_found(self, type_checker, tmp_path):
        """Test returns file parent when composer.json not found."""
        # Create structure without composer.json
        src_dir = tmp_path / "orphan" / "src"
        src_dir.mkdir(parents=True)
        php_file = src_dir / "test.php"
        php_file.touch()
        
        result = type_checker._find_project_root(php_file)
        
        assert result == src_dir

    def test_searches_up_to_10_levels(self, type_checker, tmp_path):
        """Test searches parent directories up to 10 levels."""
        # Create deep nested structure
        deep_dir = tmp_path
        for i in range(12):
            deep_dir = deep_dir / f"level{i}"
        deep_dir.mkdir(parents=True)
        
        # Put composer.json 5 levels up
        root = tmp_path / "level0" / "level1" / "level2"
        (root / "composer.json").touch()
        
        php_file = deep_dir / "test.php"
        php_file.touch()
        
        result = type_checker._find_project_root(php_file)
        
        # Should find it within 10 levels
        assert (result / "composer.json").exists()

    def test_handles_path_as_string(self, type_checker, tmp_path):
        """Test handles file_path as string."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "composer.json").touch()
        php_file = project_root / "test.php"
        php_file.touch()
        
        result = type_checker._find_project_root(str(php_file))
        
        assert result == project_root


# ============================================================================
# Tests for is_container_variable (Async with Mocked PhpactorClient)
# ============================================================================


class TestIsContainerVariable:
    """Tests for is_container_variable async method."""

    @pytest.mark.asyncio
    async def test_phpactor_returns_container_interface(
        self, type_checker, mock_phpactor, sample_type_info
    ):
        """Test returns True when Phpactor returns ContainerInterface."""
        mock_phpactor.offset_info.return_value = sample_type_info
        
        doc = MockDoc()
        line = "$container->get('service');"
        position = Position(line=1, character=20)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        assert result is True
        mock_phpactor.offset_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_phpactor_returns_non_container_type(
        self, type_checker, mock_phpactor
    ):
        """Test returns False when Phpactor returns non-container type."""
        mock_phpactor.offset_info.return_value = TypeInfo(
            type_name="Drupal\\Core\\Entity\\EntityTypeManager",
            symbol_type="variable",
            fqcn="Drupal\\Core\\Entity\\EntityTypeManager",
            offset=100,
            class_type="Drupal\\Core\\Entity\\EntityTypeManager"
        )
        
        doc = MockDoc()
        line = "$entityManager->get('node');"
        position = Position(line=1, character=22)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_phpactor_returns_none_fallback_to_heuristic_container(
        self, type_checker, mock_phpactor
    ):
        """Test fallback to heuristic when Phpactor returns None - variable is 'container'."""
        mock_phpactor.offset_info.return_value = None
        
        doc = MockDoc()
        line = "$container->get('service');"
        position = Position(line=1, character=20)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        # Should return True because variable name is "container"
        assert result is True

    @pytest.mark.asyncio
    async def test_phpactor_returns_none_fallback_other_variable(
        self, type_checker, mock_phpactor
    ):
        """Test fallback returns False for non-container variable name."""
        mock_phpactor.offset_info.return_value = None
        
        doc = MockDoc()
        line = "$something->get('service');"
        position = Position(line=1, character=20)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        # Should return False because variable name is not "container"
        assert result is False

    @pytest.mark.asyncio
    async def test_caching_prevents_second_phpactor_call(
        self, type_checker, mock_phpactor, sample_type_info
    ):
        """Test that second call uses cache instead of querying Phpactor."""
        mock_phpactor.offset_info.return_value = sample_type_info
        
        doc = MockDoc()
        line = "$container->get('service');"
        position = Position(line=1, character=20)
        
        # First call
        result1 = await type_checker.is_container_variable(doc, line, position)
        # Second call with same parameters
        result2 = await type_checker.is_container_variable(doc, line, position)
        
        assert result1 is True
        assert result2 is True
        # Phpactor should only be called once
        assert mock_phpactor.offset_info.call_count == 1

    @pytest.mark.asyncio
    async def test_no_variable_extracted_returns_false(
        self, type_checker, mock_phpactor
    ):
        """Test returns False when no variable can be extracted."""
        doc = MockDoc()
        line = "// just a comment"
        position = Position(line=1, character=5)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        assert result is False
        # Phpactor should not be called
        mock_phpactor.offset_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_different_positions_use_different_cache_keys(
        self, type_checker, mock_phpactor, sample_type_info
    ):
        """Test that different line positions create different cache entries."""
        mock_phpactor.offset_info.return_value = sample_type_info
        
        doc = MockDoc(
            lines=[
                "<?php",
                "$container->get('service1');",
                "$container->get('service2');"
            ]
        )
        
        # Call at line 1
        position1 = Position(line=1, character=20)
        await type_checker.is_container_variable(doc, "$container->get('service1');", position1)
        
        # Call at line 2
        position2 = Position(line=2, character=20)
        await type_checker.is_container_variable(doc, "$container->get('service2');", position2)
        
        # Should call Phpactor twice (different cache keys)
        assert mock_phpactor.offset_info.call_count == 2


# ============================================================================
# Tests for _query_variable_type (Async with Mocked PhpactorClient)
# ============================================================================


class TestQueryVariableType:
    """Tests for _query_variable_type async method."""

    @pytest.mark.asyncio
    async def test_returns_type_name_from_type_info(
        self, type_checker, mock_phpactor, sample_type_info
    ):
        """Test returns type_name from TypeInfo."""
        mock_phpactor.offset_info.return_value = sample_type_info
        
        doc = MockDoc()
        position = Position(line=1, character=5)
        
        result = await type_checker._query_variable_type(doc, position)
        
        assert result == "Symfony\\Component\\DependencyInjection\\ContainerInterface"

    @pytest.mark.asyncio
    async def test_returns_none_when_phpactor_returns_none(
        self, type_checker, mock_phpactor
    ):
        """Test returns None when Phpactor returns None."""
        mock_phpactor.offset_info.return_value = None
        
        doc = MockDoc()
        position = Position(line=1, character=5)
        
        result = await type_checker._query_variable_type(doc, position)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_correctly_calculates_offset(
        self, type_checker, mock_phpactor
    ):
        """Test that offset is correctly calculated and passed to Phpactor."""
        mock_phpactor.offset_info.return_value = None
        
        doc = MockDoc(lines=["<?php", "class Test {}", "// line"])
        position = Position(line=2, character=3)
        
        await type_checker._query_variable_type(doc, position)
        
        # Verify offset_info was called with correct offset
        call_args = mock_phpactor.offset_info.call_args
        offset = call_args[0][1]  # Second positional argument
        
        # "<?php" (5) + newline (1) + "class Test {}" (13) + newline (1) + 3 chars = 23
        assert offset == 23

    @pytest.mark.asyncio
    async def test_extracts_file_path_from_uri(
        self, type_checker, mock_phpactor
    ):
        """Test that file path is correctly extracted from URI."""
        mock_phpactor.offset_info.return_value = None
        
        doc = MockDoc(uri="file:///home/user/project/test.php")
        position = Position(line=0, character=0)
        
        await type_checker._query_variable_type(doc, position)
        
        call_args = mock_phpactor.offset_info.call_args
        file_path = call_args[0][0]  # First positional argument
        
        assert file_path == Path("/home/user/project/test.php")


# ============================================================================
# Tests for get_class_context (Async with Mocked PhpactorClient)
# ============================================================================


class TestGetClassContext:
    """Tests for get_class_context async method."""

    @pytest.mark.asyncio
    async def test_returns_class_context_with_drupal_type(
        self, type_checker, mock_phpactor, sample_class_reflection, tmp_path
    ):
        """Test returns ClassContext with drupal_type set."""
        # Create a real PHP file for the test
        php_file = tmp_path / "TestController.php"
        php_file.write_text("""<?php
namespace Drupal\\mymodule\\Controller;

class TestController extends ControllerBase {
    public function index() {}
}
""")
        
        mock_phpactor.class_reflect.return_value = sample_class_reflection
        mock_phpactor.get_class_hierarchy.return_value = [
            "Drupal\\Core\\Controller\\ControllerBase"
        ]
        
        uri = f"file://{php_file}"
        position = Position(line=4, character=10)
        
        result = await type_checker.get_class_context(uri, position)
        
        assert result is not None
        assert isinstance(result, ClassContext)
        # Classifier should have been called and set drupal_type
        assert result.drupal_type == DrupalClassType.CONTROLLER

    @pytest.mark.asyncio
    async def test_returns_none_for_non_php_files(
        self, type_checker, mock_phpactor, tmp_path
    ):
        """Test returns None for non-PHP files."""
        # Create a non-PHP file
        yaml_file = tmp_path / "services.yml"
        yaml_file.write_text("services:\n  test.service:\n    class: Test")
        
        uri = f"file://{yaml_file}"
        position = Position(line=1, character=5)
        
        result = await type_checker.get_class_context(uri, position)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_in_class(
        self, type_checker, mock_phpactor, tmp_path
    ):
        """Test returns None when cursor is not inside a class."""
        php_file = tmp_path / "functions.php"
        php_file.write_text("""<?php
function helper() {
    return 'test';
}
""")
        
        mock_phpactor.class_reflect.return_value = None
        
        uri = f"file://{php_file}"
        position = Position(line=2, character=5)
        
        result = await type_checker.get_class_context(uri, position)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_provided_doc_lines(
        self, type_checker, mock_phpactor, sample_class_reflection, tmp_path
    ):
        """Test uses provided doc_lines instead of reading file."""
        php_file = tmp_path / "Test.php"
        php_file.write_text("<?php\nclass OldContent {}")  # Different from doc_lines
        
        mock_phpactor.class_reflect.return_value = sample_class_reflection
        mock_phpactor.get_class_hierarchy.return_value = ["ControllerBase"]
        
        doc_lines = [
            "<?php\n",
            "namespace Drupal\\mymodule\\Controller;\n",
            "\n",
            "class TestController extends ControllerBase {\n",
            "}\n"
        ]
        
        uri = f"file://{php_file}"
        position = Position(line=4, character=5)
        
        result = await type_checker.get_class_context(uri, position, doc_lines=doc_lines)
        
        # Should find class based on doc_lines, not file content
        assert result is not None

    @pytest.mark.asyncio
    async def test_classifier_is_called(
        self, type_checker, mock_phpactor, sample_class_reflection, tmp_path
    ):
        """Test that classifier.classify() is called on context."""
        php_file = tmp_path / "FormClass.php"
        php_file.write_text("""<?php
namespace Drupal\\mymodule\\Form;

class TestForm extends FormBase {
}
""")
        
        form_reflection = ClassReflection(
            fqcn="Drupal\\mymodule\\Form\\TestForm",
            short_name="TestForm",
            parent_class="Drupal\\Core\\Form\\FormBase",
            interfaces=["Drupal\\Core\\Form\\FormInterface"],
            traits=[],
            methods=["buildForm", "submitForm"],
            properties=[],
            is_abstract=False,
            is_final=False
        )
        
        mock_phpactor.class_reflect.return_value = form_reflection
        mock_phpactor.get_class_hierarchy.return_value = ["Drupal\\Core\\Form\\FormBase"]
        
        uri = f"file://{php_file}"
        position = Position(line=4, character=5)
        
        result = await type_checker.get_class_context(uri, position)
        
        assert result is not None
        # DrupalContextClassifier should classify as FORM
        assert result.drupal_type == DrupalClassType.FORM


# ============================================================================
# Tests for clear_cache
# ============================================================================


class TestClearCache:
    """Tests for clear_cache method."""

    def test_clears_type_cache(self, type_checker):
        """Test that _type_cache is cleared."""
        # Add some items to cache
        type_checker._type_cache[("uri", 1, "var")] = "SomeType"
        type_checker._type_cache[("uri", 2, "other")] = "OtherType"
        
        assert len(type_checker._type_cache) == 2
        
        type_checker.clear_cache()
        
        assert len(type_checker._type_cache) == 0

    def test_calls_context_detector_clear_cache(self, type_checker):
        """Test that context_detector.clear_cache() is called."""
        # Mock the context_detector's clear_cache
        type_checker.context_detector.clear_cache = Mock()
        
        type_checker.clear_cache()
        
        type_checker.context_detector.clear_cache.assert_called_once()

    def test_clear_cache_is_idempotent(self, type_checker):
        """Test that calling clear_cache multiple times is safe."""
        type_checker._type_cache[("uri", 1, "var")] = "Type"
        
        type_checker.clear_cache()
        type_checker.clear_cache()  # Should not raise
        
        assert len(type_checker._type_cache) == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestTypeCheckerIntegration:
    """Integration tests combining multiple TypeChecker methods."""

    @pytest.mark.asyncio
    async def test_full_container_check_flow(
        self, type_checker, mock_phpactor
    ):
        """Test complete flow: extract variable, query type, check container."""
        mock_phpactor.offset_info.return_value = TypeInfo(
            type_name="Psr\\Container\\ContainerInterface",
            symbol_type="variable",
            fqcn="Psr\\Container\\ContainerInterface",
            offset=50,
            class_type="Psr\\Container\\ContainerInterface"
        )
        
        doc = MockDoc(
            uri="file:///project/src/Service.php",
            lines=["<?php", "$this->container->get('service');"]
        )
        line = "$this->container->get('service');"
        position = Position(line=1, character=25)
        
        result = await type_checker.is_container_variable(doc, line, position)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_cache_cleared_affects_subsequent_calls(
        self, type_checker, mock_phpactor
    ):
        """Test that clearing cache causes Phpactor to be queried again."""
        mock_phpactor.offset_info.return_value = TypeInfo(
            type_name="ContainerInterface",
            symbol_type="variable",
            fqcn="ContainerInterface",
            offset=50,
            class_type="ContainerInterface"
        )
        
        doc = MockDoc()
        line = "$container->get('service');"
        position = Position(line=1, character=20)
        
        # First call
        await type_checker.is_container_variable(doc, line, position)
        assert mock_phpactor.offset_info.call_count == 1
        
        # Clear cache
        type_checker.clear_cache()
        
        # Second call should query Phpactor again
        await type_checker.is_container_variable(doc, line, position)
        assert mock_phpactor.offset_info.call_count == 2

    def test_type_checker_without_phpactor_still_works_for_pure_methods(self):
        """Test that pure methods work even with real PhpactorClient."""
        checker = TypeChecker()  # Uses real PhpactorClient
        
        # Pure methods should still work
        result = checker._is_container_interface("ContainerInterface")
        assert result is True
        
        lines = ["abc", "def"]
        offset = checker._position_to_offset(lines, Position(line=1, character=1))
        assert offset == 5  # 3 + 1 + 1
        
        result = checker._extract_variable_from_get_call(
            "$container->get('x');",
            Position(line=0, character=18)
        )
        assert result == "container"
