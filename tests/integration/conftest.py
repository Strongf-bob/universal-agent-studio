from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from universal_agent_platform_store.models import Base, Owner, Project, Workspace
from universal_agent_platform_store.scope import RequestScope

WORKSPACE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
PROJECT_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OWNER_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def database_url_for_tests() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if url is None:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    database_name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not database_name.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must target a database ending in _test")
    return url


@pytest_asyncio.fixture
async def database_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url_for_tests())
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def database_session(
    database_engine: AsyncEngine,
) -> AsyncIterator[AsyncSession]:
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSession(database_engine, expire_on_commit=False) as session:
        session.add(
            Workspace(
                id=WORKSPACE_ID,
                slug="local",
                name="Local workspace",
            )
        )
        await session.flush()
        session.add(
            Project(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                slug="default",
                name="Default project",
            )
        )
        await session.flush()
        session.add(
            Owner(
                id=OWNER_ID,
                workspace_id=WORKSPACE_ID,
                project_id=PROJECT_ID,
                login_name="owner",
                password_hash="$argon2id$test",
                preferred_locale="ru-RU",
            )
        )
        await session.commit()
        yield session
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
def request_scope() -> RequestScope:
    return RequestScope(
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        owner_id=OWNER_ID,
    )
