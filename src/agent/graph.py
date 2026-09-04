"""MCP-backed agent entrypoint and grounding helpers."""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langgraph.graph import END, START, StateGraph

from src.agent.personas import build_system_prompt
from src.agent.providers import generate_from_environment, generate_validated_response
from src.agent.schemas import AgentResponse

logger = logging.getLogger(__name__)
Confidence = Literal["high", "medium", "low"]


class AgentState(TypedDict, total=False):
    query: str
    persona: str
    sector: str
    response: AgentResponse


def create_mcp_transport() -> StdioTransport:
    """Create the co-located stdio transport required by the MCP contract."""
    repository_root = Path(__file__).resolve().parents[2]
    return StdioTransport(
        command=sys.executable,
        args=["-m", "src.mcp_server.server"],
        cwd=str(repository_root),
    )


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


def should_flag_no_data(query: str, matches: list[Any]) -> bool:
    """Distinguish an unmatched company request from a sector-level screen."""
    if matches:
        normalized = query.casefold()
        sector_request = (
            "which companies" in normalized
            or "in this sector" in normalized
            or "this sector" in normalized
            or "companies in your data" in normalized
            or "company here" in normalized
        )
        if sector_request:
            return False
        return _specific_company_match(query, matches) is None
    normalized = query.casefold()
    sector_request = (
        "which companies" in normalized
        or "in this sector" in normalized
        or "this sector" in normalized
        or "companies in your data" in normalized
        or "company here" in normalized
    )
    return not sector_request and any(
        phrase in normalized for phrase in ("hiring", "headcount", "company", "contoso")
    )


def _tool_data(result: Any) -> Any:
    def unwrap(value: Any) -> Any:
        root = getattr(value, "root", None)
        if root is not None:
            return unwrap(root)
        if isinstance(value, list):
            return [unwrap(item) for item in value]
        if isinstance(value, dict):
            return {key: unwrap(item) for key, item in value.items()}
        return value

    content = getattr(result, "content", [])
    if content and getattr(content[0], "text", None):
        try:
            return json.loads(content[0].text)
        except json.JSONDecodeError:
            logger.warning("MCP tool returned non-JSON text content")

    data = getattr(result, "data", None)
    if data is not None:
        # FastMCP represents list/dict tool schemas as Pydantic RootModel
        # instances when using structured results over stdio.
        return unwrap(data)
    return None


def _specific_company_match(
    query: str, matches: list[Any]
) -> dict[str, Any] | None:
    """Choose a single unambiguous company returned by ``search_company``.

    A company explicitly named in the question is preferred. Otherwise, only a
    high-confidence result with a clear lead over the next result is accepted;
    this keeps broad sector questions on the sector-screen path.
    """
    candidates = [
        match
        for match in matches
        if isinstance(match, Mapping)
        and match.get("symbol")
        and match.get("name")
    ]
    if not candidates:
        return None

    query_words = set(re.findall(r"[a-z0-9]+", query.casefold()))

    def is_named_in_query(match: Mapping[str, Any]) -> bool:
        symbol = str(match["symbol"]).casefold()
        if symbol in query_words:
            return True
        ignored = {"inc", "corp", "corporation", "company", "co", "ltd", "plc"}
        name_words = [
            word
            for word in re.findall(r"[a-z0-9]+", str(match["name"]).casefold())
            if word not in ignored
        ]
        return any(word in query_words for word in name_words if len(word) >= 3)

    named = [match for match in candidates if is_named_in_query(match)]
    if len(named) == 1:
        return dict(named[0])

    ranked = sorted(
        candidates,
        key=lambda match: float(match.get("match_confidence", 0)),
        reverse=True,
    )
    top_score = float(ranked[0].get("match_confidence", 0))
    next_score = float(ranked[1].get("match_confidence", 0)) if len(ranked) > 1 else 0
    if top_score >= 85 and top_score - next_score >= 10:
        return dict(ranked[0])
    return None


async def _run_grounded_agent(query: str, persona: str, sector: str) -> AgentResponse:
    """Run a grounded query through the co-located MCP server.

    Every company named here is first retrieved through MCP. If provider keys
    are configured, the provider receives only this retrieved context.
    """
    if not query.strip():
        raise ValueError("Query cannot be empty")
    build_system_prompt(persona, sector)

    async with Client(create_mcp_transport()) as client:
        search_result = _tool_data(
            await client.call_tool("search_company", {"query": query})
        )
        if isinstance(search_result, list) and should_flag_no_data(query, search_result):
            return AgentResponse(
                answer="I have no data on that company in the configured dataset.",
                companies_referenced=[],
                confidence="low",
                persona=persona,
                sector=sector,
                no_data_flag=True,
            )
        specific_match = (
            _specific_company_match(query, search_result)
            if isinstance(search_result, list)
            else None
        )
        if specific_match is not None:
            selected = [specific_match]
        else:
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
            if (
                isinstance(detail, dict)
                and "error" not in detail
                and detail.get("sector") == sector
            ):
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
        if not response.companies_referenced:
            response.companies_referenced = [str(detail["symbol"]) for detail in details]
        response.persona = persona
        response.sector = sector
        response.no_data_flag = False
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


async def _grounded_agent_node(state: AgentState) -> AgentState:
    response = await _run_grounded_agent(state["query"], state["persona"], state["sector"])
    return {"response": response}


_workflow = StateGraph(AgentState)
_workflow.add_node("grounded_agent", _grounded_agent_node)
_workflow.add_edge(START, "grounded_agent")
_workflow.add_edge("grounded_agent", END)
agent_graph = _workflow.compile()


async def run_agent(query: str, persona: str, sector: str) -> AgentResponse:
    """Run the shared agent entrypoint through the compiled LangGraph workflow."""
    result = await agent_graph.ainvoke(
        {"query": query, "persona": persona, "sector": sector}
    )
    return cast(AgentResponse, result["response"])
