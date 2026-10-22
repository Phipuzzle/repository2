from typing import Any

import httpx
import pytest
from opentelemetry.trace import StatusCode

from app.agent.model import DeepSeekModelAdapter, ModelResponseError
from app.core.config import get_settings


class MockAsyncClient:
    def __init__(self, *, timeout: httpx.Timeout) -> None:
        self.timeout = timeout
        self.requests: list[dict[str, Any]] = []
        self.responses: list[httpx.Response | Exception] = []

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        return None

    async def post(
        self, url: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> httpx.Response:
        self.requests.append({"url": url, "headers": headers, "json": json})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.exceptions: list[Exception] = []
        self.status: Any = None

    def __enter__(self) -> "RecordingSpan":
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)

    def set_status(self, status: Any) -> None:
        self.status = status


class RecordingTracer:
    def __init__(self, span: RecordingSpan) -> None:
        self.span = span

    def start_as_current_span(self, _name: str) -> RecordingSpan:
        return self.span


@pytest.mark.asyncio
async def test_adapter_parses_json_and_uses_configured_chat_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://model.example/v1/")
    client = MockAsyncClient(timeout=httpx.Timeout(1))
    client.responses.append(
        httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"total_tokens": 4},
            },
            request=httpx.Request("POST", "https://model.example/v1/chat/completions"),
        )
    )
    monkeypatch.setattr("app.agent.model.httpx.AsyncClient", lambda **kwargs: client)

    result = await DeepSeekModelAdapter().complete_json(
        model="deepseek-flash", system="system", user="user", temperature=0.2
    )

    assert result == {"ok": True}
    assert len(client.requests) == 1
    request = client.requests[0]
    assert request["url"] == "https://model.example/v1/chat/completions"
    assert request["headers"] == {"Authorization": "Bearer test-key"}
    assert request["json"]["response_format"] == {"type": "json_object"}
    assert request["json"]["stream"] is False
    assert request["json"]["temperature"] == 0.2


@pytest.mark.asyncio
async def test_adapter_retries_transient_server_failure_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    client = MockAsyncClient(timeout=httpx.Timeout(1))
    client.responses.extend(
        [
            httpx.Response(
                503,
                request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            ),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"recovered": true}'}}]},
                request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            ),
        ]
    )
    monkeypatch.setattr("app.agent.model.httpx.AsyncClient", lambda **kwargs: client)

    result = await DeepSeekModelAdapter().complete_json(
        model="deepseek-flash", system="system", user="user"
    )

    assert result == {"recovered": True}
    assert len(client.requests) == 2


@pytest.mark.asyncio
async def test_adapter_rejects_non_object_json_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    client = MockAsyncClient(timeout=httpx.Timeout(1))
    client.responses.append(
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[1, 2]"}}]},
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        )
    )
    monkeypatch.setattr("app.agent.model.httpx.AsyncClient", lambda **kwargs: client)

    with pytest.raises(ModelResponseError, match="must be an object"):
        await DeepSeekModelAdapter().complete_json(
            model="deepseek-flash", system="system", user="user"
        )

    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_adapter_records_model_errors_and_duration_in_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    client = MockAsyncClient(timeout=httpx.Timeout(1))
    client.responses.append(
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[1, 2]"}}]},
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        )
    )
    span = RecordingSpan()
    monkeypatch.setattr("app.agent.model.trace.get_tracer", lambda *_args: RecordingTracer(span))
    monkeypatch.setattr("app.agent.model.httpx.AsyncClient", lambda **kwargs: client)

    with pytest.raises(ModelResponseError, match="must be an object"):
        await DeepSeekModelAdapter().complete_json(
            model="deepseek-flash", system="system", user="user"
        )

    assert span.exceptions
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["gen_ai.client.operation.duration_ms"] >= 0


def test_model_router_uses_flash_for_simple_and_pro_for_complex() -> None:
    adapter = DeepSeekModelAdapter()

    assert adapter.model_for("simple") == get_settings().deepseek_flash_model
    assert adapter.model_for("complex") == get_settings().deepseek_pro_model
