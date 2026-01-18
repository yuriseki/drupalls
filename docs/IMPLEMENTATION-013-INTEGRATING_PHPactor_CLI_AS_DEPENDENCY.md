# Implementing Phpactor CLI as a Dependency

## Overview

This guide implements Phpactor CLI as a bundled dependency in the DrupalLS project, making it transparent for developers to use type checking features without requiring separate Phpactor installation.

**Problem:** Users need to manually install and configure Phpactor to use type checking features.

**Solution:** Bundle Phpactor CLI with DrupalLS installation, providing seamless access to type information.

## Architecture

### Dependency Structure

```
drupalls/
├── phpactor/              # Git submodule
│   ├── bin/phpactor       # CLI executable
│   ├── composer.json      # PHP dependencies
│   └── lib/               # Phpactor source
├── scripts/
│   └── setup_phpactor.sh  # Setup script
└── drupalls/
    ├── lsp/
    │   └── phpactor_integration.py  # Updated to use bundled CLI
```

### Integration Points

1. **Git Submodule**: Phpactor repository included as submodule
2. **Setup Script**: Automated installation of PHP dependencies
3. **CLI Wrapper**: Python wrapper for accessing bundled Phpactor
4. **RPC Client**: Updated to use bundled Phpactor automatically

## Implementation

### Step 1: Add Phpactor as Git Submodule

```bash
# Add Phpactor as submodule
git submodule add https://github.com/phpactor/phpactor.git phpactor

# Configure submodule to track specific version
cd phpactor
git checkout <stable-tag>  # e.g., git checkout 2024.01.0
cd ..
git add .gitmodules phpactor
git commit -m "Add Phpactor CLI as dependency"
```

### Step 2: Create Setup Infrastructure

#### Setup Script (scripts/setup_phpactor.sh)

```bash
#!/bin/bash
# Setup script for bundled Phpactor CLI

set -e

echo "Setting up Phpactor CLI dependency..."

# Check if composer is available
if ! command -v composer &> /dev/null; then
    echo "ERROR: Composer is required to set up Phpactor"
    echo "Please install Composer: https://getcomposer.org/"
    exit 1
fi

# Navigate to phpactor directory
cd "$(dirname "$0")/../phpactor"

# Install PHP dependencies if not already installed
if [ ! -d "vendor" ]; then
    echo "Installing Phpactor PHP dependencies..."
    composer install --no-dev --optimize-autoloader
else
    echo "Phpactor dependencies already installed"
fi

# Make sure phpactor binary is executable
if [ -f "bin/phpactor" ]; then
    chmod +x bin/phpactor
    echo "✓ Phpactor CLI ready at: $(pwd)/bin/phpactor"
else
    echo "ERROR: Phpactor binary not found"
    exit 1
fi

echo "✓ Phpactor setup complete"
```

#### Python Wrapper (drupalls/phpactor_cli.py)

```python
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
                "Run setup script: python -m drupalls setup-phpactor"
            )

        # Check if vendor directory exists (dependencies installed)
        vendor_dir = self.phpactor_dir / "vendor"
        if not vendor_dir.exists():
            raise RuntimeError(
                f"Phpactor dependencies not installed. "
                "Run setup script: python -m drupalls setup-phpactor"
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
```

### Step 3: Update RPC Client to Use Bundled CLI

```python
# drupalls/lsp/phpactor_rpc.py

from drupalls.phpactor_cli import PhpactorCLI

class PhpactorRpcClient:
    """RPC client for Phpactor type queries using direct command execution."""

    def __init__(self, working_directory: str):
        self.working_directory = working_directory

    def query_type_at_offset(self, file_path: str, offset: int) -> str | None:
        """Get type at offset using bundled CLI."""
        return self.cli.get_type_at_offset(Path(file_path), offset)

    def query_type_at_position(self, file_path: str, line: int, character: int) -> str | None:
        """Get type at position using bundled CLI."""
        return self.cli.get_type_at_position(Path(file_path), line, character)
```

### Step 4: Update Setup and Installation

#### Add to setup.py/pyproject.toml

```toml
# pyproject.toml
[tool.poetry.scripts]
drupalls = "drupalls.main:main"
drupalls-setup-phpactor = "drupalls.scripts.setup_phpactor:main"
```

#### Setup Command (drupalls/scripts/setup_phpactor.py)

```python
"""
Setup command for Phpactor dependency.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Main setup function."""
    project_root = Path(__file__).parent.parent.parent
    setup_script = project_root / "scripts" / "setup_phpactor.sh"

    if not setup_script.exists():
        print("ERROR: Setup script not found")
        sys.exit(1)

    # Run setup script
    result = subprocess.run(["bash", str(setup_script)], cwd=str(project_root))

    if result.returncode == 0:
        print("✓ Phpactor CLI setup complete")
        print("You can now use type checking features in DrupalLS")
    else:
        print("✗ Phpactor setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

#### Update Installation Instructions

```bash
# Install DrupalLS with Phpactor
pip install drupalls

# Setup Phpactor (automatic)
drupalls-setup-phpactor

# Or manual setup
python -m drupalls setup-phpactor
```

### Step 5: Update CI/CD and Testing

#### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3
      with:
        submodules: recursive  # Include Phpactor submodule

    - name: Setup PHP
      uses: shivammathur/setup-php@v2
      with:
        php-version: '8.1'

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e .
        ./scripts/setup_phpactor.sh

    - name: Run tests
      run: pytest
```

#### Test for Bundled CLI

```python
# tests/test_phpactor_cli.py

def test_bundled_phpactor_cli():
    """Test that bundled Phpactor CLI works."""
    from drupalls.phpactor_cli import PhpactorCLI

    cli = PhpactorCLI()

    # Test availability
    assert cli.is_available(), "Phpactor CLI should be available"

    # Test version
    version = cli.get_version()
    assert version, "Should get Phpactor version"
    print(f"Using Phpactor version: {version}")

    # Test basic RPC command
    # (Would need a test PHP file)
```

## User Experience

### Transparent Installation

```bash
# User installs DrupalLS
pip install drupalls

# Phpactor is automatically included
# User runs setup once
drupalls-setup-phpactor

# Type checking works transparently
# No manual Phpactor installation required
```

### Automatic Detection

```python
# drupalls/lsp/phpactor_integration.py

def create_type_checker():
    """Create type checker with automatic Phpactor detection."""
    try:
        # Try bundled CLI first
        from drupalls.phpactor_cli import PhpactorCLI
        cli = PhpactorCLI()
        return TypeChecker(cli)
    except Exception:
        # Fall back to system Phpactor if available
        try:
            from drupalls.lsp.phpactor_rpc import PhpactorRpcClient
            return TypeChecker(PhpactorRpcClient())
        except Exception:
            # No Phpactor available
            return None
```

## Cross-Platform Compatibility

### Linux/macOS

- ✅ Native support via git submodule
- ✅ Composer PHP dependency management
- ✅ Bash setup scripts

### Windows

```powershell
# PowerShell setup script (scripts/setup_phpactor.ps1)
$phpactorDir = Join-Path $PSScriptRoot "..\phpactor"

if (!(Test-Path "$phpactorDir\vendor")) {
    Write-Host "Installing Phpactor dependencies..."
    composer install --no-dev --optimize-autoloader
}

# Make sure binary exists
if (!(Test-Path "$phpactorDir\bin\phpactor")) {
    Write-Error "Phpactor binary not found"
    exit 1
}

Write-Host "✓ Phpactor setup complete"
```

### CI/CD Considerations

- **Linux/macOS**: Full support with native scripts
- **Windows**: PowerShell scripts for setup
- **Docker**: Include in container build process
- **GitHub Actions**: Multi-platform testing

## Error Handling and Diagnostics

### Setup Validation

```python
def validate_phpactor_setup():
    """Validate that Phpactor is properly set up."""
    cli = PhpactorCLI()

    issues = []

    if not cli.phpactor_bin.exists():
        issues.append("Phpactor binary not found")

    if not (cli.phpactor_dir / "vendor").exists():
        issues.append("PHP dependencies not installed")

    if not cli.is_available():
        issues.append("Phpactor CLI not working")

    if issues:
        raise RuntimeError(f"Phpactor setup issues: {', '.join(issues)}")

    return True
```

### Graceful Degradation

```python
# In type checker
def is_container_variable(self, doc, line: str, position: Position) -> bool:
    try:
        # Try Phpactor type checking
        return self._check_with_phpactor(doc, line, position)
    except Exception as e:
        # Log warning but don't fail
        logger.warning(f"Phpactor type checking failed: {e}")
        # Fall back to heuristic checking
        return self._heuristic_check(line)
```

## Performance and Caching

### CLI Process Reuse

The bundled CLI approach spawns processes for each query, but you can optimize:

```python
class PhpactorCLI:
    """Optimized CLI with process pooling."""

    def __init__(self):
        self._process_pool = []  # Keep warm processes
        self._max_pool_size = 3

    def run_command(self, args, **kwargs):
        # Reuse warm processes when possible
        # Fall back to spawning new process
        pass
```

### Query Caching

```python
# Enhanced TypeChecker with persistent caching
class TypeChecker:
    def __init__(self, phpactor_client):
        self.phpactor_client = phpactor_client
        self._cache_file = Path.home() / ".drupalls" / "type_cache.json"
        self._load_cache()

    def _load_cache(self):
        """Load persistent type cache."""
        if self._cache_file.exists():
            with open(self._cache_file) as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

    def _save_cache(self):
        """Save persistent type cache."""
        self._cache_file.parent.mkdir(exist_ok=True)
        with open(self._cache_file, 'w') as f:
            json.dump(self._cache, f)
```

## Security Considerations

### Sandboxing

- Run Phpactor in restricted environment
- Limit file system access to project directory
- Validate all inputs to prevent code injection

### Dependency Updates

```bash
# Update Phpactor submodule
git submodule update --remote phpactor

# Test compatibility
pytest tests/test_phpactor_integration.py

# Update if tests pass
git add phpactor
git commit -m "Update Phpactor to latest version"
```

## Summary

This implementation makes Phpactor CLI a transparent dependency:

1. **Git Submodule**: Includes Phpactor source code
2. **Automated Setup**: One-command installation of dependencies
3. **Python Wrapper**: Clean API for accessing CLI
4. **Transparent Usage**: No manual configuration required
5. **Cross-Platform**: Works on Linux, macOS, and Windows
6. **Error Handling**: Graceful fallbacks when setup incomplete

Users get full type checking capabilities without any Phpactor installation steps.

## References

- **Phpactor Repository**: https://github.com/phpactor/phpactor
- **Git Submodules**: https://git-scm.com/book/en/v2/Git-Tools-Submodules
- **Composer**: https://getcomposer.org/
- **Python Subprocess**: https://docs.python.org/3/library/subprocess.html</content>
<parameter name="filePath">docs/IMPLEMENTATION-013-INTEGRATING_PHPactor_CLI_AS_DEPENDENCY.md