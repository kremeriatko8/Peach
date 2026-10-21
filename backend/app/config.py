from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced entirely from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Peach API"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "info"

    cognito_authority: str = ""
    cognito_client_id: str = ""
    cognito_jwks_json: str = ""

    parser_model: str = "amazon.nova-lite-v1:0"
    parser_max_tokens: int = Field(default=2048, ge=128, le=4096)
    parser_enabled: bool = False
    parser_requests_per_minute: int = Field(default=3, ge=1, le=10)
    parser_input_usd_per_million: float | None = Field(default=None, gt=0)
    parser_output_usd_per_million: float | None = Field(default=None, gt=0)

    database_url: str = "postgresql+asyncpg://peach:peach@db:5432/peach"
    # Off on Lambda: a warm but idle execution environment would otherwise hold
    # pooled connections open, and Aurora Serverless only pauses at zero.
    db_pooling: bool = True
    # NoDecode keeps pydantic-settings from JSON-parsing the env value, so the
    # validator below can accept the comma-separated form Compose passes.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string, since that is how Compose passes it."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
