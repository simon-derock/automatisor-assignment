"""Contract tests for the domain-specific MCP tools."""

import pytest

from src.mcp_server.server import (
    get_companies_by_sector,
    get_company_detail,
    get_recent_signals,
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
