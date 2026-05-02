from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="AgentTape Realtime", version="0.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "realtime"}


@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        return
