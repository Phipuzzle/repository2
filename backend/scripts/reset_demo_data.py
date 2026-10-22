"""Truncate and rebuild demo analytics data."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, dispose_engine


async def main() -> None:
    async with SessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE analytics.demo_order_items, analytics.demo_orders, "
                "analytics.demo_products, analytics.demo_regions RESTART IDENTITY CASCADE"
            )
        )
        await seed_demo_data(session)
    await dispose_engine()
    print("Demo data has been rebuilt")


if __name__ == "__main__":
    asyncio.run(main())
