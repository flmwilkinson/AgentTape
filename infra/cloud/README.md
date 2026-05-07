# Cloud deploy — Hetzner + Neon + Vercel (~€5/mo)

The minimum viable stack to run AgentTape with your laptop closed.

| Concern                                  | Where                       | Cost     |
| ---------------------------------------- | --------------------------- | -------- |
| Backend services + Redis + Caddy ingress | Hetzner CX22 VPS            | ~€5/mo   |
| Postgres database (with auto-backups)    | Neon Free                   | €0       |
| Web frontend                             | Vercel (Hobby)              | €0       |
| Domain                                   | your existing registrar     | ~€1/mo   |
| **Total**                                |                             | **~€6**  |

No Doppler, no Backblaze, no UptimeRobot — those are graduations, not
prerequisites. Add them later when something specific hurts.

---

## 0. Rotate the secrets you leaked (5 min)

Your old `.env` was pasted into a chat transcript. **Before any of this**,
revoke and reissue every key in it. Sources:

- `GITHUB_TOKEN` → https://github.com/settings/tokens
- `HUGGINGFACE_TOKEN` → https://huggingface.co/settings/tokens
- `ANTHROPIC_API_KEY` → https://console.anthropic.com/settings/keys
- `VOYAGE_API_KEY` → https://www.voyageai.com/
- `STACKEXCHANGE_KEY` → https://stackapps.com/apps/oauth
- `BLUESKY_APP_PASSWORD` → https://bsky.app/settings/app-passwords (delete + create new)
- `PRODUCT_HUNT_TOKEN` → https://api.producthunt.com/v2/oauth/applications

Don't paste them anywhere outside the new VPS's `.env`.

## 1. Sign up — Neon, Hetzner, Vercel (~10 min)

1. **Neon** — https://console.neon.tech/signup
   - Create project: name `agenttape`, region closest to your Hetzner location.
   - Database name: `agenttape`. Copy the **pooled connection string** from
     "Connection Details" → "Pooled connection". It looks like:
     `postgresql://user:password@ep-xxx-pooler.region.aws.neon.tech/agenttape?sslmode=require`
   - In your project settings, install the `vector` extension (Neon UI →
     Extensions → search `vector` → Enable). Without this, the migration
     fails because the agents.embedding column needs pgvector.
2. **Hetzner Cloud** — https://accounts.hetzner.com/signUp
   - Verify with €1 charge.
3. **Vercel** — https://vercel.com/signup (uses your GitHub).

## 2. Provision the Hetzner VPS (~5 min)

In Hetzner Cloud Console → **Add Server**:

- Image: **Debian 12**
- Type: **CX22** (2 vCPU / 4 GB / 40 GB / €4.51 + VAT)
- Location: pick the same region as your Neon project for low latency.
- SSH keys: add yours (the `id_rsa.pub` on your laptop).
- **Cloud config (User data)**: paste the contents of
  [`cloud-init.sh`](./cloud-init.sh), edit the `SSH_PUBKEY=` line at top
  to your public key.

Click Create. ~30 seconds later, note the IPv4 address.

## 3. SSH in + clone (~3 min)

```bash
ssh deploy@<your-hetzner-ip>
cd /opt/agenttape
git clone https://github.com/flmwilkinson/AgentTape .
```

## 4. Configure secrets (~5 min)

```bash
cp infra/cloud/.env.cloud.example .env
chmod 600 .env
nano .env   # or vim
```

Paste:
- Your **Neon connection string** as `DATABASE_URL`. **Replace
  `postgresql://` with `postgresql+asyncpg://`** so SQLAlchemy uses the
  async driver. Keep `?sslmode=require` at the end.
- Your **rotated** API keys.
- Save and close.

## 5. Bring up the stack (~5 min, mostly building images)

```bash
docker compose -f infra/cloud/docker-compose.cloud.yml up -d --build
```

What happens, in order:

1. `redis` starts and reports healthy.
2. `migrate` runs `alembic upgrade head` against Neon and exits 0.
3. `api`, `realtime`, `discovery`, `ingestion`, `scoring` start and
   become healthy.
4. `caddy` starts and provisions Let's Encrypt certs as soon as DNS
   resolves.

Watch progress:

```bash
docker compose -f infra/cloud/docker-compose.cloud.yml logs -f migrate
```

When migrate exits 0, you can `Ctrl+C` and tail the api:

```bash
docker compose -f infra/cloud/docker-compose.cloud.yml logs -f api
```

## 6. DNS (~5 min, in your registrar)

Add A records pointing to the Hetzner IP:

| Host                       | Type  | Target                |
| -------------------------- | ----- | --------------------- |
| `api.agenttape.io`         | A     | `<hetzner-ip>`        |
| `ws.agenttape.io`          | A     | `<hetzner-ip>`        |
| `ingestion.agenttape.io`   | A     | `<hetzner-ip>`        |
| `scoring.agenttape.io`     | A     | `<hetzner-ip>`        |
| `discovery.agenttape.io`   | A     | `<hetzner-ip>`        |

Apex `agenttape.io` and `www.agenttape.io` will point at Vercel — set
those in step 7.

DNS propagation usually takes <5 min for new records. Caddy auto-grabs
TLS certs as soon as `api.agenttape.io` resolves to the box.

## 7. Vercel (web frontend) (~5 min)

- New project → import `flmwilkinson/AgentTape`.
- **Root Directory**: `apps/web`.
- **Environment Variables**:
  - `NEXT_PUBLIC_API_URL=https://api.agenttape.io/api`
  - `NEXT_PUBLIC_REALTIME_URL=wss://ws.agenttape.io`
- Deploy. Add `agenttape.io` and `www.agenttape.io` as custom domains
  (Vercel will tell you the exact A / CNAME records to add at your
  registrar).

## 8. Smoke test (~2 min)

From your laptop:

```bash
curl -s https://api.agenttape.io/healthz
# {"status":"ok","service":"api"}

curl -s https://api.agenttape.io/agents | head -c 200
# Should return JSON

open https://agenttape.io
# Should render the floor with live data from your new backend
```

If `/healthz` returns OK but `/agents` is empty, that's expected
until the first ingestion tick (≤5 minutes) and the first scoring run
(≤5 minutes after that).

**Close your laptop.** Stack stays up. Welcome to "real" deployment.

---

## Day-2 ops cheatsheet

```bash
# Update to latest main
ssh deploy@<ip>
cd /opt/agenttape
git pull
docker compose -f infra/cloud/docker-compose.cloud.yml up -d --build
# `migrate` runs alembic upgrade head automatically; safe to redeploy.

# Logs for one service
docker compose -f infra/cloud/docker-compose.cloud.yml logs -f api

# Force a slow-tier ingestor run (normally fires daily 03:30 UTC)
docker compose -f infra/cloud/docker-compose.cloud.yml \
  --profile cron run --rm slow-tier

# Manual database peek (Neon dashboard usually easier)
docker compose -f infra/cloud/docker-compose.cloud.yml exec api \
  python -c "import os; print(os.environ['DATABASE_URL'])"

# Status of the daily slow-tier timer
sudo systemctl list-timers agenttape-*
sudo journalctl -u agenttape-slow-tier --since today
```

## When to graduate

Add the next thing only when something specifically hurts:

- **"I'm worried about leaking secrets"** → install Doppler, point compose's `env_file` at `doppler run`.
- **"I lost data once"** → Neon's auto-backups should cover this; if you've outgrown the free tier and don't want their paid backups, switch on Hetzner volume snapshots (€0.50/mo).
- **"It went down for an hour and I didn't notice"** → UptimeRobot free tier, one HTTP check per `/healthz`.
- **"VPS RAM is full"** → resize CX22 → CX32 (€10/mo, one-click, no migration).
- **"500 MB Neon free is full"** → Neon paid (€19/mo for 10 GB), or move Postgres to Hetzner managed.
