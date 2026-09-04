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
    """List every company in one supported sector.

    Use this for sector-level analysis before making peer-comparison claims. The
    result contains only dataset identity fields; call ``get_company_detail`` for
    financial metrics and ``get_recent_signals`` for dated qualitative evidence.
    """
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
    """Resolve one exact-ish company identifier to identity plus financial data.

    The lookup is case-insensitive and returns the first database match, or
    ``None`` when the dataset has no match. Financial values are a point-in-time
    snapshot, not live market data; preserve that limitation in any answer.
    """
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
    """Return dated hiring, expansion, and other curated signals for a company.

    Results are ordered newest first and include source URLs when available. An
    empty list means the company is in scope but no signal was curated; it is not
    evidence that no real-world activity occurred.
    """
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
    """Find likely in-dataset companies by ticker or name.

    Use this only to resolve an identifier, then verify the selected company with
    ``get_company_detail`` before stating company-specific facts. Match confidence
    is a dataset-resolution score, not investment confidence.
    """
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


async def screen_companies(
    sector: str,
    metric: str = "market_cap",
    limit: int = 10,
    descending: bool = True,
) -> list[dict[str, Any]] | dict[str, str]:
    """Rank in-scope companies by one available financial screening metric.

    ``sector`` must be ``tech``, ``retail``, or ``manufacturing``. ``metric`` may
    be ``market_cap``, ``ebitda``, ``eps``, ``pe_ratio``, ``price_to_sales``,
    ``price_to_book``, or ``dividend_yield``. Null metric values are placed last;
    the returned ``rank`` is only relative to this dataset snapshot and is not an
    investment recommendation. Use this for a compact peer screen, then retrieve
    company details or signals before writing a company-specific conclusion.
    """
    if sector not in VALID_SECTORS:
        return {"error": f"Invalid sector: {sector}"}

    metric_columns = {
        "market_cap": "f.market_cap",
        "ebitda": "f.ebitda",
        "eps": "f.eps",
        "pe_ratio": "f.pe_ratio",
        "price_to_sales": "f.price_to_sales",
        "price_to_book": "f.price_to_book",
        "dividend_yield": "f.dividend_yield",
    }
    column = metric_columns.get(metric)
    if column is None:
        allowed = ", ".join(metric_columns)
        return {"error": f"Invalid screening metric: {metric}; choose one of: {allowed}"}
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        return {"error": "Screening limit must be an integer from 1 to 50"}

    direction = "DESC" if descending else "ASC"
    try:
        return await fetch_all(
            f"""
            SELECT ROW_NUMBER() OVER (
                       ORDER BY {column} {direction} NULLS LAST, c.name ASC
                   )::INTEGER AS rank,
                   c.symbol, c.name, c.sector, c.sub_industry,
                   f.market_cap, f.ebitda, f.eps, f.pe_ratio,
                   f.price_to_sales, f.price_to_book, f.dividend_yield,
                   f.source_url, f.as_of_note
            FROM companies AS c
            LEFT JOIN financials AS f ON f.symbol = c.symbol
            WHERE c.sector = $1
            ORDER BY {column} {direction} NULLS LAST, c.name ASC
            LIMIT $2
            """,
            (sector, limit),
        )
    except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
        logger.exception(
            "screen_companies failed",
            extra={"sector": sector, "metric": metric, "limit": limit},
        )
        return {"error": str(exc)}


# Register the callable without replacing it with FastMCP's metadata wrapper;
# this keeps the same function directly testable and reusable by the agent.
mcp.tool(get_companies_by_sector)
mcp.tool(get_company_detail)
mcp.tool(get_recent_signals)
mcp.tool(search_company)
mcp.tool(screen_companies)


if __name__ == "__main__":
    mcp.run(transport="stdio")
