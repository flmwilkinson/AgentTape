"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import { api, type AgentDetail, type SignalSeries } from "@/lib/api-client";

// One panel that does what three did:
//
//   • Score breakdown chart (time-series of headline + 4 pillars)
//   • Pillar contributions (which signals fed each pillar, with the
//     scaled numbers that produced the score)
//   • 24h "what moved" deltas (now a badge on each pillar header)
//
// The previous design split these across separate cards, which made
// readers compare the same data in three places. The unified panel
// lets you see history at the top and drill into the formula by
// clicking a pillar header — the full math trace appears inline.

const WINDOWS = [
  { v: "1d", label: "1d" },
  { v: "7d", label: "7d" },
  { v: "30d", label: "30d" },
  { v: "90d", label: "90d" },
  { v: "all", label: "All" },
] as const;
type Window = (typeof WINDOWS)[number]["v"];

// Pillar colours kept in lock-step with components/signal-chart.tsx —
// the signals chart fans out shades within each pillar's hue family,
// and these middle shades are the canonical "this pillar is X colour"
// reference. Reading both charts side-by-side, the same colour means
// the same pillar.
const PILLAR_COLORS = {
  adoption: "hsl(217 80% 55%)",   // blue
  quality: "hsl(142 65% 48%)",    // green
  momentum: "hsl(358 70% 60%)",   // red
  community: "hsl(215 22% 55%)",  // slate
} as const;

const SERIES = [
  { key: "agent_score", label: "AgentScore", color: "hsl(var(--foreground))", width: 2.5 },
  { key: "adoption", label: "Adoption", color: PILLAR_COLORS.adoption, width: 1.5 },
  { key: "quality", label: "Quality", color: PILLAR_COLORS.quality, width: 1.5 },
  { key: "momentum", label: "Momentum", color: PILLAR_COLORS.momentum, width: 1.5 },
  { key: "community", label: "Community", color: PILLAR_COLORS.community, width: 1.5 },
] as const;

// Mirror of the unified scoring formula in apps/scoring. Anchors must
// match compute.py exactly; if either side moves, both must move.
const ANCHORS: Record<string, number> = {
  github_stars: 1_000,
  github_forks: 200,
  github_contributors: 30,
  github_commits_7d: 50,
  github_mentions_7d: 20,
  hf_downloads_30d: 100_000,
  hf_likes: 200,
  npm_weekly: 1_000,
  pypi_monthly: 10_000,
  hn_mentions_7d: 10,
  hn_points_7d: 100,
  reddit_mentions_7d: 10,
  reddit_points_7d: 100,
  bluesky_mentions_7d: 10,
  stackoverflow_questions_7d: 5,
  producthunt_upvotes: 100,
  arxiv_citations: 100,
};

const APPLICATION_PILLARS = {
  adoption: ["github_stars", "hf_downloads_30d", "npm_weekly", "pypi_monthly", "mcp_registry_listed", "stackoverflow_questions_7d", "producthunt_upvotes"],
  quality: ["benchmark_score"],
  momentum: ["github_stars", "hf_downloads_30d", "npm_weekly", "pypi_monthly", "hn_mentions_7d", "reddit_mentions_7d", "bluesky_mentions_7d"],
  community: ["github_contributors", "github_forks", "hn_points_7d", "reddit_points_7d", "bluesky_mentions_7d", "hf_likes"],
};

const FOUNDATION_MODEL_PILLARS = {
  adoption: ["hf_downloads_30d", "hn_mentions_7d", "reddit_mentions_7d", "bluesky_mentions_7d", "github_stars", "github_mentions_7d"],
  quality: ["benchmark_score"],
  momentum: ["hf_downloads_30d", "hn_mentions_7d", "reddit_mentions_7d", "bluesky_mentions_7d", "github_mentions_7d"],
  community: ["hf_likes", "github_contributors", "bluesky_mentions_7d", "reddit_points_7d"],
};

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

// Each signal has prerequisites on the agent record. github_stars
// can only ever exist if the agent has a github_repo; hf_downloads
// requires an HF org or model id; npm_weekly requires an npm package.
// We surface this distinction in the UI: "Not yet on file" means
// ingestion will pick it up, "Not applicable" means it never will.
function applicabilityFor(source: string, agent: AgentDetail): boolean {
  switch (source) {
    case "github_stars":
    case "github_forks":
    case "github_commits_7d":
    case "github_contributors":
    case "github_mentions_7d":
      return Boolean(agent.github_repo);
    case "hf_downloads_30d":
    case "hf_likes":
    case "hf_trending_rank":
      return Boolean(agent.hf_org || (agent.hf_model_ids && agent.hf_model_ids.length > 0));
    case "npm_weekly":
      return Boolean(agent.package_names && (agent.package_names as Record<string, unknown>).npm);
    case "pypi_monthly":
      return Boolean(agent.package_names && (agent.package_names as Record<string, unknown>).pypi);
    case "arxiv_citations":
      return Boolean(agent.arxiv_ids && agent.arxiv_ids.length > 0);
    case "mcp_registry_listed":
      return agent.discovered_via === "mcp_registry";
    // Benchmark, HN/Reddit/Bluesky/SO/PH mentions: applicable to
    // anything with a name (everyone has a name).
    case "benchmark_score":
    case "hn_mentions_7d":
    case "hn_points_7d":
    case "reddit_mentions_7d":
    case "reddit_points_7d":
    case "bluesky_mentions_7d":
    case "stackoverflow_questions_7d":
    case "producthunt_upvotes":
      return true;
    default:
      return true;
  }
}

interface Props {
  slug: string;
  agent: AgentDetail;
  signals: SignalSeries[];
}

export function ScoreBreakdownPanel({ slug, agent, signals }: Props) {
  const [window, setWindow] = useState<Window>("all");
  const [expanded, setExpanded] = useState<string | null>("adoption");

  const { data: history } = useQuery({
    queryKey: ["score-history", slug, window],
    queryFn: () => api.agentScoreHistory(slug, window),
  });

  const points = (history ?? []).map((p) => ({
    t: new Date(p.captured_at).getTime(),
    agent_score: p.agent_score,
    adoption: p.adoption,
    quality: p.quality,
    momentum: p.momentum,
    community: p.community,
  }));

  const pillarMap =
    agent.entity_kind === "foundation_model"
      ? FOUNDATION_MODEL_PILLARS
      : APPLICATION_PILLARS;

  // Latest reading per signal source + 24h-old reading for delta.
  const sigState = useMemo(() => buildSignalState(signals), [signals]);

  const applicabilityFn = (s: string) => applicabilityFor(s, agent);
  const rows: PillarRow[] = [
    buildPillar("Adoption", "adoption", agent.score?.adoption, pillarMap.adoption, sigState, false, applicabilityFn),
    buildPillar("Quality", "quality", agent.score?.quality, pillarMap.quality, sigState, false, applicabilityFn),
    buildPillar("Momentum", "momentum", agent.score?.momentum, pillarMap.momentum, sigState, true, applicabilityFn),
    buildPillar("Community", "community", agent.score?.community, pillarMap.community, sigState, false, applicabilityFn),
  ];

  return (
    <section className="rounded-md border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Score breakdown
          </div>
          <div className="text-[11px] text-muted-foreground">
            Headline plus the four pillars over time. Click any pillar
            below to see the signals feeding it.
          </div>
        </div>
        <div className="inline-flex rounded-md border border-border bg-background p-0.5">
          {WINDOWS.map((w) => (
            <button
              key={w.v}
              type="button"
              onClick={() => setWindow(w.v)}
              className={cn(
                "rounded-sm px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider transition-colors",
                window === w.v
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      <div className="px-2 py-3">
        {points.length < 2 ? (
          <div className="px-4 py-12 text-center text-xs text-muted-foreground">
            Not enough score history in this window yet — try a wider one.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(t) => formatTick(t as number, window)}
                stroke="hsl(var(--muted-foreground))"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                minTickGap={32}
              />
              <YAxis
                domain={[0, 100]}
                stroke="hsl(var(--muted-foreground))"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                width={28}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelFormatter={(t) =>
                  new Date(t as number).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
                formatter={(v, name) => {
                  const num = typeof v === "number" ? v : null;
                  return [num == null ? "—" : num.toFixed(1), name as string];
                }}
                isAnimationActive={false}
              />
              <Legend iconType="line" wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
              {SERIES.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={s.width}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="border-t border-border">
        <div className="border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Pillar contributions
        </div>
        <ul className="divide-y divide-border">
          {rows.map((r) => {
            const open = expanded === r.key;
            return (
              <li key={r.key}>
                <button
                  type="button"
                  onClick={() => setExpanded(open ? null : r.key)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-subtle/50"
                >
                  <ChevronRight
                    className={cn(
                      "h-3.5 w-3.5 text-muted-foreground transition-transform",
                      open && "rotate-90",
                    )}
                  />
                  <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground w-24">
                    {r.label}
                  </span>
                  <span className="num text-base font-semibold w-16">
                    {r.score == null ? "Unrated" : r.score.toFixed(1)}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {r.contributing.length}/{r.total} signals
                  </span>
                  {r.delta24h != null && r.delta24h !== 0 && (
                    <span
                      className={cn(
                        "ml-auto font-mono text-xs",
                        r.delta24h > 0 ? "text-gain" : "text-loss",
                      )}
                    >
                      {r.delta24h > 0 ? "+" : ""}
                      {r.delta24h.toFixed(2)} 24h
                    </span>
                  )}
                </button>
                {open && (
                  <div className="border-t border-border bg-subtle/30 px-4 py-3 text-sm">
                    {r.contributing.length === 0 ? (
                      <p className="text-muted-foreground">
                        {r.key === "quality"
                          ? "No benchmark results on file. Quality's 30% weight is redistributed pro-rata to the other pillars."
                          : "No signals on file for this pillar yet — pillar is Unrated."}
                      </p>
                    ) : (
                      <>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          {r.contributing.map((c) => (
                            <div
                              key={c.source}
                              className="rounded-sm border border-border bg-card px-3 py-2"
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-foreground/85">
                                  {SOURCE_LABELS[c.source] ?? c.source}
                                </span>
                                {c.delta24h != null && c.delta24h !== 0 && (
                                  <span
                                    className={cn(
                                      "font-mono text-xs",
                                      c.delta24h > 0 ? "text-gain" : "text-loss",
                                    )}
                                  >
                                    {c.delta24h > 0 ? "+" : ""}
                                    {c.delta24hPctLabel}
                                  </span>
                                )}
                              </div>
                              <div className="mt-1 flex items-baseline justify-between text-xs text-muted-foreground">
                                <span className="num">
                                  {c.raw_label}
                                </span>
                                <span className="num">
                                  → {c.scaled_label}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 font-mono text-[11px] text-muted-foreground">
                          Pillar = mean of {r.contributing.length}{" "}
                          scaled value{r.contributing.length === 1 ? "" : "s"} ={" "}
                          {r.score == null ? "—" : r.score.toFixed(1)}.
                        </p>
                      </>
                    )}
                    {r.missing.length > 0 && (
                      <p className="mt-3 text-[11px] text-muted-foreground">
                        <span className="font-mono uppercase tracking-wider text-foreground/70">
                          Awaiting first reading
                        </span>{" "}
                        — these signals apply to this agent and will be
                        ingested on the next tier tick:{" "}
                        {r.missing.map((s) => SOURCE_LABELS[s] ?? s).join(", ")}
                      </p>
                    )}
                    {r.not_applicable.length > 0 && (
                      <p className="mt-2 text-[11px] text-muted-foreground/70">
                        <span className="font-mono uppercase tracking-wider">
                          Not applicable
                        </span>{" "}
                        — this agent doesn't have the prerequisite (no
                        GitHub repo, no HF mirror, etc.) for these
                        signals to ever apply:{" "}
                        {r.not_applicable
                          .map((s) => SOURCE_LABELS[s] ?? s)
                          .join(", ")}
                      </p>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

// ----------------------------------------------------------- helpers

interface SignalState {
  latest: number;
  prior24h: number | null;
}

function buildSignalState(signals: SignalSeries[]): Map<string, SignalState> {
  const out = new Map<string, SignalState>();
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  for (const s of signals) {
    if (!s.points || s.points.length === 0) continue;
    const sorted = [...s.points].sort(
      (a, b) =>
        new Date(a.captured_at).getTime() - new Date(b.captured_at).getTime(),
    );
    const latest = sorted.at(-1)!;
    const olderPts = sorted.filter(
      (p) => new Date(p.captured_at).getTime() <= cutoff,
    );
    const prior = olderPts.length > 0 ? olderPts.at(-1)!.value : null;
    out.set(s.source, { latest: latest.value, prior24h: prior });
  }
  return out;
}

function logScale(v: number, anchor: number): number {
  if (v < 0) v = 0;
  return Math.min(100, (50 * Math.log10(v + 1)) / Math.log10(anchor + 1));
}

function scaleSignal(source: string, value: number): number | null {
  if (source === "benchmark_score") {
    return Math.max(0, Math.min(100, value));
  }
  if (source === "mcp_registry_listed") {
    return value > 0 ? 75 : 0;
  }
  const anchor = ANCHORS[source];
  if (anchor == null) return null;
  return logScale(value, anchor);
}

function formatCount(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

function formatTick(t: number, window: Window): string {
  const d = new Date(t);
  if (window === "1d") {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface ContribRow {
  source: string;
  raw_label: string;
  scaled_label: string;
  delta24h: number | null;
  delta24hPctLabel: string;
}

interface PillarRow {
  label: string;
  key: string;
  score: number | null | undefined;
  total: number;
  contributing: ContribRow[];
  missing: string[];          // applicable but no reading yet
  not_applicable: string[];   // agent doesn't have the prerequisite
  delta24h: number | null;
}

function buildPillar(
  label: string,
  key: string,
  score: number | null | undefined,
  sources: string[],
  sigState: Map<string, SignalState>,
  isMomentum: boolean,
  isApplicable: (source: string) => boolean,
): PillarRow {
  const contributing: ContribRow[] = [];
  const missing: string[] = [];
  const not_applicable: string[] = [];
  const scaledNow: number[] = [];
  const scaledPrior: number[] = [];

  for (const s of sources) {
    const state = sigState.get(s);
    if (!state) {
      // No reading on file. Distinguish "applicable but not yet
      // ingested" from "this agent has no prerequisite for this
      // signal" — readers waiting for the former is fine, waiting
      // for the latter is futile.
      if (isApplicable(s)) {
        missing.push(s);
      } else {
        not_applicable.push(s);
      }
      continue;
    }
    const scaledValue = scaleSignal(s, state.latest);
    if (scaledValue == null) {
      missing.push(s);
      continue;
    }
    scaledNow.push(scaledValue);
    let priorScaled: number | null = null;
    if (state.prior24h != null) {
      priorScaled = scaleSignal(s, state.prior24h);
      if (priorScaled != null) scaledPrior.push(priorScaled);
    }
    const rawDelta =
      state.prior24h != null ? state.latest - state.prior24h : null;
    const pct =
      rawDelta != null && state.prior24h != null && state.prior24h !== 0
        ? (rawDelta / Math.abs(state.prior24h)) * 100
        : null;
    contributing.push({
      source: s,
      raw_label: isMomentum
        ? `${formatCount(state.latest)} now`
        : formatCount(state.latest),
      scaled_label: scaledValue.toFixed(1),
      delta24h: rawDelta,
      delta24hPctLabel:
        pct != null
          ? `${pct.toFixed(1)}%`
          : rawDelta != null
            ? `${formatCount(rawDelta)}`
            : "",
    });
  }

  // 24h pillar delta (if we have prior readings for at least the same
  // sources we used now, the difference of pillar means is a fair
  // approximation of the per-pillar 24h move).
  const meanNow =
    scaledNow.length > 0
      ? scaledNow.reduce((a, b) => a + b, 0) / scaledNow.length
      : null;
  const meanPrior =
    scaledPrior.length > 0
      ? scaledPrior.reduce((a, b) => a + b, 0) / scaledPrior.length
      : null;
  const delta24h =
    meanNow != null && meanPrior != null ? meanNow - meanPrior : null;

  return {
    label,
    key,
    score,
    total: sources.length,
    contributing,
    missing,
    not_applicable,
    delta24h,
  };
}
