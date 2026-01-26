from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock

from lsprotocol.types import (
    CompletionParams,
    CompletionContext,
    Position,
    TextDocumentIdentifier,
    CompletionTriggerKind,
)

from drupalls.lsp.capabilities.services_capabilities import ServiceMethodCompletionCapability
from drupalls.workspace.services_cache import ServiceDefinition

class TestServiceMethodCompletionCapability:

    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.workspace.get_text_document.return_value.lines = ["\\Drupal::service('test.service')->"]
        server.window_log_message = Mock() # Use window_log_message for pygls v2
        return server

    @pytest.fixture
    def mock_workspace_cache(self):
        cache = Mock()
        cache.caches = {
            "services": Mock(),
            "classes": Mock()
        }
        return cache

    @pytest.fixture
    def capability(self, mock_server, mock_workspace_cache):
        # Pass mock_workspace_cache to the server, as capability accesses it via server
        mock_server.workspace_cache = mock_workspace_cache
        return ServiceMethodCompletionCapability(mock_server)

    @pytest.mark.asyncio
    async def test_can_handle_with_valid_service_call_trigger_gt(self, capability):
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=34),  # After ->
            context=CompletionContext(trigger_character=">", trigger_kind=CompletionTriggerKind.TriggerCharacter)
        )
        assert await capability.can_handle(params) == True

    @pytest.mark.asyncio
    async def test_can_handle_with_valid_service_call_no_trigger(self, capability):
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=34),
            context=CompletionContext(trigger_kind=CompletionTriggerKind.Invoked) # No trigger character, so Invoked
        )
        assert await capability.can_handle(params) == True

    @pytest.mark.asyncio
    async def test_can_handle_with_invalid_pattern(self, capability, mock_server):
        mock_server.workspace.get_text_document.return_value.lines = ["$var = 'no service';"]
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=20),
            context=CompletionContext(trigger_character=">", trigger_kind=CompletionTriggerKind.TriggerCharacter)
        )
        assert await capability.can_handle(params) == False

    @pytest.mark.asyncio
    async def test_complete_with_service_and_methods(self, capability, mock_workspace_cache):
        # Mock service definition
        service_def = ServiceDefinition(
            id="test.service",
            class_name="Test\\Service\\Class",
            file_path=Path("/path/to/service.php"),
            description="A test service",
            line_number=10,
            class_file_path="/path/to/service.php"
        )
        mock_workspace_cache.caches["services"].get.return_value = service_def
        mock_workspace_cache.caches["classes"].get_methods.return_value = ["method1", "method2"]
    
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=34),
            context=CompletionContext(trigger_character=">", trigger_kind=CompletionTriggerKind.TriggerCharacter)
        )
    
        result = await capability.complete(params)
        assert result is not None
        assert len(result.items) == 2
        assert result.items[0].label == "method1"
        assert result.items[0].insert_text == "method1()"

    @pytest.mark.asyncio
    async def test_complete_with_service_not_found(self, capability, mock_workspace_cache):
        mock_workspace_cache.caches["services"].get.return_value = None
    
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=34),
            context=CompletionContext(trigger_character=">", trigger_kind=CompletionTriggerKind.TriggerCharacter)
        )
    
        result = await capability.complete(params)
        assert result is None

    @pytest.mark.asyncio
    async def test_complete_with_no_methods(self, capability, mock_workspace_cache):
        service_def = ServiceDefinition(
            id="test.service",
            class_name="Test\\Service\\Class",
            file_path=Path("/path/to/service.php"),
            description="A test service",
            line_number=10,
            class_file_path="/path/to/service.php"
        )
        mock_workspace_cache.caches["services"].get.return_value = service_def
        mock_workspace_cache.caches["classes"].get_methods.return_value = []
    
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=34),
            context=CompletionContext(trigger_character=">", trigger_kind=CompletionTriggerKind.TriggerCharacter)
        )
    
        result = await capability.complete(params)
        assert len(result.items) == 6  # Fallback methods
        assert result.items[0].label == "get"
    def test_extract_service_id_from_line_service_pattern(self, capability):
        line = "\\Drupal::service('my.service.id')->"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "my.service.id"

    def test_extract_service_id_from_line_container_pattern(self, capability):
        line = "\\Drupal::getContainer()->get('another.service')->"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "another.service"

    def test_extract_service_id_from_line_double_quotes(self, capability):
        line = '\\Drupal::service("double.quoted.service")->'
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "double.quoted.service"

    def test_extract_service_id_from_line_with_hyphens(self, capability):
        line = '\\Drupal::service(\'service-with-hyphens\')->'
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "service-with-hyphens"

    def test_extract_service_id_from_line_no_match(self, capability):
        line = "$var = 'no service call';"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result is None

    def test_extract_service_id_from_line_partial_line(self, capability):
        line = "\\Drupal::service('partial.service')->more code"
        position = Position(line=0, character=40)  # Before 'more code'
        result = capability._extract_service_id_from_line(line, position)
        assert result == "partial.service"
