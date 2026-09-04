"""Domain-specific MCP tools backed by Supabase Postgres."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

import asyncpg
from fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("financial-data")

VALID_SECTORS = frozenset({"tech", "retail", "manufacturing"})
_pool: asyncpg.Pool[asyncpg.Record] | None = None


async def _get_pool() -> asyncpg.Pool[asyncpg.Record]:
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    return _pool


async def fetch_all(query: str, args: Sequence[object] = ()) -> list[dict[str, Any]]:
    """Run a parameterized query and convert database records to plain dicts."""
    pool = await _get_pool()
    async with pool.acquire() as connection:
        records = await connection.fetch(query, *args)
    return [dict(record) for record in records]


async def get_companies_by_sector(
    sector: str,
) -> list[dict[str, str]] | dict[str, str]:
    """Return company identity summaries for one supported sector."""
    if sector not in VALID_SECTORS:
        return {"error": f"Invalid sector: {sector}"}

    try:
        return await fetch_all(
            """
            SELECT symbol, name, sub_industry
            FROM companies
            WHERE sector = $1
            ORDER BY name
            """,
            (sector,),
        )
    except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
        logger.exception("get_companies_by_sector failed", extra={"sector": sector})
        return {"error": str(exc)}


# Register the callable without replacing it with FastMCP's metadata wrapper;
# this keeps the same function directly testable and reusable by the agent.
mcp.tool(get_companies_by_sector)


if __name__ == "__main__":
    mcp.run(transport="stdio")
