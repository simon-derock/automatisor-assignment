# MEMORY.md — Live State & Handoff

> Update this file at the END of every work session / phase, before committing.
> If you (the agent/assistant) are picking this project back up with no prior context,
> read `INIT_PROMPT` at the bottom first — it is self-contained.

---

## STATUS

**Last updated:** 2026-09-04
**Current phase:** Phase 3 — Agent core (in progress)

### ✅ Completed
- Phase 0: project metadata, dependency configuration, environment template,
  ignore rules, MIT license, CI skeleton, and pre-commit configuration added.
- Phase 0: uv lockfile generated and bootstrap quality checks are green.
- Phase 1: PostgreSQL schema added; MCP contract tests and all four initial
  domain tools are green.
- Phase 1: downloaded 503-row raw snapshots, prepared 110 filtered/joined rows,
  added 22 curated signals, and implemented the idempotent asyncpg loader.
- Phase 1: added `data/README.md` provenance manifest with source URLs, counts,
  and the financials fallback explanation.
- Phase 1: loader now reads `.env`; regression tests verify 110 prepared rows,
  all three sectors, 22 signals, and valid signal symbols.
- Phase 1: corrected a curated Microsoft signal URL and revalidated all tests.
- Phase 1/2: updated PLAN.md completion markers and added MCP database-failure
  contract coverage; full suite is green at 9 tests.
- Phase 1: added an optional disposable `TEST_DATABASE_URL` schema fixture with
  isolated tables and teardown; local suite remains green without credentials.
- Git: promoted `main` as the primary branch, merged the remote initial commit,
  and pushed the agent response schema; remote HEAD now points to `main`.
- Phase 3/4: added and pushed persona prompt configuration with distinct
  reasoning hints for all three analyst personas; 12 tests pass.
- Phase 3: added and pushed an MCP-protocol-backed grounded query loop with
  delimited tool context and explicit confidence calculation; 13 tests pass.
- Phase 3: added and pushed tenacity-backed primary retry and fallback provider
  adapter; simulated rate-limit tests pass and the suite has 15 tests.
- Phase 3: added and pushed one-shot Pydantic structured-output correction;
  simulated malformed JSON recovery passes and the suite has 16 tests.
- Phase 6: added and pushed FastAPI health/query endpoints with locked request
  validation, shared-agent delegation, and CORS; full suite has 19 tests.
- Phase 7: added and pushed Streamlit persona/sector chat UI calling the same
  `run_agent()` entrypoint; full suite and strict checks remain green.
- Phase 8: added and pushed the demo runner for all 9 persona/sector combinations
  plus hiring and out-of-scope cases; it fails fast when DATABASE_URL is absent.
- Phase 3: wired Gemini-primary/Mistral-fallback provider generation into the
  grounded loop with deterministic fallback when keys are absent.
- Phase 3: wrapped the grounded execution in a compiled LangGraph workflow and
  pushed it to `main`; full suite remains green at 19 tests.

### 🔄 Currently doing
- Finish README polish and end-to-end credentialed verification.

### 🎯 Immediate next goal
- `DATABASE_URL` is not configured in this workspace, so remote Supabase seeding
  has not been run.

### ⚠️ Open decisions / blockers
- The provided `.git` directory is a read-only mount; commits are kept in the
  task-local `/tmp/automatisor-assignment.git` metadata repository.

---

## KEY FACTS (do not re-derive — just trust these)

- Sectors locked: `tech`, `retail`, `manufacturing` (see SPEC.md §1 for GICS mapping)
- Personas locked: `mf_analyst`, `equity_analyst`, `pe_analyst` (see SPEC.md §2)
- Data source: raw CSVs from `github.com/datasets/s-and-p-500-companies` (constituents.csv +
  constituents-financials.csv), no Kaggle auth needed
- Signals table is hand-curated (~20-30 rows), lives in `data/signals_curated.json`
- MCP tools are domain-specific wrappers over asyncpg, NOT raw SQL passthrough — this is a
  hard requirement from the assignment, do not regress to a generic query tool
- Agent entrypoint `run_agent(query, persona, sector)` is the ONLY thing both API and UI call —
  never duplicate agent logic in either surface
- Full contracts live in `SPEC.md` — treat as binding, update SPEC.md first if a contract must change

---

## INIT_PROMPT
*(paste this verbatim as a fresh session's first message if the prior agent ran out of context)*

```
You are continuing work on a take-home assignment: a persona-configurable financial agent
(3 personas × 3 sectors, MCP-based tool exposure, dual interface via FastAPI + Streamlit,
Supabase-backed DB). Full contracts are in SPEC.md, phased build plan is in PLAN.md, both in
repo root. Read SPEC.md and this MEMORY.md file's "STATUS" section before doing anything else.

Rules to maintain: pure TDD (red test before implementation), Conventional Commit messages,
micro-commits (one logical change each), push after every green test run so CI validates
continuously. Do not deviate from SPEC.md without updating SPEC.md first. Do not let the agent's
system prompt hardcode any company facts — everything must come from live MCP tool calls.

Resume from "Currently doing" / "Immediate next goal" in MEMORY.md's STATUS section, then
continue down PLAN.md's phase list. Update MEMORY.md's STATUS section again before ending
this session.
```
