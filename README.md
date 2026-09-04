# Persona-Configurable Financial Agent

This project is a persona-configurable financial analysis agent for the
`tech`, `retail`, and `manufacturing` sectors. The implementation follows the
contracts in [SPEC.md](SPEC.md) and the phased build plan in [PLAN.md](PLAN.md).

## Status

Core implementation is available on `main`: the prepared dataset, MCP tools,
persona prompts, LangGraph workflow, FastAPI endpoint, Streamlit UI, and demo
runner are included. Credentialed end-to-end execution requires a Postgres
connection string; LLM API keys enable provider-generated responses, while a
deterministic grounded fallback is used when no key is configured.

## Development

Requires Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env
uv sync --dev
uv run ruff check .
uv run mypy src/
uv run pytest
```

See `SPEC.md` for the data-quality caveats and system contracts.

The downloaded raw snapshots are kept in `data/raw/`; the 110 rows surviving
the three-sector filter and Symbol join are in `data/prepared/`. The financials
URL specified by the assignment currently returns 404, so the loader and
prepared snapshot use the published companion mirror documented in
`data/README.md`.

## Run the services

Set `DATABASE_URL` and at least one of `GEMINI_API_KEY` or `MISTRAL_API_KEY` in
`.env`, then run either interface:

```sh
uv run python data/build_db.py
uv run uvicorn src.api.main:app --reload
uv run streamlit run src/ui/app.py
uv run python scripts/demo_queries.py
```

The API exposes `GET /health` and `POST /query`. Both the API and UI delegate
to the same `run_agent(query, persona, sector)` function. The agent accesses
company data through domain-specific MCP tools; it does not query Postgres
directly from the API or UI.

## Design notes

The database separates static company identity, point-in-time financials, and
curated qualitative signals. This keeps quantitative screening queryable while
allowing hiring, expansion, and other qualitative evidence to be traced to a
source URL. The MCP server exposes four narrow tools: sector listing, company
detail, recent signals, and fuzzy company search.

Persona configuration changes the analytical lens and prioritized fields, not
just the response tone. Confidence is computed from retrieved financial and
signal coverage rather than delegated to the model. Gemini is the primary
provider and Mistral is the retry/fallback provider.

## Caveats and next improvements

Financial figures are a point-in-time public S&P 500 snapshot, not live market
data, and dates are not guaranteed current. The signals table is intentionally
small (22 manually curated records), so missing signals do not imply missing
real-world activity. With more time, I would add a scheduled data refresh,
broader signal coverage, richer LangGraph tool-selection policies, and a
credentialed integration test database.

The optional video walkthrough can be replaced by a live walkthrough of the
nine persona×sector combinations and the grounding tests.
