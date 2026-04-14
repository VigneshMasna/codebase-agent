from __future__ import annotations

from pathlib import Path


SUPPORTED_LANGUAGES = {"c", "cpp", "java"}


def detect_language(filename: str) -> str | None:
    filename = filename.lower()

    if filename.endswith(".c"):
        return "c"

    if filename.endswith(".cpp") or filename.endswith(".cc") or filename.endswith(".cxx"):
        return "cpp"

    if filename.endswith(".java"):
        return "java"

    return None


def detect_language_from_path(path: Path) -> str | None:
    return detect_language(path.name)
