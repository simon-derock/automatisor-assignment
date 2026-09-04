"""FastAPI surface over the shared financial agent."""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent.schemas import AgentResponse

app = FastAPI(title="Persona-Configurable Financial Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    persona: Literal["mf_analyst", "equity_analyst", "pe_analyst"]
    sector: Literal["tech", "retail", "manufacturing"]


async def run_agent(query: str, persona: str, sector: str) -> AgentResponse:
    """Lazy-load the agent so health and request validation start independently."""
    from src.agent.graph import run_agent as agent_runner

    return await agent_runner(query, persona, sector)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query", response_model=AgentResponse)
async def query_agent(request: QueryRequest) -> AgentResponse:
    return await run_agent(request.query, request.persona, request.sector)
