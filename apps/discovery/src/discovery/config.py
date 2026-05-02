from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://agenttape:agenttape@localhost:5432/agenttape"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Optional API tokens. Scouts work without them but with lower rate limits.
    github_token: str | None = None
    huggingface_token: str | None = None

    # Optional enrichment. Promoter degrades to rule-only if these are absent.
    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None

    # Dev throttle. The scouts cap at this many candidates per run so a wild
    # GitHub query doesn't dump 10k rows into the holding pen.
    max_candidates_per_run: int = 100

    # Promoter thresholds.
    auto_admit_threshold: float = 0.6
    auto_reject_threshold: float = 0.4

    # User-Agent for outbound HTTP. Some hosts (HF, registry sites) want this.
    user_agent: str = "AgentTape-Discovery/0.0 (+https://github.com/flmwilkinson/AgentTape)"


def get_settings() -> Settings:
    return Settings()
