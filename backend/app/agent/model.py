import json
from typing import Any

import httpx
from opentelemetry import trace

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
            "response_format": {"type": "json_object"},
        }

        try:
            with trace.get_tracer("intelligent-data-agent").start_as_current_span(
                "deepseek.chat"
            ) as span:
                span.set_attribute("gen_ai.system", "deepseek")
                span.set_attribute("gen_ai.request.model", model)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    span.set_attribute("http.response.status_code", response.status_code)
                    response.raise_for_status()
                    response_body = response.json()
                    content = response_body["choices"][0]["message"]["content"]
                    usage = response_body.get("usage", {})
                    if "total_tokens" in usage:
                        span.set_attribute("gen_ai.usage.total_tokens", usage["total_tokens"])
                value = json.loads(content)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ModelResponseError(
                "DeepSeek returned an invalid or unsuccessful response"
            ) from exc
        if not isinstance(value, dict):
            raise ModelResponseError("DeepSeek JSON response must be an object")
        return value
