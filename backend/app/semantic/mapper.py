from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    SemanticDimension,
    SemanticMetric,
)


async def resolve_semantic_context(session: AsyncSession, question: str) -> str:
    normalized = question.lower()
    metrics = (await session.scalars(select(SemanticMetric).order_by(SemanticMetric.name))).all()
    dimensions = (
        await session.scalars(select(SemanticDimension).order_by(SemanticDimension.name))
    ).all()
    matched_metrics = [
        metric for metric in metrics if any(alias.lower() in normalized for alias in metric.aliases)
    ]
    matched_dimensions = [
        dimension
        for dimension in dimensions
        if any(alias.lower() in normalized for alias in dimension.aliases)
    ]
    if not matched_metrics and not matched_dimensions:
        return ""

    lines = ["标准指标："]
    for metric in matched_metrics:
        qualifier = f"，口径 {metric.qualifier}" if metric.qualifier else ""
        lines.append(
            f"- {metric.name}: 公式 {metric.formula}{qualifier}，"
            f"默认粒度 {metric.default_grain or '无'}，图表 {metric.chart_type}"
        )
    lines.append("标准维度：")
    for dimension in matched_dimensions:
        grain = f"（粒度 {dimension.time_grain}）" if dimension.time_grain else ""
        lines.append(f"- {dimension.name}: {dimension.table_name}.{dimension.column_name}{grain}")
    return "\n".join(lines)
