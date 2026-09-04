"""Contract tests for the domain-specific MCP tools."""

import pytest

from src.mcp_server.server import get_companies_by_sector


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
