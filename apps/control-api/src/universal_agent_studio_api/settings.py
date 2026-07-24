"""Environment-backed control-plane settings."""

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
