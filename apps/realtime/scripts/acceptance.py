"""End-to-end acceptance probe.

Connects a WebSocket client to ``ws://localhost:8002/ws/ticker``, then
publishes a synthetic event to ``events.global`` directly via Redis and
times how long until the WS forwards it. Passes if the event arrives
within ``MAX_LATENCY_S`` seconds.

This mirrors the wscat test in the spec without requiring an external
CLI tool. Requires the realtime service to be running (e.g.
``uvicorn realtime.main:app --port 8002``) and the docker-compose
Postgres + Redis stack to be up.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

import redis.asyncio as redis_async
import websockets

WS_URL = os.environ.get("WS_URL", "ws://localhost:8002/ws/ticker")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
MAX_LATENCY_S = float(os.environ.get("MAX_LATENCY_S", "2.0"))


async def main() -> int:
    probe_id = uuid.uuid4().hex
    print(f"connecting {WS_URL}")
    async with websockets.connect(WS_URL) as ws:
        # First frame is always the snapshot. Drop it.
        snap = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert snap.get("type") == "snapshot", f"expected snapshot, got {snap.get('type')}"
        print(f"got snapshot ({len(snap.get('events', []))} events)")

        # Publish a probe event into events.global.
        payload = {
            "kind": "score_changed",
            "probe_id": probe_id,
            "agent_id": str(uuid.uuid4()),
            "note": "acceptance",
        }
        client = redis_async.from_url(REDIS_URL, decode_responses=True)
        publish_t = time.monotonic()
        await client.publish("events.global", json.dumps(payload))
        await client.aclose()
        print(f"published probe {probe_id} at t=0")

        # Drain frames until we see our probe.
        deadline = time.monotonic() + MAX_LATENCY_S
        while time.monotonic() < deadline:
            timeout = max(0.05, deadline - time.monotonic())
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                break
            frame = json.loads(raw)
            if frame.get("type") != "event":
                continue
            event = frame.get("event") or {}
            if event.get("probe_id") == probe_id:
                latency = time.monotonic() - publish_t
                print(f"OK: probe arrived in {latency*1000:.1f} ms")
                return 0
        print(
            f"FAIL: probe did not arrive within {MAX_LATENCY_S}s "
            f"(channel={frame.get('channel') if frame else 'n/a'})"
        )
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
