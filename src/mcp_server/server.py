"""Domain-specific MCP tools backed by Supabase Postgres."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

import asyncpg
from dotenv import load_dotenv
from fastmcp import FastMCP
from rapidfuzz import fuzz, process

load_dotenv()

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


async def get_company_detail(
    symbol_or_name: str,
) -> dict[str, Any] | None:
    """Return a company and its financial snapshot, or None when not found."""
    if not symbol_or_name.strip():
        return {"error": "Company identifier cannot be empty"}
    try:
        rows = await fetch_all(
            """
            SELECT c.symbol, c.name, c.sector, c.sub_industry, c.headquarters, c.founded,
                   f.price, f.pe_ratio, f.dividend_yield, f.eps, f.week52_low,
                   f.week52_high, f.market_cap, f.ebitda, f.price_to_sales,
                   f.price_to_book, f.source_url, f.as_of_note
            FROM companies AS c
            LEFT JOIN financials AS f ON f.symbol = c.symbol
            WHERE c.symbol ILIKE $1 OR c.name ILIKE $1
            ORDER BY c.symbol
            LIMIT 1
            """,
            (symbol_or_name.strip(),),
        )
        return rows[0] if rows else None
    except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
        logger.exception("get_company_detail failed")
        return {"error": str(exc)}


async def get_recent_signals(
    symbol_or_name: str,
) -> list[dict[str, Any]] | dict[str, str]:
    """Return curated signals for a company, ordered newest first."""
    if not symbol_or_name.strip():
        return {"error": "Company identifier cannot be empty"}
    try:
        return await fetch_all(
            """
            SELECT s.id, s.symbol, s.signal_type, s.signal_text, s.source_url, s.signal_date
            FROM signals AS s
            JOIN companies AS c ON c.symbol = s.symbol
            WHERE c.symbol ILIKE $1 OR c.name ILIKE $1
            ORDER BY s.signal_date DESC NULLS LAST, s.id DESC
            """,
            (symbol_or_name.strip(),),
        )
    except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
        logger.exception("get_recent_signals failed")
        return {"error": str(exc)}


async def search_company(
    query: str,
) -> list[dict[str, Any]] | dict[str, str]:
    """Fuzzy-match a company name or ticker against the dataset."""
    if not query.strip():
        return {"error": "Search query cannot be empty"}
    try:
        companies = await fetch_all("SELECT symbol, name FROM companies ORDER BY name", ())
        choices = {str(company["symbol"]): str(company["name"]) for company in companies}
        matches = process.extract(
            query.strip(), choices, scorer=fuzz.WRatio, limit=5, score_cutoff=45
        )
        result: list[dict[str, Any]] = []
        for name, score, symbol in matches:
            normalized_query = query.strip().casefold()
            normalized_name = str(name).casefold()
            confidence = 100.0 if normalized_query in normalized_name else float(score)
            result.append(
                {"symbol": str(symbol), "name": str(name), "match_confidence": confidence}
            )
        return result
    except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
        logger.exception("search_company failed")
        return {"error": str(exc)}


# Register the callable without replacing it with FastMCP's metadata wrapper;
# this keeps the same function directly testable and reusable by the agent.
mcp.tool(get_companies_by_sector)
mcp.tool(get_company_detail)
mcp.tool(get_recent_signals)
mcp.tool(search_company)


if __name__ == "__main__":
    mcp.run(transport="stdio")
