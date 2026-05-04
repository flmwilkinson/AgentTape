from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://agenttape:agenttape@localhost:5432/agenttape"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Optional Claude for rebalance narratives.
    anthropic_api_key: str | None = None

    # Debounce — each agent recomputes at most once every N seconds even if
    # 50 signals change in that window.
    recompute_debounce_seconds: int = 60

    # Index snapshots cron — hourly per spec.
    snapshot_interval_seconds: int = 60 * 60

    # Heartbeat recompute — runs the full agent population at this
    # cadence so foundation models (and any agent without ingestion
    # events) get fresh score rows. Hourly is plenty: scoring is
    # cheap and the chart granularity already maxes at hour buckets.
    heartbeat_recompute_seconds: int = 60 * 60

    # Pillar weights (sum to 1.0).
    weight_adoption: float = 0.35
    weight_quality: float = 0.30
    weight_momentum: float = 0.20
    weight_community: float = 0.15

    user_agent: str = "AgentTape-Scoring/0.0"


def get_settings() -> Settings:
    return Settings()
