"""Resilient provider invocation for the Gemini-primary/Mistral-fallback path."""

from __future__ import annotations

import asyncio
import json
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

_OUTPUT_CONTROL = """\
You are the answer-generation stage of a grounded ReAct workflow.
Reason privately in this order: inspect the user's request, inspect only the supplied
database/tool evidence, check whether the evidence supports the claims, then compose
the answer through the requested persona and sector lens. Do not invent facts, sources,
companies, metrics, or tool results. If the evidence is insufficient, say so and set
no_data_flag appropriately.

Output protocol (highest priority): return exactly one JSON object and nothing else.
Do not emit Markdown fences, headings, commentary, a thought trace, or a preamble.
Use the requested response schema exactly; include every required field, use an array
for companies_referenced, and use only the allowed confidence value. Keep the answer
concise but explain the evidence-based reasoning and relevant caveats.
"""


def _controlled_prompt(prompt: str) -> str:
    return f"{_OUTPUT_CONTROL}\n\nGrounding context and task:\n{prompt}"


def _json_candidate(raw: str) -> str:
    """Accept strict JSON plus common provider wrappers, while rejecting ambiguity."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        start = text.find("{")
        if start < 0:
            raise
        _, end = decoder.raw_decode(text[start:])
        candidate = text[start : start + end]
        json.loads(candidate)
        return candidate


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
    controlled_prompt = _controlled_prompt(prompt)
    raw = await generate(controlled_prompt)
    try:
        return response_model.model_validate_json(_json_candidate(raw))
    except (ValidationError, json.JSONDecodeError) as first_error:
        correction_prompt = (
            f"{controlled_prompt}\n\n"
            "REPAIR REQUIRED. Your previous response was not an acceptable instance "
            "of the requested JSON schema. Return only one valid JSON object; do not "
            f"use Markdown or prose. Schema: {response_model.model_json_schema()}\n"
            f"Validation error: {first_error}"
        )
        corrected = await generate(correction_prompt)
        return response_model.model_validate_json(_json_candidate(corrected))


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
        contents=_controlled_prompt(prompt),
        config={
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "OBJECT",
                "properties": {
                    "answer": {"type": "STRING"},
                    "companies_referenced": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                    "persona": {"type": "STRING"},
                    "sector": {"type": "STRING"},
                    "no_data_flag": {"type": "BOOLEAN"},
                },
                "required": [
                    "answer",
                    "companies_referenced",
                    "confidence",
                    "persona",
                    "sector",
                ],
            },
        },
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return response.text


def _generate_mistral(api_key: str, prompt: str) -> str:
    from mistralai import Mistral

    client = Mistral(api_key=api_key)
    response = client.chat.complete(
        model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        messages=[{"role": "user", "content": _controlled_prompt(prompt)}],  # type: ignore[arg-type]
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content:
        raise RuntimeError("Mistral returned an empty response")
    return content
