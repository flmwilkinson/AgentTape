# AgentTape architecture

## No seed list

AgentTape's product is *autonomous discovery* of AI agents — not a curated
catalog. A seed list would bias the index toward whatever the maintainers
already knew; the value proposition is the opposite: surface things you
haven't heard of yet, the moment they start to matter. The `discovery`
service continuously sweeps GitHub, Hugging Face, MCP registries, package
managers (npm/PyPI), arXiv, and Hacker News. Candidates that pass
admission criteria go straight into the live index. `make seed` is
deliberately a no-op so nobody gets in the habit of hand-feeding it.

## Three ingestion tiers

Once an agent is admitted, signals refresh on a tiered cadence to balance
freshness against rate limits:

- **fast (~30s)** — mention velocity (HN, X, Discord), live download
  counters, trending API hits. Drives the "ticker" feel.
- **medium (~5–15min)** — GitHub stars/forks/issues, Hugging Face
  downloads, npm/PyPI weekly counts. Most index movement comes from here.
- **slow (~6–24h)** — benchmark scores, release notes, dependency graph,
  README diffs. Heavy queries, only worth running periodically.

Each tier is its own scheduler inside `ingestion`, so a slow benchmark
refresh can never starve the fast tape.

## Redis pub/sub fan-out

Workers never push to clients directly. `ingestion` and `scoring` publish
JSON ticks to Redis channels (`tape:ticks`, `tape:index`, `tape:admissions`).
`realtime` subscribes once per replica, multiplexes onto open WebSocket /
SSE connections, and applies per-client backpressure. Write rate is
decoupled from connection count: 100k viewers cost the workers nothing,
and `realtime` scales on connection load alone.

## Separate services

`discovery`, `ingestion`, and `scoring` have **independent failure modes**
and **independent scaling axes**. Discovery is bursty and network-bound;
ingestion is bound by per-source rate limits and scales by partitioning
sources; scoring is CPU-bound and read-heavy on Postgres. Splitting them
lets each one fail, restart, and scale on its own terms.
