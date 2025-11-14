from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    database_url: str = Field(
        default="sqlite:///./chat.db",
        description="SQLAlchemy connection string.",
    )
    secret_key: str = Field(
        default="change-me",
        description="Secret key used to sign JWT tokens.",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=120, ge=5, le=24 * 60)
    encryption_key: str | None = Field(
        default=None,
        description="Fernet key for encrypting message content.",
    )
    media_directory: Path = Field(
        default=Path(__file__).resolve().parents[2] / "media",
        description="Filesystem directory for user-uploaded media.",
    )
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Origins allowed to access the API.",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("media_directory", mode="before")
    @classmethod
    def ensure_media_directory(cls, value: str | Path) -> Path:
        path = Path(value).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolved_encryption_key(self) -> bytes:
        """Return a usable encryption key, generating and persisting one if needed."""
        if self.encryption_key:
            return self.encryption_key.encode("utf-8")

        key_path = Path(".fernet_key")
        if key_path.exists():
            key_text = key_path.read_text(encoding="utf-8").strip()
            self.encryption_key = key_text
            return key_text.encode("utf-8")

        new_key = Fernet.generate_key()
        key_path.write_text(new_key.decode("utf-8"), encoding="utf-8")
        self.encryption_key = new_key.decode("utf-8")
        return new_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Provide a cached settings instance."""
    return Settings()


