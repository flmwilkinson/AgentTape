"""WebSocket connection limits.

From the spec:
    - 1 connection per IP per stream (e.g. one /ws/agent/<slug> per IP)
    - 10 total connections per IP across all streams

Implemented as in-process counters keyed by (ip, stream_path) and (ip,).
Single-process state — fine for the single-replica realtime container
we deploy to. For HA we'd front the counters with Redis.

Also exposes a global ``connection_count()`` so the /admin status page
in apps/api can fetch live WS attachment numbers via /admin/stats.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class _Counters:
    # (ip, stream_key) → count. The stream key is the route path, so
    # /ws/agent/foo and /ws/agent/bar are different streams.
    per_stream: dict[tuple[str, str], int]
    per_ip: dict[str, int]
    total: int


_state = _Counters(per_stream=defaultdict(int), per_ip=defaultdict(int), total=0)
_lock = asyncio.Lock()

PER_STREAM_LIMIT = 1
PER_IP_LIMIT = 10


class WSLimitExceeded(Exception):
    pass


@asynccontextmanager
async def reserve(ip: str, stream_key: str):
    """Reserve a connection slot, yield, release on exit."""
    async with _lock:
        if _state.per_stream[(ip, stream_key)] >= PER_STREAM_LIMIT:
            raise WSLimitExceeded(
                f"per-stream limit {PER_STREAM_LIMIT} reached for {ip} on {stream_key}"
            )
        if _state.per_ip[ip] >= PER_IP_LIMIT:
            raise WSLimitExceeded(
                f"per-ip limit {PER_IP_LIMIT} reached for {ip}"
            )
        _state.per_stream[(ip, stream_key)] += 1
        _state.per_ip[ip] += 1
        _state.total += 1
    try:
        yield
    finally:
        async with _lock:
            _state.per_stream[(ip, stream_key)] -= 1
            if _state.per_stream[(ip, stream_key)] <= 0:
                del _state.per_stream[(ip, stream_key)]
            _state.per_ip[ip] -= 1
            if _state.per_ip[ip] <= 0:
                del _state.per_ip[ip]
            _state.total -= 1


def connection_count() -> dict[str, int]:
    """Snapshot for the admin stats endpoint."""
    return {
        "total": _state.total,
        "ips": len(_state.per_ip),
    }
