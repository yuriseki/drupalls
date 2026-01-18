import pytest
from lsprotocol.types import (
    DidOpenTextDocumentParams,
    DidSaveTextDocumentParams,
    TextDocumentIdentifier,
    TextDocumentItem,
    LogMessageParams,
    MessageType,
)

from drupalls.lsp.text_sync_manager import TextSyncManager


@pytest.fixture
def server():
    """Create a mock server for testing."""
    from unittest.mock import Mock

    server = Mock()
    server.window_log_message = Mock()
    return server


@pytest.fixture
def text_sync(server):
    """Create TextSyncManager instance."""
    return TextSyncManager(server)


@pytest.mark.asyncio
async def test_hook_registration(text_sync):
    """Test that hooks can be registered."""
    async def test_hook(params):
        pass

    text_sync.add_on_save_hook(test_hook)

    assert len(text_sync._on_save_hooks) == 1
    assert text_sync._on_save_hooks[0] == test_hook


@pytest.mark.asyncio
async def test_hook_execution(text_sync):
    """Test that registered hooks are called."""
    hook_called = False
    received_uri = None

    async def test_hook(params: DidSaveTextDocumentParams):
        nonlocal hook_called, received_uri
        hook_called = True
        received_uri = params.text_document.uri

    text_sync.add_on_save_hook(test_hook)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(
            uri='file:///test/file.php'
        )
    )

    await text_sync._broadcast_on_save(params)

    assert hook_called
    assert received_uri == 'file:///test/file.php'


@pytest.mark.asyncio
async def test_multiple_hooks_execution_order(text_sync):
    """Test that multiple hooks run in registration order."""
    execution_order = []

    async def hook1(params):
        execution_order.append(1)

    async def hook2(params):
        execution_order.append(2)

    async def hook3(params):
        execution_order.append(3)

    text_sync.add_on_save_hook(hook1)
    text_sync.add_on_save_hook(hook2)
    text_sync.add_on_save_hook(hook3)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri='file:///test.php')
    )

    await text_sync._broadcast_on_save(params)

    assert execution_order == [1, 2, 3]


@pytest.mark.asyncio
async def test_hook_error_isolation(text_sync, server):
    """Test that hook errors don't prevent other hooks from running."""
    hook2_called = False

    async def failing_hook(params):
        raise ValueError("Test error")

    async def successful_hook(params):
        nonlocal hook2_called
        hook2_called = True

    text_sync.add_on_save_hook(failing_hook)
    text_sync.add_on_save_hook(successful_hook)

    params = DidSaveTextDocumentParams(
        text_document=TextDocumentIdentifier(uri='file:///test.php')
    )

    # Should not raise exception
    await text_sync._broadcast_on_save(params)

    # Second hook should still run
    assert hook2_called

    # Error should be logged
    assert server.window_log_message.called
    # Check that error was logged
    call_args = server.window_log_message.call_args[0][0]
    assert isinstance(call_args, LogMessageParams)
    assert call_args.type == MessageType.Error
