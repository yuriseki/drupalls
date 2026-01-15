import hashlib
from pathlib import Path


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)

    return sha256.hexdigest()
