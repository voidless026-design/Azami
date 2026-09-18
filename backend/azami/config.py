"""Application configuration.

Everything is env-configurable. The defaults are chosen so the backend runs with
zero external services (SQLite, in-process job execution, in-memory rate limiting).
Set the production values to switch to Postgres / Redis / Celery / Docker runners.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "backend" / ".azami_data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZAMI_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Azami"
    environment: str = Field(default="development")  # development | production

    # --- Storage -----------------------------------------------------------
    # Default: local SQLite file. Production: e.g. postgresql+psycopg://user:pw@host/azami
    database_url: str = Field(default=f"sqlite:///{DEFAULT_DATA_DIR / 'azami.db'}")
    data_dir: Path = Field(default=DEFAULT_DATA_DIR)

    # --- Auth --------------------------------------------------------------
    jwt_secret: str = Field(default="dev-insecure-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    # A default admin is created on first boot so the app is usable immediately.
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "changeme"

    # --- Authorization -----------------------------------------------------
    # Production MUST keep this False: scopes must carry a valid signature.
    # For local development you may set it True to load unsigned scope files;
    # such engagements are flagged signature_verified=False and audited as such.
    allow_unsigned_scopes: bool = Field(default=True)

    # --- Execution ---------------------------------------------------------
    runner_backend: str = Field(default="local")  # local | docker | remote
    remote_runner_url: str | None = None
    max_global_concurrency: int = 4
    job_timeout_seconds: int = 900

    # --- Rate limiting -----------------------------------------------------
    ratelimit_backend: str = Field(default="memory")  # memory | redis
    redis_url: str | None = None

    # --- Wordlists ---------------------------------------------------------
    wordlists_dir: Path = Field(default=DEFAULT_DATA_DIR / "wordlists")
    wordlist_catalog: Path = Field(default=REPO_ROOT / "data_sources" / "wordlists.catalog.yaml")

    # --- API ---------------------------------------------------------------
    cors_origins: list[str] = Field(default=["http://localhost:5173", "tauri://localhost"])

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.wordlists_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
