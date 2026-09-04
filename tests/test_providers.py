import pytest

from src.agent.providers import generate_with_fallback


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
