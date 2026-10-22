"""Aggregate Langfuse observations and check observability SLOs."""

from __future__ import annotations

import base64
import math
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import get_settings


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_observations(
    name: str, since: datetime, headers: dict[str, str], host: str
) -> list[dict[str, Any]]:
    response = httpx.get(
        f"{host.rstrip('/')}/api/public/observations",
        headers=headers,
        params={"name": name, "limit": 100},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and (parse_time(row.get("startTime")) or datetime.min.replace(tzinfo=UTC)) >= since
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, float]:
    latencies = [
        float(row["latency"]) for row in rows if isinstance(row.get("latency"), (int, float))
    ]
    errors = sum(1 for row in rows if row.get("level") == "ERROR")
    tokens = sum(
        int(row.get("totalTokens") or 0)
        for row in rows
        if isinstance(row.get("totalTokens"), (int, float))
    )
    return {
        "count": float(len(rows)),
        "p95_seconds": percentile(latencies, 0.95),
        "error_rate": errors / len(rows) if rows else 0.0,
        "total_tokens": float(tokens),
    }


def main() -> None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        raise SystemExit("LANGFUSE_ENABLED is not true")
    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    authorization = base64.b64encode(credentials).decode()
    headers = {"Authorization": f"Basic {authorization}"}
    since = datetime.now(UTC) - timedelta(minutes=settings.slo_lookback_minutes)

    agent = summarize(fetch_observations("agent.run", since, headers, settings.langfuse_host))
    deepseek = summarize(
        fetch_observations("deepseek.chat", since, headers, settings.langfuse_host)
    )

    report = {
        "agent": agent,
        "deepseek": deepseek,
        "thresholds": {
            "agent_p95_seconds": settings.slo_agent_p95_seconds,
            "agent_error_rate": settings.slo_agent_error_rate,
            "deepseek_p95_seconds": settings.slo_deepseek_p95_seconds,
            "deepseek_error_rate": settings.slo_deepseek_error_rate,
        },
    }
    print(report)
    violations = []
    if agent["count"] and agent["p95_seconds"] > settings.slo_agent_p95_seconds:
        violations.append(f"agent p95 {agent['p95_seconds']:.2f}s exceeds threshold")
    if agent["count"] and agent["error_rate"] > settings.slo_agent_error_rate:
        violations.append(f"agent error rate {agent['error_rate']:.3f} exceeds threshold")
    if deepseek["count"] and deepseek["p95_seconds"] > settings.slo_deepseek_p95_seconds:
        violations.append(f"deepseek p95 {deepseek['p95_seconds']:.2f}s exceeds threshold")
    if deepseek["count"] and deepseek["error_rate"] > settings.slo_deepseek_error_rate:
        violations.append(f"deepseek error rate {deepseek['error_rate']:.3f} exceeds threshold")

    if violations:
        raise SystemExit("SLO violations:\n" + "\n".join(violations))
    print("OK: SLO checks passed")


if __name__ == "__main__":
    main()
