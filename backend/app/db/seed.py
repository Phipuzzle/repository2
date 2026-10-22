from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ColumnMetadata,
    DemoOrder,
    DemoOrderItem,
    DemoProduct,
    DemoRegion,
    Metric,
    Role,
    TableMetadata,
)


async def seed_demo_data(session: AsyncSession) -> None:
    existing = await session.scalar(select(DemoRegion.id).limit(1))
    if existing is None:
        regions = [DemoRegion(name=name) for name in ("华东", "华南", "华北", "西部")]
        products = [
            DemoProduct(name="智能手表", category="数码"),
            DemoProduct(name="无线耳机", category="数码"),
            DemoProduct(name="咖啡机", category="家电"),
        ]
        session.add_all(
            regions
            + products
            + [
                Role(name="analyst", description="Read-only analytics user"),
                Metric(
                    name="销售额",
                    definition="有效订单实付金额之和，不含取消订单。",
                    source="analytics.demo_orders.total_amount",
                ),
                Metric(
                    name="订单数",
                    definition="有效订单的去重订单数量。",
                    source="analytics.demo_orders.id",
                ),
            ]
        )
        await session.flush()
    else:
        regions = list((await session.scalars(select(DemoRegion).order_by(DemoRegion.id))).all())
        products = list((await session.scalars(select(DemoProduct).order_by(DemoProduct.id))).all())

    existing_metadata = await session.scalar(select(TableMetadata.id).limit(1))
    if existing_metadata is None:
        metadata = {
            "demo_orders": (
                "订单事实表",
                [
                    ("id", "integer", "订单 ID"),
                    ("region_id", "integer", "区域 ID"),
                    ("product_id", "integer", "商品 ID"),
                    ("created_at", "timestamp with time zone", "下单时间"),
                    ("total_amount", "numeric", "订单金额"),
                    ("status", "text", "订单状态"),
                ],
            ),
            "demo_order_items": (
                "订单明细表",
                [
                    ("id", "integer", "明细 ID"),
                    ("order_id", "integer", "订单 ID"),
                    ("quantity", "integer", "购买数量"),
                    ("unit_price", "numeric", "单价"),
                ],
            ),
            "demo_products": (
                "商品维度表",
                [
                    ("id", "integer", "商品 ID"),
                    ("name", "text", "商品名称"),
                    ("category", "text", "商品分类"),
                ],
            ),
            "demo_regions": (
                "区域维度表",
                [("id", "integer", "区域 ID"), ("name", "text", "区域名称")],
            ),
        }
        for table_name, (description, fields) in metadata.items():
            table = TableMetadata(
                schema_name="analytics", table_name=table_name, description=description
            )
            session.add(table)
            await session.flush()
            session.add_all(
                ColumnMetadata(
                    table_id=table.id, column_name=name, data_type=data_type, description=label
                )
                for name, data_type, label in fields
            )

    current_year = datetime.now(UTC).year
    for year in range(current_year - 2, current_year + 1):
        year_count = await session.scalar(
            select(func.count())
            .select_from(DemoOrder)
            .where(extract("year", DemoOrder.created_at) == year)
        )
        if year_count:
            continue
        for month in range(1, 13):
            for region_index, region in enumerate(regions):
                amount = Decimal(
                    10000 + (year - current_year + 2) * 1000 + month * 750 + region_index * 320
                )
                order = DemoOrder(
                    region_id=region.id,
                    product_id=products[(month + region_index) % len(products)].id,
                    created_at=datetime(year, month, 15, 12, tzinfo=UTC),
                    total_amount=amount,
                    status="paid",
                )
                session.add(order)
                await session.flush()
                session.add(
                    DemoOrderItem(order_id=order.id, quantity=1 + month % 3, unit_price=amount)
                )
    await session.commit()
