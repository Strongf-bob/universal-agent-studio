"""Password, opaque-session and CSRF security services."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from universal_agent_studio_api.auth.models import (
    AuthenticatedOwner,
    AuthStore,
    OwnerIdentity,
    SessionMaterial,
)
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.settings import Settings

DELETE_CONFIRMATION = "DELETE LOCAL WORKSPACE"


def _hash_token(value: str, key: bytes | None) -> str:
    if key is None:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


class AuthService:
    def __init__(
        self,
        store: AuthStore,
        settings: Settings,
        *,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.password_hasher = password_hasher or PasswordHasher()
        self._session_hash_key = self._load_session_hash_key(
            settings.session_hash_key_file
        )
        self._dummy_password_hash = self.password_hasher.hash(
            "unusable timing equalization password"
        )

    @staticmethod
    def _load_session_hash_key(path: Path | None) -> bytes | None:
        if path is None:
            return None
        key = path.read_bytes().strip()
        if len(key) < 32:
            raise ValueError("session_hash_key_too_short")
        return key

    def _hash_token(self, value: str) -> str:
        return _hash_token(value, self._session_hash_key)

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)

    async def bootstrap_status(self) -> bool:
        return await self.store.bootstrap_status()

    async def bootstrap(
        self,
        *,
        login_name: str,
        password: str,
        preferred_locale: str,
    ) -> SessionMaterial:
        password_hash = self.password_hasher.hash(password)
        owner = await self.store.bootstrap_owner(
            login_name=login_name,
            password_hash=password_hash,
            preferred_locale=preferred_locale,
        )
        if owner is None:
            raise ApiError(409, "bootstrap_already_completed")
        return await self._new_session(owner)

    def _password_matches(self, password_hash: str, password: str) -> bool:
        try:
            return self.password_hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError):
            return False

    async def login(
        self,
        *,
        login_name: str,
        password: str,
        current_token: str | None,
    ) -> SessionMaterial:
        owner = await self.store.owner_by_login(login_name)
        password_hash = (
            owner.password_hash if owner is not None else self._dummy_password_hash
        )
        matches = self._password_matches(password_hash, password)
        if owner is None or not matches:
            raise ApiError(401, "authentication_failed")
        if current_token is not None:
            current = await self.authenticate(current_token, required=False)
            if current is not None:
                await self.store.revoke_session(
                    current.session.id,
                    self.now(),
                )
        return await self._new_session(owner)

    async def _new_session(self, owner: OwnerIdentity) -> SessionMaterial:
        raw_session_token = secrets.token_urlsafe(32)
        raw_csrf_token = secrets.token_urlsafe(32)
        session = await self.store.create_session(
            owner=owner,
            token_hash=self._hash_token(raw_session_token),
            csrf_token_hash=self._hash_token(raw_csrf_token),
            expires_at=self.now()
            + timedelta(seconds=self.settings.session_ttl_seconds),
        )
        return SessionMaterial(
            owner=owner,
            session=session,
            raw_session_token=raw_session_token,
            raw_csrf_token=raw_csrf_token,
        )

    async def authenticate(
        self,
        raw_session_token: str | None,
        *,
        required: bool = True,
    ) -> AuthenticatedOwner | None:
        if raw_session_token is None:
            if required:
                raise ApiError(401, "authentication_failed")
            return None
        result = await self.store.session_with_owner(
            self._hash_token(raw_session_token)
        )
        if result is None:
            if required:
                raise ApiError(401, "authentication_failed")
            return None
        session, owner = result
        if session.revoked_at is not None or session.expires_at <= self.now():
            if required:
                raise ApiError(401, "authentication_failed")
            return None
        return AuthenticatedOwner(owner=owner, session=session)

    async def rotate_csrf(
        self,
        authenticated: AuthenticatedOwner,
    ) -> str:
        raw_csrf_token = secrets.token_urlsafe(32)
        session = await self.store.update_session_csrf(
            authenticated.session.id,
            self._hash_token(raw_csrf_token),
        )
        if session.revoked_at is not None:
            raise ApiError(401, "authentication_failed")
        return raw_csrf_token

    def require_csrf(
        self,
        authenticated: AuthenticatedOwner,
        raw_csrf_token: str | None,
    ) -> None:
        if raw_csrf_token is None or not hmac.compare_digest(
            authenticated.session.csrf_token_hash,
            self._hash_token(raw_csrf_token),
        ):
            raise ApiError(403, "csrf_validation_failed")

    async def logout(self, authenticated: AuthenticatedOwner) -> None:
        await self.store.revoke_session(
            authenticated.session.id,
            self.now(),
        )

    async def delete_workspace(
        self,
        authenticated: AuthenticatedOwner,
        *,
        current_password: str,
        confirmation: str,
    ) -> None:
        if confirmation != DELETE_CONFIRMATION:
            raise ApiError(400, "confirmation_mismatch")
        if not self._password_matches(
            authenticated.owner.password_hash,
            current_password,
        ):
            raise ApiError(401, "authentication_failed")
        await self.store.delete_workspace(authenticated.owner.workspace_id)
