import math

import pytest

from app.agent.embeddings import HashEmbeddingProvider
from app.agent.metadata import _hybrid_rank


def test_hash_embedding_provider_is_deterministic_and_normalized() -> None:
    provider = HashEmbeddingProvider(dimension=32)
    first = provider.embed(["销售额"])[0]
    second = provider.embed(["销售额"])[0]
    assert first == second
    assert len(first) == 32
    assert math.isclose(sum(value * value for value in first), 1.0, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_hybrid_rank_skips_sessions_without_embeddings() -> None:
    class KeywordOnlySession:
        pass

    assert await _hybrid_rank(KeywordOnlySession(), "销售额") == []  # type: ignore[arg-type]
