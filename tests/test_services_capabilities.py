"""
Comprehensive tests for drupalls/lsp/capabilities/services_capabilities.py

Tests all public and private functions with:
- Normal operation cases
- Edge cases and boundary conditions
- Error handling
- Type validation
"""
from __future__ import annotations

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionParams,
    Position,
    TextDocumentIdentifier,
    CompletionContext,
    CompletionTriggerKind,
    InsertTextFormat,
    LogMessageParams,
    MessageType,
)

# Import the module under test
from drupalls.lsp.capabilities.services_capabilities import (
    ServiceMethodCompletionCapability,
    _is_service_pattern, # Although not directly requested, it's a helper for other capabilities and might be useful to test.
    _basic_container_check, # Helper for _is_service_pattern
)
from drupalls.lsp.drupal_language_server import DrupalLanguageServer
from drupalls.workspace.cache import WorkspaceCache
from drupalls.workspace.services_cache import ServiceDefinition, ServicesCache
from drupalls.workspace.classes_cache import ClassesCache


# --- Fixtures ---

@pytest.fixture
def mock_server() -> MagicMock:
    """Provides a mock DrupalLanguageServer instance."""
    server = MagicMock(spec=DrupalLanguageServer)
    server.workspace = MagicMock()
    server.workspace_cache = MagicMock(spec=WorkspaceCache)
    server.window_log_message = MagicMock()
    server.type_checker = None # Default to no type checker
    return server

@pytest.fixture
def mock_text_document() -> MagicMock:
    """Provides a mock TextDocument."""
    doc = MagicMock()
    doc.lines = []
    doc.word_at_position.return_value = ""
    return doc

@pytest.fixture
def mock_services_cache() -> MagicMock:
    """Provides a mock ServicesCache."""
    cache = MagicMock(spec=ServicesCache)
    cache.get.return_value = None
    cache.get_all.return_value = {}
    return cache

@pytest.fixture
def mock_classes_cache() -> MagicMock:
    """Provides a mock ClassesCache."""
    cache = MagicMock(spec=ClassesCache)
    cache.get_methods.return_value = []
    return cache

@pytest.fixture
def service_method_capability(mock_server: MagicMock) -> ServiceMethodCompletionCapability:
    """Provides an instance of ServiceMethodCompletionCapability."""
    return ServiceMethodCompletionCapability(mock_server)

@pytest.fixture
def completion_params_factory():
    """Factory for creating CompletionParams."""
    def _factory(
        line: int = 0,
        character: int = 0,
        trigger_kind: CompletionTriggerKind = CompletionTriggerKind.Invoked,
        trigger_character: str | None = None,
        uri: str = "file:///test.php",
    ) -> CompletionParams:
        context = CompletionContext(
            trigger_kind=trigger_kind,
            trigger_character=trigger_character,
        )
        return CompletionParams(
            text_document=TextDocumentIdentifier(uri=uri),
            position=Position(line=line, character=character),
            context=context,
        )
    return _factory

@pytest.fixture
def sample_service_definition() -> ServiceDefinition:
    """Provides a sample ServiceDefinition."""
    return ServiceDefinition(
        id="entity_type.manager",
        class_name="Drupal\\Core\\Entity\\EntityTypeManager",
        class_file_path="/path/to/Drupal/Core/Entity/EntityTypeManager.php",
        description="Manages entity types.",
        file_path=Path("/path/to/file.yml"),
        line_number=10,
        arguments=["@container"],
    )

# --- Tests for ServiceMethodCompletionCapability ---

class TestServiceMethodCompletionCapability:
    """Tests for ServiceMethodCompletionCapability."""

    def test_name_property(self, service_method_capability: ServiceMethodCompletionCapability):
        """Test the name property."""
        assert service_method_capability.name == "Service Method Completion"

    def test_description_property(self, service_method_capability: ServiceMethodCompletionCapability):
        """Test the description property."""
        assert service_method_capability.description == "Provides auto-completion for methods on Drupal service objects."

    def test_init(self, mock_server: MagicMock):
        """Test initialization of the capability."""
        capability = ServiceMethodCompletionCapability(mock_server)
        assert capability.server == mock_server
        # No direct cache assignments in __init__ anymore, they are accessed dynamically.

    @pytest.mark.parametrize(
        "line_content, cursor_char, trigger_char, expected_can_handle",
        [
            # Valid cases
            (r"\Drupal::service('foo')->", 24, ">", True),
            (r"\Drupal::service('foo')->bar", 26, ">", True),
            (r"\Drupal::service('foo') ->", 25, ">", True), # With whitespace
            (r"\Drupal::getContainer()->get('foo')->", 37, ">", True),
            (r"\Drupal::getContainer()->get('foo') ->", 38, ">", True),
            (r"$var = \Drupal::service('my.service')->", 35, ">", True),
            (r"\Drupal::service('foo')->", 24, None, True), # Invoked, cursor after ->
            (r"\Drupal::service('foo') ->", 25, None, True), # Invoked, cursor after -> with space

            # Invalid cases (no service ID or no '->' before cursor)
            (r"\Drupal::service('foo')", 22, ">", False), # No '->'
            (r"\Drupal::service('foo')", 22, None, False), # No '->'
            (r"\Drupal::service('foo') ", 23, ">", False), # No '->'
            (r"\Drupal::service('foo') ", 23, None, False), # No '->'
            (r"some_other_call()->", 18, ">", False), # Not a service call
            (r"->", 2, ">", False), # Only '->'
            (r"foo->", 4, ">", False), # Not a service call
            (r"\Drupal::service('foo')", 10, ">", False), # Cursor before '->'
            (r"\Drupal::service('foo')->", 22, None, False), # Cursor on '-' of '->'
            (r"\Drupal::service('foo')->", 21, None, False), # Cursor before '->'
            (r"\Drupal::service('foo')->bar", 26, None, True), # Cursor after method name, still valid
            (r"\Drupal::service('foo')->bar(", 27, None, True), # Cursor after method call, still valid
            (r"\Drupal::service('foo') ->", 23, None, False), # Cursor on space before ->
            (r"\Drupal::service('foo') ->", 25, None, True), # Cursor after -> with space
        ],
    )
    @pytest.mark.asyncio
    async def test_can_handle(
        self,
        service_method_capability: ServiceMethodCompletionCapability,
        mock_server: MagicMock,
        mock_text_document: MagicMock,
        completion_params_factory,
        line_content: str,
        cursor_char: int,
        trigger_char: str | None,
        expected_can_handle: bool,
    ):
        """Test can_handle method with various line contents and cursor positions."""
        mock_text_document.lines = [line_content]
        mock_server.workspace.get_text_document.return_value = mock_text_document

        params = completion_params_factory(
            line=0, character=cursor_char, trigger_character=trigger_char
        )

        result = await service_method_capability.can_handle(params)
        assert result == expected_can_handle

    @pytest.mark.asyncio
    async def test_complete_no_workspace_cache(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, completion_params_factory
    ):
        """Test complete returns None if workspace_cache is not available."""
        mock_server.workspace_cache = None
        params = completion_params_factory()
        result = await service_method_capability.complete(params)
        assert result is None

    @pytest.mark.asyncio
    async def test_complete_no_services_cache(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, completion_params_factory
    ):
        """Test complete logs warning and returns None if services cache is missing."""
        mock_server.workspace_cache.caches = {} # No services cache
        params = completion_params_factory()
        result = await service_method_capability.complete(params)
        assert result is None
        mock_server.window_log_message.assert_called_once_with(
            LogMessageParams(
                type=MessageType.Warning,
                message="Services or Classes cache not available.",
            )
        )

    @pytest.mark.asyncio
    async def test_complete_no_classes_cache(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, completion_params_factory, mock_services_cache
    ):
        """Test complete logs warning and returns None if classes cache is missing."""
        mock_server.workspace_cache.caches = {"services": mock_services_cache} # No classes cache
        params = completion_params_factory()
        result = await service_method_capability.complete(params)
        assert result is None
        mock_server.window_log_message.assert_called_once_with(
            LogMessageParams(
                type=MessageType.Warning,
                message="Services or Classes cache not available.",
            )
        )

    @pytest.mark.asyncio
    async def test_complete_no_service_id_extracted(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache
    ):
        """Test complete returns None if _extract_service_id_from_line returns None."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"some_other_call()->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        # Mock _extract_service_id_from_line to return None
        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value=None) as mock_extract:
            params = completion_params_factory(line=0, character=18, trigger_character=">")
            result = await service_method_capability.complete(params)
            assert result is None
            mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_service_not_found_in_cache(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache
    ):
        """Test complete logs info and returns None if service not found in cache."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('non_existent_service')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        mock_services_cache.get.return_value = None # Service not found

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="non_existent_service"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)
            assert result is None
            mock_server.window_log_message.assert_called_once_with(
                LogMessageParams(
                    type=MessageType.Info,
                    message="Could not find service definition for service ID: non_existent_service",
                )
            )

    @pytest.mark.asyncio
    async def test_complete_service_definition_no_class_name(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache
    ):
        """Test complete logs info and returns None if service definition has no class name."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('service_without_class')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        # Mock service definition without class_name
        mock_service_def = MagicMock(spec=ServiceDefinition)
        mock_service_def.service_id = "service_without_class"
        mock_service_def.class_name = None
        mock_services_cache.get.return_value = mock_service_def

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="service_without_class"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)
            assert result is None
            mock_server.window_log_message.assert_called_once_with(
                LogMessageParams(
                    type=MessageType.Info,
                    message="Service definition for service_without_class has no class name.",
                )
            )

    @pytest.mark.asyncio
    async def test_complete_class_no_methods(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache, sample_service_definition
    ):
        """Test complete logs info and returns empty CompletionList if class has no methods."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('entity_type.manager')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        mock_services_cache.get.return_value = sample_service_definition
        mock_classes_cache.get_methods.return_value = [] # No methods

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="entity_type.manager"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)
            assert isinstance(result, CompletionList)
            assert result.is_incomplete is False
            assert result.items == []
            mock_server.window_log_message.assert_called_once_with(
                LogMessageParams(
                    type=MessageType.Info,
                    message=f"No methods found for class: {sample_service_definition.class_name}",
                )
            )

    @pytest.mark.asyncio
    async def test_complete_normal_operation(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache, sample_service_definition
    ):
        """Test complete method with normal operation, returning methods."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('entity_type.manager')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        mock_services_cache.get.return_value = sample_service_definition
        mock_classes_cache.get_methods.return_value = ["getDefinition", "getStorage", "getHandler"]

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="entity_type.manager"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)

            assert isinstance(result, CompletionList)
            assert result.is_incomplete is False
            assert len(result.items) == 3

            expected_labels = ["getDefinition", "getStorage", "getHandler"]
            actual_labels = [item.label for item in result.items]
            assert actual_labels == expected_labels

            for item in result.items:
                assert item.kind == CompletionItemKind.Method
                assert item.insert_text == f"{item.label}()"
                assert item.insert_text_format == InsertTextFormat.Snippet
                assert item.detail == f"Method of {sample_service_definition.class_name}"

    @pytest.mark.asyncio
    async def test_complete_multiple_methods(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache, sample_service_definition
    ):
        """Test complete method returns multiple methods correctly."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('entity_type.manager')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        mock_services_cache.get.return_value = sample_service_definition
        mock_classes_cache.get_methods.return_value = ["methodA", "methodB", "methodC", "methodD"]

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="entity_type.manager"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)

            assert isinstance(result, CompletionList)
            assert len(result.items) == 4
            assert {item.label for item in result.items} == {"methodA", "methodB", "methodC", "methodD"}

    @pytest.mark.asyncio
    async def test_complete_insert_text_format(
        self, service_method_capability: ServiceMethodCompletionCapability, mock_server: MagicMock, mock_text_document: MagicMock, completion_params_factory, mock_services_cache, mock_classes_cache, sample_service_definition
    ):
        """Test that insert_text and insert_text_format are correctly set."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [r"\Drupal::service('entity_type.manager')->"]
        mock_server.workspace_cache.caches = {"services": mock_services_cache, "classes": mock_classes_cache}

        mock_services_cache.get.return_value = sample_service_definition
        mock_classes_cache.get_methods.return_value = ["someMethod"]

        with patch.object(service_method_capability, '_extract_service_id_from_line', return_value="entity_type.manager"):
            params = completion_params_factory(line=0, character=35, trigger_character=">")
            result = await service_method_capability.complete(params)

            assert isinstance(result, CompletionList)
            assert len(result.items) == 1
            item = result.items[0]
            assert item.label == "someMethod"
            assert item.insert_text == "someMethod()"
            assert item.insert_text_format == InsertTextFormat.Snippet

    # --- Tests for _extract_service_id_from_line ---

    @pytest.mark.parametrize(
        "line_content, cursor_char, expected_service_id",
        [
            # Valid patterns
            (r"\Drupal::service('foo')->", 23, "foo"),
            (r"\Drupal::service('foo') ->", 24, "foo"), # With whitespace
            (r"\Drupal::service('foo')->bar", 23, "foo"),
            (r"\Drupal::service('foo')->bar()", 23, "foo"),
            (r"\Drupal::getContainer()->get('bar')->", 35, "bar"),
            (r"\Drupal::getContainer()->get('bar') ->", 36, "bar"),
            (r"$var = \Drupal::service('my.service')->", 31, "my.service"),
            (r"  \Drupal::service('another_service')->", 34, "another_service"), # Indented
            (r"\Drupal::service(\"foo\")->", 23, "foo"), # Double quotes
            (r"\Drupal::getContainer()->get(\"bar\")->", 35, "bar"), # Double quotes

            # Invalid patterns (no '->' or '->' not immediately after service call)
            (r"\Drupal::service('foo')", 22, None),
            (r"\Drupal::service('foo') ", 23, None),
            (r"\Drupal::service('foo')  ->", 25, None), # Too much whitespace
            (r"\Drupal::service('foo') + ->", 26, None), # Other characters
            (r"\Drupal::service('foo')method->", 29, None), # No '->' directly after service call
            (r"some_other_call()->", 18, None),
            (r"->", 2, None),
            (r"foo->", 4, None),
            (r"just a string", 10, None),
            (r"\Drupal::service('foo')", 10, None), # Cursor before '->'
            (r"\Drupal::service('foo')->", 22, None), # Cursor on '-' of '->'
            (r"\Drupal::service('foo')->", 21, None), # Cursor before '->'
            (r"\Drupal::service('foo') ->", 23, None), # Cursor on space before ->
            (r"\Drupal::service('foo')->bar", 26, "foo"), # Cursor after method name
            (r"\Drupal::service('foo')->bar(", 27, "foo"), # Cursor after method call
            (r"\Drupal::service('foo')->bar()->", 30, "foo"), # Chained calls
            (r"\Drupal::service('foo')->bar->baz", 26, "foo"), # Chained property access
            (r"\Drupal::service('foo')->bar->", 26, "foo"), # Chained property access, cursor on ->
            (r"\Drupal::service('foo')->bar->", 29, "foo"), # Chained property access, cursor after ->
            (r"\Drupal::service('foo')->bar->baz()", 26, "foo"), # Chained property access, cursor after ->
            (r"\Drupal::service('foo')->bar->baz()->", 33, "foo"), # Chained property access, cursor after ->
        ],
    )
    def test_extract_service_id_from_line(
        self,
        service_method_capability: ServiceMethodCompletionCapability,
        line_content: str,
        cursor_char: int,
        expected_service_id: str | None,
    ):
        """Test _extract_service_id_from_line with various service call patterns and cursor positions."""
        position = Position(line=0, character=cursor_char)
        result = service_method_capability._extract_service_id_from_line(line_content, position)
        assert result == expected_service_id

    @pytest.mark.parametrize(
        "line_content, cursor_char, expected_service_id",
        [
            # Cursor at the end of the service ID, before '->'
            (r"\Drupal::service('foo')", 21, None),
            (r"\Drupal::service('foo') ", 22, None),
            (r"\Drupal::service('foo') ->", 23, None),
            # Cursor inside the service ID
            (r"\Drupal::service('f|oo')->", 19, None), # | represents cursor
            (r"\Drupal::service('fo|o')->", 20, None),
            # Cursor before the service ID
            (r"\Drupal::service('|foo')->", 18, None),
            (r"|\Drupal::service('foo')->", 0, None),
        ],
    )
    def test_extract_service_id_from_line_cursor_position_sensitivity(
        self,
        service_method_capability: ServiceMethodCompletionCapability,
        line_content: str,
        cursor_char: int,
        expected_service_id: str | None,
    ):
        """Test _extract_service_id_from_line's sensitivity to cursor position relative to '->'."""
        position = Position(line=0, character=cursor_char)
        result = service_method_capability._extract_service_id_from_line(line_content, position)
        assert result == expected_service_id

# --- Tests for _is_service_pattern (helper for other capabilities, but good to test) ---

class TestIsServicePattern:
    """Tests for the _is_service_pattern helper function."""

    @pytest.mark.parametrize(
        "line_content, cursor_char, expected_result",
        [
            (r"\Drupal::service('foo')", 22, True),
            (r"\Drupal::getContainer()->get('bar')", 34, True),
            (r"$container->get('baz')", 20, True), # Basic container check
            (r"some_other_call()", 16, False),
            (r"just a string", 10, False),
            (r"->get('foo')", 11, True), # Basic container check for ->get()
            (r"get('foo')", 9, False), # Should not match without ->
            (r"new Class()", 10, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_is_service_pattern_no_type_checker(
        self,
        mock_server: MagicMock,
        mock_text_document: MagicMock,
        completion_params_factory,
        line_content: str,
        cursor_char: int,
        expected_result: bool,
    ):
        """Test _is_service_pattern when no type checker is available."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [line_content]
        mock_server.type_checker = None # Ensure no type checker

        params = completion_params_factory(line=0, character=cursor_char)
        result = await _is_service_pattern(mock_server, params)
        assert result == expected_result

    @pytest.mark.parametrize(
        "line_content, cursor_char, is_container_variable_return, expected_result",
        [
            (r"\Drupal::service('foo')", 22, False, True), # SERVICE_PATTERN matches
            (r"\Drupal::getContainer()->get('bar')", 34, False, True), # SERVICE_PATTERN matches
            (r"$container->get('baz')", 20, True, True), # Type checker confirms
            (r"$container->get('baz')", 20, False, False), # Type checker denies
            (r"$some_var->get('baz')", 20, True, True), # Type checker confirms
            (r"$some_var->get('baz')", 20, False, False), # Type checker denies
            (r"some_other_call()->get('foo')", 28, True, True), # Type checker confirms
            (r"some_other_call()->get('foo')", 28, False, False), # Type checker denies
            (r"some_other_call()", 16, False, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_is_service_pattern_with_type_checker(
        self,
        mock_server: MagicMock,
        mock_text_document: MagicMock,
        completion_params_factory,
        line_content: str,
        cursor_char: int,
        is_container_variable_return: bool,
        expected_result: bool,
    ):
        """Test _is_service_pattern when a type checker is available."""
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [line_content]

        mock_type_checker = MagicMock()
        mock_type_checker.is_container_variable.return_value = is_container_variable_return
        mock_server.type_checker = mock_type_checker

        params = completion_params_factory(line=0, character=cursor_char)
        result = await _is_service_pattern(mock_server, params)
        assert result == expected_result

        # Check if type_checker.is_container_variable was called
        # It should be called if "->get(" is in line_content AND SERVICE_PATTERN does NOT match
        if "->get(" in line_content and not _is_service_pattern_direct_check(line_content):
            mock_type_checker.is_container_variable.assert_called_once()
        else:
            mock_type_checker.is_container_variable.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_service_pattern_type_checker_exception(
        self,
        mock_server: MagicMock,
        mock_text_document: MagicMock,
        completion_params_factory,
    ):
        """Test _is_service_pattern handles exceptions from type checker gracefully."""
        line_content = r"$container->get('baz')"
        cursor_char = 20
        mock_server.workspace.get_text_document.return_value = mock_text_document
        mock_text_document.lines = [line_content]

        mock_type_checker = MagicMock()
        mock_type_checker.is_container_variable.side_effect = Exception("Type checker error")
        mock_server.type_checker = mock_type_checker

        params = completion_params_factory(line=0, character=cursor_char)
        result = await _is_service_pattern(mock_server, params)
        # Should fall back to basic check, which for "$container->get('baz')" is True
        assert result is True
        mock_type_checker.is_container_variable.assert_called_once()

# Helper function to replicate the SERVICE_PATTERN check for testing purposes
import re
SERVICE_PATTERN_TEST = re.compile(r'::service\([\'"]?|getContainer\(\)->get\([\'"]?')
def _is_service_pattern_direct_check(line: str) -> bool:
    return SERVICE_PATTERN_TEST.search(line) is not None

# --- Tests for _basic_container_check ---

class TestBasicContainerCheck:
    """Tests for the _basic_container_check helper function."""

    @pytest.mark.parametrize(
        "line_content, expected_result",
        [
            (r"$container->get('foo')", True),
            (r"$this->container->get('foo')", True),
            (r"$service_container->get('foo')", True),
            (r"$c->get('foo')", False), # Not a container-like variable name
            (r"some_var->get('foo')", False),
            (r"new Class()->get('foo')", False),
            (r"just a string", False),
            (r"->get('foo')", True), # This pattern is caught by the regex
            (r"get('foo')", False),
        ],
    )
    def test_basic_container_check(self, line_content: str, expected_result: bool):
        """Test _basic_container_check with various line contents."""
        from drupalls.lsp.capabilities.services_capabilities import _basic_container_check
        result = _basic_container_check(line_content)
        assert result == expected_result
