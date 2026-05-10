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

    # Index snapshot + heartbeat cadence. Aligned with ingestion FAST
    # tier (5 min) so every visible surface — sectors, indexes,
    # models, agents — refreshes on the same clock. The user-facing
    # promise is "ticking every 5 minutes"; nothing should be lying.
    # Foundation models still produce flat lines between metadata
    # changes (their score is derived from OpenRouter facts, not
    # ingestion signals) but you'll see the timestamp advance.
    snapshot_interval_seconds: int = 5 * 60
    heartbeat_recompute_seconds: int = 5 * 60

    # Pillar weights are entity-kind specific. Applications and
    # foundation models have different "what makes them good" profiles:
    #
    #   • Apps win on real-world adoption + community investment
    #     (npm/PyPI installs, contributors, forks, MCP listings).
    #     Benchmarks rarely apply, momentum is hype-prone.
    #   • Foundation models win on benchmarks (Quality) and how widely
    #     they power other tools (Adoption, including
    #     github_repos_using_model). Community is real but secondary.
    #
    # Both sets sum to 1.0 so headline scores stay on the 0-100 scale.
    # Keeping a single set used to penalise mature apps that don't have
    # benchmark coverage and reward newer projects with momentum noise.
    weight_app_adoption: float = 0.40
    weight_app_quality: float = 0.20
    weight_app_momentum: float = 0.10
    weight_app_community: float = 0.30

    weight_fm_adoption: float = 0.30
    weight_fm_quality: float = 0.40
    weight_fm_momentum: float = 0.10
    weight_fm_community: float = 0.20

    # Legacy single-set weights — kept as a fallback for any callers
    # that still want a single number (eg. unit tests). Prefer the
    # entity-kind specific fields above.
    weight_adoption: float = 0.35
    weight_quality: float = 0.30
    weight_momentum: float = 0.20
    weight_community: float = 0.15

    user_agent: str = "AgentTape-Scoring/0.0"


def get_settings() -> Settings:
    return Settings()
