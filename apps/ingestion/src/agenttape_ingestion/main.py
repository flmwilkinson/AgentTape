from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="AgentTape Ingestion", version="0.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
