from pathlib import Path

from drupalls.phpactor_cli import PhpactorCLI


class PhpactorRpcClient:
    """RPC client for Phpactor type queries using direct command execution."""

    def __init__(self, working_directory: Path) -> None:
        self.working_directory = working_directory
        self.cli = PhpactorCLI()

    async def query_type_at_offset(self, file_path: str, offset: int) -> str | None:
        """Get type at offset using bundled CLI."""
        return await self.cli.get_type_at_offset(Path(file_path), offset)

    async def query_type_at_position(self, file_path: str, line: int, character: int) -> str | None:
        """Get type at position using bundled CLI."""
        return await self.cli.get_type_at_position(Path(file_path), line, character)


