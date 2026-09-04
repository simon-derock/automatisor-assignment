"""Download the public S&P 500 snapshots and seed the configured Postgres DB."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg
import pandas as pd

CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
)
FINANCIALS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents-financials.csv"
)
MANUFACTURING_KEYWORDS = (
    "Machinery",
    "Industrial Conglomerates",
    "Auto Parts",
    "Electrical Equipment",
)


def parse_number(value: object) -> float | None:
    """Convert a public CSV number, including blank and dash values."""
    if pd.isna(value) or str(value).strip().lower() in {"-", "n/a", "nan", "none"}:
        return None
    return float(str(value).replace(",", "").replace("$", "").strip())


def parse_founded(value: object) -> int | None:
    match = re.search(r"\b(\d{4})\b", str(value))
    return int(match.group(1)) if match else None


def join_and_filter(constituents: pd.DataFrame, financials: pd.DataFrame) -> pd.DataFrame:
    """Join the two public snapshots and add the assignment's three sector labels."""
    joined = constituents.merge(financials, on="Symbol", how="inner", suffixes=("", "_financial"))
    sub_industry = joined["GICS Sub-Industry"].fillna("")
    manufacturing = sub_industry.str.contains("|".join(MANUFACTURING_KEYWORDS), regex=True)
    joined["sector"] = pd.NA
    joined.loc[joined["GICS Sector"] == "Information Technology", "sector"] = "tech"
    joined.loc[sub_industry.str.contains("Retail"), "sector"] = "retail"
    joined.loc[manufacturing, "sector"] = "manufacturing"
    return joined.loc[joined["sector"].notna()].copy()


async def seed_database(
    database_url: str,
    constituents: str | Path = CONSTITUENTS_URL,
    financials: str | Path = FINANCIALS_URL,
    signals_path: str | Path = "data/signals_curated.json",
) -> None:
    constituents_frame = pd.read_csv(constituents)
    financials_frame = pd.read_csv(financials)
    joined = join_and_filter(constituents_frame, financials_frame)
    signals = json.loads(Path(signals_path).read_text(encoding="utf-8"))
    schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"

    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(schema.read_text(encoding="utf-8"))
            for row in joined.to_dict(orient="records"):
                await connection.execute(
                    """
                    INSERT INTO companies(symbol, name, sector, sub_industry, headquarters, founded)
                    VALUES($1, $2, $3, $4, $5, $6)
                    ON CONFLICT(symbol) DO UPDATE SET name=EXCLUDED.name,
                      sector=EXCLUDED.sector, sub_industry=EXCLUDED.sub_industry,
                      headquarters=EXCLUDED.headquarters, founded=EXCLUDED.founded
                    """,
                    row["Symbol"], row["Name"], row["sector"], row["GICS Sub-Industry"],
                    row["Headquarters Location"], parse_founded(row["Founded"]),
                )
                await connection.execute(
                    """
                    INSERT INTO financials(symbol, price, pe_ratio, dividend_yield, eps,
                      week52_low, week52_high, market_cap, ebitda, price_to_sales,
                      price_to_book, source_url, as_of_note)
                    VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT(symbol) DO UPDATE SET price=EXCLUDED.price,
                      pe_ratio=EXCLUDED.pe_ratio, dividend_yield=EXCLUDED.dividend_yield,
                      eps=EXCLUDED.eps, week52_low=EXCLUDED.week52_low,
                      week52_high=EXCLUDED.week52_high, market_cap=EXCLUDED.market_cap,
                      ebitda=EXCLUDED.ebitda, price_to_sales=EXCLUDED.price_to_sales,
                      price_to_book=EXCLUDED.price_to_book, source_url=EXCLUDED.source_url,
                      as_of_note=EXCLUDED.as_of_note
                    """,
                    row["Symbol"], parse_number(row.get("Price")),
                    parse_number(row.get("Price/Earnings")),
                    parse_number(row.get("Dividend Yield")),
                    parse_number(row.get("Earnings/Share")),
                    parse_number(row.get("52 Week Low")), parse_number(row.get("52 Week High")),
                    parse_number(row.get("Market Cap")), parse_number(row.get("EBITDA")),
                    parse_number(row.get("Price/Sales")), parse_number(row.get("Price/Book")),
                    row.get("SEC Filings"),
                    "Public S&P 500 snapshot; source dates are not guaranteed current.",
                )
            await connection.execute("DELETE FROM signals")
            for signal in signals:
                await connection.execute(
                    """
                    INSERT INTO signals(symbol, signal_type, signal_text, source_url, signal_date)
                    VALUES($1, $2, $3, $4, $5)
                    """,
                    signal["symbol"], signal["signal_type"], signal["signal_text"],
                    signal.get("source_url"), signal.get("signal_date"),
                )
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--signals", default="data/signals_curated.json")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    asyncio.run(seed_database(args.database_url, signals_path=args.signals))


if __name__ == "__main__":
    main()
