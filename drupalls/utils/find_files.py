from pathlib import Path


def find_files_pathlib(
    pattern,
    directory=".",
    exclude_dirs={"venv", "node_modules", ".git", "__pycache__", "vendor"},
):
    """
    Finds all files matching a pattern in the given directory and its subfolders.

    Args:
        pattern (str): The filename pattern to match (e.g., '*.txt', '*test*').
        directory (str): The starting directory for the search. Defaults to the current directory ('.').

    Returns:
        list: A list of Path objects for all matching files.
    """
    base_path = Path(directory)

    matching_files = [
        p for p in base_path.rglob(pattern) 
        if not any(exclude in p.parts for exclude_dirs) and p.is_file()
    ]
    return matching_files


print(find_files_pathlib("ser*.py", "."))
