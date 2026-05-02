from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://agenttape:agenttape@localhost:5432/agenttape"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Optional auth — sources soft-fail without these.
    github_token: str | None = None
    huggingface_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    semantic_scholar_api_key: str | None = None

    # Tier intervals (seconds). Pulled out of code so tests can crank them down.
    fast_tier_seconds: int = 5 * 60
    medium_tier_seconds: int = 60 * 60
    slow_tier_seconds: int = 24 * 60 * 60

    # Spike threshold — emit signal_spike when new value is > this multiple of prior.
    spike_multiplier: float = 2.0

    # Manipulation thresholds.
    star_spike_24h_multiplier: float = 10.0
    min_contributors_for_organic_spike: int = 5

    user_agent: str = "AgentTape-Ingestion/0.0 (+https://github.com/flmwilkinson/AgentTape)"


def get_settings() -> Settings:
    return Settings()
