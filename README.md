# Persona-Configurable Financial Agent

An MCP-grounded financial analysis agent that answers the same question through
three distinct investment lenses and two interfaces. The reviewer chooses a
persona and sector independently; both the Streamlit application and REST API
execute the same `run_agent(query, persona, sector)` workflow.

This repository is the primary submission artifact for the AI Engineer
take-home assignment. It contains source snapshots, a reproducible database
loader, schema, MCP server, LangGraph orchestration, provider fallback,
FastAPI API, Streamlit UI, tests, and a runnable demo matrix.

## At a glance

| Concern | Implementation |
| --- | --- |
| Personas | `mf_analyst`, `equity_analyst`, `pe_analyst` |
| Sectors | `tech`, `retail`, `manufacturing` |
| Database | Supabase-hosted PostgreSQL via `asyncpg` |
| Integration boundary | MCP over a co-located `stdio` subprocess |
| Orchestration | Compiled LangGraph workflow |
| Primary LLM | Gemini (`gemini-3.6-flash` by default) |
| Fallback | Mistral, then deterministic grounded response |
| Human interface | Streamlit |
| Programmatic interface | FastAPI `GET /health`, `POST /query` |
| Response contract | Pydantic `AgentResponse` |

## What is implemented

- One configurable agent with nine valid persona × sector combinations.
- Persona-specific analytical priorities, not merely different labels:
  - **Mutual Fund Analyst:** benchmark-relative valuation, sustainable growth,
    dividends, and portfolio fit.
  - **Equity Analyst:** EPS, EBITDA, margins, earnings trajectory, and
    competitive positioning.
  - **PE Analyst:** EBITDA, deal-size proxy, leverage capacity, operational
    levers, and exit-multiple potential.
- Live database retrieval through five domain-specific MCP tools.
- Search-first named-company handling, sector validation, and honest out-of-
  scope responses.
- Structured responses with referenced companies, confidence, persona, sector,
  and `no_data_flag`.
- Gemini structured-output enforcement, one Pydantic correction attempt, and
  Gemini → Mistral retry/fallback behavior.
- Streamlit and FastAPI calling the same underlying agent entrypoint.
- Reproducible data preparation and idempotent database seeding.

## Architecture and request flow

```text
Streamlit or FastAPI
          │
          ▼
run_agent(query, persona, sector)
          │
          ▼
Compiled LangGraph workflow
          │
          ▼
FastMCP client ── stdio ──► MCP database subprocess
                              │
                              ▼
                         Supabase Postgres
                         companies / financials / signals
          │
          ▼
Delimited tool context + persona prompt
          │
          ▼
Gemini → Mistral → grounded deterministic fallback
          │
          ▼
Validated AgentResponse JSON
```

The API and UI do not contain separate business logic and do not query
PostgreSQL directly. The agent consumes database context through MCP. Tool
results are wrapped in `<tool_result>...</tool_result>` delimiters and treated
as data rather than instructions.

### ReAct-style reasoning policy

The prompt implements a bounded ReAct loop: classify the request, choose the
smallest sufficient tool call, inspect the observation, validate identity and
sector, and answer. Hidden chain-of-thought is never exposed; the user receives
the conclusion, supporting observations, uncertainty, and symbols actually
used.

| Question shape | Retrieval path | Guardrail |
| --- | --- | --- |
| Named company, ticker, or hiring signal | `search_company` → `get_company_detail` and/or `get_recent_signals` | Resolve one unambiguous match and verify its selected sector |
| Sector comparison or screening | `get_companies_by_sector` → targeted detail/signal calls | Keep every record inside the requested sector |
| Unknown company or unavailable fact | Search/inspect the relevant MCP result | State that the dataset is insufficient; never use model memory |

The prompt separates observed database facts, persona-specific interpretation,
and the decision caveat. Provider output is constrained to `AgentResponse`, and
retrieval evidence controls identity, scope, confidence, and referenced-company
fields.

## Data and database

`data/build_db.py` downloads public S&P 500 snapshots, joins them on `Symbol`,
applies the three sector rules, and seeds PostgreSQL:

- `data/raw/constituents.csv`: 503 source rows.
- `data/raw/constituents-financials.csv`: 503 financial source rows.
- `data/prepared/`: 110 joined rows retained by the sector rules.
- `data/signals_curated.json`: 22 hand-curated qualitative signals with source
  URLs and dates.

The requested financials URL currently returns HTTP 404. The loader preserves
that URL as the primary source and falls back to the published companion
repository documented in [`data/README.md`](data/README.md), rather than hiding
the substitution.

The schema separates concerns:

- `companies`: identity and classification (`symbol`, name, sector,
  sub-industry, headquarters, founded year).
- `financials`: point-in-time quantitative snapshot keyed one-to-one to a
  company (price, P/E, dividend yield, EPS, 52-week range, market cap, EBITDA,
  price/sales, price/book, and source metadata).
- `signals`: qualitative evidence such as hiring, expansion, and leadership
  signals, with source URL and date.

This separation supports numeric screening and traceable qualitative grounding.
Company and financial rows are upserted; the curated signal set is replaced
transactionally, so the seed is safe to rerun. See
[`src/db/schema.sql`](src/db/schema.sql).

## MCP boundary

The MCP server is a co-located `stdio` subprocess launched by the agent. This
makes the protocol boundary explicit without introducing an unnecessary network
service for a single-machine assignment. Database access remains asynchronous
through `asyncpg`; the API and UI never bypass MCP.

| MCP tool | Purpose |
| --- | --- |
| `search_company(query)` | Fuzzy search with match-confidence scores |
| `get_companies_by_sector(sector)` | Sector-level company list |
| `screen_companies(sector, metric, limit)` | Ranked peer screen by an allowlisted financial metric |
| `get_company_detail(symbol_or_name)` | Company identity joined to financials |
| `get_recent_signals(symbol_or_name)` | Newest curated signals for one company |

All tools return JSON-serializable lists/dicts. Genuine database failures are
returned as structured errors, while “not found” remains distinct from “the
database failed.” Named-company questions use search results to route detail
and signal calls to the matched company; a match from another selected sector
is rejected.

## Agent contract and grounding

Every request enters:

```python
await run_agent(query, persona, sector) -> AgentResponse
```

Example response:

```json
{
  "answer": "...",
  "companies_referenced": ["AAPL"],
  "confidence": "high",
  "persona": "equity_analyst",
  "sector": "tech",
  "no_data_flag": false
}
```

Confidence is computed from retrieval evidence rather than trusted to the LLM:

- `high`: financials and at least one signal were retrieved for referenced
  companies.
- `medium`: financials were retrieved, but no matching signals were found.
- `low`: ambiguous/partial retrieval, sector-level generalization without
  company detail, or an out-of-scope request.
- `no_data_flag=true` always forces `low` confidence.

If search cannot establish that a named company is in the configured dataset,
the agent says so instead of fabricating an opinion.

### Why the three personas are materially different

The same retrieved rows are passed to each persona, while the prompt changes
the decision question and evidence priority:

| Persona | Decision question | Evidence emphasis | Conclusion style |
| --- | --- | --- | --- |
| Mutual Fund Analyst | Does this improve a diversified, long-only portfolio? | P/E, dividend yield, market cap, price/book, durable growth and peer/index context | Compounding quality, valuation discipline, portfolio fit, and downside trade-offs |
| Equity Analyst | Are operating fundamentals improving enough to support the thesis? | EPS, EBITDA, margins where available, price/sales, 52-week trend and catalysts | Earnings trajectory, competitive position, catalysts, risks, and price-target framing |
| PE Analyst | Can an owner create value at an executable entry price? | EBITDA, market-cap deal-size proxy, price/book asset proxy, cash-flow durability, leverage and exit considerations | Entry feasibility, operational levers, deleveraging, exit path, and value-creation risks |

This is a lens change, not three datasets or three agents. The answer must
distinguish observed metrics from interpretation and disclose when the database
has only a proxy—for example, market cap is a deal-size proxy, not a leverage or
cash-flow measurement.

## Setup

Requirements: Python 3.11 or 3.12 and
[`uv`](https://docs.astral.sh/uv/).

### Install

```bash
uv sync --dev
cp .env.example .env
```

### Configure

In Supabase, open **Connect → Session pooler → URI** and copy the PostgreSQL
connection string. This project uses the database connection directly; it does
not need Supabase REST, publishable, anon, or service-role keys.

```dotenv
DATABASE_URL=postgres://postgres.<project-ref>:<password>@aws-<region>.pooler.supabase.com:5432/postgres
GEMINI_API_KEY=...
MISTRAL_API_KEY=...
GEMINI_MODEL=gemini-3.6-flash
MISTRAL_MODEL=mistral-small-latest
```

Gemini is primary and Mistral is fallback. Keep `.env` private; no real
credentials belong in Git. Reviewers create their own Supabase project and can
rebuild the database from the included loader.

### Seed

```bash
uv run python data/build_db.py
```

Expected seeded counts are 110 `companies`, 110 `financials`, and 22
`signals`. The script is idempotent and safe to rerun.

### Run

```bash
uv run streamlit run src/ui/app.py
```

or:

```bash
uv run uvicorn src.api.main:app --reload
```

The UI provides persona and sector selectors plus a chat input. The API’s
interactive documentation is at `http://127.0.0.1:8000/docs`.

## API example

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Walk me through the margin profile of the companies in your data.",
    "persona": "equity_analyst",
    "sector": "manufacturing"
  }'
```

The assignment permits any three sectors; this implementation selected
`tech`, `retail`, and `manufacturing` rather than `logistics`. Therefore,
`logistics` is intentionally rejected with HTTP 422, and `manufacturing` is the
corresponding supported industrial-sector example.

The request accepts exactly one value from each controlled enum:
`mf_analyst`, `equity_analyst`, or `pe_analyst`; and `tech`, `retail`, or
`manufacturing`. A successful response contains `answer`,
`companies_referenced`, `confidence`, `persona`, `sector`, and `no_data_flag`.
Malformed JSON, an empty query, or an unsupported value is rejected by FastAPI
with a validation error. A valid request can still return `no_data_flag: true`
when the company or evidence is outside the dataset.

## Demo and verification

Run the scenario matrix:

```bash
uv run python scripts/demo_queries.py
```

It covers all nine persona × sector combinations, the identical cross-persona
question for all three personas, MF/Retail core holdings, Equity/Manufacturing
margin analysis, PE/Tech take-private analysis, company-specific hiring, and
an out-of-scope company.

### Reviewer smoke test

After configuring a reviewer-owned Supabase database and provider key, the
shortest end-to-end check is:

1. Run the seed command and confirm `110 / 110 / 22` rows.
2. Start the API and confirm `GET /health` returns HTTP 200.
3. Submit the API example above through `/docs`.
4. Ask the same Tech question as all three personas and compare evidence,
   decision criteria, and conclusion—not just the persona label.
5. Ask for the latest hiring/headcount signal for a known company such as
   Apple; confirm the response references retrieved company evidence.
6. Ask about `Contoso`; confirm `no_data_flag` is true and no facts are invented.
7. Start Streamlit, change both sidebar selectors, and submit the same prompt;
   confirm it reaches the same `run_agent` path as the API.

The MCP boundary can be checked independently with the stdio handshake and the
five tool names documented above. This verifies that database context crosses
MCP rather than being obtained by a direct database import in the UI or API.

Local quality gates:

```bash
uv run ruff check .
uv run mypy src/
uv run pytest -q
```

Current repository tests cover data preparation, MCP contracts and failures,
stdio transport, persona prompts, provider retry/fallback and structured
validation, LangGraph grounding, Streamlit wiring, demo coverage, and the API
contract.

Live verification in the author’s environment confirmed:

- Supabase counts of 110 / 110 / 22 and sector counts of 64 tech, 22 retail,
  and 24 manufacturing;
- MCP stdio handshake and all five tools;
- API health and structured responses;
- Streamlit bootstrap and a PE/Tech chat submission;
- all nine LangGraph/MCP/Supabase persona-sector paths;
- Apple signal retrieval and Contoso no-data handling.

Provider quotas can cause a request to use the deterministic grounded response.
That behavior is deliberate: database grounding and a stable response contract
remain available when an LLM is unavailable or rate-limited.

## State and scope

Each request is independent. The assignment requires a configurable agent and
dual interfaces, but does not require multi-turn persistence. Accordingly:

- FastAPI is stateless.
- Streamlit keeps the visible transcript in `st.session_state`, but prior turns
  are not sent as model context.
- MCP tool calls execute per request and are not persisted.
- LangGraph checkpointing and long-term memory are intentionally not enabled.

For production, the next step would be a session ID plus Supabase conversation
and tool-trace tables, a LangGraph checkpointer, scheduled data refreshes, and
broader signal coverage.

## Caveats and next improvements

Financial values are a public point-in-time S&P 500 snapshot, not live market
data; source dates are not guaranteed current. The 22 signals are intentionally
small, so an empty signal list means “no signal in this dataset,” not “no
real-world activity.” Sector membership follows the explicit rules in
[`SPEC.md`](SPEC.md), not a claim that the labels cover every industry.

With more time I would add freshness validation and scheduled refreshes,
broader independently sourced signals, persisted sessions/checkpointing,
quota-aware circuit breaking, and deployed browser-level CI for both interfaces.

The optional video walkthrough can be replaced by a live walkthrough of the
nine combinations, grounding query, and out-of-scope test; the repository
contains the reproducible demo cases.

## Repository map

```text
data/                    download, prepare, and seed data
src/agent/               schemas, personas, providers, LangGraph workflow
src/api/main.py          FastAPI interface
src/db/schema.sql        PostgreSQL schema
src/mcp_server/server.py stdio MCP tools
src/ui/app.py            Streamlit interface
scripts/demo_queries.py  assignment scenario matrix
tests/                   contract and integration-boundary tests
PLAN.md / SPEC.md        implementation plan and source-of-truth contracts
```
