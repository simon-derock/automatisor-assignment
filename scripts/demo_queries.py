"""Run the assignment's persona/sector matrix and named grading scenarios."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.agent.schemas import AgentResponse


@dataclass(frozen=True)
class DemoCase:
    """One grading scenario to execute against the shared agent entry point."""

    name: str
    query: str
    persona: str
    sector: str


# Keep the cross-persona query byte-for-byte identical: output differences
# should come from the persona lens, not from changing the user's question.
CROSS_PERSONA_QUERY = (
    "Which companies in this sector look most attractive based on the data you have?"
)

MATRIX_CASES: tuple[DemoCase, ...] = (
    DemoCase(
        "mf_retail_core_holding",
        "Which retail companies look suitable as core long-only holdings based on valuation, "
        "dividend yield, and portfolio fit?",
        "mf_analyst",
        "retail",
    ),
    DemoCase(
        "mf_tech_screen", "Screen this sector for long-term opportunities.", "mf_analyst", "tech"
    ),
    DemoCase(
        "mf_manufacturing_screen",
        "Screen this sector for long-term opportunities.",
        "mf_analyst",
        "manufacturing",
    ),
    DemoCase(
        "equity_retail_earnings_review",
        "Which retail companies have the strongest earnings setup?",
        "equity_analyst",
        "retail",
    ),
    DemoCase(
        "equity_manufacturing_margin_walk",
        "Walk me through the earnings and margin trajectory of the leading manufacturing "
        "companies using EPS and EBITDA data.",
        "equity_analyst",
        "manufacturing",
    ),
    DemoCase(
        "hiring_headcount",
        "Which companies have recent hiring or headcount signals, and what do those signals say?",
        "equity_analyst",
        "tech",
    ),
    DemoCase(
        "pe_retail_value_creation",
        "Which retail companies offer the clearest value-creation opportunities?",
        "pe_analyst",
        "retail",
    ),
    DemoCase(
        "pe_manufacturing_value_creation",
        "Which manufacturing companies offer the clearest value-creation opportunities?",
        "pe_analyst",
        "manufacturing",
    ),
    DemoCase(
        "pe_tech_take_private",
        "Which technology companies could support a take-private thesis based on EBITDA, deal "
        "size, leverage capacity, operating levers, and exit potential?",
        "pe_analyst",
        "tech",
    ),
)

CROSS_PERSONA_CASES: tuple[DemoCase, ...] = tuple(
    DemoCase(
        f"cross_persona_same_question_{persona.removesuffix('_analyst')}",
        CROSS_PERSONA_QUERY,
        persona,
        "retail",
    )
    for persona in ("mf_analyst", "equity_analyst", "pe_analyst")
)

DEMO_CASES: tuple[DemoCase, ...] = (
    *MATRIX_CASES,
    *CROSS_PERSONA_CASES,
    DemoCase(
        "out_of_scope",
        "What does Contoso's recent hiring activity look like?",
        "equity_analyst",
        "tech",
    ),
)

AgentRunner = Callable[[str, str, str], Awaitable[AgentResponse]]


async def collect_demo_results(agent_runner: AgentRunner) -> list[dict[str, object]]:
    """Execute every named scenario and return JSON-ready structured results."""
    results: list[dict[str, object]] = []
    for case in DEMO_CASES:
        response = await agent_runner(case.query, case.persona, case.sector)
        results.append(
            {
                "case": case.name,
                "query": case.query,
                "persona": case.persona,
                "sector": case.sector,
                **response.model_dump(),
            }
        )
    return results


async def run_demo(agent_runner: AgentRunner | None = None) -> None:
    """Print demo results, or exit safely when the database is not configured."""
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL is not configured; demo requires the seeded Postgres database.")
        return

    if agent_runner is None:
        # Import after the environment guard so an unconfigured checkout does
        # not initialize the MCP/DB stack merely to show the message.
        from src.agent.graph import run_agent

        agent_runner = run_agent

    print(json.dumps(await collect_demo_results(agent_runner), indent=2))


if __name__ == "__main__":
    asyncio.run(run_demo())
