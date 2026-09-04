"""Resilient provider invocation for the Gemini-primary/Mistral-fallback path."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
ProviderCall = Callable[[], Awaitable[str]]
ModelT = TypeVar("ModelT", bound=BaseModel)


async def _retry_provider(provider: ProviderCall) -> str:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.01, max=0.1),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    ):
        with attempt:
            return await provider()
    raise RuntimeError("Provider retry loop exited unexpectedly")


async def generate_with_fallback(primary: ProviderCall, fallback: ProviderCall) -> str:
    """Retry Gemini-style primary calls, then retry the Mistral-style fallback."""
    try:
        return await _retry_provider(primary)
    except Exception:
        logger.exception("Primary LLM provider failed; trying fallback provider")
        return await _retry_provider(fallback)


async def generate_validated_response(
    generate: Callable[[str], Awaitable[str]],
    prompt: str,
    response_model: type[ModelT],
) -> ModelT:
    """Parse provider JSON and retry once with Pydantic feedback on failure."""
    raw = await generate(prompt)
    try:
        return response_model.model_validate_json(raw)
    except ValidationError as first_error:
        correction_prompt = (
            f"{prompt}\n\nYour previous response failed validation. "
            f"Return only valid JSON matching the schema. Validation error:\n{first_error}"
        )
        corrected = await generate(correction_prompt)
        return response_model.model_validate_json(corrected)
