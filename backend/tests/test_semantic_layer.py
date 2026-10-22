import pytest

from app.core.config import get_settings
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, dispose_engine, engine
from app.semantic.mapper import resolve_semantic_context


@pytest.fixture(autouse=True)
async def reset_database_engine() -> None:
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_semantic_context_resolves_metric_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "demo_scale", 1)
    monkeypatch.setattr(get_settings(), "demo_years", 1)
    async with SessionLocal() as session:
        await seed_demo_data(session)
        context = await resolve_semantic_context(session, "成交额是多少")
    await dispose_engine()

    assert "销售额" in context
    assert "SUM" in context
    assert "demo_orders.total_amount" in context


@pytest.mark.asyncio
async def test_semantic_context_resolves_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "demo_scale", 1)
    monkeypatch.setattr(get_settings(), "demo_years", 1)
    async with SessionLocal() as session:
        await seed_demo_data(session)
        context = await resolve_semantic_context(session, "各地区的订单数")
    await dispose_engine()

    assert "区域" in context
    assert "订单数" in context
