"""Environment-backed control-plane settings."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UAS_",
        env_file=".env",
        extra="ignore",
    )

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://uas:unsafe-example@postgres/uas"
    )
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "control-api"]
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    secure_cookies: bool = False
    session_ttl_seconds: int = Field(default=43_200, ge=300, le=604_800)
    max_request_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    auth_rate_limit: int = Field(default=10, ge=1, le=1000)
    auth_rate_window_seconds: int = Field(default=60, ge=1, le=3600)
    temporal_address: str = "temporal:7233"
    runtime_task_queue: str = "uas-runtime-v1"
    session_hash_key_file: Path | None = None
    execution_signing_key_file: Path = Path("/run/secrets/uas_execution_signing_key")
    api_key_hash_key_file: Path = Path("/run/secrets/uas_api_key_hash_key")
    public_capability_key_file: Path = Path(
        "/run/secrets/uas_public_capability_key"
    )
    webhook_signing_key_file: Path = Path(
        "/run/secrets/uas_webhook_signing_key"
    )
    webhook_allowed_origins: list[str] = Field(default_factory=list)
    sse_poll_interval_seconds: float = Field(default=0.25, gt=0, le=5)
    sse_heartbeat_seconds: float = Field(default=15, gt=0, le=60)
    sse_max_polls: int = Field(default=1200, ge=1, le=100_000)
