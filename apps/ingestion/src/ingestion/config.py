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
    # Semantic Scholar gates personal email; OpenAlex is the equivalent
    # open replacement and only wants a contact mailto. Either or both
    # may be set — the citation ingestor prefers OpenAlex when present.
    semantic_scholar_api_key: str | None = None
    openalex_mailto: str | None = None
    # Stack Overflow public read works without auth at low rate. A
    # free key lifts the daily quota from 300 → 10,000.
    stackexchange_key: str | None = None
    # Product Hunt: optional. If unset the ingestor soft-skips. Token
    # comes from a free OAuth app at api.producthunt.com.
    product_hunt_token: str | None = None
    # Bluesky: optional. The public search API recently went auth-only.
    # Use your account handle (e.g. "you.bsky.social") and an app
    # password from https://bsky.app/settings/app-passwords (NOT your
    # main login password). Soft-skips if either is missing.
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None

    # Tier intervals (seconds). Pulled out of code so tests can crank them down.
    # Originally fast=5min/medium=1h/slow=24h; with ~700 admitted agents
    # and a 512 MB Neon limit, the 5-min cadence on the fast tier
    # filled the database in 11 days. Bumped the floor to 1 hour
    # across the board — combined with insert-on-change dedupe in
    # base.py, this keeps signals + scores growth in the low-MB-per-
    # day range. Override via env (FAST_TIER_SECONDS=900 etc.) when
    # the DB has headroom for tighter cadence.
    fast_tier_seconds: int = 60 * 60
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
