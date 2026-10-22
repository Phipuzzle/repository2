import asyncio

from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, dispose_engine


async def main() -> None:
    async with SessionLocal() as session:
        await seed_demo_data(session)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
