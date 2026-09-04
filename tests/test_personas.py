import pytest

from src.agent.personas import PERSONAS, build_system_prompt


def test_all_three_personas_have_distinct_reasoning_hints() -> None:
    prompts = [build_system_prompt(persona, "retail") for persona in PERSONAS]

    assert len(set(prompts)) == 3
    assert "market cap" in prompts[0]
    assert "EPS" in prompts[1]
    assert "leverage" in prompts[2]


def test_invalid_persona_and_sector_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown persona"):
        build_system_prompt("day_trader", "tech")
    with pytest.raises(ValueError, match="Unknown sector"):
        build_system_prompt("mf_analyst", "logistics")
