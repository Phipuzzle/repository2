from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DemoOrder, QueryRun


def normalize_question(question: str) -> str:
    return " ".join(question.lower().split())


def build_cache_key(question: str, data_version: str) -> str:
    normalized = normalize_question(question)
    return hashlib.sha256(f"{normalized}\x00{data_version}".encode()).hexdigest()


async def get_data_version(session: AsyncSession) -> str:
    max_id = await session.scalar(select(func.max(DemoOrder.id)))
    max_created = await session.scalar(select(func.max(DemoOrder.created_at)))
    return f"{max_id or 0}:{max_created.isoformat() if max_created else 'empty'}"


async def find_cached_run(
    session: AsyncSession,
    *,
    user_id: UUID,
    question: str,
    data_version: str,
) -> QueryRun | None:
    now = datetime.now(UTC)
    cache_key = build_cache_key(question, data_version)
    cached = await session.scalar(
        select(QueryRun)
        .where(
            QueryRun.user_id == user_id,
            QueryRun.cache_key == cache_key,
            QueryRun.status == "completed",
            QueryRun.result_rows.is_not(None),
            QueryRun.cache_expires_at > now,
        )
        .order_by(QueryRun.created_at.desc())
        .limit(1)
    )
    if cached is not None:
        return cached

    # Preserve compatibility with runs created before cache metadata existed.
    return await session.scalar(
        select(QueryRun)
        .where(
            QueryRun.user_id == user_id,
            QueryRun.question == question,
            QueryRun.status == "completed",
            QueryRun.result_rows.is_not(None),
            QueryRun.cache_key.is_(None),
        )
        .order_by(QueryRun.created_at.desc())
        .limit(1)
    )


def cache_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(seconds=get_settings().query_cache_ttl_seconds)
