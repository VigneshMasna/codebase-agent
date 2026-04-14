from __future__ import annotations

from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:

    def __init__(self) -> None:
        try:
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load embedding model 'all-MiniLM-L6-v2': {exc}. "
                "Ensure the model is cached or an internet connection is available."
            ) from exc

    def generate(self, text: str) -> list[float] | None:
        if not text or not text.strip():
            return None
        try:
            return self.model.encode(text).tolist()
        except Exception as exc:
            raise RuntimeError(f"Embedding generation failed: {exc}") from exc
