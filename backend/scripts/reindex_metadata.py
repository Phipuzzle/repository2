"""Rebuild metadata embeddings for semantic retrieval."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select

from app.agent.embeddings import get_embedding_provider
from app.db.models import ColumnMetadata, MetadataEmbedding, Metric, TableMetadata
from app.db.session import SessionLocal, dispose_engine


@dataclass(frozen=True)
class EmbeddingRecord:
    content_kind: str
    ref_id: UUID
    content_text: str


async def build_records() -> list[EmbeddingRecord]:
    async with SessionLocal() as session:
        tables = (await session.scalars(select(TableMetadata))).all()
        columns = (await session.scalars(select(ColumnMetadata))).all()
        metrics = (await session.scalars(select(Metric))).all()

    records = [
        EmbeddingRecord(
            "table",
            table.id,
            f"{table.schema_name}.{table.table_name} {table.description}",
        )
        for table in tables
    ]
    records.extend(
        EmbeddingRecord(
            "column",
            column.id,
            f"{column.column_name} {column.description}",
        )
        for column in columns
    )
    records.extend(
        EmbeddingRecord(
            "metric",
            metric.id,
            f"{metric.name} {metric.definition} {metric.source}",
        )
        for metric in metrics
    )
    return records


async def main() -> None:
    provider = get_embedding_provider()
    records = await build_records()
    if not records:
        print("No metadata records to index")
        return

    vectors = provider.embed([record.content_text for record in records])
    async with SessionLocal() as session:
        await session.execute(
            delete(MetadataEmbedding).where(MetadataEmbedding.model_id == provider.model_id)
        )
        session.add_all(
            MetadataEmbedding(
                content_kind=record.content_kind,
                ref_id=record.ref_id,
                content_text=record.content_text,
                embedding=vector,
                model_id=provider.model_id,
                version=provider.version,
            )
            for record, vector in zip(records, vectors, strict=True)
        )
        await session.commit()

    print(
        f"Indexed {len(records)} metadata records with "
        f"model={provider.model_id} version={provider.version}"
    )
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
