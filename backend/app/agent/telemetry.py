import base64
from functools import lru_cache

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from app.core.config import get_settings


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
