# PLAN.md — Persona-Configurable Financial Agent

**Repo:** https://github.com/simon-derock/automatisor-assignment

> Companion to `SPEC.md` (contracts) and `MEMORY.md` (live state/handoff).
> Methodology: Spec-Driven Development → TDD → micro-commits → CI on every push.

---

## 0. Source of Truth Recap (from Agent_JD.pdf — do not drift from this)

| # | Requirement | Non-negotiable detail |
|---|---|---|
| 1 | Persona-configurable agent | 3 personas (MF Analyst, Equity Analyst, PE Analyst), switchable via config/param. Must change **reasoning**, not just tone. |
| 2 | Sector context, DB-backed | 3 sectors, switchable independently of persona (9 valid combos). Real DB (SQLite/Postgres ok). No hardcoded facts in prompts. Schema + sourcing + data-quality caveats documented in README. |
| 3 | MCP-based tool exposure | DB query capability exposed as MCP tools. Agent consumes via MCP, not direct DB client calls. |
| 4 | Dual interface | Streamlit (or equiv) UI + REST API. **Same underlying agent** — no duplicated logic. |
| — | Grading tests we must pass | (a) cross-persona same-question divergence, (b) DB-grounding stress test (hiring/headcount lookup), (c) out-of-scope test (company not in DB → honest "no data"), (d) API structured JSON test (answer + companies_referenced + confidence). |
| — | Submission checklist | GitHub repo + README, `.env.example`, sample DB or rebuild script, ~1 page write-up (schema decisions / MCP design / one improvement), optional Loom video. |
| — | Explicit permission | If time-constrained: prioritize working MCP + dual-interface skeleton over persona polish, and say so in README. |

---

## 1. Tech Stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Package/env mgmt | `uv`, Python pinned `>=3.11,<3.13` in `pyproject.toml` | fast, lockfile-based, reproducible interpreter version |
| DB | Supabase (Postgres, free tier) | real DB, networked, works for local dev |
| DB access | `asyncpg` (async, direct) inside our own MCP tool functions — **not** `supabase-py` (sync client would block LangGraph's async event loop) | avoids sync/async mismatch; still just "our DB driver," no ORM leak through MCP |
| MCP server | `fastmcp`, transport = **stdio**, spawned as a subprocess of the agent process (co-located, same machine/container) | simplest correct choice for this scope; HTTP/SSE transport is unnecessary complexity since nothing needs to reach the MCP server except our own agent |
| Agent orchestration | `langgraph` | tool-calling loop, structured output enforcement |
| LLM providers | Gemini (primary) + Mistral (fallback), both free-tier API keys, with `tenacity` retry-with-backoff on both | documented per assignment's "note your LLM choice"; free tiers WILL rate-limit during testing, must handle gracefully |
| API | FastAPI, CORS enabled, `GET /health` endpoint | REST, structured JSON responses, standard prod hygiene |
| Frontend | Streamlit, imports `run_agent()` directly (no HTTP hop to own API) | required by spec ("or equivalent"); avoids duplicate logic per requirement #4 |
| Testing | `pytest` + `pytest-asyncio`, against a dedicated **test schema** in Supabase (not the demo tables) | TDD on MCP tool contracts + API contracts, without polluting/rate-limiting the demo DB |
| CI | GitHub Actions | lint (ruff) + type-check (mypy) + test on every push |
| Deployment | **None planned for submission** — repo + README + local run instructions is the deliverable per the assignment's actual ask. Offer a **live walkthrough call** instead of a Loom video (explicitly optional per spec; live demo is our stated strength). A deployed link may be added later as a portfolio item, not a submission blocker. |

---

## 2. Repo Layout (minimal file count, on purpose)

```
automatisor-assignment/
├── SPEC.md
├── PLAN.md
├── MEMORY.md
├── README.md
├── LICENSE                      # MIT
├── .gitignore                   # .env, __pycache__, .venv, uv cache, etc.
├── .env.example
├── pyproject.toml
├── uv.lock
├── .github/workflows/ci.yml
├── data/
│   ├── build_db.py              # fetches CSVs, seeds Supabase, adds curated signals
│   └── signals_curated.json     # manually sourced hiring/news signals (~20-30 rows)
├── src/
│   ├── db/
│   │   └── schema.sql
│   ├── mcp_server/
│   │   └── server.py            # FastMCP tools: get_companies_by_sector, get_company_detail,
│   │                             #                get_recent_signals, search_company
│   ├── agent/
│   │   ├── personas.py          # persona prompt blocks + tool-priority hints
│   │   ├── graph.py             # LangGraph agent (MCP client + structured output + retry)
│   │   └── schemas.py           # Pydantic: AgentResponse(answer, companies_referenced, confidence, ...)
│   ├── api/
│   │   └── main.py              # FastAPI: POST /query, GET /health
│   └── ui/
│       └── app.py               # Streamlit: persona/sector dropdowns + chat
├── scripts/
│   └── demo_queries.py          # runnable script hitting all 9 combos + the 4 grading-test cases
└── tests/
    ├── conftest.py              # test-schema fixtures, isolated from demo data
    ├── test_mcp_tools.py
    ├── test_agent_contract.py
    └── test_api_contract.py
```
Rationale for minimal files: reviewers are grading system design, not file count — one file per concern, no premature splitting.

---

## 3. Engineering Standards (top-tier dev practices)

- **Git worktrees** for parallel phase work (e.g. `git worktree add ../wt-mcp-server feature/mcp-server`) — avoid branch-switch churn while iterating on isolated phases.
- **Pre-commit hooks** (`pre-commit` framework): ruff (lint + format), mypy/pyright (type check), trailing-whitespace/end-of-file fixers — run automatically before every commit, not just in CI.
- **Type hints everywhere** — Pydantic models + `mypy --strict` (or `pyright`) as a CI gate, not optional.
- **Conventional Commits + commitlint** — enforce format at commit-time via hook, not just convention by habit.
- **Direct pushes to `main`** — solo takehome, move fast; CI still runs on every push as the safety net instead of PR review.
- **`ruff` for both lint + format** — single fast tool, replaces flake8+black+isort.
- **Dependency pinning via `uv.lock`** — committed, reproducible installs.
- **Structured logging** (not print statements) in MCP server + agent for tool-call tracing/debuggability.
- **Secrets hygiene** — `.env` gitignored, `.env.example` maintained in sync, no secrets ever in commit history (checked via `gitleaks` pre-commit hook if time allows).
- **Semantic versioning + CHANGELOG.md** (optional but signals maturity) if you tag a release for submission.

---

## 4. Git Discipline

- **Commit style:** Conventional Commits — `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:` — imperative mood, scoped when useful (`feat(mcp): ...`).
- **Frequency:** one commit per red→green TDD cycle or one logical unit — never bundle unrelated changes.
- **Push cadence:** push after every green test run so CI validates continuously, not in one batch at the end.
- **No direct fact-dumps in commit bodies** — commit message states *what* and *why* in one line; body only if a decision needs justification (e.g. why asyncpg over supabase-py).
- **Worktrees per phase** (see §3) — e.g. `wt-db`, `wt-mcp-server`, `wt-agent`, `wt-api-ui` — merge back to `main` via fast-forward when a phase's tests are green.

---

## 5. GitHub Actions (`.github/workflows/ci.yml`) — scope

- Trigger: `on: [push, pull_request]`
- Steps: checkout → setup `uv` → `uv sync` → `uv run ruff check .` → `uv run mypy src/` → `uv run pytest`
- Keep to one workflow file; no matrix builds needed for this scope.

---

## 6. SDLC Phases (each phase = its own worktree, micro-commits within)

### Phase 0 — Bootstrap
- [x] `uv init`, `pyproject.toml` (Python version pinned), `.env.example`, `.gitignore`, `LICENSE` (MIT), CI skeleton, pre-commit config
- Commit: `chore: bootstrap uv project, CI skeleton, env template, license`

### Phase 1 — Data layer (TDD)
1. [x] Write `tests/test_mcp_tools.py` stubs asserting shape of `get_companies_by_sector("tech")` **before** implementing (red)
2. [x] `data/build_db.py`: pull the two GitHub CSVs (constituents + constituents-financials), filter to 3 sectors via GICS sub-industry keywords, load into Supabase via `asyncpg`
3. [x] Add `data/signals_curated.json` — 20-30 hand-sourced hiring/news signal rows
4. [x] `tests/conftest.py`: dedicated test-schema fixture, separate from demo tables
5. Commit sequence (micro):
   - `feat(db): schema.sql for companies/financials/signals tables`
   - `feat(data): build_db.py fetches and filters S&P500 CSVs by sector`
   - `feat(data): seed signals_curated.json into signals table`
   - `test(db): isolated test-schema fixture`

### Phase 2 — MCP server (TDD)
1. [x] Red: contract tests for each tool's return shape, including empty/not-found and **error** cases
2. [x] Implement `src/mcp_server/server.py` tool by tool (stdio transport) until green
3. [x] Define consistent error shape (`{"error": "..."}`) for connection/timeout failures, distinct from "not found"
4. Commits:
   - `feat(mcp): get_companies_by_sector tool`
   - `feat(mcp): get_company_detail tool with not-found handling`
   - `feat(mcp): get_recent_signals tool`
   - `feat(mcp): search_company tool with fuzzy-match ambiguity resolution`
   - `feat(mcp): consistent error contract for tool failures`
   - `test(mcp): contract tests for all four tools incl. error paths`

### Phase 3 — Agent core (single persona/sector hardcoded first)
1. [x] Red: `test_agent_contract.py` asserts `AgentResponse` schema on a canned query
2. [x] Implement LangGraph agent as MCP client (stdio subprocess), one persona hardcoded, structured output via Pydantic + validation-retry-once on parse failure
   - [x] MCP client path, Pydantic response model, one validation-correction retry, Gemini/Mistral provider wiring, and compiled LangGraph orchestration are implemented.
3. [x] Add `tenacity` retry/backoff wrapper around LLM API calls (Gemini + Mistral fallback)
4. Commits:
   - `feat(agent): base LangGraph agent as MCP client over stdio`
   - `feat(agent): structured AgentResponse schema with retry-on-parse-failure`
   - `feat(agent): LLM retry/backoff + Gemini-to-Mistral fallback`
   - `test(agent): contract test on hardcoded persona`

### Phase 4 — Persona + sector switching
1. [x] `personas.py`: unified prompt template + persona block + tool-priority hint (see SPEC.md §4)
2. [x] Parametrize agent entrypoint: `run_agent(query, persona, sector)`
3. [x] Define `confidence` computation rule explicitly (see SPEC.md §5)
4. Commits:
   - `feat(agent): persona prompt blocks (mf_analyst, equity_analyst, pe_analyst)`
   - `feat(agent): sector param threading through tool calls`
   - `feat(agent): confidence scoring rule based on tool-result completeness`
   - `test(agent): cross-persona divergence smoke test (same query, 3 personas, assert differing tool-priority fields)`

### Phase 5 — Grounding + honesty guardrails
1. [x] Add explicit "no data found → say so" instruction + verify via test with an out-of-scope company name
2. [x] Note on tool-result handling: wrap tool output in a clearly delimited context block in the prompt (light prompt-injection hygiene, low risk here but documented)
3. Commits:
   - `feat(agent): honest no-data handling for out-of-scope companies`
   - `feat(agent): delimited tool-context blocks in prompt construction`
   - `test(agent): out-of-scope company returns explicit no-data response`

### Phase 6 — API
1. [x] Red: `test_api_contract.py` — POST `/query` returns `answer`, `companies_referenced`, `confidence`, `persona`, `sector`
2. [x] Implement FastAPI wrapper calling `run_agent()` directly (no reimplementation), add CORS middleware + `GET /health`
3. Commits:
   - `feat(api): POST /query endpoint wrapping shared agent`
   - `feat(api): CORS config + health check endpoint`
   - `test(api): structured JSON contract test`

### Phase 7 — Streamlit UI
1. [x] Persona/sector dropdowns, chat box, calls `run_agent()` directly (same function as API)
2. Commits:
   - `feat(ui): streamlit app with persona/sector selectors`
   - `feat(ui): chat display of AgentResponse`

### Phase 8 — Demo script + polish + submission
- [x] `scripts/demo_queries.py`: runnable script that fires all 4 grading-test categories + a spread across the 9 combos, printing results — this is what stands in for the video
- [x] README: setup instructions, schema decisions, MCP design rationale, "what I'd improve," data-quality caveats, note offering a **live walkthrough in place of a video**
- Final CI green run
- Commits:
   - `feat(scripts): demo_queries.py covering all grading-test cases`
   - `docs: README with schema/MCP write-up and setup instructions`
   - `chore: final cleanup pass`

---

## 7. Definition of Done (map back to §0 table)

- [ ] 9 persona×sector combos runnable and manually spot-checked (at least 4-5 combos incl. the doc's example queries)
- [ ] Cross-persona same-question test shows genuinely different reasoning (tool-priority + framing), not just tone
- [ ] Hiring/headcount stress-test query forces real `get_recent_signals` DB call
- [x] Out-of-scope company query returns explicit "no data" — verified by test
- [x] API POST /query returns structured JSON per SPEC.md contract
- [x] Streamlit UI and API both call the same `run_agent()` — no duplicate logic
- [ ] `scripts/demo_queries.py` runs clean end-to-end, covering all 4 grading-test categories
- [x] README contains: setup steps, schema decisions, MCP design rationale, data-quality caveats, "what I'd improve with more time," live-walkthrough offer
- [x] `.env.example`, `.gitignore`, `LICENSE` present, no real keys committed
- [ ] CI green (lint + type-check + tests) on final commit
- [x] Retry/fallback logic verified to survive at least one simulated rate-limit
