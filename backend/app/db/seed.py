from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    ColumnMetadata,
    DemoOrder,
    DemoOrderItem,
    DemoProduct,
    DemoRegion,
    Metric,
    Role,
    SemanticDimension,
    SemanticMapping,
    SemanticMetric,
    TableMetadata,
)
from app.semantic.dictionary import (
    SEMANTIC_DIMENSIONS,
    SEMANTIC_MAPPINGS,
    SEMANTIC_METRICS,
)

REGION_NAMES = (
    "华东",
    "华南",
    "华北",
    "西南",
    "华中",
    "东北",
    "西北",
    "港澳",
    "海外",
    "其他",
)

PRODUCTS = (
    ("智能手表", "数码"),
    ("无线耳机", "数码"),
    ("平板电脑", "数码"),
    ("咖啡机", "家电"),
    ("空气净化器", "家电"),
    ("扫地机器人", "家电"),
    ("运动鞋", "服饰"),
    ("羽绒服", "服饰"),
    ("休闲裤", "服饰"),
    ("坚果礼盒", "食品"),
    ("速溶咖啡", "食品"),
    ("矿泉水", "食品"),
    ("床垫", "家居"),
    ("台灯", "家居"),
    ("收纳箱", "家居"),
    ("洗面奶", "美妆"),
    ("面霜", "美妆"),
    ("防晒霜", "美妆"),
    ("蓝牙音箱", "数码"),
    ("电动牙刷", "家电"),
)

METADATA = {
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


async def _ensure_dimensions(session: AsyncSession) -> tuple[list[DemoRegion], list[DemoProduct]]:
    regions = list((await session.scalars(select(DemoRegion).order_by(DemoRegion.id))).all())
    region_by_name = {region.name: region for region in regions}
    for name in REGION_NAMES:
        if name not in region_by_name:
            region = DemoRegion(name=name)
            session.add(region)
            regions.append(region)
            region_by_name[name] = region

    products = list((await session.scalars(select(DemoProduct).order_by(DemoProduct.id))).all())
    product_by_name = {product.name: product for product in products}
    for name, category in PRODUCTS:
        if name not in product_by_name:
            product = DemoProduct(name=name, category=category)
            session.add(product)
            products.append(product)
            product_by_name[name] = product

    await session.flush()
    return regions, products


async def _ensure_metadata(session: AsyncSession) -> None:
    existing_metric = await session.scalar(select(Metric.id).limit(1))
    if existing_metric is None:
        session.add(
            Role(name="analyst", description="Read-only analytics user"),
        )
        session.add_all(
            [
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

    existing_table = await session.scalar(select(TableMetadata.id).limit(1))
    if existing_table is None:
        for table_name, (description, fields) in METADATA.items():
            table = TableMetadata(
                schema_name="analytics",
                table_name=table_name,
                description=description,
            )
            session.add(table)
            await session.flush()
            session.add_all(
                ColumnMetadata(
                    table_id=table.id,
                    column_name=name,
                    data_type=data_type,
                    description=label,
                )
                for name, data_type, label in fields
            )
    await session.flush()


async def _ensure_semantics(session: AsyncSession) -> None:
    metric_by_name = {}
    for item in SEMANTIC_METRICS:
        metric = await session.scalar(
            select(SemanticMetric).where(SemanticMetric.name == item["name"])
        )
        if metric is None:
            metric = SemanticMetric(**item)
            session.add(metric)
            await session.flush()
        metric_by_name[item["name"]] = metric

    dimension_by_name = {}
    for item in SEMANTIC_DIMENSIONS:
        dimension = await session.scalar(
            select(SemanticDimension).where(SemanticDimension.name == item["name"])
        )
        if dimension is None:
            dimension = SemanticDimension(**item)
            session.add(dimension)
            await session.flush()
        dimension_by_name[item["name"]] = dimension

    for metric_name, dimension_names in SEMANTIC_MAPPINGS:
        metric = metric_by_name[metric_name]
        for dimension_name in dimension_names:
            dimension = dimension_by_name[dimension_name]
            existing = await session.scalar(
                select(SemanticMapping.id).where(
                    SemanticMapping.metric_id == metric.id,
                    SemanticMapping.dimension_id == dimension.id,
                )
            )
            if existing is None:
                session.add(SemanticMapping(metric_id=metric.id, dimension_id=dimension.id))
    await session.flush()


async def _seed_orders(
    session: AsyncSession,
    *,
    regions: list[DemoRegion],
    products: list[DemoProduct],
) -> None:
    settings = get_settings()
    scale = max(1, settings.demo_scale)
    years = max(1, settings.demo_years)
    current_year = datetime.now(UTC).year
    randomizer = random.Random(20261022)

    for year in range(current_year - years + 1, current_year + 1):
        year_count = await session.scalar(
            select(func.count())
            .select_from(DemoOrder)
            .where(extract("year", DemoOrder.created_at) == year)
        )
        if year_count:
            continue

        for month in range(1, 13):
            for region_index, region in enumerate(regions):
                for product_index, product in enumerate(products):
                    bucket = scale + randomizer.randint(0, 2)
                    for offset in range(bucket):
                        seasonal = 1 + 0.25 * max(0, month - 6) + 0.15 * (month in {11, 12})
                        regional = 1 + region_index * 0.03
                        product_premium = 1 + (product_index % 4) * 0.08
                        amount = Decimal(
                            round(
                                (120 + month * 18 + region_index * 11 + offset * 9)
                                * seasonal
                                * regional
                                * product_premium,
                                2,
                            )
                        )
                        status_roll = (year + month + region_index + product_index + offset) % 23
                        status = (
                            "paid"
                            if status_roll < 20
                            else ("refunded" if status_roll == 20 else "cancelled")
                        )
                        day = 1 + (year + month + offset) % 28
                        order = DemoOrder(
                            region_id=region.id,
                            product_id=product.id,
                            created_at=datetime(year, month, day, 8 + offset % 10, tzinfo=UTC),
                            total_amount=amount,
                            status=status,
                        )
                        session.add(order)
                        await session.flush()
                        session.add(
                            DemoOrderItem(
                                order_id=order.id,
                                quantity=1 + (month + product_index + offset) % 3,
                                unit_price=amount,
                            )
                        )
    await session.commit()


async def seed_demo_data(session: AsyncSession) -> None:
    regions, products = await _ensure_dimensions(session)
    await _ensure_metadata(session)
    await _ensure_semantics(session)
    await _seed_orders(session, regions=regions, products=products)
