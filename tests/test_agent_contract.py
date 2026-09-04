from src.agent.graph import confidence_from_context, delimited_tool_context, should_flag_no_data
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


def test_company_query_without_search_match_is_flagged_as_no_data() -> None:
    assert should_flag_no_data("What does Contoso hiring look like?", []) is True
    assert should_flag_no_data("Which companies are in this sector?", []) is False
    assert should_flag_no_data("What does Contoso hiring look like?", [{"symbol": "CTSO"}]) is False
