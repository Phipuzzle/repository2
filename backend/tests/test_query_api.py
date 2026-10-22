from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.authentication import get_current_user
from app.core.config import get_settings
from app.db.models import (
    AuditLog,
    EvaluationCandidate,
    Feedback,
    QueryEvent,
    QueryRun,
    User,
)
from app.db.session import SessionLocal, engine
from app.main import app

API_USER_ID = UUID("00000000-0000-0000-0000-000000000101")
OTHER_API_USER_ID = UUID("00000000-0000-0000-0000-000000000102")


def make_api_user(user_id: UUID, email: str, subject: str) -> User:
    return User(
        id=user_id,
        email=email,
        display_name="API test user",
        identity_issuer="test-issuer",
        identity_subject=subject,
        is_active=True,
    )


@pytest.fixture(autouse=True)
async def clean_api_test_data() -> AsyncIterator[None]:
    get_settings().agent_enabled = False
    await engine.dispose()
    api_user = make_api_user(API_USER_ID, "api-test@example.invalid", "api-test-subject")
    other_api_user = make_api_user(
        OTHER_API_USER_ID, "api-test-other@example.invalid", "api-test-other-subject"
    )
    async with SessionLocal() as session:
        for user in (api_user, other_api_user):
            if await session.get(User, user.id) is None:
                session.add(user)
        await session.commit()
        run_ids = list(
            (
                await session.scalars(
                    select(QueryRun.id).where(QueryRun.question.like("[api-test]%"))
                )
            ).all()
        )
        if run_ids:
            await session.execute(delete(Feedback).where(Feedback.run_id.in_(run_ids)))
            await session.execute(delete(AuditLog).where(AuditLog.run_id.in_(run_ids)))
            await session.execute(delete(QueryEvent).where(QueryEvent.run_id.in_(run_ids)))
            await session.execute(delete(QueryRun).where(QueryRun.id.in_(run_ids)))
        await session.commit()
    app.dependency_overrides[get_current_user] = lambda: api_user
    yield
    async with SessionLocal() as session:
        run_ids = list(
            (
                await session.scalars(
                    select(QueryRun.id).where(QueryRun.question.like("[api-test]%"))
                )
            ).all()
        )
        if run_ids:
            await session.execute(delete(Feedback).where(Feedback.run_id.in_(run_ids)))
            await session.execute(delete(AuditLog).where(AuditLog.run_id.in_(run_ids)))
            await session.execute(delete(QueryEvent).where(QueryEvent.run_id.in_(run_ids)))
            await session.execute(delete(QueryRun).where(QueryRun.id.in_(run_ids)))
        await session.execute(delete(User).where(User.id.in_([API_USER_ID, OTHER_API_USER_ID])))
        await session.commit()
    await engine.dispose()
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_query_run_create_read_list_cancel_and_result(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] list sales"})
    assert created.status_code == 201
    run = created.json()
    run_id = UUID(run["id"])
    assert run["status"] == "submitting"
    assert run["events"][0]["id"] == 1
    assert run["events"][0]["type"] == "submitted"

    async with SessionLocal() as session:
        saved_run = await session.get(QueryRun, run_id)
        assert saved_run is not None
        assert saved_run.user_id == API_USER_ID
        saved_run.result_rows = [
            {"month": "2026-01", "sales": 128000},
            {"month": "2026-02", "sales": 146500},
        ]
        saved_run.result_schema = [
            {"name": "month", "type": "string", "label": "月份"},
            {"name": "sales", "type": "number", "label": "销售额"},
        ]
        saved_run.result_total = 2
        await session.commit()

    result = await client.get(f"/api/v1/query-runs/{run_id}/result?limit=1&offset=1")
    assert result.status_code == 200
    assert result.json() == {
        "rows": [{"month": "2026-02", "sales": 146500}],
        "schema": [
            {"name": "month", "type": "string", "label": "月份"},
            {"name": "sales", "type": "number", "label": "销售额"},
        ],
        "total": 2,
        "limit": 1,
        "offset": 1,
    }

    cancelled = await client.post(f"/api/v1/query-runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    fetched = await client.get(f"/api/v1/query-runs/{run_id}")
    assert fetched.status_code == 200
    assert [event["id"] for event in fetched.json()["events"]] == [1, 2]

    listed = await client.get("/api/v1/query-runs?limit=10&offset=0")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert any(item["id"] == str(run_id) for item in listed.json()["items"])


@pytest.mark.asyncio
async def test_repeated_completed_question_returns_historical_result(
    client: AsyncClient,
) -> None:
    first = await client.post(
        "/api/v1/query-runs", json={"question": "[api-test] repeated question"}
    )
    run_id = first.json()["id"]

    async with SessionLocal() as session:
        run = await session.get(QueryRun, UUID(run_id))
        assert run is not None
        run.status = "completed"
        run.sql = "SELECT 1"
        run.result_rows = [{"sales": 128000}]
        run.result_schema = [{"name": "sales", "type": "number", "label": "销售额"}]
        run.result_total = 1
        run.completed_at = run.completed_at or datetime.now(UTC)
        await session.commit()

    repeated = await client.post(
        "/api/v1/query-runs", json={"question": "[api-test] repeated question"}
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == run_id
    assert repeated.json()["status"] == "completed"
    assert repeated.json()["result"]["rows"] == [{"sales": 128000}]

    listed = await client.get("/api/v1/query-runs?limit=100")
    matching = [item for item in listed.json()["items"] if item["id"] == run_id]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_expired_cache_creates_a_new_run(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "query_cache_ttl_seconds", -1)
    first = await client.post("/api/v1/query-runs", json={"question": "[api-test] expired cache"})
    first_id = first.json()["id"]
    async with SessionLocal() as session:
        run = await session.get(QueryRun, UUID(first_id))
        assert run is not None
        run.status = "completed"
        run.result_rows = [{"sales": 1}]
        run.result_schema = [{"name": "sales", "type": "number", "label": "销售额"}]
        run.result_total = 1
        await session.commit()

    second = await client.post("/api/v1/query-runs", json={"question": "[api-test] expired cache"})
    assert second.status_code == 201
    assert second.json()["id"] != first_id


@pytest.mark.asyncio
async def test_recompute_creates_a_new_run(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] recompute"})
    run_id = created.json()["id"]
    recomputed = await client.post(f"/api/v1/query-runs/{run_id}/recompute")
    assert recomputed.status_code == 200
    assert recomputed.json()["id"] != run_id


@pytest.mark.asyncio
async def test_conversation_follow_up_increments_turn(client: AsyncClient) -> None:
    first = await client.post("/api/v1/query-runs", json={"question": "[api-test] first turn"})
    conversation_id = first.json()["conversationId"]
    assert conversation_id is not None
    assert first.json()["turnIndex"] == 0

    second = await client.post(
        "/api/v1/query-runs",
        json={"question": "[api-test] follow up", "conversation_id": conversation_id},
    )
    assert second.json()["conversationId"] == conversation_id
    assert second.json()["turnIndex"] == 1


@pytest.mark.asyncio
async def test_sse_replays_events_and_respects_last_event_id(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] replay"})
    run_id = created.json()["id"]
    await client.post(f"/api/v1/query-runs/{run_id}/cancel")

    all_events = await client.get(f"/api/v1/query-runs/{run_id}/events")
    assert all_events.status_code == 200
    assert all_events.headers["content-type"].startswith("text/event-stream")
    assert "id: 1" in all_events.text
    assert "id: 2" in all_events.text
    assert "event: stream_end" in all_events.text

    resumed = await client.get(
        f"/api/v1/query-runs/{run_id}/events", headers={"Last-Event-ID": "1"}
    )
    assert "id: 1" not in resumed.text
    assert "id: 2" in resumed.text
    assert "event: reconnected" in resumed.text

    fetched = await client.get(f"/api/v1/query-runs/{run_id}")
    assert fetched.json()["reconnectCount"] == 1
    assert fetched.json()["events"][-1]["type"] == "reconnected"


@pytest.mark.asyncio
async def test_feedback_metrics_audit_and_openapi(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] feedback"})
    run_id = created.json()["id"]
    feedback = await client.post(
        "/api/v1/feedback", json={"run_id": run_id, "rating": "positive", "comment": "Good"}
    )
    assert feedback.status_code == 201
    assert feedback.json()["rating"] == "positive"

    metrics = await client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert {item["name"] for item in metrics.json()} >= {"销售额", "订单数"}

    audit = await client.get("/api/v1/audit-logs?limit=20")
    assert audit.status_code == 200
    assert any(
        item["action"] == "feedback.created" and item["run_id"] == run_id for item in audit.json()
    )

    openapi = (await client.get("/openapi.json")).json()
    assert "/api/v1/query-runs/{run_id}/events" in openapi["paths"]
    assert "/api/v1/feedback" in openapi["paths"]


@pytest.mark.asyncio
async def test_negative_feedback_creates_evaluation_candidate(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/query-runs", json={"question": "[api-test] negative feedback"}
    )
    run_id = created.json()["id"]
    feedback = await client.post(
        "/api/v1/feedback",
        json={"run_id": run_id, "rating": "negative", "comment": "result wrong"},
    )
    assert feedback.status_code == 201
    feedback_id = UUID(feedback.json()["id"])

    async with SessionLocal() as session:
        candidate = await session.scalar(
            select(EvaluationCandidate).where(EvaluationCandidate.feedback_id == feedback_id)
        )
        assert candidate is not None
        assert candidate.question == "[api-test] negative feedback"
        assert str(candidate.run_id) == run_id


@pytest.mark.asyncio
async def test_validation_and_not_found_errors(client: AsyncClient) -> None:
    invalid = await client.post("/api/v1/query-runs", json={"question": "   "})
    assert invalid.status_code == 422
    missing = await client.get("/api/v1/query-runs/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_approval_requires_pending_approval(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] approval"})
    run_id = UUID(created.json()["id"])
    rejected = await client.post(f"/api/v1/query-runs/{run_id}/approve")
    assert rejected.status_code == 409

    async with SessionLocal() as session:
        run = await session.get(QueryRun, run_id)
        assert run is not None
        run.status = "awaiting_approval"
        run.approval_reason = "测试需要用户确认"
        await session.commit()

    approved = await client.post(f"/api/v1/query-runs/{run_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "streaming"
    assert approved.json()["events"][-1]["type"] == "approval_granted"


@pytest.mark.asyncio
async def test_query_runs_and_feedback_are_isolated_by_owner(client: AsyncClient) -> None:
    created = await client.post("/api/v1/query-runs", json={"question": "[api-test] private"})
    run_id = created.json()["id"]
    other_api_user = make_api_user(
        OTHER_API_USER_ID, "api-test-other@example.invalid", "api-test-other-subject"
    )
    app.dependency_overrides[get_current_user] = lambda: other_api_user

    detail = await client.get(f"/api/v1/query-runs/{run_id}")
    events = await client.get(f"/api/v1/query-runs/{run_id}/events")
    approval = await client.post(f"/api/v1/query-runs/{run_id}/approve")
    feedback = await client.post("/api/v1/feedback", json={"run_id": run_id, "rating": "positive"})

    assert detail.status_code == 404
    assert events.status_code == 404
    assert approval.status_code == 404
    assert feedback.status_code == 404
    assert (await client.get("/api/v1/query-runs")).json()["total"] == 0
