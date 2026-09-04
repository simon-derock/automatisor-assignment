# MEMORY.md — Live State & Handoff

> Update this file at the END of every work session / phase, before committing.
> If you (the agent/assistant) are picking this project back up with no prior context,
> read `INIT_PROMPT` at the bottom first — it is self-contained.

---

## STATUS

**Last updated:** 2026-09-04
**Current phase:** Phase 1 — Data layer (complete; DB seeding pending credentials)

### ✅ Completed
- Phase 0: project metadata, dependency configuration, environment template,
  ignore rules, MIT license, CI skeleton, and pre-commit configuration added.
- Phase 0: uv lockfile generated and bootstrap quality checks are green.
- Phase 1: PostgreSQL schema added; MCP contract tests and all four initial
  domain tools are green.
- Phase 1: downloaded 503-row raw snapshots, prepared 110 filtered/joined rows,
  added 22 curated signals, and implemented the idempotent asyncpg loader.

### 🔄 Currently doing
- Phase 2: expand MCP failure-path coverage and add the agent core.

### 🎯 Immediate next goal
- `DATABASE_URL` is not configured in this workspace, so remote Supabase seeding
  has not been run. No git remote is configured, so pushes are currently unavailable.

### ⚠️ Open decisions / blockers
- The provided `.git` directory is empty, so git commits cannot currently be created
  in this workspace; source changes and `uv.lock` are present for handoff.

---

## KEY FACTS (do not re-derive — just trust these)

- Sectors locked: `tech`, `retail`, `manufacturing` (see SPEC.md §1 for GICS mapping)
- Personas locked: `mf_analyst`, `equity_analyst`, `pe_analyst` (see SPEC.md §2)
- Data source: raw CSVs from `github.com/datasets/s-and-p-500-companies` (constituents.csv +
  constituents-financials.csv), no Kaggle auth needed
- Signals table is hand-curated (~20-30 rows), lives in `data/signals_curated.json`
- MCP tools are domain-specific wrappers over `supabase-py`, NOT raw SQL passthrough — this is a
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
