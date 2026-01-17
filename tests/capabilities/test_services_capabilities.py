"""
Tests for all services-related LSP capabilities.

Tests:
- ServicesCompletionCapability: Service name autocompletion
- ServicesHoverCapability: Service information on hover
- ServicesDefinitionCapability: PHP → YAML navigation
- ServicesYamlDefinitionCapability: YAML → PHP navigation
"""

from unittest.mock import Mock

import pytest
import pytest_asyncio
from lsprotocol.types import (
    CompletionParams,
    DefinitionParams,
    HoverParams,
    Position,
    TextDocumentIdentifier,
)

from drupalls.lsp.capabilities.services_capabilities import (
    ServicesCompletionCapability,
    ServicesDefinitionCapability,
    ServicesHoverCapability,
    ServicesYamlDefinitionCapability,
)
from drupalls.lsp.server import create_server
from drupalls.workspace.cache import WorkspaceCache
from drupalls.workspace.services_cache import ServiceDefinition


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def drupal_workspace(tmp_path):
    """Create a temporary Drupal workspace with core structure."""
    # Create core directory structure
    core_lib = tmp_path / "core" / "lib" / "Drupal" / "Core"
    core_lib.mkdir(parents=True, exist_ok=True)

    # Create core.services.yml
    core_services = tmp_path / "core" / "core.services.yml"
    core_services.write_text(
        """services:
  logger.factory:
    class: Drupal\\Core\\Logger\\LoggerChannelFactory
    arguments: ['@container']
  entity_type.manager:
    class: Drupal\\Core\\Entity\\EntityTypeManager
    arguments: ['@container']
"""
    )

    # Create PHP class files
    logger_factory_php = core_lib / "Logger" / "LoggerChannelFactory.php"
    logger_factory_php.parent.mkdir(parents=True, exist_ok=True)
    logger_factory_php.write_text(
        """<?php

namespace Drupal\\Core\\Logger;

class LoggerChannelFactory {
  public function get($channel) {
    // Implementation
  }
}
"""
    )

    entity_manager_php = core_lib / "Entity" / "EntityTypeManager.php"
    entity_manager_php.parent.mkdir(parents=True, exist_ok=True)
    entity_manager_php.write_text(
        """<?php

namespace Drupal\\Core\\Entity;

class EntityTypeManager {
  // Implementation
}
"""
    )

    # Create server and initialize workspace cache
    server = create_server()
    server.workspace_cache = WorkspaceCache(tmp_path, tmp_path)
    await server.workspace_cache.initialize()

    # Mock the workspace protocol
    mock_workspace = Mock()
    server.protocol._workspace = mock_workspace

    return {
        "server": server,
        "tmp_path": tmp_path,
        "mock_workspace": mock_workspace,
        "core_services_file": core_services,
        "logger_factory_php": logger_factory_php,
        "entity_manager_php": entity_manager_php,
    }


# ============================================================================
# ServicesCompletionCapability Tests
# ============================================================================


@pytest.mark.asyncio
async def test_services_completion_can_handle_service_pattern(drupal_workspace):
    """Test that completion capability detects service call patterns."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document with service call
    mock_doc = Mock()
    mock_doc.lines = [
        "<?php",
        "$logger = \\Drupal::service('logger.factory');",
        "$manager = $container->getContainer()->get('entity');",
    ]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesCompletionCapability(server)

    # Test ::service() pattern
    params = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=1, character=35),  # Inside service('')
    )
    assert await capability.can_handle(params) is True

    # Test getContainer()->get() pattern
    params_container = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=2, character=45),  # Inside get('')
    )
    assert await capability.can_handle(params_container) is True


@pytest.mark.asyncio
async def test_services_completion_cannot_handle_non_service_context(drupal_workspace):
    """Test that completion capability ignores non-service contexts."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document without service call
    mock_doc = Mock()
    mock_doc.lines = ["<?php", "$variable = 'some string';", "function test() {}"]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesCompletionCapability(server)

    params = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=1, character=15),
    )
    assert await capability.can_handle(params) is False


@pytest.mark.asyncio
async def test_services_completion_returns_all_services(drupal_workspace):
    """Test that completion returns all available services."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document with service call
    mock_doc = Mock()
    mock_doc.lines = ["$logger = \\Drupal::service('');"]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesCompletionCapability(server)

    params = CompletionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=32),
    )

    result = await capability.complete(params)

    # Should return completion list with services
    assert result is not None
    assert len(result.items) == 2  # logger.factory and entity_type.manager
    assert result.is_incomplete is False

    # Check service IDs are present
    service_labels = [item.label for item in result.items]
    assert "logger.factory" in service_labels
    assert "entity_type.manager" in service_labels

    # Check completion items have correct details
    logger_item = next(item for item in result.items if item.label == "logger.factory")
    assert logger_item.detail is not None
    assert "LoggerChannelFactory" in logger_item.detail
    assert logger_item.documentation is not None
    # documentation can be string or MarkupContent
    doc_str = logger_item.documentation if isinstance(logger_item.documentation, str) else ""
    assert "core" in doc_str


# ============================================================================
# ServicesHoverCapability Tests
# ============================================================================


@pytest.mark.asyncio
async def test_services_hover_can_handle_service_pattern(drupal_workspace):
    """Test that hover capability detects service patterns."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document with service call
    mock_doc = Mock()
    mock_doc.lines = ["$logger = \\Drupal::service('logger.factory');"]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesHoverCapability(server)

    params = HoverParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),  # On 'logger.factory'
    )
    assert await capability.can_handle(params) is True


@pytest.mark.asyncio
async def test_services_hover_returns_service_information(drupal_workspace):
    """Test that hover returns detailed service information."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document with service call
    mock_doc = Mock()
    mock_doc.lines = ["$logger = \\Drupal::service('logger.factory');"]
    mock_doc.word_at_position = Mock(return_value="logger.factory")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesHoverCapability(server)

    params = HoverParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),
    )

    result = await capability.hover(params)

    # Should return hover with service details
    assert result is not None
    # contents can be MarkupContent, str, or list of MarkedString
    if isinstance(result.contents, str):
        assert "logger.factory" in result.contents
        assert "LoggerChannelFactory" in result.contents
    else:
        # MarkupContent
        from lsprotocol.types import MarkupContent
        if isinstance(result.contents, MarkupContent):
            assert result.contents.kind == "markdown"
            assert "logger.factory" in result.contents.value
            assert "LoggerChannelFactory" in result.contents.value
            assert "core" in result.contents.value.lower()


@pytest.mark.asyncio
async def test_services_hover_returns_none_for_unknown_service(drupal_workspace):
    """Test that hover returns None for unknown service IDs."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock document with unknown service
    mock_doc = Mock()
    mock_doc.lines = ["$unknown = \\Drupal::service('nonexistent.service');"]
    mock_doc.word_at_position = Mock(return_value="nonexistent.service")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesHoverCapability(server)

    params = HoverParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),
    )

    result = await capability.hover(params)
    assert result is None


# ============================================================================
# ServicesDefinitionCapability Tests (PHP → YAML)
# ============================================================================


@pytest.mark.asyncio
async def test_services_definition_php_to_yaml_can_handle(drupal_workspace):
    """Test that definition capability detects service patterns in PHP."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock PHP document with service call
    mock_doc = Mock()
    mock_doc.lines = ["$logger = \\Drupal::service('logger.factory');"]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),
    )
    assert await capability.can_handle(params) is True


@pytest.mark.asyncio
async def test_services_definition_php_to_yaml_navigation(drupal_workspace):
    """Test navigating from PHP service call to YAML definition."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]
    core_services = workspace["core_services_file"]

    # Mock PHP document with service call
    mock_doc = Mock()
    mock_doc.lines = ["$logger = \\Drupal::service('logger.factory');"]
    mock_doc.word_at_position = Mock(return_value="logger.factory")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),
    )

    result = await capability.definition(params)

    # Should navigate to YAML file
    assert result is not None
    assert core_services.as_uri() == result.uri
    assert result.range.start.line >= 0  # Should point to service definition line


@pytest.mark.asyncio
async def test_services_definition_php_to_yaml_unknown_service(drupal_workspace):
    """Test that unknown service returns None."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock PHP document with unknown service
    mock_doc = Mock()
    mock_doc.lines = ["$unknown = \\Drupal::service('unknown.service');"]
    mock_doc.word_at_position = Mock(return_value="unknown.service")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=0, character=35),
    )

    result = await capability.definition(params)
    assert result is None


# ============================================================================
# ServicesYamlDefinitionCapability Tests (YAML → PHP)
# ============================================================================


@pytest.mark.asyncio
async def test_yaml_definition_can_handle_yaml_file(drupal_workspace):
    """Test that YAML definition capability only handles .services.yml files."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock YAML document
    mock_doc = Mock()
    mock_doc.uri = "file:///core/core.services.yml"
    mock_doc.lines = [
        "services:",
        "  logger.factory:",
        "    class: Drupal\\Core\\Logger\\LoggerChannelFactory",
    ]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesYamlDefinitionCapability(server)

    # Should handle YAML file with class: line
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///core/core.services.yml"),
        position=Position(line=2, character=15),  # On class line
    )
    assert await capability.can_handle(params) is True


@pytest.mark.asyncio
async def test_yaml_definition_cannot_handle_non_yaml_file(drupal_workspace):
    """Test that YAML definition capability ignores non-YAML files."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock PHP document
    mock_doc = Mock()
    mock_doc.uri = "file:///test.php"
    mock_doc.lines = ["<?php", "class Test {}"]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesYamlDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.php"),
        position=Position(line=1, character=10),
    )
    assert await capability.can_handle(params) is False


@pytest.mark.asyncio
async def test_yaml_definition_cannot_handle_non_class_line(drupal_workspace):
    """Test that capability ignores lines without 'class:' property."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock YAML document on arguments line
    mock_doc = Mock()
    mock_doc.uri = "file:///core/core.services.yml"
    mock_doc.lines = [
        "services:",
        "  logger.factory:",
        "    class: Drupal\\Core\\Logger\\LoggerChannelFactory",
        "    arguments: ['@container']",
    ]
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesYamlDefinitionCapability(server)

    # On arguments line (not class line)
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///core/core.services.yml"),
        position=Position(line=3, character=15),
    )
    assert await capability.can_handle(params) is False


@pytest.mark.asyncio
async def test_yaml_to_class_navigation(drupal_workspace):
    """Test navigating from YAML service definition to PHP class."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]
    logger_factory_php = workspace["logger_factory_php"]

    # Mock YAML document
    yaml_content = """services:
  logger.factory:
    class: Drupal\\Core\\Logger\\LoggerChannelFactory
    arguments: ['@container']
"""

    mock_doc = Mock()
    mock_doc.uri = "file:///core/core.services.yml"
    mock_doc.lines = yaml_content.strip().split("\n")
    mock_workspace.get_text_document.return_value = mock_doc

    # Create capability
    capability = ServicesYamlDefinitionCapability(server)

    # User invokes "Go to Definition" on the class line
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///core/core.services.yml"),
        position=Position(line=2, character=15),  # On "Drupal\Core\..."
    )
    result = await capability.definition(params)

    # Should navigate to the PHP class file
    assert result is not None
    if isinstance(result, list):
        assert len(result) == 1
        location = result[0]
    else:
        location = result
    
    assert logger_factory_php.as_uri() == location.uri
    assert location.range.start.line == 4  # Class declaration on line 4 (0-indexed)


@pytest.mark.asyncio
async def test_yaml_to_class_navigation_entity_manager(drupal_workspace):
    """Test navigating to EntityTypeManager class."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]
    entity_manager_php = workspace["entity_manager_php"]

    # Mock YAML document
    yaml_content = """services:
  entity_type.manager:
    class: Drupal\\Core\\Entity\\EntityTypeManager
    arguments: ['@container']
"""

    mock_doc = Mock()
    mock_doc.uri = "file:///core/core.services.yml"
    mock_doc.lines = yaml_content.strip().split("\n")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesYamlDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///core/core.services.yml"),
        position=Position(line=2, character=20),
    )
    result = await capability.definition(params)

    assert result is not None
    if isinstance(result, list):
        assert len(result) == 1
        location = result[0]
        assert entity_manager_php.as_uri() == location.uri
        assert location.range.start.line == 4  # Class declaration line
    else:
        assert entity_manager_php.as_uri() == result.uri
        assert result.range.start.line == 4  # Class declaration line


def test_extract_class_name_from_yaml():
    """Test class name extraction from various YAML formats."""
    server = create_server()
    capability = ServicesYamlDefinitionCapability(server)

    # Test unquoted class name
    line1 = "    class: Drupal\\Core\\Logger\\LoggerChannelFactory"
    assert (
        capability._extract_class_name(line1)
        == "Drupal\\Core\\Logger\\LoggerChannelFactory"
    )

    # Test single-quoted class name
    line2 = "    class: 'Drupal\\Core\\Logger\\LoggerChannelFactory'"
    assert (
        capability._extract_class_name(line2)
        == "Drupal\\Core\\Logger\\LoggerChannelFactory"
    )

    # Test double-quoted class name
    line3 = '    class: "Drupal\\Core\\Logger\\LoggerChannelFactory"'
    assert (
        capability._extract_class_name(line3)
        == "Drupal\\Core\\Logger\\LoggerChannelFactory"
    )

    # Test line without class
    line4 = "    arguments: ['@container']"
    assert capability._extract_class_name(line4) is None


@pytest.mark.asyncio
async def test_yaml_definition_returns_none_for_nonexistent_class(drupal_workspace):
    """Test that navigation returns None when PHP class doesn't exist."""
    workspace = drupal_workspace
    server = workspace["server"]
    mock_workspace = workspace["mock_workspace"]

    # Mock YAML with non-existent class
    yaml_content = """services:
  nonexistent.service:
    class: Drupal\\NonExistent\\FakeClass
"""

    mock_doc = Mock()
    mock_doc.uri = "file:///test.services.yml"
    mock_doc.lines = yaml_content.strip().split("\n")
    mock_workspace.get_text_document.return_value = mock_doc

    capability = ServicesYamlDefinitionCapability(server)

    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri="file:///test.services.yml"),
        position=Position(line=2, character=15),
    )
    result = await capability.definition(params)

    assert result is None


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_all_capabilities_registered(drupal_workspace):
    """Test that all service capabilities are properly initialized."""
    workspace = drupal_workspace
    server = workspace["server"]

    # Verify all capabilities can be created
    completion_cap = ServicesCompletionCapability(server)
    hover_cap = ServicesHoverCapability(server)
    definition_cap = ServicesDefinitionCapability(server)
    yaml_def_cap = ServicesYamlDefinitionCapability(server)

    # Check names are unique
    names = {
        completion_cap.name,
        hover_cap.name,
        definition_cap.name,
        yaml_def_cap.name,
    }
    assert len(names) == 4  # All unique

    # Check all have descriptions
    assert completion_cap.description
    assert hover_cap.description
    assert definition_cap.description
    assert yaml_def_cap.description


@pytest.mark.asyncio
async def test_workspace_cache_integration(drupal_workspace):
    """Test that capabilities properly access workspace cache."""
    workspace = drupal_workspace
    server = workspace["server"]

    # Verify workspace cache is initialized
    assert server.workspace_cache is not None

    # Verify services are loaded
    services_cache = server.workspace_cache.caches.get("services")
    assert services_cache is not None

    all_services = services_cache.get_all()
    assert len(all_services) == 2

    # Verify specific services exist
    logger_service = services_cache.get("logger.factory")
    assert logger_service is not None
    assert logger_service.class_name == "Drupal\\Core\\Logger\\LoggerChannelFactory"

    entity_service = services_cache.get("entity_type.manager")
    assert entity_service is not None
    assert entity_service.class_name == "Drupal\\Core\\Entity\\EntityTypeManager"
