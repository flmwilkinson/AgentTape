# Deploying AgentTape

This is the minimal recipe to get a production AgentTape running. The
target stack is **Vercel + Railway + Neon + Upstash**, all sharing the
single GitHub repo. Each Python service is its own Railway service
pointing at its own Dockerfile path.

## Prerequisites

- A GitHub repo connected to Vercel and Railway.
- A [Neon](https://neon.tech) project. Use a pooled connection string
  (it ends in `?sslmode=require`).
- An [Upstash](https://upstash.com) Redis database. Use the **TLS**
  connection string (`rediss://...`) and turn off eviction — we rely
  on pub/sub durability for the tick fan-out.
- An [Anthropic](https://console.anthropic.com) API key for discovery
  enrichment + scoring narratives. Optional but recommended.
- A GitHub personal access token (`public_repo` scope) so the
  ingestion service can use the GraphQL batched-stars endpoint.

## Environment matrix

| Variable | api | realtime | discovery | ingestion | scoring | web | Source |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| `DATABASE_URL` | ✓ | ✓ | ✓ | ✓ | ✓ |   | Neon (pooled, `postgresql://`) |
| `REDIS_URL` | ✓ | ✓ | ✓ | ✓ | ✓ |   | Upstash (TLS, `rediss://`) |
| `GITHUB_TOKEN` |   |   | ✓ | ✓ |   |   | GitHub PAT |
| `HUGGINGFACE_TOKEN` |   |   | ✓ | ✓ |   |   | HF token (optional) |
| `REDDIT_CLIENT_ID` / `_SECRET` |   |   |   | ✓ |   |   | reddit.com/prefs/apps |
| `ANTHROPIC_API_KEY` |   |   | ✓ |   | ✓ |   | Anthropic console |
| `VOYAGE_API_KEY` | ✓ |   | ✓ |   |   |   | Voyage AI |
| `SEMANTIC_SCHOLAR_API_KEY` |   |   |   | ✓ |   |   | api.semanticscholar.org |
| `ADMIN_USER` / `ADMIN_PASSWORD` | ✓ |   |   |   |   |   | Random; controls /admin |
| `RATE_LIMIT_REDIS_URL` | ✓ |   |   |   |   |   | Same as `REDIS_URL` |
| `REALTIME_INTERNAL_URL` | ✓ |   |   |   |   |   | `http://realtime.railway.internal:8002` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ✓ | ✓ | ✓ | ✓ | ✓ |   | OTLP collector (optional) |
| `DEPLOY_ENV` | ✓ | ✓ | ✓ | ✓ | ✓ |   | `production` / `staging` |
| `NEXT_PUBLIC_API_URL` |   |   |   |   |   | ✓ | https://api.<your-domain> |
| `NEXT_PUBLIC_REALTIME_URL` |   |   |   |   |   | ✓ | wss://realtime.<your-domain> |

The `init_telemetry(...)` call at module import in every service
no-ops when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset, so you can ship
without an observability backend and bolt it on later.

## Railway

Five separate Railway services, all pointing at the same GitHub repo.
For each, set the **build root** to the corresponding `apps/<svc>`
path, the **Dockerfile path** to `Dockerfile`, and copy the env vars
from the matrix.

| Service | Build root | Internal port | Public? |
|---|---|:-:|:-:|
| api | `apps/api` | 8001 | yes |
| realtime | `apps/realtime` | 8002 | yes |
| discovery | `apps/discovery` | 8003 | no |
| ingestion | `apps/ingestion` | 8004 | no |
| scoring | `apps/scoring` | 8005 | no |

`discovery`, `ingestion`, and `scoring` should NOT be exposed to the
public internet — they have no auth and are not designed for inbound
traffic. Keep them on Railway's private network.

### Migrations

Run Alembic against Neon once before the first boot:

```bash
DATABASE_URL=postgresql://... uv run --with alembic --with psycopg \
  -m alembic -c apps/api/alembic.ini upgrade head
```

Subsequent migrations: add a Railway one-off command to the api service
that runs the same line, gated on a `MIGRATE=1` env var so casual
restarts don't re-attempt them.

### Cron jobs

Railway has a built-in cron scheduler. Configure these from the api
service (it has the apps/api `.venv` with everything installed):

| Schedule | Command | Purpose |
|---|---|---|
| `*/30 * * * *` | `python -m discovery.run all` | Discovery + promoter sweep |
| `* * * * *` | (handled in-process via APScheduler) | Ingestion FAST tier |
| `*/5 * * * *` | `python -m scoring.run rebalance` (only on weekly cron) | — |
| `0 3 * * 1` | `python -m scoring.run rebalance` | Weekly rebalance, Mondays 03:00 UTC |
| `@hourly` | `python -m scoring.run snapshot` | Hourly index snapshots |
| `0 0 * * 0` | `python -m scripts.launch_report` | Refresh the launch / weekly report |

The schedulers in `discovery/main.py`, `ingestion/main.py`, and
`scoring/main.py` ALSO run inside the container as APScheduler jobs.
The Railway cron entries above are the second-line defense for cases
where the long-running container restarts mid-tick.

## Vercel (apps/web)

- Project root: `apps/web`
- Framework preset: Next.js
- Install command: `pnpm install`
- Build command: `pnpm build`
- Output: handled by `next build`
- Env: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_REALTIME_URL` (must be `wss://` in prod).
- Add the production domain (`agenttape.io`) and a staging
  (`staging.agenttape.io`) at minimum.

The `pnpm build` step in `packages/shared` runs
`openapi-typescript` against the bundled `apps/api/openapi.json`. Run
`apps/api/scripts/export_openapi.py` whenever the API schema changes
and commit the regenerated `apps/api/openapi.json` so Vercel builds
the latest types.

## Neon

- Use a single Postgres instance. The schema in `apps/api/migrations`
  takes care of pgvector + the partitioned `signals` table.
- Pooled connection string for all services. Direct connection only
  for ad-hoc Alembic runs.
- Storage: at the cadence we ingest, the `signals` table grows ≈ 200K
  rows/day for 100 admitted agents. The monthly partitioning means
  storage is reclaimable by dropping old partitions when needed.

## Upstash

- TLS on. **Eviction policy: noeviction.** We rely on pub/sub
  durability for the tape ticks; LRU eviction would silently drop
  events under load.
- Rate-limit-friendly plan if you can — we publish 100s of ticks per
  minute on `events.global`.

## Smoke test

After a fresh deploy:

```bash
# Liveness
curl -fsS https://api.<domain>/health
curl -fsS https://realtime.<domain>/health

# Readiness (DB + Redis pings)
curl -fsS https://api.<domain>/ready

# REST sanity
curl -fsS https://api.<domain>/agents?limit=1

# WS roundtrip
wscat -c wss://realtime.<domain>/ws/ticker  # expect a snapshot frame within 1s

# /admin (basic auth)
curl -u "$ADMIN_USER:$ADMIN_PASSWORD" https://api.<domain>/admin/status
```

The `/admin/status` payload should show a non-zero `admitted_agents`
count and recent `last_signal_per_source` timestamps within minutes
of the deploy.

## Rollback

Every Railway service deploy is independently tagged. We do not run
schema migrations on deploy (those go through the explicit Alembic
runbook above), so a code rollback is a pure restart of the previous
image.

```bash
# Revert the bad commit on main
git revert <bad-sha> -m "rollback: <reason>"
git push origin main
```

Railway picks up the push and redeploys. For a faster path:

1. **Railway dashboard → service → Deployments → previous
   deployment → "Redeploy"**. Bypasses the build queue.
2. If the bad change included a migration, run the Alembic
   `downgrade -1` against Neon BEFORE redeploying the previous code:
   ```bash
   DATABASE_URL=postgresql://... uv run --with alembic --with psycopg \
     -m alembic -c apps/api/alembic.ini downgrade -1
   ```

Frontend rollback is one click in Vercel — every push to main
produces a new immutable deployment URL; promote any prior one to
production.

## Day-2 checklist

- Make sure `ADMIN_PASSWORD` is rotated weekly. Store it in Vercel
  env or Railway secrets, never in git.
- Set up an OTLP collector (Honeycomb, Tempo, Grafana Cloud — any) and
  point the five services at it via `OTEL_EXPORTER_OTLP_ENDPOINT`.
  Each service ships traces correlated by `service.name`; filter on
  `service.name = agenttape-discovery` to debug discovery, etc.
- Watch the `/admin/status` endpoint's `last_signal_per_source` —
  if any source's `last_at` is older than 4× its tier interval, the
  ingestor for that source is stuck.
- Run `python -m scripts.launch_report` weekly. It writes the PDF
  alongside `apps/web/public/launch-report.json` so the
  `/report/inaugural` page picks it up automatically.
