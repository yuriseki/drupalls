from pathlib import Path


def resolve_class_file(fqcn: str, workspace_root: Path) -> Path | None:
    r"""
    Convert fully qualified class name to file path.

    Uses Drupal's PSR-4 autoloading conventions:
    - Drupal\\Core\\...       → core/lib/Drupal/Core/...
    - Drupal\\[module]\\...   → modules/.../src/...

    Args:
        fqcn: Fully qualified class name (e.g., "Drupal\\Core\\Logger\\LoggerChannelFactory")
        workspace_root: Path to Drupal workspace root directory

    Returns:
        Path to PHP file, or None if cannot resolve
    """

    # Split namespace into parts
    parts = fqcn.split("\\")

    if len(parts) < 2:
        return None

    # Handle Drupal\Core* classes
    if parts[0] == "Drupal" and parts[1] == "Core":
        # Drupal\Core\Logger\LoggerChannelFactory
        # -> core/lib/Drupal/Core/Logger/LoggerChannelFactory.php
        relative_path = Path("core/lib") / "/".join(parts)
        class_file = workspace_root / f"{relative_path}.php"
        return class_file

    # Handle Drupal\[module]\* classes
    if parts[0] == "Drupal" and len(parts) >= 2:
        # Drupal\mymodule\Controller\MyController
        # -> modules/.../mymodule/src/Controller/MyController.php
        module_name = parts[1].lower()  # Module names are lowercase

        # Remaining namespace parts after "Drupal\[module]\"
        relative_parts = parts[2:]  # Skip "Drupal" and module name

        # Build the relative path within the module's src/ directory
        if relative_parts:
            class_relative_path = Path("/".join(relative_parts)).with_suffix(".php")
        else:
            return None

        # Search for module recursively in common base directories
        # This handles nested directories like modules/custom/vendor/mymodule
        search_base_dirs = [
            workspace_root / "modules",
            workspace_root / "core" / "modules",
            workspace_root / "core" / "profiles",
            workspace_root / "profiles",
        ]

        for base_dir in search_base_dirs:
            if not base_dir.exists():
                continue

            # Use rglob to search recursively for module directories
            # Look for any directory matching the module name that contains a src/ folder
            for module_dir in base_dir.rglob(module_name):
                if module_dir.is_dir():
                    src_dir = module_dir / "src"
                    if src_dir.exists() and src_dir.is_dir():
                        class_file = src_dir / class_relative_path
                        if class_file.exists():
                            return class_file

    return None
