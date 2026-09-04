from src.agent.graph import (
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
    assert should_flag_no_data("What does Contoso hiring look like?", [{"symbol": "CTSO"}]) is False


def test_agent_transport_is_stdio_subprocess() -> None:
    transport = create_mcp_transport()

    assert transport.command.endswith("python")
    assert transport.args == ["-m", "src.mcp_server.server"]
