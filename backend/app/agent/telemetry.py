import base64
from functools import lru_cache
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings

_instrumented_engines: set[int] = set()


@lru_cache
def configure_telemetry() -> None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        return
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        raise ValueError("Langfuse is enabled but its public or secret key is missing")

    credentials = f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    authorization = base64.b64encode(credentials).decode()
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {authorization}"},
    )
    provider = TracerProvider(resource=Resource.create({"service.name": "intelligent-data-agent"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def get_tracer() -> Tracer:
    return trace.get_tracer("intelligent-data-agent")


def instrument_sqlalchemy(engine: AsyncEngine) -> None:
    if id(engine) in _instrumented_engines:
        return
    sync_engine = engine.sync_engine
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)

    def redact_statement(
        _connection: Any,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("db.statement", "[redacted]")
            span.set_attribute("db.query.text", "[redacted]")

    event.listen(sync_engine, "after_cursor_execute", redact_statement)
    _instrumented_engines.add(id(engine))


def instrument_fastapi(app: Any) -> None:
    FastAPIInstrumentor.instrument_app(app)
