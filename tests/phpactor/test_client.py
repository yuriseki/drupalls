"""
Comprehensive tests for drupalls/phpactor/client.py

Tests all public and private functions with:
- Normal operation cases
- Edge cases and boundary conditions
- Error handling
- Type validation
"""
from __future__ import annotations

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from drupalls.phpactor.client import (
    ClassReflection,
    PhpactorClient,
    TypeInfo,
)


# =============================================================================
# TypeInfo Dataclass Tests
# =============================================================================


class TestTypeInfo:
    """Tests for TypeInfo dataclass."""

    def test_creation_with_all_values(self):
        """Test creating TypeInfo with all fields populated."""
        type_info = TypeInfo(
            type_name="EntityTypeManager",
            symbol_type="class",
            fqcn="Drupal\\Core\\Entity\\EntityTypeManager",
            offset=150,
            class_type="Drupal\\Core\\Entity\\EntityTypeManager",
        )

        assert type_info.type_name == "EntityTypeManager"
        assert type_info.symbol_type == "class"
        assert type_info.fqcn == "Drupal\\Core\\Entity\\EntityTypeManager"
        assert type_info.offset == 150
        assert type_info.class_type == "Drupal\\Core\\Entity\\EntityTypeManager"

    def test_creation_with_none_values(self):
        """Test creating TypeInfo with None values for optional fields."""
        type_info = TypeInfo(
            type_name=None,
            symbol_type=None,
            fqcn=None,
            offset=0,
            class_type=None,
        )

        assert type_info.type_name is None
        assert type_info.symbol_type is None
        assert type_info.fqcn is None
        assert type_info.offset == 0
        assert type_info.class_type is None

    def test_creation_with_mixed_values(self):
        """Test creating TypeInfo with some None and some populated values."""
        type_info = TypeInfo(
            type_name="string",
            symbol_type="variable",
            fqcn=None,
            offset=42,
            class_type=None,
        )

        assert type_info.type_name == "string"
        assert type_info.symbol_type == "variable"
        assert type_info.fqcn is None
        assert type_info.offset == 42

    def test_symbol_types(self):
        """Test TypeInfo with different symbol types."""
        symbol_types = ["class", "method", "property", "variable"]

        for sym_type in symbol_types:
            type_info = TypeInfo(
                type_name="Test",
                symbol_type=sym_type,
                fqcn=None,
                offset=10,
                class_type=None,
            )
            assert type_info.symbol_type == sym_type

    def test_offset_zero(self):
        """Test TypeInfo with offset at position zero."""
        type_info = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Test",
            offset=0,
            class_type="Test",
        )
        assert type_info.offset == 0

    def test_offset_large_value(self):
        """Test TypeInfo with large offset value."""
        large_offset = 1_000_000
        type_info = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Test",
            offset=large_offset,
            class_type="Test",
        )
        assert type_info.offset == large_offset

    def test_equality(self):
        """Test TypeInfo equality comparison."""
        type_info1 = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Drupal\\Test",
            offset=100,
            class_type="Drupal\\Test",
        )
        type_info2 = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Drupal\\Test",
            offset=100,
            class_type="Drupal\\Test",
        )
        assert type_info1 == type_info2

    def test_inequality(self):
        """Test TypeInfo inequality comparison."""
        type_info1 = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Drupal\\Test",
            offset=100,
            class_type="Drupal\\Test",
        )
        type_info2 = TypeInfo(
            type_name="Test",
            symbol_type="class",
            fqcn="Drupal\\Test",
            offset=200,  # Different offset
            class_type="Drupal\\Test",
        )
        assert type_info1 != type_info2


# =============================================================================
# ClassReflection Dataclass Tests
# =============================================================================


class TestClassReflection:
    """Tests for ClassReflection dataclass."""

    def test_creation_with_all_values(self):
        """Test creating ClassReflection with all fields populated."""
        reflection = ClassReflection(
            fqcn="Drupal\\Core\\Entity\\EntityTypeManager",
            short_name="EntityTypeManager",
            parent_class="Drupal\\Core\\Entity\\EntityTypeManagerBase",
            interfaces=["EntityTypeManagerInterface", "ContainerAwareInterface"],
            traits=["StringTranslationTrait"],
            methods=["getDefinition", "getDefinitions", "hasDefinition"],
            properties=["definitions", "handlers"],
            is_abstract=False,
            is_final=True,
        )

        assert reflection.fqcn == "Drupal\\Core\\Entity\\EntityTypeManager"
        assert reflection.short_name == "EntityTypeManager"
        assert reflection.parent_class == "Drupal\\Core\\Entity\\EntityTypeManagerBase"
        assert reflection.interfaces == [
            "EntityTypeManagerInterface",
            "ContainerAwareInterface",
        ]
        assert reflection.traits == ["StringTranslationTrait"]
        assert reflection.methods == ["getDefinition", "getDefinitions", "hasDefinition"]
        assert reflection.properties == ["definitions", "handlers"]
        assert reflection.is_abstract is False
        assert reflection.is_final is True

    def test_creation_with_minimal_values(self):
        """Test creating ClassReflection with minimal values."""
        reflection = ClassReflection(
            fqcn="SimpleClass",
            short_name="SimpleClass",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=[],
            properties=[],
            is_abstract=False,
            is_final=False,
        )

        assert reflection.fqcn == "SimpleClass"
        assert reflection.short_name == "SimpleClass"
        assert reflection.parent_class is None
        assert reflection.interfaces == []
        assert reflection.traits == []
        assert reflection.methods == []
        assert reflection.properties == []
        assert reflection.is_abstract is False
        assert reflection.is_final is False

    def test_creation_abstract_class(self):
        """Test creating ClassReflection for an abstract class."""
        reflection = ClassReflection(
            fqcn="Drupal\\Core\\Entity\\EntityBase",
            short_name="EntityBase",
            parent_class=None,
            interfaces=["EntityInterface"],
            traits=[],
            methods=["id", "uuid", "label"],
            properties=["entityTypeId"],
            is_abstract=True,
            is_final=False,
        )

        assert reflection.is_abstract is True
        assert reflection.is_final is False

    def test_creation_final_class(self):
        """Test creating ClassReflection for a final class."""
        reflection = ClassReflection(
            fqcn="Drupal\\Core\\StringTranslation\\TranslatableMarkup",
            short_name="TranslatableMarkup",
            parent_class="FormattableMarkup",
            interfaces=[],
            traits=[],
            methods=["__toString", "getUntranslatedString"],
            properties=["string", "arguments"],
            is_abstract=False,
            is_final=True,
        )

        assert reflection.is_abstract is False
        assert reflection.is_final is True

    def test_class_cannot_be_both_abstract_and_final(self):
        """Test that while technically possible to set both, it represents invalid PHP."""
        # Note: This is a data class, so it allows setting both
        # The validation would happen in PHP itself
        reflection = ClassReflection(
            fqcn="Invalid",
            short_name="Invalid",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=[],
            properties=[],
            is_abstract=True,
            is_final=True,
        )
        # Both can be set in the dataclass (no validation)
        assert reflection.is_abstract is True
        assert reflection.is_final is True

    def test_multiple_interfaces(self):
        """Test ClassReflection with multiple interfaces."""
        interfaces = [
            "EntityInterface",
            "AccessibleInterface",
            "CacheableDependencyInterface",
            "RefinableCacheableDependencyInterface",
        ]
        reflection = ClassReflection(
            fqcn="Drupal\\Core\\Entity\\Entity",
            short_name="Entity",
            parent_class=None,
            interfaces=interfaces,
            traits=[],
            methods=[],
            properties=[],
            is_abstract=False,
            is_final=False,
        )

        assert len(reflection.interfaces) == 4
        assert reflection.interfaces == interfaces

    def test_multiple_traits(self):
        """Test ClassReflection with multiple traits."""
        traits = [
            "StringTranslationTrait",
            "DependencySerializationTrait",
            "MessengerTrait",
        ]
        reflection = ClassReflection(
            fqcn="Drupal\\Core\\Form\\FormBase",
            short_name="FormBase",
            parent_class=None,
            interfaces=["FormInterface"],
            traits=traits,
            methods=["buildForm", "validateForm", "submitForm"],
            properties=["messenger"],
            is_abstract=True,
            is_final=False,
        )

        assert len(reflection.traits) == 3
        assert reflection.traits == traits

    def test_equality(self):
        """Test ClassReflection equality comparison."""
        reflection1 = ClassReflection(
            fqcn="Test",
            short_name="Test",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=["test"],
            properties=[],
            is_abstract=False,
            is_final=False,
        )
        reflection2 = ClassReflection(
            fqcn="Test",
            short_name="Test",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=["test"],
            properties=[],
            is_abstract=False,
            is_final=False,
        )
        assert reflection1 == reflection2

    def test_inequality_different_fqcn(self):
        """Test ClassReflection inequality when FQCN differs."""
        reflection1 = ClassReflection(
            fqcn="Test1",
            short_name="Test",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=[],
            properties=[],
            is_abstract=False,
            is_final=False,
        )
        reflection2 = ClassReflection(
            fqcn="Test2",
            short_name="Test",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=[],
            properties=[],
            is_abstract=False,
            is_final=False,
        )
        assert reflection1 != reflection2


# =============================================================================
# PhpactorClient Tests
# =============================================================================


class TestPhpactorClientInit:
    """Tests for PhpactorClient.__init__."""

    def test_init_with_explicit_root(self, tmp_path: Path):
        """Test initialization with explicit DrupalLS root directory."""
        client = PhpactorClient(drupalls_root=tmp_path)

        assert client.drupalls_root == tmp_path
        assert client.phpactor_dir == tmp_path / "phpactor"
        assert client.phpactor_bin == tmp_path / "phpactor" / "bin" / "phpactor"
        assert client._reflection_cache == {}

    def test_init_auto_detects_root(self):
        """Test initialization auto-detects DrupalLS root when None."""
        client = PhpactorClient(drupalls_root=None)

        # Should resolve to the project root (parent.parent.parent of client.py)
        expected_root = Path(__file__).resolve().parent.parent.parent
        # The client computes from its own location, so we just verify paths are set
        assert client.drupalls_root is not None
        assert client.phpactor_dir is not None
        assert client.phpactor_bin is not None
        assert client._reflection_cache == {}

    def test_init_creates_empty_cache(self, tmp_path: Path):
        """Test initialization creates an empty reflection cache."""
        client = PhpactorClient(drupalls_root=tmp_path)

        assert isinstance(client._reflection_cache, dict)
        assert len(client._reflection_cache) == 0


class TestPhpactorClientIsAvailable:
    """Tests for PhpactorClient.is_available."""

    def test_is_available_when_phpactor_not_exists(self, tmp_path: Path):
        """Test is_available returns False when phpactor binary doesn't exist."""
        client = PhpactorClient(drupalls_root=tmp_path)

        assert client.is_available() is False

    @patch("subprocess.run")
    def test_is_available_when_phpactor_works(
        self, mock_run: Mock, tmp_path: Path
    ):
        """Test is_available returns True when phpactor runs successfully."""
        # Create the phpactor binary path
        phpactor_bin = tmp_path / "phpactor" / "bin" / "phpactor"
        phpactor_bin.parent.mkdir(parents=True)
        phpactor_bin.touch()

        mock_run.return_value = Mock(returncode=0)

        client = PhpactorClient(drupalls_root=tmp_path)
        result = client.is_available()

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert str(phpactor_bin) in call_args[0][0]
        assert "--version" in call_args[0][0]

    @patch("subprocess.run")
    def test_is_available_when_phpactor_returns_error(
        self, mock_run: Mock, tmp_path: Path
    ):
        """Test is_available returns False when phpactor returns non-zero."""
        phpactor_bin = tmp_path / "phpactor" / "bin" / "phpactor"
        phpactor_bin.parent.mkdir(parents=True)
        phpactor_bin.touch()

        mock_run.return_value = Mock(returncode=1)

        client = PhpactorClient(drupalls_root=tmp_path)
        result = client.is_available()

        assert result is False

    @patch("subprocess.run")
    def test_is_available_when_subprocess_raises_exception(
        self, mock_run: Mock, tmp_path: Path
    ):
        """Test is_available returns False when subprocess raises exception."""
        phpactor_bin = tmp_path / "phpactor" / "bin" / "phpactor"
        phpactor_bin.parent.mkdir(parents=True)
        phpactor_bin.touch()

        mock_run.side_effect = OSError("Command not found")

        client = PhpactorClient(drupalls_root=tmp_path)
        result = client.is_available()

        assert result is False

    @patch("subprocess.run")
    def test_is_available_timeout(self, mock_run: Mock, tmp_path: Path):
        """Test is_available handles timeout correctly."""
        phpactor_bin = tmp_path / "phpactor" / "bin" / "phpactor"
        phpactor_bin.parent.mkdir(parents=True)
        phpactor_bin.touch()

        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="phpactor", timeout=5)

        client = PhpactorClient(drupalls_root=tmp_path)
        result = client.is_available()

        assert result is False


class TestPhpactorClientOffsetInfo:
    """Tests for PhpactorClient.offset_info (async)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    @pytest.fixture
    def sample_php_file(self, tmp_path: Path) -> Path:
        """Create a sample PHP file for testing."""
        php_file = tmp_path / "test.php"
        php_file.write_text("<?php\n$var = new EntityTypeManager();\n")
        return php_file

    @pytest.mark.asyncio
    async def test_offset_info_success(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info returns TypeInfo on successful call."""
        mock_stdout = b"Symbol Type: class\nType: EntityTypeManager\nClass: Drupal\\Core\\Entity\\EntityTypeManager\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_stdout, b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.offset_info(sample_php_file, offset=50)

            assert result is not None
            assert isinstance(result, TypeInfo)
            assert result.type_name == "EntityTypeManager"
            assert result.symbol_type == "class"
            assert result.fqcn == "Drupal\\Core\\Entity\\EntityTypeManager"
            assert result.offset == 50

    @pytest.mark.asyncio
    async def test_offset_info_with_working_dir(
        self, client: PhpactorClient, sample_php_file: Path, tmp_path: Path
    ):
        """Test offset_info uses provided working directory."""
        mock_stdout = b"Type: string\nSymbol Type: variable\n"
        working_dir = tmp_path / "project"
        working_dir.mkdir()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_stdout, b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.offset_info(
                sample_php_file, offset=10, working_dir=working_dir
            )

            assert result is not None
            # Verify working_dir was passed to subprocess
            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["cwd"] == str(working_dir)

    @pytest.mark.asyncio
    async def test_offset_info_returns_none_on_non_zero_return(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info returns None when phpactor returns non-zero."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error occurred")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await client.offset_info(sample_php_file, offset=50)

            assert result is None

    @pytest.mark.asyncio
    async def test_offset_info_returns_none_on_exception(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info returns None when exception occurs."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = OSError("Process failed to start")

            result = await client.offset_info(sample_php_file, offset=50)

            assert result is None

    @pytest.mark.asyncio
    async def test_offset_info_parses_partial_output(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info handles partial CLI output."""
        # Only type, no class info
        mock_stdout = b"Type: mixed\nSymbol Type: variable\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_stdout, b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.offset_info(sample_php_file, offset=10)

            assert result is not None
            assert result.type_name == "mixed"
            assert result.symbol_type == "variable"
            assert result.fqcn is None  # Not in output

    @pytest.mark.asyncio
    async def test_offset_info_empty_output(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info handles empty CLI output."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.offset_info(sample_php_file, offset=10)

            assert result is not None
            assert result.type_name is None
            assert result.symbol_type is None
            assert result.fqcn is None
            assert result.offset == 10

    @pytest.mark.asyncio
    async def test_offset_info_default_working_dir(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test offset_info uses file parent as default working dir."""
        mock_stdout = b"Type: Test\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_stdout, b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            await client.offset_info(sample_php_file, offset=10)

            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["cwd"] == str(sample_php_file.parent)


class TestPhpactorClientClassReflect:
    """Tests for PhpactorClient.class_reflect (async)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    @pytest.fixture
    def sample_php_file(self, tmp_path: Path) -> Path:
        """Create a sample PHP file for testing."""
        php_file = tmp_path / "EntityTypeManager.php"
        php_file.write_text("<?php\nclass EntityTypeManager {}\n")
        return php_file

    @pytest.mark.asyncio
    async def test_class_reflect_success(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect returns ClassReflection on success."""
        rpc_response = {
            "class": "Drupal\\Core\\Entity\\EntityTypeManager",
            "name": "EntityTypeManager",
            "parent": "Drupal\\Core\\Entity\\EntityTypeManagerBase",
            "interfaces": ["EntityTypeManagerInterface"],
            "traits": ["StringTranslationTrait"],
            "methods": [{"name": "getDefinition"}, {"name": "getDefinitions"}],
            "properties": [{"name": "definitions"}, {"name": "handlers"}],
            "abstract": False,
            "final": True,
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(rpc_response).encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.class_reflect(sample_php_file, offset=50)

            assert result is not None
            assert isinstance(result, ClassReflection)
            assert result.fqcn == "Drupal\\Core\\Entity\\EntityTypeManager"
            assert result.short_name == "EntityTypeManager"
            assert result.parent_class == "Drupal\\Core\\Entity\\EntityTypeManagerBase"
            assert result.interfaces == ["EntityTypeManagerInterface"]
            assert result.traits == ["StringTranslationTrait"]
            assert result.methods == ["getDefinition", "getDefinitions"]
            assert result.properties == ["definitions", "handlers"]
            assert result.is_abstract is False
            assert result.is_final is True

    @pytest.mark.asyncio
    async def test_class_reflect_with_working_dir(
        self, client: PhpactorClient, sample_php_file: Path, tmp_path: Path
    ):
        """Test class_reflect uses provided working directory."""
        working_dir = tmp_path / "project"
        working_dir.mkdir()

        rpc_response = {
            "class": "Test",
            "name": "Test",
            "parent": None,
            "interfaces": [],
            "traits": [],
            "methods": [],
            "properties": [],
            "abstract": False,
            "final": False,
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(rpc_response).encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            await client.class_reflect(
                sample_php_file, offset=10, working_dir=working_dir
            )

            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["cwd"] == str(working_dir)

    @pytest.mark.asyncio
    async def test_class_reflect_returns_none_on_non_zero_return(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect returns None when phpactor returns non-zero."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await client.class_reflect(sample_php_file, offset=50)

            assert result is None

    @pytest.mark.asyncio
    async def test_class_reflect_returns_none_on_exception(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect returns None when exception occurs."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = OSError("Process failed")

            result = await client.class_reflect(sample_php_file, offset=50)

            assert result is None

    @pytest.mark.asyncio
    async def test_class_reflect_handles_empty_response(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect returns None for empty response."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"{}", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Empty dict evaluates to False in Python
            result = await client.class_reflect(sample_php_file, offset=50)

            # Empty dict {} is falsy, so this returns None
            assert result is None

    @pytest.mark.asyncio
    async def test_class_reflect_handles_minimal_response(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect handles minimal valid response."""
        rpc_response = {
            "class": "SimpleClass",
            "name": "SimpleClass",
            # All other fields missing - should use defaults
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(rpc_response).encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.class_reflect(sample_php_file, offset=50)

            assert result is not None
            assert result.fqcn == "SimpleClass"
            assert result.short_name == "SimpleClass"
            assert result.parent_class is None
            assert result.interfaces == []
            assert result.traits == []
            assert result.methods == []
            assert result.properties == []
            assert result.is_abstract is False
            assert result.is_final is False

    @pytest.mark.asyncio
    async def test_class_reflect_handles_invalid_json(
        self, client: PhpactorClient, sample_php_file: Path
    ):
        """Test class_reflect returns None for invalid JSON response."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"not valid json", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.class_reflect(sample_php_file, offset=50)

            assert result is None


class TestPhpactorClientGetClassHierarchy:
    """Tests for PhpactorClient.get_class_hierarchy (async)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    @pytest.mark.asyncio
    async def test_get_class_hierarchy_single_parent(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test getting hierarchy with single parent class."""
        responses = [
            {"class": "ChildClass", "parent": "ParentClass"},
            {"class": "ParentClass", "parent": None},
        ]
        response_iter = iter(responses)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            async def mock_communicate(input=None):
                response = next(response_iter)
                return (json.dumps(response).encode(), b"")

            mock_process = AsyncMock()
            mock_process.communicate = mock_communicate
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.get_class_hierarchy(
                "ChildClass", working_dir=tmp_path
            )

            assert result == ["ParentClass"]

    @pytest.mark.asyncio
    async def test_get_class_hierarchy_multiple_parents(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test getting hierarchy with multiple parent classes."""
        responses = [
            {"class": "GrandChild", "parent": "Child"},
            {"class": "Child", "parent": "Parent"},
            {"class": "Parent", "parent": "GrandParent"},
            {"class": "GrandParent", "parent": None},
        ]
        response_iter = iter(responses)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            async def mock_communicate(input=None):
                response = next(response_iter)
                return (json.dumps(response).encode(), b"")

            mock_process = AsyncMock()
            mock_process.communicate = mock_communicate
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.get_class_hierarchy("GrandChild", working_dir=tmp_path)

            assert result == ["Child", "Parent", "GrandParent"]

    @pytest.mark.asyncio
    async def test_get_class_hierarchy_no_parent(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test getting hierarchy for class with no parent."""
        rpc_response = {"class": "StandaloneClass", "parent": None}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(rpc_response).encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.get_class_hierarchy(
                "StandaloneClass", working_dir=tmp_path
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_get_class_hierarchy_empty_response(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test getting hierarchy when RPC returns empty response."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await client.get_class_hierarchy("Unknown", working_dir=tmp_path)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_class_hierarchy_prevents_infinite_loop(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test that hierarchy lookup prevents infinite loops from circular refs."""
        # Simulate circular reference: A -> B -> A
        # The code adds each parent to the hierarchy, then checks if the NEXT
        # class was already seen before continuing
        responses = [
            {"class": "ClassA", "parent": "ClassB"},
            {"class": "ClassB", "parent": "ClassA"},  # Circular!
        ]
        response_iter = iter(responses)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            async def mock_communicate(input=None):
                try:
                    response = next(response_iter)
                    return (json.dumps(response).encode(), b"")
                except StopIteration:
                    return (b"{}", b"")

            mock_process = AsyncMock()
            mock_process.communicate = mock_communicate
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client.get_class_hierarchy("ClassA", working_dir=tmp_path)

            # The code behavior: adds ClassB, then sees ClassA is parent of ClassB,
            # adds ClassA to hierarchy, then when trying ClassA again it's already
            # in 'seen' so it stops. Result is ["ClassB", "ClassA"]
            # This prevents infinite loops even though both are included.
            assert result == ["ClassB", "ClassA"]
            # Verify we didn't loop forever (only 2 subprocess calls)
            assert mock_exec.call_count == 2


class TestPhpactorClientRpcCommandAsync:
    """Tests for PhpactorClient._rpc_command_async (private async method)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    @pytest.mark.asyncio
    async def test_rpc_command_async_success(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test successful RPC command execution."""
        expected_response = {"result": "success", "data": {"foo": "bar"}}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(expected_response).encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client._rpc_command_async(
                "test_action", {"param": "value"}, working_dir=tmp_path
            )

            assert result == expected_response

            # Verify correct RPC data was sent
            call_args = mock_process.communicate.call_args
            input_data = json.loads(call_args.kwargs["input"].decode())
            assert input_data["action"] == "test_action"
            assert input_data["parameters"] == {"param": "value"}

    @pytest.mark.asyncio
    async def test_rpc_command_async_returns_none_on_error(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test RPC command returns None on subprocess error."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"Error message")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await client._rpc_command_async(
                "test_action", {}, working_dir=tmp_path
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_rpc_command_async_returns_none_on_exception(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test RPC command returns None when exception occurs."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = Exception("Unexpected error")

            result = await client._rpc_command_async(
                "test_action", {}, working_dir=tmp_path
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_rpc_command_async_returns_none_on_invalid_json(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test RPC command returns None when response is invalid JSON."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"not json", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await client._rpc_command_async(
                "test_action", {}, working_dir=tmp_path
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_rpc_command_async_uses_correct_command(
        self, client: PhpactorClient, tmp_path: Path
    ):
        """Test RPC command uses correct phpactor CLI arguments."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"{}", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            await client._rpc_command_async("test", {}, working_dir=tmp_path)

            call_args = mock_exec.call_args[0]
            assert "rpc" in call_args
            assert "--working-dir" in call_args
            assert str(tmp_path) in call_args


class TestPhpactorClientParseCliOutput:
    """Tests for PhpactorClient._parse_cli_output (private method)."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    def test_parse_cli_output_standard_format(self, client: PhpactorClient):
        """Test parsing standard CLI output format."""
        output = "Type: EntityTypeManager\nSymbol Type: class\nClass: Drupal\\Core\\Entity\\EntityTypeManager\n"

        result = client._parse_cli_output(output)

        assert result["type"] == "EntityTypeManager"
        assert result["symbol_type"] == "class"  # Normalized to snake_case
        assert result["class"] == "Drupal\\Core\\Entity\\EntityTypeManager"

    def test_parse_cli_output_empty_string(self, client: PhpactorClient):
        """Test parsing empty output."""
        result = client._parse_cli_output("")

        assert result == {}

    def test_parse_cli_output_no_colons(self, client: PhpactorClient):
        """Test parsing output with no key-value pairs."""
        output = "Some random text without colons\nAnother line"

        result = client._parse_cli_output(output)

        assert result == {}

    def test_parse_cli_output_strips_whitespace(self, client: PhpactorClient):
        """Test that keys and values are stripped of whitespace."""
        output = "  Type  :  EntityTypeManager  \n  Class  :  Test  "

        result = client._parse_cli_output(output)

        assert result["type"] == "EntityTypeManager"
        assert result["class"] == "Test"

    def test_parse_cli_output_handles_value_with_colons(self, client: PhpactorClient):
        """Test parsing values that contain colons (like namespaces)."""
        output = "Class: Drupal\\Core\\Entity::EntityTypeManager\n"

        result = client._parse_cli_output(output)

        # Should only split on first colon
        assert result["class"] == "Drupal\\Core\\Entity::EntityTypeManager"

    def test_parse_cli_output_lowercases_keys(self, client: PhpactorClient):
        """Test that keys are lowercased and spaces replaced with underscores."""
        output = "TYPE: test\nSYMBOL TYPE: class\nCLASS: MyClass\n"

        result = client._parse_cli_output(output)

        assert "type" in result
        assert "symbol_type" in result  # Spaces replaced with underscores
        assert "class" in result
        assert "TYPE" not in result

    def test_parse_cli_output_preserves_value_case(self, client: PhpactorClient):
        """Test that values preserve their original case."""
        output = "Class: Drupal\\Core\\Entity\\EntityTypeManager\n"

        result = client._parse_cli_output(output)

        assert result["class"] == "Drupal\\Core\\Entity\\EntityTypeManager"

    def test_parse_cli_output_handles_empty_value(self, client: PhpactorClient):
        """Test parsing line with empty value."""
        output = "Type:\nClass: Test\n"

        result = client._parse_cli_output(output)

        assert result["type"] == ""
        assert result["class"] == "Test"

    def test_parse_cli_output_single_line(self, client: PhpactorClient):
        """Test parsing single line output."""
        output = "Type: string"

        result = client._parse_cli_output(output)

        assert result["type"] == "string"


class TestPhpactorClientClearCache:
    """Tests for PhpactorClient.clear_cache."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    def test_clear_cache_empty(self, client: PhpactorClient):
        """Test clearing an already empty cache."""
        assert client._reflection_cache == {}

        client.clear_cache()

        assert client._reflection_cache == {}

    def test_clear_cache_with_entries(self, client: PhpactorClient):
        """Test clearing cache with entries."""
        # Add some entries to cache
        reflection = ClassReflection(
            fqcn="Test",
            short_name="Test",
            parent_class=None,
            interfaces=[],
            traits=[],
            methods=[],
            properties=[],
            is_abstract=False,
            is_final=False,
        )
        client._reflection_cache["Test"] = reflection
        client._reflection_cache["Test2"] = reflection

        assert len(client._reflection_cache) == 2

        client.clear_cache()

        assert client._reflection_cache == {}
        assert len(client._reflection_cache) == 0

    def test_clear_cache_can_be_called_multiple_times(self, client: PhpactorClient):
        """Test that clear_cache can be called multiple times safely."""
        client.clear_cache()
        client.clear_cache()
        client.clear_cache()

        assert client._reflection_cache == {}


# =============================================================================
# Integration-like Tests (still with mocked subprocess)
# =============================================================================


class TestPhpactorClientIntegration:
    """Integration-like tests for PhpactorClient workflows."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> PhpactorClient:
        """Create a PhpactorClient for testing."""
        return PhpactorClient(drupalls_root=tmp_path)

    @pytest.fixture
    def php_project(self, tmp_path: Path) -> Path:
        """Create a mock PHP project structure."""
        project = tmp_path / "drupal"
        project.mkdir()

        # Create some PHP files
        (project / "EntityTypeManager.php").write_text(
            """<?php
namespace Drupal\\Core\\Entity;

class EntityTypeManager extends EntityTypeManagerBase {
    public function getDefinition($entity_type_id) {}
}
"""
        )

        return project

    @pytest.mark.asyncio
    async def test_full_workflow_offset_to_class_reflect(
        self, client: PhpactorClient, php_project: Path
    ):
        """Test workflow: get type at offset, then get full class reflection."""
        php_file = php_project / "EntityTypeManager.php"

        # First call: offset_info
        offset_response = b"Type: EntityTypeManager\nSymbol Type: class\nClass: Drupal\\Core\\Entity\\EntityTypeManager\n"

        # Second call: class_reflect via RPC
        rpc_response = {
            "class": "Drupal\\Core\\Entity\\EntityTypeManager",
            "name": "EntityTypeManager",
            "parent": "Drupal\\Core\\Entity\\EntityTypeManagerBase",
            "interfaces": ["EntityTypeManagerInterface"],
            "traits": [],
            "methods": [{"name": "getDefinition"}],
            "properties": [],
            "abstract": False,
            "final": False,
        }

        call_count = [0]

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            async def mock_communicate(input=None):
                call_count[0] += 1
                if call_count[0] == 1:
                    return (offset_response, b"")
                else:
                    return (json.dumps(rpc_response).encode(), b"")

            mock_process = AsyncMock()
            mock_process.communicate = mock_communicate
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Step 1: Get type at offset
            type_info = await client.offset_info(php_file, offset=100)

            assert type_info is not None
            assert type_info.fqcn == "Drupal\\Core\\Entity\\EntityTypeManager"

            # Step 2: Get full class reflection
            reflection = await client.class_reflect(php_file, offset=100)

            assert reflection is not None
            assert reflection.fqcn == type_info.fqcn
            assert reflection.parent_class == "Drupal\\Core\\Entity\\EntityTypeManagerBase"
            assert "getDefinition" in reflection.methods
