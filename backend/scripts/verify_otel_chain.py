"""Run one real agent query and verify its OpenTelemetry trace reaches Langfuse."""

from __future__ import annotations

import asyncio
import base64
import time
from uuid import UUID

import httpx
from opentelemetry import trace
from sqlalchemy import select

from app.agent.service import run_agent
from app.agent.telemetry import configure_telemetry, get_tracer
from app.core.config import Settings, get_settings
from app.db.models import QueryRun, Role, User, UserRole
from app.db.session import SessionLocal, dispose_engine
from app.services.query_service import add_event

QUESTION = "查询今年华东区域各月的销售额和订单数"


async def create_run() -> UUID:
    async with SessionLocal() as session:
        user_id = await session.scalar(
            select(User.id)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == "analyst", User.is_active.is_(True))
            .order_by(User.created_at)
            .limit(1)
        )
        if user_id is None:
            raise SystemExit("No active analyst user is available")
        run = QueryRun(user_id=user_id, question=QUESTION, status="submitting")
        session.add(run)
        await session.flush()
        await add_event(session, run, "submitted", "OTel 链路验证")
        await session.commit()
        return run.id


def wait_for_trace(settings: Settings) -> None:
    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    authorization = base64.b64encode(credentials).decode()
    url = f"{settings.langfuse_host.rstrip('/')}/api/public/traces"
    for _ in range(10):
        response = httpx.get(
            url,
            headers={"Authorization": f"Basic {authorization}"},
            params={"name": "agent.run", "limit": 5},
            timeout=10,
        )
        if response.status_code == 200:
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if rows:
                print(f"OK: agent.run trace reached Langfuse ({len(rows)} trace(s))")
                return
        time.sleep(3)
    raise SystemExit("FAILED: agent.run trace did not reach Langfuse")


async def main() -> None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        raise SystemExit("LANGFUSE_ENABLED is not true in the current environment")
    if not settings.deepseek_api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")

    configure_telemetry()
    run_id = await create_run()
    tracer = get_tracer()
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute("query_run.id", str(run_id))
        await run_agent(run_id)

    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if shutdown is not None:
        shutdown()
    await dispose_engine()
    wait_for_trace(settings)


if __name__ == "__main__":
    asyncio.run(main())
