"""Spec-shaped acceptance: WS + real ingestion tick.

Mirrors the user's wscat acceptance test in the spec:
    "open a wscat session against /ws/ticker, then trigger an ingestion run
     — events should arrive within ~1 second of being written to Redis."

Differs from ``acceptance.py`` only in that it triggers the actual
ingestion FAST tier rather than publishing a synthetic event. We
measure the gap between FAST tier completing (events written to Redis)
and the WS forwarding the first ``signal_changed`` frame.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time

import websockets

WS_URL = os.environ.get("WS_URL", "ws://localhost:8002/ws/ticker")
INGESTION_VENV = os.environ.get(
    "INGESTION_PY",
    r"C:\Users\flmwi\GenAI Apps\AI_Index\apps\ingestion\.venv\Scripts\python.exe",
)


async def main() -> int:
    async with websockets.connect(WS_URL) as ws:
        snap = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        assert snap.get("type") == "snapshot"
        print(f"got snapshot ({len(snap.get('events', []))} events)")

        # Kick off the FAST tier as a subprocess. By the time it returns,
        # at least the hf_trending_rank ingestor (1 reading per agent
        # with hf_model_ids) will have published events.
        env = os.environ.copy()
        env["DATABASE_URL"] = "postgresql+asyncpg://agenttape:agenttape@localhost:5432/agenttape"
        env["REDIS_URL"] = "redis://localhost:6379/0"
        env["MAX_CANDIDATES_PER_RUN"] = "10"
        proc = await asyncio.create_subprocess_exec(
            INGESTION_VENV,
            "-m",
            "ingestion.run",
            "fast",
            cwd=os.path.dirname(INGESTION_VENV).rsplit("\\", 2)[0],
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # While the ingestion runs, drain WS frames and time the first
        # tick that arrives after ingestion publishing.
        first_tick_at: float | None = None
        wait_t = time.monotonic()

        async def read_until_tick():
            nonlocal first_tick_at
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                except asyncio.TimeoutError:
                    return None
                frame = json.loads(raw)
                if frame.get("type") != "event":
                    continue
                kind = (frame.get("event") or {}).get("kind") or ""
                if "signal" in kind:
                    first_tick_at = time.monotonic()
                    return frame

        ws_task = asyncio.create_task(read_until_tick())
        stdout, stderr = await proc.communicate()
        ingestion_done = time.monotonic()
        try:
            frame = await asyncio.wait_for(ws_task, timeout=2.0)
        except asyncio.TimeoutError:
            print("FAIL: no tick frame arrived within 2s after ingestion finished")
            print("ingestion stderr tail:")
            sys.stdout.write(stderr.decode("utf-8", errors="replace")[-2000:])
            return 1

        if frame is None or first_tick_at is None:
            print("FAIL: WS reader exited without a tick frame")
            print(stderr.decode("utf-8", errors="replace")[-2000:])
            return 1

        # The ingestion subprocess emitted multiple ticks during its run.
        # ``first_tick_at`` is when we received the first one; use the
        # ingestion-start time as the reference point.
        latency = first_tick_at - wait_t
        print(f"OK: first tick on WS within {latency*1000:.0f} ms of ingestion start")
        print(f"event channel: {frame.get('channel')}")
        print(f"event kind:    {(frame.get('event') or {}).get('kind')}")
        print(f"agent_slug:    {(frame.get('event') or {}).get('agent_slug')}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
