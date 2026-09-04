import asyncio
import json

import scripts.demo_queries as demo_queries
from src.agent.personas import PERSONAS
from src.agent.schemas import AgentResponse


def test_demo_cases_cover_spec_categories_and_repeat_cross_persona_question() -> None:
    cases = {case.name: case for case in demo_queries.DEMO_CASES}

    assert {
        "mf_retail_core_holding",
        "equity_manufacturing_margin_walk",
        "pe_tech_take_private",
        "hiring_headcount",
        "out_of_scope",
    } <= cases.keys()

    assert len(demo_queries.MATRIX_CASES) == 9
    assert {(case.persona, case.sector) for case in demo_queries.MATRIX_CASES} == {
        (persona, sector)
        for persona in PERSONAS
        for sector in ("retail", "tech", "manufacturing")
    }

    cross_persona = [
        case
        for case in demo_queries.DEMO_CASES
        if case.name.startswith("cross_persona_same_question_")
    ]
    assert {case.persona for case in cross_persona} == set(PERSONAS)
    assert {case.query for case in cross_persona} == {demo_queries.CROSS_PERSONA_QUERY}
    assert {case.sector for case in cross_persona} == {"retail"}

    assert (cases["mf_retail_core_holding"].persona, cases["mf_retail_core_holding"].sector) == (
        "mf_analyst",
        "retail",
    )
    assert (
        cases["equity_manufacturing_margin_walk"].persona,
        cases["equity_manufacturing_margin_walk"].sector,
    ) == ("equity_analyst", "manufacturing")
    assert (cases["pe_tech_take_private"].persona, cases["pe_tech_take_private"].sector) == (
        "pe_analyst",
        "tech",
    )
    assert (cases["hiring_headcount"].persona, cases["hiring_headcount"].sector) == (
        "equity_analyst",
        "tech",
    )


def test_collect_demo_results_executes_every_case_with_structured_output() -> None:
    calls: list[tuple[str, str, str]] = []

    async def fake_agent(query: str, persona: str, sector: str) -> AgentResponse:
        calls.append((query, persona, sector))
        return AgentResponse(
            answer="Grounded answer",
            companies_referenced=["ACME"],
            confidence="medium",
            persona=persona,
            sector=sector,
        )

    results = asyncio.run(demo_queries.collect_demo_results(fake_agent))

    assert len(calls) == len(demo_queries.DEMO_CASES)
    assert [result["case"] for result in results] == [case.name for case in demo_queries.DEMO_CASES]
    assert all(result["companies_referenced"] == ["ACME"] for result in results)
    json.dumps(results)


def test_run_demo_does_not_call_agent_without_database_url(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("agent must not run without DATABASE_URL")

    asyncio.run(demo_queries.run_demo(fail_if_called))

    assert "DATABASE_URL is not configured" in capsys.readouterr().out
