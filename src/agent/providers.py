"""Resilient provider invocation for the Gemini-primary/Mistral-fallback path."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

load_dotenv()

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


async def generate_from_environment(prompt: str) -> str:
    """Generate JSON through Gemini first and Mistral second using environment keys."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not gemini_key and not mistral_key:
        raise RuntimeError("No LLM provider API keys are configured")

    async def gemini_call() -> str:
        if not gemini_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        return await asyncio.to_thread(_generate_gemini, gemini_key, prompt)

    async def mistral_call() -> str:
        if not mistral_key:
            raise RuntimeError("MISTRAL_API_KEY is not configured")
        return await asyncio.to_thread(_generate_mistral, mistral_key, prompt)

    return await generate_with_fallback(gemini_call, mistral_call)


def _generate_gemini(api_key: str, prompt: str) -> str:
    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
        contents=prompt,
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return response.text


def _generate_mistral(api_key: str, prompt: str) -> str:
    from mistralai import Mistral

    client = Mistral(api_key=api_key)
    response = client.chat.complete(
        model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        messages=[{"role": "user", "content": prompt}],  # type: ignore[arg-type]
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content:
        raise RuntimeError("Mistral returned an empty response")
    return content
