"""Structured response models for the financial agent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentResponse(BaseModel):
    """The stable response shape shared by the API and Streamlit UI."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    companies_referenced: list[str]
    confidence: Literal["high", "medium", "low"]
    persona: str
    sector: str
    no_data_flag: bool = False
