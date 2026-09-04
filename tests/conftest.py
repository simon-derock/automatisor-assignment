"""Optional isolated Postgres fixture for database-backed contract tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def test_database() -> AsyncIterator[asyncpg.Connection[asyncpg.Record]]:
    """Yield a connection whose tables live in a disposable schema."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    schema_name = f"test_{uuid4().hex}"
    schema_sql = Path("src/db/schema.sql").read_text(encoding="utf-8")
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(f'CREATE SCHEMA "{schema_name}"')
        await connection.execute(f'SET search_path TO "{schema_name}"')
        await connection.execute(schema_sql)
        yield connection
    finally:
        await connection.close()
        cleanup = await asyncpg.connect(database_url)
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema_name}" CASCADE')
        finally:
            await cleanup.close()
