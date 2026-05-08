import { api } from "@/lib/api-client";

// RSS feed of the past 7 days' biggest movers. Lightweight
// subscription channel that doesn't require any account
// infrastructure on our side — readers point a feed reader at
// /rss/trending.xml and they get pinged whenever a new agent
// climbs (or falls) by enough to enter the top of the movers list.

export const revalidate = 600;  // refresh server cache every 10 min

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.com";

function escape(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export async function GET() {
  const movers = await api.movers("7d", 25).catch(() => []);
  const now = new Date().toUTCString();

  const items = movers
    .map((m) => {
      const direction = m.delta >= 0 ? "climbed" : "fell";
      const magnitude = Math.abs(m.delta).toFixed(1);
      const title =
        `${m.agent.name} ${direction} ${magnitude} points to ${m.score_now.toFixed(1)}`;
      const link = `${SITE}/agents/${m.agent.slug}`;
      const description =
        `${m.agent.entity_kind === "foundation_model" ? "Foundation model" : "Application agent"} ` +
        `${m.agent.discovered_via.replace(/_/g, " ")}. AgentScore moved from ${m.score_at_window_start?.toFixed(1) ?? "—"} to ${m.score_now.toFixed(1)} over the past 7 days.`;
      return `
    <item>
      <title>${escape(title)}</title>
      <link>${link}</link>
      <guid isPermaLink="false">${m.agent.slug}-${m.score_now.toFixed(2)}</guid>
      <description>${escape(description)}</description>
      <pubDate>${now}</pubDate>
    </item>`;
    })
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AgentTape · Trending</title>
    <link>${SITE}/trending</link>
    <description>The 25 biggest 7-day movers on AgentTape.</description>
    <language>en-us</language>
    <lastBuildDate>${now}</lastBuildDate>${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=600, stale-while-revalidate=3600",
    },
  });
}
