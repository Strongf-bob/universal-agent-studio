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
from universal_agent_studio_runtime.webhooks.dispatcher import (
    HttpxWebhookClient,
    SqlWebhookDeliveryStore,
    WebhookDispatcher,
)
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UAS_", extra="ignore")

    database_url: SecretStr
    temporal_address: str = "temporal:7233"
    runtime_task_queue: str = "uas-runtime-v1"
    execution_signing_key_file: Path = Path("/run/secrets/uas_execution_signing_key")
    webhook_signing_key_file: Path = Path(
        "/run/secrets/uas_webhook_signing_key"
    )
    webhook_allowed_origins: list[str] = []
    webhook_timeout_seconds: float = 3
    webhook_max_response_bytes: int = 65_536
    webhook_max_attempts: int = 5
    webhook_poll_interval_seconds: float = 1
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
    session_factory = create_session_factory(engine)
    activities = RunExecutionActivities(
        signing_key=load_signing_key(resolved.execution_signing_key_file),
        persistence=SqlRuntimePersistence(session_factory),
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
    http_client = HttpxWebhookClient()
    dispatcher = WebhookDispatcher(
        store=SqlWebhookDeliveryStore(session_factory),
        http_client=http_client,
        webhook_master=load_signing_key(
            resolved.webhook_signing_key_file
        ),
        allowed_origins=resolved.webhook_allowed_origins,
        timeout_seconds=resolved.webhook_timeout_seconds,
        max_response_bytes=resolved.webhook_max_response_bytes,
        max_attempts=resolved.webhook_max_attempts,
        poll_interval_seconds=resolved.webhook_poll_interval_seconds,
    )
    stop_dispatcher = asyncio.Event()
    try:
        resolved.readiness_file.touch(mode=0o600)
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(worker.run())
            tasks.create_task(dispatcher.run(stop_dispatcher))
    finally:
        stop_dispatcher.set()
        await http_client.close()
        resolved.readiness_file.unlink(missing_ok=True)
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
