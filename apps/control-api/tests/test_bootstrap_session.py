from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import MemoryAuthStore
from httpx import ASGITransport, AsyncClient
from pytest import LogCaptureFixture, mark
from universal_agent_kernel.contracts.validation import validation_codes
from universal_agent_studio_api.auth.models import SessionIdentity
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings


@mark.asyncio
async def test_owner_bootstrap_is_one_time_and_hashes_secrets(
    client: AsyncClient,
    auth_store: MemoryAuthStore,
    caplog: LogCaptureFixture,
) -> None:
    status = await client.get("/api/v1/bootstrap/status")
    assert status.json() == {"bootstrap_required": True}
    password = "correct horse battery staple"
    response = await client.post(
        "/api/v1/bootstrap/owner",
        json={
            "login_name": "owner",
            "password": password,
            "preferred_locale": "ru-RU",
        },
    )

    assert response.status_code == 201
    assert auth_store.owner is not None
    assert auth_store.owner.password_hash.startswith("$argon2id$")
    assert password not in auth_store.owner.password_hash
    completed = await client.get("/api/v1/bootstrap/status")
    assert completed.json() == {"bootstrap_required": False}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    raw_token = client.cookies.get("uas_session")
    assert raw_token is not None
    assert all(
        session.token_hash != raw_token
        for session in auth_store.sessions.values()
    )
    assert raw_token not in caplog.text
    assert password not in caplog.text
    assert "csrf_token" not in cookie.lower()

    repeated = await client.post(
        "/api/v1/bootstrap/owner",
        json={
            "login_name": "another",
            "password": "another correct horse password",
            "preferred_locale": "en-US",
        },
    )
    assert repeated.status_code == 409
    assert repeated.json()["code"] == "bootstrap_already_completed"


@mark.asyncio
async def test_login_is_generic_and_rotates_session(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
    auth_store: MemoryAuthStore,
) -> None:
    first_token, _ = bootstrapped_session
    wrong_user = await client.post(
        "/api/v1/session",
        json={"login_name": "missing", "password": "definitely not the password"},
    )
    wrong_password = await client.post(
        "/api/v1/session",
        json={"login_name": "owner", "password": "definitely not the password"},
    )
    assert wrong_user.status_code == wrong_password.status_code == 401
    assert wrong_user.json() == wrong_password.json()
    assert validation_codes(
        wrong_user.json(),
        "error-envelope.schema.json",
    ) == []

    response = await client.post(
        "/api/v1/session",
        json={
            "login_name": "owner",
            "password": "correct horse battery staple",
        },
    )
    second_token = client.cookies.get("uas_session")

    assert response.status_code == 201
    assert second_token is not None and second_token != first_token
    assert any(
        session.revoked_at is not None
        for session in auth_store.sessions.values()
    )


@mark.asyncio
async def test_expired_and_revoked_sessions_are_rejected(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
    auth_store: MemoryAuthStore,
) -> None:
    session_id, session = next(iter(auth_store.sessions.items()))
    auth_store.sessions[session_id] = SessionIdentity(
        **{
            **session.__dict__,
            "expires_at": datetime.now(UTC) - timedelta(seconds=1),
        }
    )

    assert (await client.get("/api/v1/session")).status_code == 401


@mark.asyncio
async def test_authenticated_session_rotates_csrf_on_read(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, original_csrf = bootstrapped_session

    response = await client.get("/api/v1/session")

    assert response.status_code == 200
    assert response.json()["csrf_token"] != original_csrf


@mark.asyncio
async def test_trusted_host_origin_request_limit_and_correlation(
    client: AsyncClient,
) -> None:
    bad_host = await client.get(
        "/api/v1/bootstrap/status",
        headers={"Host": "evil.example"},
    )
    bad_origin = await client.post(
        "/api/v1/bootstrap/owner",
        headers={"Origin": "https://evil.example"},
        json={
            "login_name": "owner",
            "password": "correct horse battery staple",
            "preferred_locale": "en-US",
        },
    )
    oversized = await client.post(
        "/api/v1/bootstrap/owner",
        content=b"x" * 20_000,
        headers={"Content-Type": "application/json"},
    )
    correlated = await client.get("/api/v1/bootstrap/status")

    assert bad_host.status_code == 400
    assert bad_origin.status_code == 403
    assert oversized.status_code == 413
    assert correlated.headers["x-request-id"]


@mark.asyncio
async def test_login_rate_limit_is_bounded() -> None:
    app = create_app(
        auth_store=MemoryAuthStore(),
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
            auth_rate_limit=2,
            auth_rate_window_seconds=60,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as limited_client:
        statuses: list[int] = []
        for _ in range(3):
            response = await limited_client.post(
                "/api/v1/session",
                json={
                    "login_name": "missing",
                    "password": "not the correct password",
                },
            )
            statuses.append(response.status_code)

    assert statuses == [401, 401, 429]
