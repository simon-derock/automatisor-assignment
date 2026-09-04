import pytest

from src.agent.providers import generate_with_fallback, generate_validated_response
from src.agent.schemas import AgentResponse


@pytest.mark.asyncio
async def test_primary_provider_retries_before_succeeding() -> None:
    calls = 0

    async def primary() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise RuntimeError("rate limited")
        return "primary result"

    async def fallback() -> str:
        raise AssertionError("fallback should not be called")

    assert await generate_with_fallback(primary, fallback) == "primary result"
    assert calls == 2


@pytest.mark.asyncio
async def test_fallback_provider_runs_after_primary_exhausts_retries() -> None:
    async def primary() -> str:
        raise RuntimeError("provider unavailable")

    async def fallback() -> str:
        return "fallback result"

    assert await generate_with_fallback(primary, fallback) == "fallback result"


@pytest.mark.asyncio
async def test_structured_output_gets_one_validation_correction_retry() -> None:
    prompts: list[str] = []
    responses = ["{}", '{"answer":"ok","companies_referenced":[],"confidence":"low",'
                 '"persona":"equity_analyst","sector":"tech"}']

    async def generate(prompt: str) -> str:
        prompts.append(prompt)
        return responses.pop(0)

    result = await generate_validated_response(generate, "Answer with JSON.", AgentResponse)

    assert result.answer == "ok"
    assert len(prompts) == 2
    assert "validation" in prompts[1].lower()
