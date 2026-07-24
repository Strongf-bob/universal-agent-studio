"""Runtime worker process entrypoint."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from temporalio.client import Client
from temporalio.worker import Worker
from universal_agent_platform_store.session import (
    check_database_connectivity,
    create_engine,
    create_session_factory,
)

from universal_agent_studio_runtime.activities.events import SqlRuntimePersistence
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UAS_", extra="ignore")

    database_url: SecretStr
    temporal_address: str = "temporal:7233"
    runtime_task_queue: str = "uas-runtime-v1"
    execution_signing_key_file: Path = Path("/run/secrets/uas_execution_signing_key")
    readiness_file: Path = Path("/tmp/uas-worker-ready")
    deterministic_delay_ms: int = 0


def load_signing_key(path: Path) -> bytes:
    key = path.read_bytes().strip()
    if len(key) < 32:
        raise ValueError("execution_signing_key_too_short")
    return key


async def run_worker(settings: RuntimeSettings | None = None) -> None:
    resolved = settings or RuntimeSettings()  # type: ignore[call-arg]
    client = await Client.connect(resolved.temporal_address)
    engine = create_engine(resolved.database_url.get_secret_value())
    await check_database_connectivity(engine)
    activities = RunExecutionActivities(
        signing_key=load_signing_key(resolved.execution_signing_key_file),
        persistence=SqlRuntimePersistence(create_session_factory(engine)),
        deterministic_delay_seconds=resolved.deterministic_delay_ms / 1000,
    )
    worker = Worker(
        client,
        task_queue=resolved.runtime_task_queue,
        workflows=[AgentRunWorkflow],
        activities=[
            activities.execute_run,
            activities.finalize_cancelled_run,
            activities.finalize_failed_run,
        ],
    )
    try:
        resolved.readiness_file.touch(mode=0o600)
        await worker.run()
    finally:
        resolved.readiness_file.unlink(missing_ok=True)
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
