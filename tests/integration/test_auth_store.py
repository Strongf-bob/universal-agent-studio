from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from universal_agent_platform_store.models import Base, Session
from universal_agent_platform_store.session import create_session_factory
from universal_agent_studio_api.auth.service import AuthService
from universal_agent_studio_api.auth.store import SqlAuthStore
from universal_agent_studio_api.settings import Settings


async def test_sql_auth_store_hashes_session_and_deletes_workspace(
    database_engine: AsyncEngine,
) -> None:
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    store = SqlAuthStore(create_session_factory(database_engine))
    service = AuthService(store, Settings(secure_cookies=False))
    material = await service.bootstrap(
        login_name="owner",
        password="correct horse battery staple",
        preferred_locale="en-US",
    )

    async with store.session_factory() as session:
        stored_hash = await session.scalar(select(Session.token_hash))
    assert stored_hash is not None
    assert stored_hash != material.raw_session_token
    authenticated = await service.authenticate(material.raw_session_token)
    assert authenticated is not None

    await service.delete_workspace(
        authenticated,
        current_password="correct horse battery staple",
        confirmation="DELETE LOCAL WORKSPACE",
    )
    async with store.session_factory() as session:
        remaining = await session.scalar(select(func.count(Session.id)))
    assert remaining == 0
