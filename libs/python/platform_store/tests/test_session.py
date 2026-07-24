from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from universal_agent_platform_store.session import check_database_connectivity


class _Connection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: object) -> None:
        self.statements.append(str(statement))


class _ConnectionContext:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _Connection:
        return self.connection

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def connect(self) -> _ConnectionContext:
        return _ConnectionContext(self.connection)


@pytest.mark.asyncio
async def test_database_connectivity_executes_a_real_probe() -> None:
    connection = _Connection()
    engine = cast(AsyncEngine, _Engine(connection))

    await check_database_connectivity(engine)

    assert connection.statements == ["SELECT 1"]
