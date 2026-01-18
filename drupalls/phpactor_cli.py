"""
Wrapper for accessing bundled Phpactor CLI.
"""

import os
import subprocess
import sys
from pathlib import Path

class PhpactorCLI:
    """Wrapper for bundled Phpactor CLI."""

    def __init__(self, project_root: Path | None = None):
        """Initialize Phpactor CLI wrapper.

        Args:
            project_root: Root directory of the DrupalLS project.
                        If None, auto-detects from this file's location.
        """
        if project_root is None:
            # Auto-detect project root (assuming this file is in drupalls/)
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent

        self.project_root = project_root
        self.phpactor_dir = project_root / "phpactor"
        self.phpactor_bin = self.phpactor_dir / "bin" / "phpactor"

        # Check if setup is needed
        self._ensure_phpactor_ready()

    def _ensure_phpactor_ready(self) -> None:
        """Ensure Phpactor is properly set up."""
        if not self.phpactor_bin.exists():
            raise FileNotFoundError(
                f"Phpactor binary not found at {self.phpactor_bin}. "
                "Run setup script: drupalls-setup-phpactor"
            )

        # Check if vendor directory exists (dependencies installed)
        vendor_dir = self.phpactor_dir / "vendor"
        if not vendor_dir.exists():
            raise RuntimeError(
                f"Phpactor dependencies not installed. "
                "Run setup script: drupalls-setup-phpactor"
            )

    def run_command(self, args: list[str], cwd: Path | None = None,
                   timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a Phpactor command.

        Args:
            args: Command arguments (without 'phpactor')
            cwd: Working directory for command
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess instance

        Raises:
            subprocess.TimeoutExpired: If command times out
            FileNotFoundError: If phpactor binary not found
        """
        if not self.phpactor_bin.exists():
            raise FileNotFoundError(f"Phpactor binary not found: {self.phpactor_bin}")

        cmd = [str(self.phpactor_bin)] + args

        # Set working directory
        if cwd is None:
            cwd = self.project_root

        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit codes
            )
        except subprocess.TimeoutExpired as e:
            raise subprocess.TimeoutExpired(cmd, timeout, e.stdout, e.stderr)

    def rpc_command(self, action: str, parameters: dict,
                    working_dir: Path | None = None) -> dict:
        """Execute an RPC command.

        Args:
            action: RPC action name
            parameters: Action parameters
            working_dir: Working directory for command

        Returns:
            Parsed JSON response

        Raises:
            RuntimeError: If command fails or returns invalid JSON
        """
        import json

        rpc_data = {
            "action": action,
            "parameters": parameters
        }

        # Run RPC command with working directory override
        args = ["rpc", "--working-dir", str(working_dir or self.project_root)]
        result = self.run_command(args, input=json.dumps(rpc_data))

        if result.returncode != 0:
            raise RuntimeError(
                f"Phpactor RPC command failed: {result.stderr.strip()}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Invalid JSON response from Phpactor: {e}"
            ) from e

    def get_type_at_offset(self, file_path: Path, offset: int,
                          working_dir: Path | None = None) -> str | None:
        """Get type information at file offset.

        Args:
            file_path: Path to PHP file
            offset: Byte offset in file
            working_dir: Working directory (defaults to project root)

        Returns:
            Type string or None if not found
        """
        try:
            response = self.rpc_command(
                "type_at_offset",
                {
                    "source_path": str(file_path),
                    "offset": offset
                },
                working_dir=working_dir
            )
            return response.get("type")
        except Exception:
            return None

    def get_type_at_position(self, file_path: Path, line: int, character: int,
                           working_dir: Path | None = None) -> str | None:
        """Get type information at line/character position.

        Args:
            file_path: Path to PHP file
            line: Line number (0-indexed)
            character: Character position (0-indexed)
            working_dir: Working directory

        Returns:
            Type string or None if not found
        """
        # Convert position to byte offset
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            lines = content.splitlines()
            offset = 0

            # Calculate offset up to target line
            for i in range(line):
                if i < len(lines):
                    offset += len(lines[i]) + 1  # +1 for newline

            # Add character offset within line
            if line < len(lines):
                offset += min(character, len(lines[line]))

            return self.get_type_at_offset(file_path, offset, working_dir)

        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if Phpactor CLI is available and working."""
        try:
            result = self.run_command(["--version"], timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def get_version(self) -> str | None:
        """Get Phpactor version."""
        try:
            result = self.run_command(["--version"])
            if result.returncode == 0:
                # Parse version from output
                return result.stdout.strip().split()[-1]
        except Exception:
            pass
        return None
