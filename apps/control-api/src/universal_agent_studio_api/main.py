"""Universal Agent Studio modular control-plane application."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from temporalio.client import Client
from universal_agent_platform_store.session import (
    check_database_connectivity,
    create_engine,
    create_session_factory,
)

from universal_agent_studio_api.agents.models import AgentVersionPersistence
from universal_agent_studio_api.agents.service import (
    AgentVersionService,
    SqlAgentVersionPersistence,
)
from universal_agent_studio_api.api import (
    agent_versions,
    bootstrap,
    runs,
    session,
    workspace,
)
from universal_agent_studio_api.auth.models import AuthStore
from universal_agent_studio_api.auth.service import AuthService
from universal_agent_studio_api.auth.store import SqlAuthStore
from universal_agent_studio_api.errors import error_document, install_exception_handlers
from universal_agent_studio_api.runs.durable import DurableExecutionPort
from universal_agent_studio_api.runs.service import (
    RunPersistence,
    RunService,
    SqlRunPersistence,
)
from universal_agent_studio_api.runs.temporal_adapter import (
    TemporalDurableExecutionAdapter,
)
from universal_agent_studio_api.settings import Settings


class RequestGuardsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self._attempts: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._rate_lock = asyncio.Lock()

    async def _rate_limited(self, request: Request) -> bool:
        if request.method != "POST" or request.url.path not in {
            "/api/v1/bootstrap/owner",
            "/api/v1/session",
            "/api/v1/agent-versions/import",
            "/api/v1/runs",
        }:
            return False
        client_host = request.client.host if request.client is not None else "unknown"
        key = (client_host, request.url.path)
        now = time.monotonic()
        cutoff = now - self.settings.auth_rate_window_seconds
        async with self._rate_lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.settings.auth_rate_limit:
                return True
            attempts.append(now)
            return False

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.settings.max_request_bytes
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(
                    error_document("request_too_large"),
                    status_code=413,
                )

        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin not in self.settings.allowed_origins:
                return JSONResponse(
                    error_document("origin_not_allowed"),
                    status_code=403,
                )
            if await self._rate_limited(request):
                return JSONResponse(
                    error_document(
                        "rate_limit_exceeded",
                        retryable=True,
                    ),
                    status_code=429,
                    headers={
                        "Retry-After": str(self.settings.auth_rate_window_seconds)
                    },
                )
            if len(await request.body()) > self.settings.max_request_bytes:
                return JSONResponse(
                    error_document("request_too_large"),
                    status_code=413,
                )
        return await call_next(request)


def create_app(
    *,
    auth_store: AuthStore | None = None,
    agent_persistence: AgentVersionPersistence | None = None,
    run_persistence: RunPersistence | None = None,
    durable_execution: DurableExecutionPort | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    if (run_persistence is None) != (durable_execution is None):
        raise ValueError("run_persistence_and_durable_execution_required")
    if run_persistence is not None and agent_persistence is None:
        raise ValueError("agent_persistence_required_for_runs")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if auth_store is not None:
            app.state.auth_service = AuthService(
                auth_store,
                resolved_settings,
            )
            if agent_persistence is not None:
                app.state.agent_version_service = AgentVersionService(
                    agent_persistence,
                    max_document_bytes=resolved_settings.max_request_bytes,
                )
            if run_persistence is not None and durable_execution is not None:
                assert agent_persistence is not None
                app.state.run_service = RunService(
                    run_persistence=run_persistence,
                    agent_persistence=agent_persistence,
                    durable_execution=durable_execution,
                )
            app.state.ready = True
            try:
                yield
            finally:
                app.state.ready = False
            return

        engine = create_engine(resolved_settings.database_url.get_secret_value())
        await check_database_connectivity(engine)
        app.state.database_engine = engine
        session_factory = create_session_factory(engine)
        app.state.auth_service = AuthService(
            SqlAuthStore(session_factory),
            resolved_settings,
        )
        agent_version_persistence = SqlAgentVersionPersistence.from_factory(
            session_factory
        )
        app.state.agent_version_service = AgentVersionService(
            agent_version_persistence,
            max_document_bytes=resolved_settings.max_request_bytes,
        )
        temporal_client = await Client.connect(resolved_settings.temporal_address)
        signing_key = resolved_settings.execution_signing_key_file.read_bytes().strip()
        app.state.run_service = RunService(
            run_persistence=SqlRunPersistence(session_factory),
            agent_persistence=agent_version_persistence,
            durable_execution=TemporalDurableExecutionAdapter(
                temporal_client,
                signing_key=signing_key,
                task_queue=resolved_settings.runtime_task_queue,
            ),
        )
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            await engine.dispose()

    app = FastAPI(
        title="Universal Agent Studio Control API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.ready = auth_store is not None
    app.state.database_engine = None
    app.state.settings = resolved_settings
    if auth_store is not None:
        app.state.auth_service = AuthService(auth_store, resolved_settings)
    if agent_persistence is not None:
        app.state.agent_version_service = AgentVersionService(
            agent_persistence,
            max_document_bytes=resolved_settings.max_request_bytes,
        )
    if run_persistence is not None and durable_execution is not None:
        assert agent_persistence is not None
        app.state.run_service = RunService(
            run_persistence=run_persistence,
            agent_persistence=agent_persistence,
            durable_execution=durable_execution,
        )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=resolved_settings.allowed_hosts,
    )
    app.add_middleware(
        RequestGuardsMiddleware,
        settings=resolved_settings,
    )

    @app.middleware("http")
    async def correlate_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    install_exception_handlers(app)
    app.include_router(bootstrap.router)
    app.include_router(session.router)
    app.include_router(workspace.router)
    app.include_router(agent_versions.router)
    app.include_router(runs.router)

    @app.get("/health/live", include_in_schema=False)
    @app.get("/healthz", include_in_schema=False)
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def health_ready() -> Response:
        if not bool(app.state.ready):
            return JSONResponse({"status": "starting"}, status_code=503)
        database_engine = app.state.database_engine
        if database_engine is not None:
            try:
                await check_database_connectivity(database_engine)
            except Exception:
                return JSONResponse(
                    {"status": "not_ready"},
                    status_code=503,
                )
        return JSONResponse({"status": "ready"})

    return app


app = create_app()
