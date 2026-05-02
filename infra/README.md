# Infra

Local stack and notes on hosting AgentTape in production.

## Local

```
make dev    # postgres + redis + api + realtime + discovery + ingestion + scoring
make web    # Next.js on :3000 (run separately on host)
```

Health endpoints:

| Service     | URL                                |
|-------------|------------------------------------|
| api         | http://localhost:8001/health       |
| realtime    | http://localhost:8002/health (ws @ /ws) |
| discovery   | http://localhost:8003/health       |
| ingestion   | http://localhost:8004/health       |
| scoring     | http://localhost:8005/health       |

## Production hosting

The intended split:

| Concern               | Host        | Notes                                                              |
|-----------------------|-------------|--------------------------------------------------------------------|
| `apps/web`            | **Vercel**  | Next.js 15 App Router. Reads `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_REALTIME_URL`. |
| `apps/api`            | **Railway** | Stateless. Scales horizontally. Exposes the public REST + OpenAPI spec. |
| `apps/realtime`       | **Railway** | Sticky-less; subscribes to Redis pub/sub and fans out to WS/SSE clients. Scale on connection count. |
| `apps/discovery`      | **Railway** | Long-lived worker. Single replica is fine; idempotent admission keyed by `(source, source_id)`. |
| `apps/ingestion`      | **Railway** | Cron-like worker running fast/medium/slow tiers. Single replica per tier. |
| `apps/scoring`        | **Railway** | Pulls from Redis stream, writes to Postgres, publishes ticks. Horizontally scalable by partition. |
| Postgres              | **Neon**    | Serverless Postgres. Use a pooled connection string for API + workers. |
| Redis (pub/sub + queue) | **Upstash** | Global Redis. Use the TLS connection string. The realtime fan-out is the hot path. |

### Env vars expected in production

```
DATABASE_URL=...        # Neon pooled connection
REDIS_URL=...           # Upstash TLS URL (rediss://)
GITHUB_TOKEN=...        # discovery + ingestion (GitHub signals)
HF_TOKEN=...            # discovery + ingestion (Hugging Face)
SENTRY_DSN=...          # all services (optional)
```

### Notes
- Railway one service per repo path; point each to its `apps/<svc>/Dockerfile`.
- Vercel project root: `apps/web` with `pnpm` install; the workspace root is detected automatically.
- Neon: enable pooled endpoint for API; workers can use direct.
- Upstash: turn on **TLS** + **eviction off** (we rely on pub/sub durability for ticks via streams).
