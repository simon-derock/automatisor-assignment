import pytest

from src.agent.personas import PERSONAS, build_system_prompt


def test_all_three_personas_have_distinct_reasoning_hints() -> None:
    prompts = [build_system_prompt(persona, "retail") for persona in PERSONAS]

    assert len(set(prompts)) == 3
    assert "market cap" in prompts[0]
    assert "EPS" in prompts[1]
    assert "leverage" in prompts[2]


def test_prompt_defines_controlled_react_and_tool_policy() -> None:
    prompt = build_system_prompt("equity_analyst", "tech")

    assert "CONTROLLED REACT LOOP" in prompt
    assert "think → act → observe" in prompt
    assert "never reveal private chain-of-thought" in prompt
    assert "search_company" in prompt
    assert "get_company_detail" in prompt
    assert "get_recent_signals" in prompt
    assert "get_companies_by_sector" in prompt
    assert "For a sector-wide question" in prompt


def test_prompt_has_senior_role_evidence_and_uncertainty_guardrails() -> None:
    prompt = build_system_prompt("pe_analyst", "manufacturing")

    assert "15+ years of institutional investment research experience" in prompt
    assert "Never invent companies, figures, dates, signals" in prompt
    assert "EVIDENCE AND UNCERTAINTY RULES" in prompt
    assert "I don't have sufficient data in the" in prompt
    assert "Active sector: manufacturing" in prompt
    assert "Active persona: pe_analyst" in prompt


def test_invalid_persona_and_sector_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown persona"):
        build_system_prompt("day_trader", "tech")
    with pytest.raises(ValueError, match="Unknown sector"):
        build_system_prompt("mf_analyst", "logistics")
