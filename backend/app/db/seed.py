from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DemoOrder, DemoOrderItem, DemoProduct, DemoRegion, Metric, Role


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(DemoRegion.id).limit(1))
    if existing is None:
        regions = [DemoRegion(name=name) for name in ("华东", "华南", "华北", "西部")]
        products = [
            DemoProduct(name="智能手表", category="数码"),
            DemoProduct(name="无线耳机", category="数码"),
            DemoProduct(name="咖啡机", category="家电"),
        ]
        session.add_all(regions + products + [
            Role(name="analyst", description="Read-only analytics user"),
            Metric(name="销售额", definition="有效订单实付金额之和，不含取消订单。", source="analytics.demo_orders.total_amount"),
            Metric(name="订单数", definition="有效订单的去重订单数量。", source="analytics.demo_orders.id"),
        ])
        await session.flush()
    else:
        regions = list((await session.scalars(select(DemoRegion).order_by(DemoRegion.id))).all())
        products = list((await session.scalars(select(DemoProduct).order_by(DemoProduct.id))).all())

    current_year = datetime.now(UTC).year
    for year in range(current_year - 2, current_year + 1):
        year_count = await session.scalar(select(func.count()).select_from(DemoOrder).where(extract("year", DemoOrder.created_at) == year))
        if year_count:
            continue
        for month in range(1, 13):
            for region_index, region in enumerate(regions):
                amount = Decimal(10000 + (year - current_year + 2) * 1000 + month * 750 + region_index * 320)
                order = DemoOrder(
                    region_id=region.id,
                    product_id=products[(month + region_index) % len(products)].id,
                    created_at=datetime(year, month, 15, 12, tzinfo=UTC),
                    total_amount=amount,
                    status="paid",
                )
                session.add(order)
                await session.flush()
                session.add(DemoOrderItem(order_id=order.id, quantity=1 + month % 3, unit_price=amount))
    await session.commit()
