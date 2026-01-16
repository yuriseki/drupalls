# Drupal Root Detection Guide

## Problem Statement

Drupal projects can have different directory structures. The actual Drupal installation (containing `core/`, `modules/`, `sites/`) may be located in various subdirectories:

- **Composer-based projects**: `web/`, `docroot/`, `html/`
- **Custom setups**: `app/`, `drupal/`, `public/`
- **Root installation**: Drupal directly in project root

The language server needs to detect the correct Drupal root to properly scan for services, hooks, and other definitions.

## Detection Strategy

### Primary Method: Find `core/lib/Drupal` Directory

The most reliable indicator of a Drupal installation is the presence of `core/lib/Drupal/` directory, which contains core Drupal classes.

### Algorithm

```python
from pathlib import Path
from typing import Optional

def find_drupal_root(workspace_root: Path) -> Optional[Path]:
    """
    Find the Drupal root directory within a workspace.
    
    Searches for the directory containing 'core/lib/Drupal'.
    
    Args:
        workspace_root: The workspace root path (from LSP params)
        
    Returns:
        Path to Drupal root, or None if not found
        
    Examples:
        workspace_root = /home/user/myproject
        
        If Drupal is in /home/user/myproject/web/
        Returns: /home/user/myproject/web
        
        If Drupal is in /home/user/myproject/
        Returns: /home/user/myproject
    """
    # Check common locations first (optimization)
    common_locations = ['web', 'docroot', 'html', 'app', 'public', 'drupal']
    
    for location in common_locations:
        candidate = workspace_root / location
        if _is_drupal_root(candidate):
            return candidate
    
    # Check workspace root itself
    if _is_drupal_root(workspace_root):
        return workspace_root
    
    # Fallback: Search all subdirectories (max depth 3)
    for candidate in _search_subdirectories(workspace_root, max_depth=3):
        if _is_drupal_root(candidate):
            return candidate
    
    return None


def _is_drupal_root(path: Path) -> bool:
    """
    Check if a path is a Drupal root directory.
    
    A valid Drupal root must contain:
    - core/lib/Drupal/ directory (primary indicator)
    - core/core.services.yml file (validation)
    """
    if not path.is_dir():
        return False
    
    # Primary check: core/lib/Drupal exists
    core_lib_drupal = path / "core" / "lib" / "Drupal"
    if not core_lib_drupal.is_dir():
        return False
    
    # Validation check: core.services.yml exists
    core_services = path / "core" / "core.services.yml"
    if not core_services.is_file():
        return False
    
    return True


def _search_subdirectories(root: Path, max_depth: int = 3) -> list[Path]:
    """
    Recursively search subdirectories up to max_depth.
    
    Returns list of candidate directories.
    """
    candidates = []
    
    def _recurse(path: Path, depth: int):
        if depth > max_depth:
            return
        
        try:
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    candidates.append(item)
                    _recurse(item, depth + 1)
        except PermissionError:
            # Skip directories we can't read
            pass
    
    _recurse(root, 1)
    return candidates
```

## Usage in Language Server

### During Server Initialization

```python
# drupalls/lsp/server.py
from pygls.server import LanguageServer
from lsprotocol.types import InitializeParams
from pathlib import Path
from drupalls.workspace.cache import WorkspaceCache
from drupalls.workspace.utils import find_drupal_root

server = LanguageServer('drupalls', 'v0.1.0')

@server.feature('initialize')
async def initialize(ls: LanguageServer, params: InitializeParams):
    """Initialize the language server."""
    
    # Get workspace root from LSP params
    workspace_uri = params.root_uri or params.workspace_folders[0].uri
    workspace_root = Path(workspace_uri.path)
    
    # Find Drupal root
    drupal_root = find_drupal_root(workspace_root)
    
    if drupal_root is None:
        ls.show_message("Drupal installation not found in workspace")
        return
    
    ls.show_message(f"Drupal root detected: {drupal_root}")
    
    # Initialize workspace cache with Drupal root
    ls.workspace_cache = WorkspaceCache(drupal_root)
    await ls.workspace_cache.initialize()
    
    return InitializeResult(...)
```

### Handling Multiple Drupal Installations

Some projects may contain multiple Drupal installations (e.g., monorepo with multiple sites).

```python
def find_all_drupal_roots(workspace_root: Path, max_depth: int = 3) -> list[Path]:
    """
    Find all Drupal installations in workspace.
    
    Returns list of paths, ordered by depth (shallowest first).
    """
    drupal_roots = []
    
    # Check common locations
    common_locations = ['web', 'docroot', 'html', 'app', 'public']
    for location in common_locations:
        candidate = workspace_root / location
        if _is_drupal_root(candidate):
            drupal_roots.append(candidate)
    
    # Check workspace root
    if _is_drupal_root(workspace_root):
        drupal_roots.append(workspace_root)
    
    # Search subdirectories
    for candidate in _search_subdirectories(workspace_root, max_depth):
        if _is_drupal_root(candidate):
            drupal_roots.append(candidate)
    
    # Sort by depth (prefer shallower installations)
    drupal_roots.sort(key=lambda p: len(p.parts))
    
    return drupal_roots


# Usage
@server.feature('initialize')
async def initialize(ls: LanguageServer, params: InitializeParams):
    workspace_root = Path(params.root_uri.path)
    
    drupal_roots = find_all_drupal_roots(workspace_root)
    
    if len(drupal_roots) == 0:
        ls.show_message("No Drupal installation found")
        return
    
    if len(drupal_roots) > 1:
        # Use the first (shallowest) one
        ls.show_message(
            f"Multiple Drupal installations found. Using: {drupal_roots[0]}"
        )
    
    drupal_root = drupal_roots[0]
    ls.workspace_cache = WorkspaceCache(drupal_root)
    await ls.workspace_cache.initialize()
```

## Alternative Detection Methods

### Method 2: Check for composer.json

For Composer-based projects, check `composer.json` for Drupal packages:

```python
import json

def find_drupal_root_via_composer(workspace_root: Path) -> Optional[Path]:
    """
    Find Drupal root by parsing composer.json.
    
    Looks for 'extra.drupal-scaffold.locations.web-root' configuration.
    """
    composer_file = workspace_root / "composer.json"
    
    if not composer_file.exists():
        return None
    
    try:
        with open(composer_file) as f:
            composer_data = json.load(f)
        
        # Check for drupal/core-recommended package
        requires = composer_data.get('require', {})
        if 'drupal/core-recommended' not in requires and 'drupal/core' not in requires:
            return None
        
        # Check for web-root configuration
        web_root = composer_data.get('extra', {}).get('drupal-scaffold', {}).get('locations', {}).get('web-root')
        
        if web_root:
            # web_root is relative path like "web/" or "./docroot/"
            drupal_root = workspace_root / web_root.strip('./')
            if _is_drupal_root(drupal_root):
                return drupal_root
        
        # Fallback: check common locations
        return find_drupal_root(workspace_root)
        
    except (json.JSONDecodeError, KeyError):
        return None
```

**Example composer.json**:
```json
{
  "require": {
    "drupal/core-recommended": "^10.0"
  },
  "extra": {
    "drupal-scaffold": {
      "locations": {
        "web-root": "web/"
      }
    }
  }
}
```

### Method 3: Check for index.php and autoload.php

```python
def _is_drupal_root_simple(path: Path) -> bool:
    """
    Simpler check: look for index.php and autoload.php.
    
    Less reliable but faster for initial screening.
    """
    index_php = path / "index.php"
    autoload = path / "autoload.php"
    core_dir = path / "core"
    
    return (
        index_php.is_file() and
        autoload.is_file() and
        core_dir.is_dir()
    )
```

## Complete Implementation

### Add to `drupalls/workspace/utils.py`

```python
# drupalls/workspace/utils.py
import hashlib
import json
from pathlib import Path
from typing import Optional


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content."""
    sha256 = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    
    return sha256.hexdigest()


def find_drupal_root(workspace_root: Path) -> Optional[Path]:
    """
    Find the Drupal root directory within a workspace.
    
    Searches for the directory containing 'core/lib/Drupal'.
    
    Args:
        workspace_root: The workspace root path
        
    Returns:
        Path to Drupal root, or None if not found
    """
    # Check common locations first
    common_locations = ['web', 'docroot', 'html', 'app', 'public', 'drupal']
    
    for location in common_locations:
        candidate = workspace_root / location
        if is_drupal_root(candidate):
            return candidate
    
    # Check workspace root itself
    if is_drupal_root(workspace_root):
        return workspace_root
    
    # Fallback: search subdirectories (max depth 3)
    for candidate in _search_subdirectories(workspace_root, max_depth=3):
        if is_drupal_root(candidate):
            return candidate
    
    return None


def is_drupal_root(path: Path) -> bool:
    """
    Check if a path is a Drupal root directory.
    
    A valid Drupal root must contain:
    - core/lib/Drupal/ directory
    - core/core.services.yml file
    """
    if not path.is_dir():
        return False
    
    core_lib_drupal = path / "core" / "lib" / "Drupal"
    if not core_lib_drupal.is_dir():
        return False
    
    core_services = path / "core" / "core.services.yml"
    if not core_services.is_file():
        return False
    
    return True


def find_all_drupal_roots(workspace_root: Path, max_depth: int = 3) -> list[Path]:
    """
    Find all Drupal installations in workspace.
    
    Returns list of paths, ordered by depth (shallowest first).
    """
    drupal_roots = []
    
    # Check common locations
    common_locations = ['web', 'docroot', 'html', 'app', 'public']
    for location in common_locations:
        candidate = workspace_root / location
        if is_drupal_root(candidate):
            drupal_roots.append(candidate)
    
    # Check workspace root
    if is_drupal_root(workspace_root):
        drupal_roots.append(workspace_root)
    
    # Search subdirectories
    for candidate in _search_subdirectories(workspace_root, max_depth):
        if is_drupal_root(candidate):
            drupal_roots.append(candidate)
    
    # Remove duplicates and sort by depth
    drupal_roots = list(set(drupal_roots))
    drupal_roots.sort(key=lambda p: len(p.parts))
    
    return drupal_roots


def find_drupal_root_via_composer(workspace_root: Path) -> Optional[Path]:
    """
    Find Drupal root by parsing composer.json.
    
    Looks for 'extra.drupal-scaffold.locations.web-root' configuration.
    """
    composer_file = workspace_root / "composer.json"
    
    if not composer_file.exists():
        return None
    
    try:
        with open(composer_file) as f:
            composer_data = json.load(f)
        
        # Check for Drupal packages
        requires = composer_data.get('require', {})
        if not any(pkg.startswith('drupal/') for pkg in requires):
            return None
        
        # Check for web-root configuration
        web_root = (
            composer_data
            .get('extra', {})
            .get('drupal-scaffold', {})
            .get('locations', {})
            .get('web-root')
        )
        
        if web_root:
            # web_root is relative path like "web/" or "./docroot/"
            drupal_root = workspace_root / web_root.strip('./')
            if is_drupal_root(drupal_root):
                return drupal_root
        
        # Fallback to normal search
        return find_drupal_root(workspace_root)
        
    except (json.JSONDecodeError, KeyError):
        return None


def _search_subdirectories(root: Path, max_depth: int = 3) -> list[Path]:
    """
    Recursively search subdirectories up to max_depth.
    
    Returns list of candidate directories.
    """
    candidates = []
    
    def _recurse(path: Path, depth: int):
        if depth > max_depth:
            return
        
        try:
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    candidates.append(item)
                    _recurse(item, depth + 1)
        except PermissionError:
            pass
    
    _recurse(root, 1)
    return candidates
```

## Testing

### Unit Tests

```python
# tests/workspace/test_drupal_root_detection.py
import pytest
from pathlib import Path
from drupalls.workspace.utils import find_drupal_root, is_drupal_root


def test_drupal_in_web_directory(tmp_path):
    """Test detection when Drupal is in 'web/' subdirectory."""
    # Create structure: tmp_path/web/core/lib/Drupal/
    web_dir = tmp_path / "web"
    core_lib_drupal = web_dir / "core" / "lib" / "Drupal"
    core_lib_drupal.mkdir(parents=True)
    
    core_services = web_dir / "core" / "core.services.yml"
    core_services.write_text("services: {}")
    
    # Detect
    drupal_root = find_drupal_root(tmp_path)
    
    assert drupal_root == web_dir


def test_drupal_in_project_root(tmp_path):
    """Test detection when Drupal is in project root."""
    # Create structure: tmp_path/core/lib/Drupal/
    core_lib_drupal = tmp_path / "core" / "lib" / "Drupal"
    core_lib_drupal.mkdir(parents=True)
    
    core_services = tmp_path / "core" / "core.services.yml"
    core_services.write_text("services: {}")
    
    # Detect
    drupal_root = find_drupal_root(tmp_path)
    
    assert drupal_root == tmp_path


def test_no_drupal_found(tmp_path):
    """Test when no Drupal installation exists."""
    drupal_root = find_drupal_root(tmp_path)
    
    assert drupal_root is None


def test_is_drupal_root_validation(tmp_path):
    """Test validation logic."""
    # Invalid: missing core/lib/Drupal
    assert not is_drupal_root(tmp_path)
    
    # Invalid: has core/lib/Drupal but no core.services.yml
    core_lib_drupal = tmp_path / "core" / "lib" / "Drupal"
    core_lib_drupal.mkdir(parents=True)
    assert not is_drupal_root(tmp_path)
    
    # Valid: has both
    core_services = tmp_path / "core" / "core.services.yml"
    core_services.write_text("services: {}")
    assert is_drupal_root(tmp_path)


def test_custom_drupal_location(tmp_path):
    """Test detection in custom 'app/' directory."""
    app_dir = tmp_path / "app"
    core_lib_drupal = app_dir / "core" / "lib" / "Drupal"
    core_lib_drupal.mkdir(parents=True)
    
    core_services = app_dir / "core" / "core.services.yml"
    core_services.write_text("services: {}")
    
    drupal_root = find_drupal_root(tmp_path)
    
    assert drupal_root == app_dir
```

## Performance Considerations

### Optimization Strategies

1. **Check common locations first**: 90% of projects use `web/` or `docroot/`
2. **Limit search depth**: Max depth of 3 prevents scanning entire filesystem
3. **Skip hidden directories**: Ignore `.git/`, `.idea/`, `node_modules/`, etc.
4. **Cache result**: Store detected Drupal root in server instance

### Caching Implementation

```python
class LanguageServer:
    def __init__(self):
        self._drupal_root_cache: Optional[Path] = None
    
    def get_drupal_root(self, workspace_root: Path) -> Optional[Path]:
        """Get Drupal root with caching."""
        if self._drupal_root_cache is None:
            self._drupal_root_cache = find_drupal_root(workspace_root)
        return self._drupal_root_cache
    
    def invalidate_drupal_root_cache(self):
        """Clear cache when workspace changes."""
        self._drupal_root_cache = None
```

## Edge Cases

### 1. Nested Drupal Installations

```
project/
├── web/                    # Main site
│   └── core/
└── sites/
    └── dev/
        └── core/          # Dev instance
```

**Solution**: Use `find_all_drupal_roots()` and select the shallowest one, or prompt user.

### 2. Symlinked Directories

```python
def is_drupal_root(path: Path) -> bool:
    """Handle symlinks by resolving them."""
    if not path.exists():
        return False
    
    # Resolve symlinks
    resolved_path = path.resolve()
    
    core_lib_drupal = resolved_path / "core" / "lib" / "Drupal"
    core_services = resolved_path / "core" / "core.services.yml"
    
    return core_lib_drupal.is_dir() and core_services.is_file()
```

### 3. Missing core/ Directory (Platform.sh, Pantheon)

Some hosting platforms exclude `core/` from the repository. In such cases:

```python
def find_drupal_root_fallback(workspace_root: Path) -> Optional[Path]:
    """
    Fallback detection for environments without core/.
    
    Looks for:
    - sites/default/settings.php
    - modules/ and themes/ directories
    - index.php with Drupal bootstrap
    """
    for candidate in [workspace_root] + list(workspace_root.glob('*/')):
        if not candidate.is_dir():
            continue
        
        settings_php = candidate / "sites" / "default" / "settings.php"
        modules_dir = candidate / "modules"
        index_php = candidate / "index.php"
        
        if settings_php.exists() and modules_dir.is_dir() and index_php.exists():
            # Verify index.php contains Drupal bootstrap
            try:
                content = index_php.read_text()
                if 'DrupalKernel' in content or 'drupal_handle_request' in content:
                    return candidate
            except:
                pass
    
    return None
```

## Configuration

### Allow Users to Override Detection

```python
# In server initialization, check for .drupalls.json config
def load_drupal_config(workspace_root: Path) -> dict:
    """Load .drupalls.json configuration."""
    config_file = workspace_root / ".drupalls.json"
    
    if not config_file.exists():
        return {}
    
    try:
        with open(config_file) as f:
            return json.load(f)
    except:
        return {}


# Example .drupalls.json
{
  "drupalRoot": "web",
  "enableDiskCache": true,
  "scanPatterns": {
    "modules": ["modules/custom/**/*.php"]
  }
}
```

## Summary

**Recommended approach**:

1. ✅ **Primary**: Search for `core/lib/Drupal/` directory
2. ✅ **Optimization**: Check common locations first (`web/`, `docroot/`)
3. ✅ **Validation**: Verify `core/core.services.yml` exists
4. ✅ **Fallback**: Parse `composer.json` or do deep search
5. ✅ **Edge cases**: Handle symlinks, nested installations

This ensures reliable detection across all Drupal project structures while maintaining good performance.
