"""Bounded resumable Server-Sent Events stream."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Request
from universal_agent_kernel.contracts.canonical import canonicalize
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.runs.service import (
    TERMINAL_EVENTS,
    TERMINAL_STATUSES,
    RunService,
)


def encode_sse_event(document: dict[str, object]) -> bytes:
    sequence = int(str(document["sequence"]))
    event_type = str(document["type"])
    data = canonicalize(document).decode("utf-8")
    return f"id: {sequence}\nevent: {event_type}\ndata: {data}\n\n".encode()


async def stream_run_events(
    *,
    request: Request,
    service: RunService,
    scope: RequestScope,
    run_id: UUID,
    after_sequence: int,
    poll_interval_seconds: float,
    heartbeat_seconds: float,
    max_polls: int,
) -> AsyncIterator[bytes]:
    cursor = after_sequence
    last_write = time.monotonic() - heartbeat_seconds
    for _ in range(max_polls):
        if await request.is_disconnected():
            return
        events = await service.list_events(
            run_id,
            scope,
            after_sequence=cursor,
        )
        for event in events:
            cursor = int(event["sequence"])
            yield encode_sse_event(event)
            last_write = time.monotonic()
            if str(event["type"]) in TERMINAL_EVENTS:
                return
        run = await service.get_run(run_id, scope)
        if run.status in TERMINAL_STATUSES:
            return
        if time.monotonic() - last_write >= heartbeat_seconds:
            yield b": heartbeat\n\n"
            last_write = time.monotonic()
        await asyncio.sleep(poll_interval_seconds)
