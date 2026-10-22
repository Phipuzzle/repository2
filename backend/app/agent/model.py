import json
import time
from typing import Any

import httpx
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.agent.prompts import PROMPT_VERSION
from app.core.config import get_settings


class ModelConfigurationError(RuntimeError):
    pass


class ModelResponseError(RuntimeError):
    pass


class DeepSeekModelAdapter:
    def __init__(self) -> None:
        self.settings = get_settings()

    def model_for(self, complexity: str) -> str:
        if complexity == "complex":
            return self.settings.deepseek_pro_model
        return self.settings.deepseek_flash_model

    async def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if not self.settings.deepseek_api_key:
            raise ModelConfigurationError(
                "DeepSeek API key is not configured. Set DEEPSEEK_API_KEY in backend/.env."
            )

        endpoint = self.settings.deepseek_base_url.rstrip("/") + "/chat/completions"
        timeout = httpx.Timeout(self.settings.deepseek_timeout_seconds)
        headers = {"Authorization": f"Bearer {self.settings.deepseek_api_key}"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": self.settings.deepseek_max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }

        started_at = time.perf_counter()
        try:
            with trace.get_tracer("intelligent-data-agent").start_as_current_span(
                "deepseek.chat"
            ) as span:
                try:
                    span.set_attribute("gen_ai.system", "deepseek")
                    span.set_attribute("gen_ai.request.model", model)
                    span.set_attribute("gen_ai.prompt.version", PROMPT_VERSION)
                    span.set_attribute("gen_ai.request.temperature", temperature)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        for attempt in range(2):
                            try:
                                response = await client.post(
                                    endpoint, headers=headers, json=payload
                                )
                                response.raise_for_status()
                                break
                            except httpx.HTTPStatusError as exc:
                                retryable = (
                                    exc.response.status_code in {408, 429}
                                    or exc.response.status_code >= 500
                                )
                                if attempt == 0 and retryable:
                                    continue
                                raise ModelResponseError(
                                    "DeepSeek returned an unsuccessful response"
                                ) from exc
                            except httpx.TransportError as exc:
                                if attempt == 0:
                                    continue
                                raise ModelResponseError(
                                    "DeepSeek request failed after retry"
                                ) from exc
                        span.set_attribute("http.response.status_code", response.status_code)
                        response_body = response.json()
                        choice = response_body["choices"][0]
                        finish_reason = choice.get("finish_reason")
                        if finish_reason == "length":
                            raise ModelResponseError("DeepSeek JSON response was truncated")
                        content = choice["message"].get("content")
                        if not isinstance(content, str) or not content.strip():
                            raise ModelResponseError("DeepSeek returned empty JSON content")
                        usage = response_body.get("usage", {})
                        for key, attribute in (
                            ("prompt_tokens", "gen_ai.usage.input_tokens"),
                            ("completion_tokens", "gen_ai.usage.output_tokens"),
                            ("total_tokens", "gen_ai.usage.total_tokens"),
                        ):
                            if key in usage:
                                span.set_attribute(attribute, usage[key])
                    value = json.loads(content)
                    if not isinstance(value, dict):
                        raise ModelResponseError("DeepSeek JSON response must be an object")
                    return value
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                    raise
                finally:
                    span.set_attribute(
                        "gen_ai.client.operation.duration_ms",
                        (time.perf_counter() - started_at) * 1000,
                    )
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ModelResponseError(
                "DeepSeek returned an invalid or unsuccessful response"
            ) from exc
        return value
