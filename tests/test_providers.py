import pytest

from src.agent.providers import (
    _OUTPUT_CONTROL,
    _json_candidate,
    generate_validated_response,
    generate_with_fallback,
)
from src.agent.schemas import AgentResponse


def test_agent_response_schema_requires_all_structured_fields() -> None:
    schema = AgentResponse.model_json_schema()

    assert set(schema["required"]) >= {
        "answer",
        "companies_referenced",
        "confidence",
        "persona",
        "sector",
    }


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
    assert "ReAct" in prompts[0]
    assert "JSON object" in prompts[0]


def test_json_candidate_handles_fence_and_leading_provider_prose() -> None:
    payload = '{"answer":"ok"}'

    assert _json_candidate(f"Here is the result:\n{payload}\nDone") == payload
    assert _json_candidate(f"```json\n{payload}\n```") == payload


def test_output_control_requires_private_grounded_reasoning_and_json_only() -> None:
    assert "database/tool evidence" in _OUTPUT_CONTROL
    assert "Do not emit" in _OUTPUT_CONTROL
    assert "Do not invent facts" in _OUTPUT_CONTROL
