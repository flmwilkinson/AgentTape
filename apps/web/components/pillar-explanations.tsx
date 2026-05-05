import type { AgentDetail, SignalSeries } from "@/lib/api-client";

// "How this score was computed" panel.
//
// Mirrors the unified scoring formula in apps/scoring/src/scoring/
// compute.py. For each pillar, we list the signals that contributed,
// the raw value of each, and the scaled 0–100 contribution. Pillars
// with no contributing signal are shown as Unrated.
//
// One panel for both application agents and foundation models — the
// formula is identical, only the source list differs.

const SOURCE_LABELS: Record<string, string> = {
  github_stars: "GitHub stars",
  github_forks: "GitHub forks",
  github_commits_7d: "Commits (7d)",
  github_contributors: "Contributors",
  github_mentions_7d: "GitHub mentions (7d)",
  hf_downloads_30d: "HF downloads (30d)",
  hf_likes: "HF likes",
  hf_trending_rank: "HF trending rank",
  npm_weekly: "npm weekly installs",
  pypi_monthly: "PyPI monthly installs",
  mcp_registry_listed: "MCP registry listing",
  hn_points_7d: "HN points (7d)",
  hn_mentions_7d: "HN mentions (7d)",
  reddit_points_7d: "Reddit points (7d)",
  reddit_mentions_7d: "Reddit mentions (7d)",
  bluesky_mentions_7d: "Bluesky mentions (7d)",
  stackoverflow_questions_7d: "SO questions (7d)",
  producthunt_upvotes: "Product Hunt upvotes",
  benchmark_score: "Benchmark score",
  arxiv_citations: "arXiv citations",
};

const APPLICATION_PILLARS = {
  adoption: [
    "github_stars",
    "hf_downloads_30d",
    "npm_weekly",
    "pypi_monthly",
    "mcp_registry_listed",
    "stackoverflow_questions_7d",
    "producthunt_upvotes",
  ],
  quality: ["benchmark_score"],
  momentum: [
    "github_stars",
    "hf_downloads_30d",
    "npm_weekly",
    "pypi_monthly",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
  ],
  community: [
    "github_contributors",
    "github_forks",
    "hn_points_7d",
    "reddit_points_7d",
    "bluesky_mentions_7d",
    "hf_likes",
  ],
};

const FOUNDATION_MODEL_PILLARS = {
  adoption: [
    "hf_downloads_30d",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
    "github_stars",
    "github_mentions_7d",
  ],
  quality: ["benchmark_score"],
  momentum: [
    "hf_downloads_30d",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
    "github_mentions_7d",
  ],
  community: [
    "hf_likes",
    "github_contributors",
    "bluesky_mentions_7d",
    "reddit_points_7d",
  ],
};

interface Props {
  agent: AgentDetail;
  signals: SignalSeries[];
}

export function PillarExplanations({ agent, signals }: Props) {
  const pillarMap =
    agent.entity_kind === "foundation_model"
      ? FOUNDATION_MODEL_PILLARS
      : APPLICATION_PILLARS;

  const latest = signalLatestMap(signals);

  const rows: Row[] = [
    buildRow("Adoption", agent.score?.adoption, pillarMap.adoption, latest, false),
    buildRow("Quality", agent.score?.quality, pillarMap.quality, latest, false),
    buildRow("Momentum", agent.score?.momentum, pillarMap.momentum, latest, true),
    buildRow("Community", agent.score?.community, pillarMap.community, latest, false),
  ];

  return (
    <section className="rounded-md border border-border bg-card">
      <div className="border-b border-border px-4 py-2.5">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          How this score was computed
        </div>
        <div className="text-[11px] text-muted-foreground">
          Each pillar is the mean of its available scaled signals. Pillars
          with no reading are Unrated. The same formula runs for application
          agents and foundation models — only the source list differs.
        </div>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => (
          <li key={r.pillar} className="px-4 py-3">
            <div className="flex items-baseline gap-3">
              <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                {r.pillar}
              </span>
              <span className="num text-base font-semibold">
                {r.score == null ? "Unrated" : r.score.toFixed(1)}
              </span>
              <span className="ml-auto text-[11px] text-muted-foreground">
                {r.contributing.length}/{r.total} signals
              </span>
            </div>
            {r.contributing.length === 0 ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {r.pillar === "Quality"
                  ? "No benchmark results on file. Quality's 30% weight is redistributed pro-rata to the other pillars."
                  : "No signals on file for this pillar yet."}
              </p>
            ) : (
              <ul className="mt-2 grid grid-cols-1 gap-1.5 text-sm sm:grid-cols-2">
                {r.contributing.map((c) => (
                  <li
                    key={c.source}
                    className="flex items-center justify-between gap-3 rounded-sm bg-subtle px-2.5 py-1"
                  >
                    <span className="truncate text-foreground/85">
                      {SOURCE_LABELS[c.source] ?? c.source}
                    </span>
                    <span className="num text-xs text-muted-foreground">
                      {c.raw_label}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {r.missing.length > 0 && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                Not yet on file:{" "}
                {r.missing.map((s) => SOURCE_LABELS[s] ?? s).join(", ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

interface ContribRow {
  source: string;
  raw_label: string;
}

interface Row {
  pillar: string;
  score: number | null | undefined;
  total: number;
  contributing: ContribRow[];
  missing: string[];
}

function buildRow(
  pillar: string,
  score: number | null | undefined,
  sources: string[],
  latest: Record<string, number>,
  isMomentum: boolean,
): Row {
  const contributing: ContribRow[] = [];
  const missing: string[] = [];
  for (const s of sources) {
    const v = latest[s];
    if (v == null) {
      missing.push(s);
      continue;
    }
    contributing.push({
      source: s,
      raw_label: isMomentum ? `${formatCount(v)} now` : formatCount(v),
    });
  }
  return { pillar, score, total: sources.length, contributing, missing };
}

function signalLatestMap(signals: SignalSeries[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of signals) {
    if (!s.points || s.points.length === 0) continue;
    const sorted = [...s.points].sort(
      (a, b) =>
        new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime(),
    );
    out[s.source] = sorted[0].value;
  }
  return out;
}

function formatCount(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}
