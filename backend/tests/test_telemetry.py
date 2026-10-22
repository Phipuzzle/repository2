import base64
from collections.abc import Iterator
from typing import Any

import pytest

from app.agent import telemetry
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def clear_telemetry_cache() -> Iterator[None]:
    telemetry.configure_telemetry.cache_clear()
    yield
    telemetry.configure_telemetry.cache_clear()


def test_telemetry_is_noop_when_langfuse_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "langfuse_enabled", False)
    monkeypatch.setattr(
        "opentelemetry.trace.set_tracer_provider",
        lambda _provider: pytest.fail("disabled telemetry must not install an exporter"),
    )

    telemetry.configure_telemetry()


def test_telemetry_rejects_missing_langfuse_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "langfuse_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    with pytest.raises(ValueError, match="public or secret key is missing"):
        telemetry.configure_telemetry()


def test_telemetry_builds_otlp_exporter_with_basic_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "langfuse_enabled", True)
    monkeypatch.setattr(settings, "langfuse_public_key", "public-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "secret-test")
    monkeypatch.setattr(settings, "langfuse_host", "https://langfuse.example/")
    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, *, resource: Any) -> None:
            captured["resource"] = resource

        def add_span_processor(self, processor: Any) -> None:
            captured["processor"] = processor

    class FakeProcessor:
        def __init__(self, exporter: Any) -> None:
            captured["exporter"] = exporter

    monkeypatch.setattr(
        telemetry,
        "OTLPSpanExporter",
        lambda **kwargs: captured.update(kwargs) or object(),
    )
    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", FakeProcessor)
    monkeypatch.setattr(
        "opentelemetry.trace.set_tracer_provider",
        lambda provider: captured.update(provider=provider),
    )
    telemetry.configure_telemetry()

    assert captured["endpoint"] == "https://langfuse.example/api/public/otel/v1/traces"
    assert (
        captured["headers"]["Authorization"]
        == "Basic " + base64.b64encode(b"public-test:secret-test").decode()
    )
    assert isinstance(captured["provider"], FakeProvider)
