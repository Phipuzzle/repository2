from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ColumnMetadata, Metric, TableMetadata


async def retrieve_context(session: AsyncSession) -> str:
    tables = (
        await session.scalars(
            select(TableMetadata).order_by(TableMetadata.schema_name, TableMetadata.table_name)
        )
    ).all()
    columns = (
        await session.scalars(
            select(ColumnMetadata).order_by(ColumnMetadata.table_id, ColumnMetadata.column_name)
        )
    ).all()
    metrics = (await session.scalars(select(Metric).order_by(Metric.name))).all()
    table_names = {table.id: f"{table.schema_name}.{table.table_name}" for table in tables}
    lines = ["可用表和字段："]
    for table_id, table_name in table_names.items():
        fields = [
            f"{column.column_name} ({column.data_type}): {column.description}"
            for column in columns
            if column.table_id == table_id
        ]
        lines.append(f"- {table_name}: " + ", ".join(fields))
    lines.append("指标定义：")
    lines.extend(
        f"- {metric.name}: {metric.definition}，来源 {metric.source}" for metric in metrics
    )
    if len(lines) == 2:
        lines.append(
            "- analytics.demo_orders, analytics.demo_order_items, "
            "analytics.demo_products, analytics.demo_regions"
        )
    return "\n".join(lines)
