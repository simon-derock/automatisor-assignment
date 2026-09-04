import json

import pytest

from src.agent.graph import (
    _run_grounded_agent,
    _specific_company_match,
    _tool_data,
    confidence_from_context,
    create_mcp_transport,
    delimited_tool_context,
    should_flag_no_data,
)
from src.agent.schemas import AgentResponse


def test_agent_response_accepts_the_spec_contract() -> None:
    response = AgentResponse(
        answer="ACME has the strongest available profile.",
        companies_referenced=["ACME"],
        confidence="medium",
        persona="equity_analyst",
        sector="tech",
    )

    assert response.no_data_flag is False
    assert response.model_dump()["confidence"] == "medium"


def test_tool_context_is_delimited_and_confidence_is_explicit() -> None:
    context = delimited_tool_context({"symbol": "ACME", "signal_text": "A signal"})

    assert context.startswith("<tool_result>")
    assert context.endswith("</tool_result>")
    assert confidence_from_context(has_financials=True, has_signals=True) == "high"
    assert confidence_from_context(has_financials=True, has_signals=False) == "medium"
    assert confidence_from_context(has_financials=False, has_signals=False) == "low"


def test_tool_data_unwraps_fastmcp_root_models() -> None:
    class RootResult:
        data = type(
            "RootModel",
            (),
            {
                "root": [
                    type("ItemRoot", (), {"root": {"symbol": "ACME"}})(),
                ]
            },
        )()

    assert _tool_data(RootResult()) == [{"symbol": "ACME"}]


def test_tool_data_prefers_fastmcp_json_content() -> None:
    class Content:
        text = '[{"symbol": "ACME"}]'

    class ContentResult:
        content = [Content()]

    assert _tool_data(ContentResult()) == [{"symbol": "ACME"}]


def test_company_query_without_search_match_is_flagged_as_no_data() -> None:
    assert should_flag_no_data("What does Contoso hiring look like?", []) is True
    assert should_flag_no_data("Which companies are in this sector?", []) is False
    assert (
        should_flag_no_data(
            "Walk me through the margin profile of the companies in your data", []
        )
        is False
    )
    assert should_flag_no_data("Which company here should I take private?", []) is False
    assert should_flag_no_data("What does Contoso hiring look like?", [{"symbol": "CTSO"}]) is True


def test_agent_transport_is_stdio_subprocess() -> None:
    transport = create_mcp_transport()

    assert transport.command.endswith("python")
    assert transport.args == ["-m", "src.mcp_server.server"]


def test_specific_company_match_prefers_named_high_confidence_result() -> None:
    matches = [
        {"symbol": "AAPL", "name": "Apple Inc.", "match_confidence": 72.0},
        {"symbol": "AMAT", "name": "Applied Materials", "match_confidence": 68.0},
    ]

    assert (
        _specific_company_match("What is the latest hiring signal for Apple?", matches)
        == matches[0]
    )


@pytest.mark.asyncio
async def test_named_company_routes_detail_and_signals_without_sector_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Result:
        def __init__(self, value: object) -> None:
            self.content = [type("Content", (), {"text": json.dumps(value)})()]

    class FakeClient:
        def __init__(self, _transport: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def call_tool(self, name: str, arguments: dict[str, str]) -> Result:
            calls.append((name, arguments))
            values: dict[str, object] = {
                "search_company": [
                    {"symbol": "AAPL", "name": "Apple Inc.", "match_confidence": 72.0},
                    {"symbol": "AMAT", "name": "Applied Materials", "match_confidence": 68.0},
                ],
                "get_company_detail": {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "sector": "tech",
                    "price": 100.0,
                },
                "get_recent_signals": [
                    {"symbol": "AAPL", "signal_text": "Hiring expanded."}
                ],
            }
            return Result(values[name])

    async def fake_generate(*_args: object, **_kwargs: object) -> AgentResponse:
        return AgentResponse(
            answer="Apple has a recent hiring signal.",
            companies_referenced=["AAPL"],
            confidence="high",
            persona="equity_analyst",
            sector="tech",
        )

    monkeypatch.setattr("src.agent.graph.Client", FakeClient)
    monkeypatch.setattr("src.agent.graph.generate_validated_response", fake_generate)

    await _run_grounded_agent(
        "What is the most recent hiring or headcount signal for Apple?",
        "equity_analyst",
        "tech",
    )

    assert [name for name, _ in calls] == [
        "search_company",
        "get_company_detail",
        "get_recent_signals",
    ]
    assert calls[1][1] == {"symbol_or_name": "AAPL"}
    assert calls[2][1] == {"symbol_or_name": "AAPL"}
