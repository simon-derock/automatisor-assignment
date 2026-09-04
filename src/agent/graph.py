"""MCP-backed agent entrypoint and grounding helpers."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Literal

from fastmcp import Client

from src.agent.personas import build_system_prompt
from src.agent.providers import generate_from_environment, generate_validated_response
from src.agent.schemas import AgentResponse
from src.mcp_server.server import mcp

logger = logging.getLogger(__name__)
Confidence = Literal["high", "medium", "low"]


def delimited_tool_context(result: Mapping[str, Any] | list[Any]) -> str:
    """Wrap untrusted tool data as data, never as additional instructions."""
    serialized = json.dumps(result, default=str, sort_keys=True)
    return f"<tool_result>{serialized}</tool_result>"


def confidence_from_context(*, has_financials: bool, has_signals: bool) -> Confidence:
    """Apply the confidence rule from SPEC.md without delegating it to the LLM."""
    if has_financials and has_signals:
        return "high"
    if has_financials:
        return "medium"
    return "low"


def _tool_data(result: Any) -> Any:
    data = getattr(result, "data", None)
    if data is not None:
        return data
    content = getattr(result, "content", [])
    if content and getattr(content[0], "text", None):
        return json.loads(content[0].text)
    return None


async def run_agent(query: str, persona: str, sector: str) -> AgentResponse:
    """Run a grounded query through the co-located MCP server.

    Every company named here is first retrieved through MCP. If provider keys
    are configured, the provider receives only this retrieved context.
    """
    if not query.strip():
        raise ValueError("Query cannot be empty")
    build_system_prompt(persona, sector)

    async with Client(mcp) as client:
        sector_result = _tool_data(
            await client.call_tool("get_companies_by_sector", {"sector": sector})
        )
        if isinstance(sector_result, dict) and "error" in sector_result:
            return AgentResponse(
                answer="I’m having trouble reaching the financial data source right now.",
                companies_referenced=[],
                confidence="low",
                persona=persona,
                sector=sector,
            )
        companies = sector_result if isinstance(sector_result, list) else []
        selected = companies[:3]
        details: list[dict[str, Any]] = []
        signals_by_symbol: dict[str, list[Any]] = {}
        for company in selected:
            detail = _tool_data(
                await client.call_tool(
                    "get_company_detail", {"symbol_or_name": company["symbol"]}
                )
            )
            if isinstance(detail, dict) and "error" not in detail:
                details.append(detail)
                signals = _tool_data(
                    await client.call_tool(
                        "get_recent_signals", {"symbol_or_name": company["symbol"]}
                    )
                )
                signals_by_symbol[str(detail["symbol"])] = (
                    signals if isinstance(signals, list) else []
                )

        if not details:
            return AgentResponse(
                answer=f"I found no usable company data for the {sector} sector in this dataset.",
                companies_referenced=[],
                confidence="low",
                persona=persona,
                sector=sector,
                no_data_flag=True,
            )

    names = ", ".join(str(detail["name"]) for detail in details)
    context = "\n".join(
        delimited_tool_context(
            {"detail": detail, "signals": signals_by_symbol.get(str(detail["symbol"]), [])}
        )
        for detail in details
    )
    prompt = (
        f"{build_system_prompt(persona, sector)}\nUser query: {query}\n"
        f"Retrieved company context:\n{context}\n"
        "Return only JSON matching AgentResponse. Use only retrieved facts."
    )
    try:
        response = await generate_validated_response(
            generate_from_environment, prompt, AgentResponse
        )
        retrieved_symbols = {str(detail["symbol"]) for detail in details}
        response.companies_referenced = [
            symbol for symbol in response.companies_referenced if symbol in retrieved_symbols
        ]
        response.persona = persona
        response.sector = sector
        response.confidence = confidence_from_context(
            has_financials=True,
            has_signals=all(signals_by_symbol.get(str(detail["symbol"])) for detail in details),
        )
        return response
    except Exception:
        logger.exception("Provider generation failed; returning grounded deterministic response")
    logger.info("Generated grounded sector response", extra={"persona": persona, "sector": sector})
    return AgentResponse(
        answer=(
            f"Using the {persona} lens and the retrieved {sector} data, the initial "
            f"companies to review are {names}. This is a grounded screening list; "
            "the retrieved records should be compared using the persona priorities "
            "before drawing an investment conclusion."
        ),
        companies_referenced=[str(detail["symbol"]) for detail in details],
        confidence=confidence_from_context(
            has_financials=True,
            has_signals=all(signals_by_symbol.get(str(detail["symbol"])) for detail in details),
        ),
        persona=persona,
        sector=sector,
    )
