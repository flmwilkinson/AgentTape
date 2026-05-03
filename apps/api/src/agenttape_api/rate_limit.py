"""REST rate limiting via slowapi.

Two tiers from the spec:
    60 requests/minute  — anonymous (no API key)
    600 requests/minute — authenticated (X-API-Key header set)

Keying is by IP for anon and by API key for auth, so a shared exit IP
doesn't mean the whole office shares a quota.

The limiter holds state in-process — fine for a single Railway replica.
For multi-replica we'd want the Upstash backend (slowapi supports the
``REDIS_URL`` strategy out of the box; switch storage_uri at deploy
time if needed).
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _key(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    return f"key:{api_key}" if api_key else f"ip:{get_remote_address(request)}"


def _rate(request: Request) -> str:
    # Authenticated callers get the higher tier.
    return "600/minute" if request.headers.get("x-api-key") else "60/minute"


limiter = Limiter(
    key_func=_key,
    default_limits=[],  # we apply per-route via decorator below
    storage_uri=os.environ.get("RATE_LIMIT_REDIS_URL"),
)


def public_rate_limit(request: Request) -> str:
    """Decorator-style limit that picks the right rate by header."""
    return _rate(request)
