from pathlib import Path


def find_files_pathlib(
    pattern,
    directory=".",
    exclude_dirs={"venv", "node_modules", ".git", "__pycache__", "vendor"},
) -> list[Path]:
    """
    Finds all files matching a pattern in the given directory and its subfolders.

    Args:
        pattern (str): The filename pattern to match (e.g., '*.txt', '*test*').
        directory (str): The starting directory for the search. Defaults to the current directory ('.').

    Returns:
        list: A list of Path objects for all matching files.
    """
    base_path = Path(directory)

    results = []

    for item in base_path.iterdir():
        if item.is_dir():
            if item.name not in exclude_dirs:
                results.extend(find_files_pathlib(item, pattern, exclude_dirs))
        elif item.match(pattern):
            results.append(item)

    return results


def find_drupal_root(workspace_root: Path) -> Path | None:
    """
    Find the Drupal root directory within a workspace.

    Searches for the directory containing 'core/lib/Drupal'.

    Args:
        workspace_root: The workspace root path

    Returns:
        Path to Drupal root, or None if not found
    """
    # Check common locations first
    common_locations = ["web", "docroot", "html", "app", "public", "drupal"]

    for location in common_locations:
        candidate = workspace_root / location
        if is_drupal_root(candidate):
            return candidate

    # Check workspace root itself
    if is_drupal_root(workspace_root):
        return workspace_root
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
