import type { NextRequest } from "next/server";
import { api } from "@/lib/api-client";

// Embeddable SVG badge for an agent. Authors put
//   ![AgentTape](https://agenttape.io/api/badge/<slug>.svg)
// on their README and get a live "Featured on AgentTape · Score X ·
// Rank #N" pill. Cacheable for an hour so the badge endpoint doesn't
// hammer our API per page view from third-party traffic.

export const runtime = "edge";
export const revalidate = 3600;

interface RouteParams {
  params: Promise<{ slug: string }>;
}

const PRIMARY = "#2563eb";
const FOREGROUND = "#0f172a";
const BACKGROUND = "#ffffff";
const MUTED = "#64748b";

export async function GET(_req: NextRequest, { params }: RouteParams) {
  const raw = (await params).slug;
  // Allow ".svg" suffix in the URL: /api/badge/foo.svg → slug "foo".
  const slug = raw.replace(/\.svg$/i, "");

  const agent = await api.getAgent(slug).catch(() => null);

  const score = agent?.score?.agent_score ?? null;
  const rank = agent?.score?.rank_now ?? null;
  const name = agent?.name ?? slug;

  const headline = `AgentTape · Score ${score == null ? "—" : score.toFixed(1)}`;
  const tail = rank == null ? name : `${name} · #${rank}`;

  const safe = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Width auto-grows to fit the longer of the two lines, capped.
  const width = Math.min(
    420,
    80 + Math.max(headline.length, tail.length) * 6.5,
  );
  const height = 64;

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${safe(headline)} — ${safe(tail)}">
  <rect width="${width}" height="${height}" rx="6" fill="${BACKGROUND}" stroke="#e2e8f0" />
  <rect x="0" y="0" width="6" height="${height}" rx="6 0 0 6" fill="${PRIMARY}" />
  <g font-family="ui-monospace, 'JetBrains Mono', monospace, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif">
    <text x="20" y="22" font-size="11" font-weight="600" letter-spacing="1.4" fill="${MUTED}">AGENTTAPE</text>
    <text x="20" y="42" font-size="14" font-weight="600" fill="${FOREGROUND}">${safe(name)}</text>
    <text x="20" y="56" font-size="11" fill="${MUTED}">${safe(`Score ${score == null ? "—" : score.toFixed(1)}${rank == null ? "" : ` · Rank #${rank}`}`)}</text>
  </g>
</svg>`;

  return new Response(svg, {
    headers: {
      "Content-Type": "image/svg+xml; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
