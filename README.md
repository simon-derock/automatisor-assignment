# Persona-Configurable Financial Agent

This project is a persona-configurable financial analysis agent for the
`tech`, `retail`, and `manufacturing` sectors. The implementation follows the
contracts in [SPEC.md](SPEC.md) and the phased build plan in [PLAN.md](PLAN.md).

## Status

Bootstrap is complete. The data, MCP server, agent, API, and Streamlit UI
will be added phase by phase.

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
