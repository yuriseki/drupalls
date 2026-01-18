"""
Basic tests for the Drupal Language Server.

These tests verify that the server can be created and has the expected features registered.
"""

import pytest
from drupalls.lsp.server import create_server
from lsprotocol.types import (
    TEXT_DOCUMENT_DEFINITION,
    TEXT_DOCUMENT_DID_OPEN,
    TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_HOVER,
)


def test_server_creation():
    """Test that the server can be created successfully."""
    server = create_server()
    assert server is not None
    assert server.name == "drupalls"
    assert server.version == "0.1.0"


def test_server_has_completion_feature():
    """Test that completion feature is registered."""
    server = create_server()

    # Check that completion handler is registered
    assert TEXT_DOCUMENT_COMPLETION in server.protocol.fm._features


def test_server_has_hover_feature():
    """Test that hover feature is registered."""
    server = create_server()

    # Check that hover handler is registered
    assert TEXT_DOCUMENT_HOVER in server.protocol.fm._features


def test_server_has_definition_features():
    """Test that definition feature registered."""
    server = create_server()

    # Check that the didOpen handler is registered
    assert TEXT_DOCUMENT_DEFINITION in server.protocol.fm._features
