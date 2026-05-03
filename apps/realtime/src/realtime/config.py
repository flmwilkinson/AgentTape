from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://agenttape:agenttape@localhost:5432/agenttape"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Per-connection ring buffer size. New events are dropped (oldest-first)
    # when the queue is full and the client gets a single warning frame.
    queue_size: int = 256

    heartbeat_seconds: float = 20.0

    user_agent: str = "AgentTape-Realtime/0.0"


def get_settings() -> Settings:
    return Settings()
