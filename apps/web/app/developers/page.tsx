import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Developers — AgentTape",
  description:
    "Public JSON endpoints, RSS feeds and embeddable badges. Build with the same data that drives agenttape.io.",
  alternates: { canonical: "/developers" },
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://agenttape.io/api";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.io";

const ENDPOINTS = [
  {
    title: "Agents",
    items: [
      {
        method: "GET",
        path: "/agents",
        params: "?q=&tag_kind=&tag_value=&entity_kind=&sort=score|discovered|name&limit=&offset=",
        body: "List admitted agents. Filter by tag_kind+tag_value, entity_kind, or substring query. Sort by score / admission date / name.",
      },
      { method: "GET", path: "/agents/{slug}", body: "Full detail for one agent: scores, pillars, tags, raw payload, OpenRouter facts (FMs)." },
      { method: "GET", path: "/agents/{slug}/signals", params: "?sources=&window=", body: "Time-series of signal readings. Window: 1h, 1d, 7d, 30d, 90d, all." },
      { method: "GET", path: "/agents/{slug}/score-history", params: "?window=", body: "Time-series of headline + four pillar scores." },
      { method: "GET", path: "/agents/{slug}/benchmarks", body: "Most recent benchmark results across every leaderboard the agent appears on." },
      { method: "GET", path: "/agents/{slug}/similar", params: "?limit=", body: "Vibe-search neighbours via embedding cosine similarity." },
      { method: "GET", path: "/agents/{slug}/signals.csv", params: "?window=", body: "Same data as /signals but as a downloadable CSV." },
    ],
  },
  {
    title: "Indexes",
    items: [
      { method: "GET", path: "/indexes", body: "List of indexes with current composite values." },
      { method: "GET", path: "/indexes/{slug}", body: "Index detail with constituents, weights, last rebalance time." },
      { method: "GET", path: "/indexes/{slug}/history", params: "?window=", body: "Composite value time-series." },
      { method: "GET", path: "/indexes/{slug}/rebalances", params: "?limit=", body: "Rebalance log entries with diffs." },
    ],
  },
  {
    title: "Sectors",
    items: [
      { method: "GET", path: "/sectors", params: "?kind=capability|deployment|maturity&window=1d|7d|30d", body: "Per-tag rollup with avg score, member count, verdict (booming / growing / steady / cooling / declining)." },
      { method: "GET", path: "/sectors/{kind}/{value}/history", params: "?window=", body: "Cohort average score time-series." },
    ],
  },
  {
    title: "Movers / search / events",
    items: [
      { method: "GET", path: "/movers", params: "?window=1h|1d|7d|30d&limit=&capability=&deployment=&entity_kind=", body: "Biggest absolute score movers in the window. Optional tag filters." },
      { method: "GET", path: "/search", params: "?q=&mode=text|vibe&limit=", body: "Text or embedding search across agents." },
      { method: "GET", path: "/search/suggest", params: "?q=&limit=", body: "Prefix-prioritised autocomplete (powers the header search box)." },
      { method: "GET", path: "/tags", body: "Every tag with admitted-agent counts." },
      { method: "GET", path: "/events", params: "?kind=&limit=&offset=", body: "Recent events (admissions, score changes, spikes, rebalances)." },
      { method: "GET", path: "/discovery/recent", params: "?limit=", body: "Most recently admitted agents." },
    ],
  },
];

const FEEDS = [
  {
    title: "RSS · Trending",
    href: "/rss/trending.xml",
    body: "Top 25 biggest 7-day movers as an RSS feed. Refreshes every 10 minutes.",
  },
  {
    title: "Sitemap",
    href: "/sitemap.xml",
    body: "Every agent, index, sector landing page and article — for indexing and crawling.",
  },
];

export default function DevelopersPage() {
  return (
    <article className="container py-10 md:py-14 max-w-4xl space-y-12">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Developers
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          Build with AgentTape data.
        </h1>
        <p className="editorial mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
          Every page on this site is rendered from a public JSON API. The
          full surface is below — no auth, no rate limits beyond the
          obvious "don't be a jerk" cap. If you build something with it,
          let us know on the GitHub repo.
        </p>
      </header>

      <section>
        <H2>Base URL</H2>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm">
          {API_BASE}
        </pre>
        <p className="mt-2 text-sm text-muted-foreground">
          All endpoints below are relative to this base.
        </p>
      </section>

      {ENDPOINTS.map((group) => (
        <section key={group.title}>
          <H2>{group.title}</H2>
          <div className="rounded-md border border-border bg-card divide-y divide-border">
            {group.items.map((e) => (
              <div key={e.path} className="px-4 py-3">
                <div className="flex items-baseline gap-3 font-mono text-sm">
                  <span className="rounded-sm bg-primary/10 px-1.5 py-0.5 text-[11px] uppercase tracking-wider text-primary">
                    {e.method}
                  </span>
                  <span className="font-medium">{e.path}</span>
                  {e.params && (
                    <span className="text-xs text-muted-foreground">
                      {e.params}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{e.body}</p>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section>
        <H2>Feeds</H2>
        <div className="grid gap-3 md:grid-cols-2">
          {FEEDS.map((f) => (
            <Link
              key={f.href}
              href={f.href}
              className="rounded-md border border-border bg-card p-4 hover:bg-subtle"
            >
              <div className="font-medium">{f.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">{f.body}</div>
              <div className="mt-2 font-mono text-xs text-primary">{f.href}</div>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <H2>Embeddable badges</H2>
        <p className="text-sm text-muted-foreground">
          Add a live AgentTape badge to your project's README. Renders the
          agent's name, current AgentScore and rank on a 0–100 scale,
          updating hourly.
        </p>
        <pre className="mt-3 overflow-x-auto rounded-md border border-border bg-card p-4 font-mono text-xs leading-relaxed">
          {`# Markdown
[![AgentTape](${SITE_URL}/api/badge/<slug>.svg)](${SITE_URL}/agents/<slug>)

# HTML
<a href="${SITE_URL}/agents/<slug>"><img src="${SITE_URL}/api/badge/<slug>.svg" alt="AgentTape" /></a>`}
        </pre>
        <p className="mt-3 text-xs text-muted-foreground">
          Badge previews and copy-paste snippets live on each agent page.
        </p>
      </section>

      <section>
        <H2>Source code</H2>
        <p className="text-sm text-muted-foreground">
          AgentTape is open source.{" "}
          <a
            href="https://github.com/flmwilkinson/AgentTape"
            target="_blank"
            rel="noreferrer"
            className="text-primary hover:underline"
          >
            github.com/flmwilkinson/AgentTape
          </a>{" "}
          — issues and PRs welcome.
        </p>
      </section>
    </article>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="editorial mb-4 text-2xl font-semibold leading-tight md:text-3xl">
      {children}
    </h2>
  );
}
