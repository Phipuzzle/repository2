import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.embeddings import get_embedding_provider
from app.core.config import get_settings
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


async def _hybrid_rank(session: AsyncSession, question: str) -> list[tuple[str, UUID, float]]:
    if not hasattr(session, "execute"):
        return []
    settings = get_settings()
    provider = get_embedding_provider()
    vector = provider.embed([question])[0]
    literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
    try:
        result = await session.execute(
            text(
                "SELECT content_kind, ref_id, "
                "1 - (embedding <=> CAST(:q AS vector)) AS score "
                "FROM metadata.embeddings "
                "ORDER BY embedding <=> CAST(:q AS vector) "
                "LIMIT :limit"
            ),
            {"q": literal, "limit": settings.metadata_retrieval_top_k},
        )
    except Exception:
        return []
    return [(row.content_kind, row.ref_id, float(row.score)) for row in result]


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
    ranked = await _hybrid_rank(session, question)

    if ranked:
        column_ids = {ref_id for kind, ref_id, _ in ranked if kind == "column"}
        table_ids = {column.table_id for column in columns if column.id in column_ids}
        table_ids.update(ref_id for kind, ref_id, _ in ranked if kind == "table")
        metric_ids = {ref_id for kind, ref_id, _ in ranked if kind == "metric"}
    else:
        table_ids = {
            table.id
            for table in tables
            if not terms
            or _score_metadata(f"{table.table_name} {table.description}", terms)
            or any(
                _score_metadata(f"{column.column_name} {column.description}", terms)
                for column in columns
                if column.table_id == table.id
            )
        }
        metric_ids = {
            metric.id
            for metric in metrics
            if not terms or _score_metadata(f"{metric.name} {metric.definition}", terms)
        }

    for table in tables:
        if table.table_name in {"demo_regions", "demo_products"}:
            table_ids.add(table.id)
    if not table_ids:
        table_ids = {table.id for table in tables}
    if not metric_ids:
        metric_ids = {metric.id for metric in metrics}

    lines = ["可用表和字段："]
    for table in tables:
        if table.id not in table_ids:
            continue
        fields = [
            f"{column.column_name} ({column.data_type}): {column.description}"
            for column in columns
            if column.table_id == table.id
        ]
        lines.append(f"- {table.schema_name}.{table.table_name}: " + ", ".join(fields))

    lines.append("指标定义：")
    lines.extend(
        f"- {metric.name}: {metric.definition}，来源 {metric.source}"
        for metric in metrics
        if metric.id in metric_ids
    )
    if len(lines) == 2:
        lines.append(
            "- analytics.demo_orders, analytics.demo_order_items, "
            "analytics.demo_products, analytics.demo_regions"
        )
    return "\n".join(lines)
