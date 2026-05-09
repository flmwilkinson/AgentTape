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
    max_candidates_per_run: int = 200

    # Promoter thresholds. Set to the same value so there is NO middle
    # "pending review" bucket — every candidate either admits or
    # rejects on the first promoter pass. Otherwise the bucket grows
    # without bound (no automated review process exists).
    #
    # 0.5 = "has an LLM dependency AND at least one supporting signal
    # (agent vocab / popularity / maintained / packaged)". Stricter
    # than 0.4 (LLM dep alone) so we don't admit any repo that
    # name-drops "openai" once.
    auto_admit_threshold: float = 0.5
    auto_reject_threshold: float = 0.5

    # User-Agent for outbound HTTP. Some hosts (HF, registry sites) want this.
    user_agent: str = "AgentTape-Discovery/0.0 (+https://github.com/flmwilkinson/AgentTape)"


def get_settings() -> Settings:
    return Settings()
