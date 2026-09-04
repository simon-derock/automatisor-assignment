"""Contract tests for the domain-specific MCP tools."""

import pytest

from src.mcp_server.server import (
    get_companies_by_sector,
    get_company_detail,
    get_recent_signals,
    screen_companies,
    search_company,
)


@pytest.mark.asyncio
async def test_get_companies_by_sector_returns_company_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        return [{"symbol": "ACME", "name": "Acme Corp", "sub_industry": "Software"}]

    monkeypatch.setattr("src.mcp_server.server.fetch_all", fake_fetch_all)

    result = await get_companies_by_sector("tech")

    assert result == [{"symbol": "ACME", "name": "Acme Corp", "sub_industry": "Software"}]


@pytest.mark.asyncio
async def test_get_companies_by_sector_rejects_unknown_sector() -> None:
    result = await get_companies_by_sector("utilities")

    assert result == {"error": "Invalid sector: utilities"}


@pytest.mark.asyncio
async def test_get_companies_by_sector_returns_error_object_on_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failed_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        raise OSError("database unavailable")

    monkeypatch.setattr("src.mcp_server.server.fetch_all", failed_fetch_all)

    assert await get_companies_by_sector("tech") == {"error": "database unavailable"}


@pytest.mark.asyncio
async def test_get_company_detail_returns_none_when_company_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr("src.mcp_server.server.fetch_all", fake_fetch_all)

    assert await get_company_detail("NOT-IN-DATASET") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [get_company_detail, get_recent_signals])
async def test_identifier_tools_reject_blank_input_without_querying_database(
    tool: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        pytest.fail("blank identifiers must be rejected before database access")

    monkeypatch.setattr("src.mcp_server.server.fetch_all", unexpected_fetch_all)

    result = await tool("  \t")  # type: ignore[operator]

    assert result == {"error": "Company identifier cannot be empty"}


@pytest.mark.asyncio
async def test_get_recent_signals_returns_empty_list_without_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        return []

    monkeypatch.setattr("src.mcp_server.server.fetch_all", fake_fetch_all)

    assert await get_recent_signals("ACME") == []


@pytest.mark.asyncio
async def test_search_company_returns_match_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(_query: str, _args: tuple[object, ...]) -> list[dict[str, str]]:
        return [{"symbol": "ACME", "name": "Acme Corp"}]

    monkeypatch.setattr("src.mcp_server.server.fetch_all", fake_fetch_all)

    assert await search_company("Acme") == [
        {"symbol": "ACME", "name": "Acme Corp", "match_confidence": 100.0}
    ]


@pytest.mark.asyncio
async def test_screen_companies_ranks_requested_sector_and_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_fetch_all(query: str, args: tuple[object, ...]) -> list[dict[str, object]]:
        captured["query"] = query
        captured["args"] = args
        return [{"rank": 1, "symbol": "ACME", "market_cap": 1000}]

    monkeypatch.setattr("src.mcp_server.server.fetch_all", fake_fetch_all)

    result = await screen_companies("tech", metric="market_cap", limit=3)

    assert result == [{"rank": 1, "symbol": "ACME", "market_cap": 1000}]
    assert captured["args"] == ("tech", 3)
    assert "ORDER BY f.market_cap DESC NULLS LAST" in str(captured["query"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"sector": "utilities"}, "Invalid sector: utilities"),
        ({"sector": "tech", "metric": "price"}, "Invalid screening metric"),
        ({"sector": "tech", "limit": 0}, "Screening limit must be an integer"),
    ],
)
async def test_screen_companies_rejects_invalid_screen_parameters(
    kwargs: dict[str, object], message: str
) -> None:
    result = await screen_companies(**kwargs)  # type: ignore[arg-type]

    assert isinstance(result, dict)
    assert str(result["error"]).startswith(message)
