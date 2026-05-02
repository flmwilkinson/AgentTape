# AgentTape

A live, autonomously-populated stock-index-style tracker for AI agents.

We do **not** seed agents manually. The `discovery` service continuously scans
GitHub, Hugging Face, MCP registries, package managers, arXiv, and Hacker News
and admits new agents automatically. Signals (stars, downloads, benchmarks,
mentions) are pulled on a tiered cadence and streamed to the UI over WebSockets
so the index "ticks" in near real-time.

## Layout

```
apps/
  web/         Next.js 15 (App Router, Tailwind, shadcn/ui)
  api/         FastAPI public API
  realtime/    FastAPI WebSocket + SSE fan-out
  discovery/   Continuous source scanner (admits new agents)
  ingestion/   Tiered signal scheduler (fast / medium / slow)
  scoring/     Recomputes scores + index membership
packages/
  shared/      TS types generated from the API OpenAPI spec
infra/
  docker-compose.yml
  README.md    Hosting notes (Vercel + Railway + Neon + Upstash)
docs/
  architecture.md
```

## Getting started

Prereqs: `pnpm`, `uv`, Docker, GNU `make`.

```
make install   # JS + Python deps
make dev       # bring up Postgres, Redis, all 5 Python services
cd apps/web && pnpm dev
```

See [docs/architecture.md](docs/architecture.md) for design.
