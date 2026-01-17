from unittest.mock import Mock

import pytest
from lsprotocol.types import DefinitionParams, Position, TextDocumentIdentifier

from drupalls.lsp.capabilities.services_capabilities import (
    ServicesYamlDefinitionCapability,
)
from drupalls.lsp.server import create_server
from drupalls.workspace.cache import WorkspaceCache


@pytest.mark.asyncio
async def test_yaml_to_class_navigation(tmp_path, mocker):
    """Test navigating from YAML service definition to PHP class."""

    # Given: A .services.yml file with a service class
    yaml_uri = "file:///path/to/mymodule.services.yml"
    yaml_content = """
services:
  logger.factory:
    class: Drupal\\Core\\Logger\\LoggerChannelFactory
    arguments: ['@container']
"""

    # Set up temporary Drupal file structure
    php_file = tmp_path / "core" / "lib" / "Drupal" / "Core" / "Logger" / "LoggerChannelFactory.php"
    php_file.parent.mkdir(parents=True, exist_ok=True)
    php_file.write_text("<?php\nclass LoggerChannelFactory {}\n")

    # Create server and initialize workspace cache
    server = create_server()
    server.workspace_cache = WorkspaceCache(tmp_path, tmp_path)
    await server.workspace_cache.initialize()

    # Mock the workspace
    mock_workspace = Mock()
    server.protocol._workspace = mock_workspace

    # Mock the document retrieval
    mock_doc = Mock()
    mock_doc.lines = yaml_content.strip().split('\n')
    mock_workspace.get_text_document.return_value = mock_doc

    # Create capability
    capability = ServicesYamlDefinitionCapability(server)

    # When: User invokes "Go to Definition" on the class line
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri=yaml_uri),
        position=Position(line=2, character=15)  # On "Drupal\Core\..."
    )
    result = await capability.definition(params)

    # Then: Should navigate to the PHP class file
    assert result is not None
    assert not isinstance(result, list)  # Should be a single Location
    assert php_file.as_uri() == result.uri
    assert result.range.start.line == 1  # Class declaration on line 1 (0-indexed)
