"""Export negative feedback as golden question candidates."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import EvaluationCandidate
from app.db.session import SessionLocal, dispose_engine

OUTPUT_PATH = Path("evals/feedback_candidates.json")


async def main() -> None:
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(EvaluationCandidate)
                .where(EvaluationCandidate.reviewed.is_(False))
                .order_by(EvaluationCandidate.created_at.desc())
                .limit(500)
            )
        ).all()

    candidates = [
        {
            "question": candidate.question,
            "run_id": str(candidate.run_id) if candidate.run_id else None,
            "feedback_id": str(candidate.feedback_id),
            "comment": candidate.comment,
            "created_at": candidate.created_at.isoformat(),
        }
        for candidate in rows
    ]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(candidates)} negative feedback candidate(s)")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
