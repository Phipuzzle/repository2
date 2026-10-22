from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    model_id: str
    version: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class HashEmbeddingProvider:
    """Deterministic fallback embedding for environments without a model."""

    def __init__(self, dimension: int = 512) -> None:
        self.dimension = dimension
        self.model_id = "local-hash"
        self.version = "hash-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vector = [
                ((digest[index % len(digest)] / 127.5) - 1.0) for index in range(self.dimension)
            ]
            vectors.append(_normalize(vector))
        return vectors


class SentenceTransformerProvider:
    def __init__(self, model_id: str, dimension: int = 512) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError(
                "Install the embedding extra with `pip install -e '.[embeddings]'`"
            ) from exc
        self.model_id = model_id
        self.version = f"{model_id}-v1"
        self.dimension = dimension
        self._model = SentenceTransformer(model_id)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [list(vector) for vector in vectors]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return SentenceTransformerProvider(
            settings.embedding_model_id,
            settings.embedding_dimension,
        )
    return HashEmbeddingProvider(settings.embedding_dimension)
