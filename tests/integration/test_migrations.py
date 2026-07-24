from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from universal_agent_platform_store.models import Base

from tests.integration.conftest import database_url_for_tests

ROOT = Path(__file__).parents[2]
EXPECTED_TABLES = {
    "agent_active_versions",
    "agent_versions",
    "agents",
    "node_executions",
    "owners",
    "projects",
    "run_events",
    "run_requests",
    "run_traces",
    "runs",
    "sessions",
    "tool_invocations",
    "workspaces",
}


@pytest.mark.asyncio
async def test_empty_database_migrates_to_head() -> None:
    url = database_url_for_tests()
    config = Config(str(ROOT / "infra" / "migrations" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    cleanup_engine = create_async_engine(url)
    try:
        async with cleanup_engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        await cleanup_engine.dispose()

    await asyncio.to_thread(command.upgrade, config, "head")

    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
    finally:
        await engine.dispose()

    assert EXPECTED_TABLES <= tables
    await asyncio.to_thread(command.downgrade, config, "base")
