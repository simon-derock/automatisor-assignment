import json
from datetime import date

import pandas as pd

from data.build_db import join_and_filter, parse_founded, parse_number, parse_signal_date


def test_join_and_filter_keeps_only_the_three_specified_sector_rules() -> None:
    constituents = pd.DataFrame(
        [
            {
                "Symbol": "TECH",
                "Name": "Tech Co",
                "GICS Sector": "Information Technology",
                "GICS Sub-Industry": "Software",
            },
            {
                "Symbol": "SHOP",
                "Name": "Shop Co",
                "GICS Sector": "Consumer Discretionary",
                "GICS Sub-Industry": "Broadline Retail",
            },
            {
                "Symbol": "MACH",
                "Name": "Machine Co",
                "GICS Sector": "Industrials",
                "GICS Sub-Industry": "Construction Machinery",
            },
            {
                "Symbol": "BANK",
                "Name": "Bank Co",
                "GICS Sector": "Financials",
                "GICS Sub-Industry": "Diversified Banks",
            },
        ]
    )
    financials = pd.DataFrame([{"Symbol": symbol} for symbol in ("TECH", "SHOP", "MACH", "BANK")])

    result = join_and_filter(constituents, financials)

    assert dict(zip(result["Symbol"], result["sector"], strict=True)) == {
        "TECH": "tech",
        "SHOP": "retail",
        "MACH": "manufacturing",
    }


def test_parsers_handle_snapshot_values_and_missing_values() -> None:
    assert parse_number("$1,234.50") == 1234.5
    assert parse_number("-") is None
    assert parse_founded("2013 (1888)") == 2013
    assert parse_founded(float("nan")) is None
    assert parse_signal_date("2024-06-10") == date(2024, 6, 10)
    assert parse_signal_date(None) is None


def test_prepared_snapshot_and_curated_signals_match_contract() -> None:
    prepared = pd.read_csv("data/prepared/companies.csv")
    signals = json.loads(open("data/signals_curated.json", encoding="utf-8").read())

    assert set(prepared["sector"]) == {"tech", "retail", "manufacturing"}
    assert len(prepared) == 110
    assert len(signals) == 22
    assert {signal["symbol"] for signal in signals} <= set(prepared["Symbol"])
