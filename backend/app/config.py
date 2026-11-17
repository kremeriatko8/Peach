from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


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
    # db-f1-micro allows ~25 connections; Cloud Run max instances x (pool + overflow) must fit.
    db_pool_size: int = Field(default=5, ge=1, le=20)

    # Cloud Run + Cloud SQL: when INSTANCE_CONNECTION_NAME is set, DATABASE_URL is
    # built from these parts and points at the unix socket Cloud Run mounts at
    # /cloudsql/<project>:<region>:<instance>. DB_PASSWORD comes from Secret Manager.
    instance_connection_name: str = ""
    cloudsql_socket_dir: str = "/cloudsql"
    db_user: str = ""
    db_password: str = Field(default="", repr=False)
    db_name: str = ""
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

    @model_validator(mode="after")
    def _cloud_sql_socket_url(self) -> Settings:
        """On Cloud Run, connect through the Cloud SQL unix socket instead of TCP."""
        if self.instance_connection_name:
            if not (self.db_user and self.db_password and self.db_name):
                raise ValueError("INSTANCE_CONNECTION_NAME needs DB_USER, DB_PASSWORD and DB_NAME")
            url = URL.create(
                "postgresql+asyncpg",
                username=self.db_user,
                password=self.db_password,
                database=self.db_name,
                query={"host": f"{self.cloudsql_socket_dir}/{self.instance_connection_name}"},
            )
            self.database_url = url.render_as_string(hide_password=False)
        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
