"""
SymbolExtractor — language router.

Passes the shared SymbolIndex and EmbeddingGenerator into the correct
language-specific extractor.
"""
from __future__ import annotations

from extraction.java_extractor import JavaExtractor
from extraction.c_extractor import CExtractor
from extraction.cpp_extractor import CppExtractor
from extraction.symbol_index import SymbolIndex
from extraction.symbol_models import CodeGraph


class SymbolExtractor:

    def __init__(
        self,
        language: str,
        symbol_index: SymbolIndex,
        embedder=None,
    ) -> None:
        if language == "java":
            self._extractor = JavaExtractor(symbol_index, embedder)
        elif language == "c":
            self._extractor = CExtractor(symbol_index, embedder)
        elif language == "cpp":
            self._extractor = CppExtractor(symbol_index, embedder)
        else:
            raise ValueError(f"Unsupported language: {language!r}")

    def extract(self, root_node, file_name: str) -> CodeGraph:
        return self._extractor.extract(root_node, file_name)
