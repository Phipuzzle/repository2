import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ColumnMetadata, Metric, TableMetadata


def _question_terms(question: str) -> set[str]:
    normalized = question.lower()
    terms = set(re.findall(r"[a-z0-9_]+", normalized))
    for phrase in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(phrase) <= 3:
            terms.add(phrase)
        else:
            terms.update(
                phrase[index : index + width]
                for width in (2, 3)
                for index in range(len(phrase) - width + 1)
            )
    return terms


def _score_metadata(text: str, terms: set[str]) -> int:
    normalized = text.lower()
    return sum(1 for term in terms if term in normalized)


async def retrieve_context(session: AsyncSession, question: str = "") -> str:
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
    terms = _question_terms(question)
    table_names = {
        table.id: f"{table.schema_name}.{table.table_name}"
        for table in tables
        if not terms
        or _score_metadata(f"{table.table_name} {table.description}", terms)
        or any(
            _score_metadata(f"{column.column_name} {column.description}", terms)
            for column in columns
            if column.table_id == table.id
        )
    }
    for table in tables:
        if table.table_name in {"demo_regions", "demo_products"}:
            table_names[table.id] = f"{table.schema_name}.{table.table_name}"
    if not table_names:
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
    relevant_metrics = [
        metric
        for metric in metrics
        if not terms or _score_metadata(f"{metric.name} {metric.definition}", terms)
    ]
    lines.extend(
        f"- {metric.name}: {metric.definition}，来源 {metric.source}"
        for metric in (relevant_metrics or metrics)
    )
    if len(lines) == 2:
        lines.append(
            "- analytics.demo_orders, analytics.demo_order_items, "
            "analytics.demo_products, analytics.demo_regions"
        )
    return "\n".join(lines)
