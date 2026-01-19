import pytest
from drupalls.lsp.phpactor_integration import TypeChecker
from lsprotocol.types import Position


@pytest.mark.asyncio
async def test_cli_type_checking():
    """Test CLI-based type checking."""
    type_checker = TypeChecker()

    # Mock document
    class MockDoc:
        uri = "file:///test/file.php"
        lines = ["$container->get('service');"]

    # Test position at ->get(
    position = Position(line=0, character=18)  # Position of '('

    # This should work without any LSP client
    result = await type_checker.is_container_variable(
        MockDoc(), MockDoc.lines[0], position
    )
    assert result
