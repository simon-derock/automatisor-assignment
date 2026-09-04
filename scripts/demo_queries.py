"""Run the required persona/sector and grounding smoke queries."""

from __future__ import annotations

import asyncio
import json
import os

from src.agent.graph import run_agent
from src.agent.personas import PERSONAS, SECTORS

QUERIES = {
    "sector_screen": "Which companies should I review first in this sector?",
    "hiring_signal": "Which companies have recent hiring or headcount signals?",
    "out_of_scope": "What does Contoso's recent hiring activity look like?",
}


async def run_demo() -> None:
    if not os.getenv("DATABASE_URL"):
        print("DATABASE_URL is not configured; demo requires the seeded Postgres database.")
        return

    results: list[dict[str, object]] = []
    for persona in PERSONAS:
        for sector in SECTORS:
            response = await run_agent(QUERIES["sector_screen"], persona, sector)
            results.append({"case": "sector_screen", **response.model_dump()})

    for case in ("hiring_signal", "out_of_scope"):
        response = await run_agent(QUERIES[case], "equity_analyst", "tech")
        results.append({"case": case, **response.model_dump()})

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(run_demo())
