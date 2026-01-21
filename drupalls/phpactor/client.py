import asyncio
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TypeInfo:
    """Type information returned by Phpactor."""

    type_name: str | None
    symbol_type: str | None  # "class", "method", "property", "variable"
    fqcn: str | None
    offset: int
    class_type: str | None


@dataclass
class ClassReflection:
    """Class reflection data from Phpactor."""

    fqcn: str
    short_name: str
    parent_class: str | None
    interfaces: list[str]
    traits: list[str]
    methods: list[str]
    properties: list[str]
    is_abstract: bool
    is_final: bool


class PhpactorClient:
    """
    Unified client for Phpactor CLI/RPC communication.

    This client wraps all Phpactor interactions, providing both
    synchronous and asynchronous methods for querying PHP code.
    """

    def __init__(self, drupalls_root: Path | None = None):
        """
        Initialize Phpactor client.

        Args:
            drupalls_root: Root directory of DrupalLS installation.
                          Auto-detects if None.
        """
        if drupalls_root is None:
            current_file = Path(__file__).resolve()
            drupalls_root = current_file.parent.parent.parent

        self.drupalls_root = drupalls_root
        self.phpactor_dir = drupalls_root / "phpactor"
        self.phpactor_bin = self.phpactor_dir / "bin" / "phpactor"

        # Cache for class reflections
        self._reflection_cache: dict[str, ClassReflection] = {}

    def is_available(self) -> bool:
        """Check if Phpactor CLI is available and working."""
        if not self.phpactor_bin.exists():
            return False

        try:
            import subprocess

            result = subprocess.run(
                [str(self.phpactor_bin), "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def offset_info(
        self, file_path: Path, offset: int, working_dir: Path | None = None
    ) -> TypeInfo | None:
        """
        Get type information at a specific byte offset.

        Args:
            file_path: Path to PHP file
            offset: Byte offset in file
            working_dir: Working directory for Phpactor (project root)

        Returns:
            TypeInfo with type details, or None if not found
        """
        try:
            cmd = [
                str(self.phpactor_bin),
                "offset:info",
                "--working-dir",
                str(working_dir or file_path.parent),
                str(file_path),
                str(offset),
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir or file_path.parent),
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                return None

            parsed = self._parse_cli_output(stdout.decode())

            return TypeInfo(
                type_name=parsed.get("type"),
                symbol_type=parsed.get("symbol_type"),
                fqcn=parsed.get("class"),
                offset=offset,
                class_type=parsed.get("class_type"),
            )

        except Exception:
            return None

    async def class_reflect(
        self, file_path: Path, offset: int, working_dir: Path | None = None
    ) -> ClassReflection | None:
        """
        Get full class reflection at offset using RPC.

        Args:
            file_path: Path to PHP file
            offset: Byte offset in file (anywhere in class)
            working_dir: Working directory for Phpactor

        Returns:
            ClassReflection with full class details, or None
        """
        try:
            response = await self._rpc_command_async(
                "class_reflect",
                {"source": str(file_path), "offset": offset},
                working_dir=working_dir or file_path.parent,
            )

            if not response:
                return None

            # Parse the reflection response
            return ClassReflection(
                fqcn=response.get("class", ""),
                short_name=response.get("name", ""),
                parent_class=response.get("parent"),
                interfaces=response.get("interfaces", []),
                traits=response.get("traits", []),
                methods=[m["name"] for m in response.get("methods", [])],
                properties=[p["name"] for p in response.get("properties", [])],
                is_abstract=response.get("abstract", False),
                is_final=response.get("final", False),
            )

        except Exception:
            return None

    async def get_class_hierarchy(self, fqcn: str, working_dir: Path) -> list[str]:
        """
        Get full class hierarchy (all parent classes).

        Args:
            fqcn: Fully qualified class name
            working_dir: Project working directory

        Returns:
            List of parent classes in order (immediate parent first)
        """
        hierarchy: list[str] = []
        current_class = fqcn
        seen: set[str] = set()

        while current_class and current_class not in seen:
            seen.add(current_class)

            response = await self._rpc_command_async(
                "class_reflect", {"class": current_class}, working_dir=working_dir
            )

            if not response:
                break

            parent = response.get("parent")
            if parent:
                hierarchy.append(parent)
                current_class = parent
            else:
                break

        return hierarchy

    async def _rpc_command_async(
        self, action: str, parameters: dict, working_dir: Path
    ) -> dict | None:
        """Execute RPC command asynchronously."""
        try:
            rpc_data = {"action": action, "parameters": parameters}

            cmd = [str(self.phpactor_bin), "rpc", "--working-dir", str(working_dir)]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
            )

            stdout, stderr = await result.communicate(
                input=json.dumps(rpc_data).encode()
            )

            if result.returncode != 0:
                return None

            return json.loads(stdout.decode())

        except Exception:
            return None

    def _parse_cli_output(self, output: str) -> dict[str, str]:
        """Parse phpactor offset:info CLI output into key-value pairs.
        
        Normalizes keys to snake_case for consistent access.
        Example: "Symbol Type: class" -> {"symbol_type": "class"}
        """
        lines = output.strip().split("\n")
        parsed: dict[str, str] = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                # Normalize key: lowercase and replace spaces with underscores
                normalized_key = key.strip().lower().replace(" ", "_")
                parsed[normalized_key] = value.strip()

        return parsed

    def clear_cache(self) -> None:
        """Clear all internal caches."""
        self._reflection_cache.clear()
