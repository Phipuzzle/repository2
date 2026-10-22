"""Smoke-test that an OpenTelemetry span reaches Langfuse end to end.

Run from the backend directory with the project environment active, e.g.
``.venv\\Scripts\\python.exe -m scripts.verify_langfuse_trace``.
"""

from __future__ import annotations

import base64
import time
import uuid

import httpx
from opentelemetry import trace

from app.agent.telemetry import configure_telemetry, get_tracer
from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        raise SystemExit("LANGFUSE_ENABLED is not true in the current environment")

    configure_telemetry()

    trace_name = f"ida-stage3-smoke-{uuid.uuid4().hex[:8]}"
    tracer = get_tracer()
    with tracer.start_as_current_span(trace_name) as span:
        span.set_attribute("ida.check", "langfuse-end-to-end")

    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if shutdown is not None:
        shutdown()

    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    authorization = base64.b64encode(credentials).decode()
    headers = {"Authorization": f"Basic {authorization}"}
    url = f"{settings.langfuse_host.rstrip('/')}/api/public/traces"

    last_status: int | None = None
    last_detail = ""
    for _attempt in range(10):
        try:
            response = httpx.get(
                url,
                headers=headers,
                params={"name": trace_name, "limit": 10},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001 - report any transport failure
            last_detail = str(exc)
            time.sleep(3)
            continue

        last_status = response.status_code
        if response.status_code == 200:
            payload = response.json()
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            if rows:
                print(f"OK: trace '{trace_name}' reached Langfuse ({len(rows)} match(es))")
                return
            last_detail = "no matching trace yet"
        else:
            last_detail = response.text[:300]
        time.sleep(3)

    raise SystemExit(
        f"FAILED: trace did not appear in Langfuse. "
        f"status={last_status} detail={last_detail}"
    )


if __name__ == "__main__":
    main()
