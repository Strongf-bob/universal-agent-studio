"""Async SQLAlchemy engine and session factory construction."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("database_url_must_use_postgresql_asyncpg")
    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def check_database_connectivity(engine: AsyncEngine) -> None:
    """Prove the database accepts queries before a process reports readiness."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
