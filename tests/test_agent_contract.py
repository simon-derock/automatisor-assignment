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
