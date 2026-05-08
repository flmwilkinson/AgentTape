"""AgentTape realtime: WebSocket + SSE fan-out from Redis pub/sub.

Endpoints:
    /ws/ticker           — every event (subscribes events.global)
    /ws/agent/:slug      — events for one agent (events.agent.<slug>)
    /ws/index/:slug      — events for one index (events.index.<slug>)
    /ws/watchlist?slug=a&slug=b... — multiplex per-agent channels

    /sse/* mirrors with Server-Sent Events for clients that can't open
    a WebSocket. Same on-the-wire frames; line-prefixed by sse-starlette.

Each connection sends a snapshot frame first, then live event frames,
with periodic heartbeat frames to keep the link warm. When a client
falls behind the bounded queue, the oldest events are dropped and a
single ``warning`` frame is sent so they know.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import redis.asyncio as redis_async
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from realtime import snapshots
from realtime.connection import Connection
from realtime.db import session_factory
from realtime.limits import WSLimitExceeded, connection_count, reserve
from realtime.telemetry import init as init_telemetry

init_telemetry("agenttape-realtime")

log = logging.getLogger(__name__)

app = FastAPI(
    title="AgentTape Realtime",
    version="0.0.0",
    description="Live WebSocket + SSE fan-out from Redis pub/sub.",
)

# CORS — the SSE endpoints are accessed via fetch() from agenttape.com
# (different origin to ws.agenttape.com). WebSocket connections have
# their own Origin handshake and don't go through CORS, but the
# /sse/* mirrors do. Public read-only stream — `*` is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- meta


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "agenttape-realtime"}


@app.get("/health", tags=["meta"])
@app.get("/healthz", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "realtime"}


@app.get("/ready", tags=["meta"])
async def ready() -> dict[str, Any]:
    checks: dict[str, Any] = {"db": False, "redis": False}
    db_err = redis_err = None
    try:
        async with session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception as e:  # noqa: BLE001
        db_err = str(e)
    try:
        client = redis_async.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await client.ping()
        await client.aclose()
        checks["redis"] = True
    except Exception as e:  # noqa: BLE001
        redis_err = str(e)
    if all(checks.values()):
        return {"status": "ready", **checks}
    raise HTTPException(
        status_code=503,
        detail={
            "status": "not_ready",
            **checks,
            "db_error": db_err,
            "redis_error": redis_err,
        },
    )


# ---------------------------------------------------------------- ws


def _client_ip(websocket: WebSocket) -> str:
    # Honor X-Forwarded-For when behind Railway / a proxy; fall back to
    # the socket's remote.
    fwd = websocket.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if websocket.client:
        return websocket.client.host
    return "anonymous"


async def _enforce_limit(
    websocket: WebSocket, stream_key: str
):
    """Reserve a slot or close the socket. Returns the reserve cm or None."""
    ip = _client_ip(websocket)
    cm = reserve(ip, stream_key)
    try:
        await cm.__aenter__()
    except WSLimitExceeded as e:
        await websocket.close(code=4429, reason=str(e))
        return None
    return cm


@app.websocket("/ws/ticker")
async def ws_ticker(websocket: WebSocket) -> None:
    await websocket.accept()
    cm = await _enforce_limit(websocket, "/ws/ticker")
    if cm is None:
        return
    conn = Connection(["events.global"])
    await conn.start()
    try:
        async with session_factory()() as session:
            await websocket.send_json(await snapshots.ticker_snapshot(session))
        await _forward_ws(conn, websocket)
    except WebSocketDisconnect:
        return
    finally:
        await conn.stop()
        await cm.__aexit__(None, None, None)


@app.websocket("/ws/agent/{slug}")
async def ws_agent(websocket: WebSocket, slug: str) -> None:
    await websocket.accept()
    async with session_factory()() as session:
        snap = await snapshots.agent_snapshot(session, slug)
    if snap is None:
        await websocket.close(code=4404, reason="agent not found")
        return

    cm = await _enforce_limit(websocket, f"/ws/agent/{slug}")
    if cm is None:
        return
    conn = Connection([f"events.agent.{slug}"])
    await conn.start()
    try:
        await websocket.send_json(snap)
        await _forward_ws(conn, websocket)
    except WebSocketDisconnect:
        return
    finally:
        await conn.stop()
        await cm.__aexit__(None, None, None)


@app.websocket("/ws/index/{slug}")
async def ws_index(websocket: WebSocket, slug: str) -> None:
    await websocket.accept()
    async with session_factory()() as session:
        snap = await snapshots.index_snapshot(session, slug)
    if snap is None:
        await websocket.close(code=4404, reason="index not found")
        return

    cm = await _enforce_limit(websocket, f"/ws/index/{slug}")
    if cm is None:
        return
    conn = Connection([f"events.index.{slug}"])
    await conn.start()
    try:
        await websocket.send_json(snap)
        await _forward_ws(conn, websocket)
    except WebSocketDisconnect:
        return
    finally:
        await conn.stop()
        await cm.__aexit__(None, None, None)


@app.get("/admin/stats", tags=["admin"])
async def admin_stats() -> dict[str, Any]:
    """Internal — exposed for apps/api's /admin page to scrape WS counts."""
    return {"connections": connection_count()}


@app.websocket("/ws/watchlist")
async def ws_watchlist(websocket: WebSocket) -> None:
    """Watchlist of agent slugs sent on connect.

    Two ways to specify slugs:
    - URL query: ``/ws/watchlist?slug=foo&slug=bar``
    - First text frame: a JSON ``{"slugs": ["foo", "bar"]}`` after accept

    The query form wins when present.
    """
    await websocket.accept()
    slugs: list[str] = list(websocket.query_params.getlist("slug"))
    if not slugs:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            slugs = list((json.loads(raw) or {}).get("slugs") or [])
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.close(code=4400, reason="no slugs supplied")
            return
    if not slugs:
        await websocket.close(code=4400, reason="no slugs supplied")
        return

    channels = [f"events.agent.{s}" for s in slugs]
    conn = Connection(channels)
    await conn.start()
    try:
        async with session_factory()() as session:
            await websocket.send_json(await snapshots.watchlist_snapshot(session, slugs))
        await _forward_ws(conn, websocket)
    except WebSocketDisconnect:
        return
    finally:
        await conn.stop()


async def _forward_ws(conn: Connection, websocket: WebSocket) -> None:
    async for frame in conn.messages():
        try:
            await websocket.send_json(frame)
        except (WebSocketDisconnect, RuntimeError):
            return


# ---------------------------------------------------------------- sse


@app.get("/sse/ticker", tags=["sse"])
async def sse_ticker():
    conn = Connection(["events.global"])
    await conn.start()

    async def gen():
        try:
            async with session_factory()() as session:
                yield {
                    "event": "snapshot",
                    "data": json.dumps(await snapshots.ticker_snapshot(session)),
                }
            async for frame in conn.messages():
                yield _to_sse(frame)
        finally:
            await conn.stop()

    return EventSourceResponse(gen())


@app.get("/sse/agent/{slug}", tags=["sse"])
async def sse_agent(slug: str):
    async with session_factory()() as session:
        snap = await snapshots.agent_snapshot(session, slug)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"agent {slug!r} not found")

    conn = Connection([f"events.agent.{slug}"])
    await conn.start()

    async def gen():
        try:
            yield {"event": "snapshot", "data": json.dumps(snap)}
            async for frame in conn.messages():
                yield _to_sse(frame)
        finally:
            await conn.stop()

    return EventSourceResponse(gen())


@app.get("/sse/index/{slug}", tags=["sse"])
async def sse_index(slug: str):
    async with session_factory()() as session:
        snap = await snapshots.index_snapshot(session, slug)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"index {slug!r} not found")

    conn = Connection([f"events.index.{slug}"])
    await conn.start()

    async def gen():
        try:
            yield {"event": "snapshot", "data": json.dumps(snap)}
            async for frame in conn.messages():
                yield _to_sse(frame)
        finally:
            await conn.stop()

    return EventSourceResponse(gen())


@app.get("/sse/watchlist", tags=["sse"])
async def sse_watchlist(slug: list[str] = Query(..., min_length=1)):
    channels = [f"events.agent.{s}" for s in slug]
    conn = Connection(channels)
    await conn.start()

    async def gen():
        try:
            async with session_factory()() as session:
                yield {
                    "event": "snapshot",
                    "data": json.dumps(
                        await snapshots.watchlist_snapshot(session, slug)
                    ),
                }
            async for frame in conn.messages():
                yield _to_sse(frame)
        finally:
            await conn.stop()

    return EventSourceResponse(gen())


def _to_sse(frame: dict[str, Any]) -> dict[str, Any]:
    return {"event": frame.get("type", "event"), "data": json.dumps(frame)}
