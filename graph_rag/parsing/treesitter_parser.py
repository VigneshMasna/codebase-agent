from __future__ import annotations

from pathlib import Path

from tree_sitter_languages import get_language, get_parser


_SUPPORTED_LANGUAGES = {"c", "cpp", "java"}


class TreeSitterParser:

    def __init__(self, language_name: str) -> None:
        if language_name not in _SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{language_name}'. "
                f"Supported languages: {sorted(_SUPPORTED_LANGUAGES)}"
            )
        try:
            self.language = get_language(language_name)
            self.parser   = get_parser(language_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load Tree-Sitter parser for '{language_name}': {exc}"
            ) from exc

    def parse_code(self, code: str) -> object:
        try:
            return self.parser.parse(bytes(code or "", "utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Tree-Sitter failed to parse code: {exc}") from exc

    def parse_file(self, file_path: str) -> object:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        try:
            code = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            raise OSError(f"Failed to read source file '{file_path}': {exc}") from exc
        return self.parse_code(code)


def traverse(node: object, depth: int = 0) -> None:
    print("  " * depth + node.type)
    for child in node.children:
        traverse(child, depth + 1)
