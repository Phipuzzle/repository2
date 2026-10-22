"""Export negative feedback as golden question candidates."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import Feedback, QueryRun
from app.db.session import SessionLocal, dispose_engine

OUTPUT_PATH = Path("evals/feedback_candidates.json")


async def main() -> None:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Feedback, QueryRun)
                .join(QueryRun, QueryRun.id == Feedback.run_id)
                .where(Feedback.rating == "negative")
                .order_by(Feedback.created_at.desc())
                .limit(500)
            )
        ).all()

    candidates = [
        {
            "question": run.question,
            "run_id": str(run.id),
            "feedback_id": str(feedback.id),
            "comment": feedback.comment,
            "created_at": feedback.created_at.isoformat(),
        }
        for feedback, run in rows
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
