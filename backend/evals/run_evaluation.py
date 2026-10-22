"""Run the golden question set end to end and report accuracy metrics.

Usage from the backend directory:
    .venv\\Scripts\\python.exe -m evals.run_evaluation
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.agent.authorization import authorize_read_query, load_policies
from app.agent.executor import execute_read_query
from app.agent.model import DeepSeekModelAdapter
from app.agent.workflow import build_workflow
from app.core.config import get_settings
from app.db.models import Role, User, UserRole
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, dispose_engine, engine
from evals.metrics import (
    chart_accuracy,
    result_accuracy,
    sql_semantic_accuracy,
)

CASES_PATH = Path(__file__).with_name("golden_questions.json")
RESULTS_PATH = Path(__file__).with_name("results.json")


def load_cases() -> list[dict[str, Any]]:
    with CASES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list) or not payload:
        raise ValueError("golden_questions.json must contain a non-empty list")
    return payload


async def self_check(cases: list[dict[str, Any]]) -> None:
    failures: list[str] = []
    for case in cases:
        try:
            rows, _ = await execute_read_query(engine, case["golden_sql"])
            print(f"[self-check] {case['id']}: {len(rows)} row(s)", flush=True)
        except Exception as exc:
            failures.append(case["id"])
            print(f"[self-check] {case['id']}: FAILED {exc}", flush=True)
    await dispose_engine()
    if failures:
        raise SystemExit(f"golden SQL self-check failed for: {', '.join(failures)}")


async def ensure_analyst_user() -> UUID:
    async with SessionLocal() as session:
        await seed_demo_data(session)
        user_id = await session.scalar(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == "analyst", User.is_active.is_(True))
            .order_by(User.created_at)
            .limit(1)
        )
    if user_id is None:
        raise SystemExit(
            "No active analyst user is available. Run "
            "`python scripts/provision_dev_oidc_user.py` first."
        )
    return user_id


async def evaluate_case(
    case: dict[str, Any],
    *,
    adapter: DeepSeekModelAdapter,
    user_id: UUID,
) -> dict[str, Any]:
    graph = build_workflow(
        session_factory=SessionLocal,
        engine=engine,
        adapter=adapter,
    )
    try:
        final = await graph.ainvoke(
            {
                "run_id": f"eval-{case['id']}-{datetime.now(UTC).isoformat()}",
                "user_id": str(user_id),
                "question": case["question"],
                "status": "streaming",
                "approved": False,
                "sql": "",
            }
        )
    except Exception as exc:
        return {
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "status": "failed",
            "sql": "",
            "insight": "",
            "metrics": {
                "sql_execution_accuracy": 0.0,
                "result_accuracy": 0.0,
                "permission_accuracy": 0.0,
                "chart_accuracy": 0.0,
                "sql_semantic_accuracy": 0.0,
            },
            "cost_estimated": None,
            "model": None,
            "error": str(exc)[:500],
        }

    actual_sql = str(final.get("sql", ""))
    actual_rows = final.get("result_rows") or []
    expected_kind = str(case.get("expected_result_kind", "exact"))
    expected_rows: list[dict[str, Any]] = []
    if expected_kind == "exact":
        expected_rows, _ = await execute_read_query(engine, case["golden_sql"])

    permission_ok = False
    try:
        async with SessionLocal() as session:
            policies = await load_policies(session, user_id)
        authorize_read_query(actual_sql, policies, user_id=user_id)
        permission_ok = True
    except Exception:
        permission_ok = False

    executed_ok = final.get("status") == "completed" and bool(actual_sql)
    metrics = {
        "sql_execution_accuracy": 1.0 if executed_ok else 0.0,
        "result_accuracy": result_accuracy(
            actual_rows,
            expected_rows,
            expected_kind=expected_kind,
            invariants=case.get("invariants"),
        ),
        "permission_accuracy": 1.0 if permission_ok else 0.0,
        "chart_accuracy": chart_accuracy(final.get("chart_spec"), case.get("expected_chart")),
        "sql_semantic_accuracy": sql_semantic_accuracy(actual_sql, case.get("required_terms", [])),
    }
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "status": final.get("status"),
        "sql": actual_sql,
        "insight": final.get("insight", ""),
        "metrics": metrics,
        "cost_estimated": final.get("query_cost"),
        "model": final.get("model"),
    }


def aggregate(results: list[dict[str, Any]]) -> dict[str, float]:
    names = [
        "sql_execution_accuracy",
        "result_accuracy",
        "permission_accuracy",
        "chart_accuracy",
        "sql_semantic_accuracy",
    ]
    return {name: sum(item["metrics"][name] for item in results) / len(results) for name in names}


def aggregate_by_category(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item["category"], []).append(item)
    return {category: aggregate(items) for category, items in sorted(grouped.items())}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the golden question evaluation")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of cases")
    parser.add_argument("--category", help="Only run cases with this category")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Only validate that every golden SQL executes",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.agent_enabled:
        raise SystemExit("AGENT_ENABLED is not true; the evaluation requires the real agent")
    if not settings.deepseek_api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")

    cases = load_cases()
    if args.category:
        cases = [case for case in cases if case["category"] == args.category]
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
    if args.self_check:
        await self_check(cases)
        return
    user_id = await ensure_analyst_user()
    adapter = DeepSeekModelAdapter()
    results = []
    try:
        for case in cases:
            print(f"[eval] running {case['id']} ({case['category']})", flush=True)
            result = await evaluate_case(case, adapter=adapter, user_id=user_id)
            results.append(result)
            print(
                f"[eval] {case['id']}: status={result['status']} "
                f"exec={result['metrics']['sql_execution_accuracy']:.0f} "
                f"result={result['metrics']['result_accuracy']:.0f} "
                f"permission={result['metrics']['permission_accuracy']:.0f} "
                f"chart={result['metrics']['chart_accuracy']:.0f} "
                f"semantic={result['metrics']['sql_semantic_accuracy']:.2f}",
                flush=True,
            )
    finally:
        await dispose_engine()

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cases": results,
        "accuracy": aggregate(results),
        "by_category": aggregate_by_category(results),
    }
    RESULTS_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary["accuracy"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
