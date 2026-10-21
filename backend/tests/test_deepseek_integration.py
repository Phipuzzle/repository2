import os

import pytest

from app.agent.model import DeepSeekModelAdapter
from app.core.config import get_settings


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_DEEPSEEK_INTEGRATION") != "1",
    reason="set RUN_DEEPSEEK_INTEGRATION=1 to call the configured DeepSeek API",
)
async def test_configured_deepseek_model_returns_json_object() -> None:
    settings = get_settings()
    assert settings.deepseek_api_key, "configure DEEPSEEK_API_KEY in backend/.env"

    result = await DeepSeekModelAdapter().complete_json(
        model=settings.deepseek_flash_model,
        system='Return only a JSON object: {"stage3_test":"ok"}.',
        user='Return the JSON object {"stage3_test":"ok"}.',
        temperature=0.0,
    )

    assert result.get("stage3_test") == "ok"
