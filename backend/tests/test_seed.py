import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import DemoOrder, DemoRegion
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal


@pytest.mark.asyncio
async def test_seed_demo_data_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "demo_scale", 1)
    monkeypatch.setattr(get_settings(), "demo_years", 2)

    async with SessionLocal() as session:
        before_orders = await session.scalar(select(func.count()).select_from(DemoOrder))
        await seed_demo_data(session)
        after_first = await session.scalar(select(func.count()).select_from(DemoOrder))
        await seed_demo_data(session)
        after_second = await session.scalar(select(func.count()).select_from(DemoOrder))
        regions = await session.scalar(select(func.count()).select_from(DemoRegion))

    assert after_first >= before_orders
    assert after_second == after_first
    assert (regions or 0) >= 10
