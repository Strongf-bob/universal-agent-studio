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
from universal_agent_platform_store.session import (
    create_engine,
    create_session_factory,
)

from universal_agent_studio_api.agents.models import AgentVersionPersistence
from universal_agent_studio_api.agents.service import (
    AgentVersionService,
    SqlAgentVersionPersistence,
)
from universal_agent_studio_api.api import agent_versions, bootstrap, session, workspace
from universal_agent_studio_api.auth.models import AuthStore
from universal_agent_studio_api.auth.service import AuthService
from universal_agent_studio_api.auth.store import SqlAuthStore
from universal_agent_studio_api.errors import error_document, install_exception_handlers
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
                        "Retry-After": str(
                            self.settings.auth_rate_window_seconds
                        )
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
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()

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
            yield
            return

        engine = create_engine(resolved_settings.database_url.get_secret_value())
        session_factory = create_session_factory(engine)
        app.state.auth_service = AuthService(
            SqlAuthStore(session_factory),
            resolved_settings,
        )
        app.state.agent_version_service = AgentVersionService(
            SqlAgentVersionPersistence.from_factory(session_factory),
            max_document_bytes=resolved_settings.max_request_bytes,
        )
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Universal Agent Studio Control API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    if auth_store is not None:
        app.state.auth_service = AuthService(auth_store, resolved_settings)
    if agent_persistence is not None:
        app.state.agent_version_service = AgentVersionService(
            agent_persistence,
            max_document_bytes=resolved_settings.max_request_bytes,
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

    @app.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
