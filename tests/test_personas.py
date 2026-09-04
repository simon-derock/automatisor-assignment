import pytest

from src.agent.personas import PERSONAS, build_system_prompt


def test_all_three_personas_have_distinct_reasoning_hints() -> None:
    prompts = [build_system_prompt(persona, "retail") for persona in PERSONAS]

    assert len(set(prompts)) == 3
    assert "market cap" in prompts[0]
    assert "EPS" in prompts[1]
    assert "leverage" in prompts[2]


def test_personas_have_distinct_senior_operating_mandates() -> None:
    mf, equity, pe = [build_system_prompt(persona, "tech") for persona in PERSONAS]

    assert "long-only public-equities" in mf
    assert "benchmark-relative" in mf
    assert "sell-side equity research analyst" in equity
    assert "reported fundamentals from forecasts" in equity
    assert "private-equity investment professional" in pe
    assert "quality-of-earnings review" in pe
    assert all("Decision rubric:" in prompt for prompt in (mf, equity, pe))


def test_prompt_defines_controlled_react_and_tool_policy() -> None:
    prompt = build_system_prompt("equity_analyst", "tech")

    assert "REACT LOOP — PRIVATE CONTROL, PUBLIC EVIDENCE" in prompt
    assert "Reason → Act → Observe → Answer" in prompt
    assert "Do not disclose private chain-of-thought" in prompt
    assert "stopping condition" in prompt
    assert "search_company" in prompt
    assert "get_company_detail" in prompt
    assert "get_recent_signals" in prompt
    assert "get_companies_by_sector" in prompt
    assert "For a sector-wide question" in prompt
    assert "discard mismatches" in prompt


def test_prompt_has_senior_role_evidence_and_uncertainty_guardrails() -> None:
    prompt = build_system_prompt("pe_analyst", "manufacturing")

    assert "15+ years" in prompt
    assert "Never invent" in prompt
    assert "EVIDENCE AND UNCERTAINTY RULES" in prompt
    assert "I don't have sufficient data in the" in prompt
    assert "proxy-only evidence" in prompt
    assert "Active sector: manufacturing" in prompt
    assert "Active persona: pe_analyst" in prompt


def test_invalid_persona_and_sector_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown persona"):
        build_system_prompt("day_trader", "tech")
    with pytest.raises(ValueError, match="Unknown sector"):
        build_system_prompt("mf_analyst", "logistics")
