from pathlib import Path
import os
import re


def list_files_recursively() -> list[tuple[str, int]]:
    """
    List all files recursively in a directory along with their sizes.

    Returns:
        List of tuples containing (relative file path, file size in bytes)
    """
    ignore_patterns = [
        r"\.git/",
        r"\.cog/",
        r"\.venv/",
        r"__pycache__/",
        r"\.pytest_cache/",
        r"\.DS_Store$",
        r"\.pyc$",
        r"\.ipynb_checkpoints/",
        r"autocog-history\.jsonlines$",
    ]
    compiled_patterns = [re.compile(pattern) for pattern in ignore_patterns]

    all_files = []
    base_path = Path(".")

    for root, _, files in os.walk(base_path):
        root_path = Path(root)
        rel_path = root_path.relative_to(base_path)

        for file in files:
            file_path = rel_path / file
            file_path_str = str(file_path)

            # Skip if matches any ignore pattern
            if any(pattern.search(file_path_str) for pattern in compiled_patterns):
                continue

            # Get file size in bytes using pathlib
            full_path = base_path / file_path
            file_size = full_path.stat().st_size

            all_files.append((file_path_str, file_size))

    return sorted(all_files, key=lambda x: x[0])


def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file

    Returns:
        Contents of the file as a string
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        # For binary files, just return a message rather than failing
        return "[Binary file - content not displayed]"


def read_files(file_paths: list[str]) -> dict[str, str]:
    """
    Read multiple files and return their contents.

    Args:
        file_paths: List of file paths to read

    Returns:
        Dictionary mapping file paths to their contents
    """
    return {path: read_file(path) for path in file_paths}
