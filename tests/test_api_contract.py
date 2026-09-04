from fastapi.testclient import TestClient

from src.agent.schemas import AgentResponse
from src.api.main import app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_endpoint_returns_structured_agent_response(monkeypatch) -> None:
    async def fake_run_agent(query: str, persona: str, sector: str) -> AgentResponse:
        return AgentResponse(
            answer=f"Grounded answer for {query}",
            companies_referenced=["ACME"],
            confidence="medium",
            persona=persona,
            sector=sector,
        )

    monkeypatch.setattr("src.api.main.run_agent", fake_run_agent)
    client = TestClient(app)

    response = client.post(
        "/query",
        json={"query": "Compare ACME", "persona": "equity_analyst", "sector": "tech"},
    )

    assert response.status_code == 200
    assert response.json()["companies_referenced"] == ["ACME"]
    assert response.json()["confidence"] == "medium"


def test_query_endpoint_rejects_invalid_persona() -> None:
    response = TestClient(app).post(
        "/query",
        json={"query": "Compare", "persona": "day_trader", "sector": "tech"},
    )

    assert response.status_code == 422
