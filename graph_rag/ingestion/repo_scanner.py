from __future__ import annotations

import os
from pathlib import Path


SUPPORTED_EXTENSIONS = {".c", ".cpp", ".h", ".java"}

# Directories that should never be scanned for source files
_SKIP_DIRS = {
    "venv", ".venv", "__pycache__", "node_modules",
    ".git", ".idea", ".vscode", "build", "dist", "target",
}


def scan_repository(repo_path: str) -> list[str]:
    """
    Walk `repo_path` and return all supported source file paths.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the path is not a directory.
    """
    path = Path(repo_path)
    if not path.exists():
        raise FileNotFoundError(f"Repository path not found: {repo_path}")
    if not path.is_dir():
        raise ValueError(f"Repository path is not a directory: {repo_path}")

    code_files: list[str] = []
    for root, dirs, files in os.walk(path):
        # Prune dirs in-place to skip irrelevant subtrees
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for file in files:
            if Path(file).suffix.lower() in SUPPORTED_EXTENSIONS:
                code_files.append(os.path.join(root, file))

    return code_files
