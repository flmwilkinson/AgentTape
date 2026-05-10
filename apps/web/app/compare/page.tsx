"use client";

import { ChevronDown, Plus, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Fragment, Suspense, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CompareChart } from "@/components/compare-chart";
import { MoverChip } from "@/components/mover-chip";
import { PillarBar } from "@/components/pillar-bar";
import { RankArrow } from "@/components/rank-arrow";
import { SearchCombobox } from "@/components/search-combobox";

// /compare — up to 5 agents side by side, with an overlay score chart,
// per-agent cards, a "Best at X" verdict per agent, and a side-by-side
// scorecard matrix that breaks each pillar into its contributing
// signals so the comparison is fully traceable.
//
// URL is the canonical state: /compare?slugs=foo,bar,baz — shareable.
// Old /compare?a=foo&b=bar URLs are still honoured so existing links
// don't break.

const MAX = 5;

// Next 15 wants useSearchParams under a Suspense boundary so the rest
// of the route can statically pre-render. The shell here is what
// satisfies that requirement; the real component is below.
export default function ComparePage() {
  return (
    <Suspense
      fallback={
        <div className="container py-8 md:py-12">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Compare
          </div>
          <div className="mt-2 h-10 w-72 animate-pulse rounded-md bg-muted" />
        </div>
      }
    >
      <ComparePageInner />
    </Suspense>
  );
}

function ComparePageInner() {
  const router = useRouter();
  const params = useSearchParams();
  // Accept either ?slugs=a,b,c OR the legacy ?a=&b= pair so old shared
  // links keep working.
  const raw = params.get("slugs") ?? "";
  const legacyA = params.get("a");
  const legacyB = params.get("b");
  const slugs = raw
    ? raw.split(",").filter(Boolean).slice(0, MAX)
    : [legacyA, legacyB].filter((s): s is string => Boolean(s)).slice(0, MAX);
  // Ref on the combobox wrapper so empty slot cards can scroll-and-
  // focus it instead of routing the user away to /search.
  const comboWrapRef = useRef<HTMLDivElement>(null);
  const focusDraftInput = () => {
    const el = comboWrapRef.current;
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    const input = el.querySelector("input");
    if (input) setTimeout(() => input.focus(), 250);
  };

  // Stable Set so the combobox's exclude-list dependency doesn't
  // change on every render (slugs is a fresh array each time).
  const slugsKey = slugs.join(",");
  const excludeSlugs = useMemo(
    () => new Set(slugsKey ? slugsKey.split(",") : []),
    [slugsKey],
  );

  function addSlug(slug: string) {
    if (!slug || slugs.includes(slug) || slugs.length >= MAX) return;
    setSlugs([...slugs, slug]);
  }

  const detailQueries = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ["agent", slug],
      queryFn: () => api.getAgent(slug),
      enabled: slugs.length > 0,
    })),
  });
  const histories = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ["score-history", slug, "30d"],
      queryFn: () => api.agentScoreHistory(slug, "30d"),
      enabled: slugs.length > 0,
    })),
  });
  // Per-agent signals so the verdict block can name which raw signal
  // is doing the work behind each pillar.
  const signalQueries = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ["agent-signals", slug, "30d"],
      queryFn: () => api.agentSignals(slug, { window: "30d" }),
      enabled: slugs.length > 0,
    })),
  });

  // Suggestions when /compare opens with no slugs.
  const { data: suggestions } = useQuery({
    queryKey: ["compare-suggestions"],
    queryFn: () => api.listAgents({ sort: "score", limit: 8 }),
    enabled: slugs.length === 0,
  });

  function setSlugs(next: string[]) {
    const cur = new URLSearchParams(params.toString());
    if (next.length) cur.set("slugs", next.join(","));
    else cur.delete("slugs");
    router.replace(`/compare?${cur.toString()}`);
  }

  const series = slugs.flatMap((slug, i) => {
    const detail = detailQueries[i].data;
    const hist = histories[i].data;
    if (!detail || !hist) return [];
    return [{ slug, name: detail.name, points: hist }];
  });

  const verdicts = computeVerdicts(detailQueries.map((q) => q.data ?? null));

  return (
    <div className="container py-8 md:py-12 space-y-8">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Compare
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Up to five, side by side.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Add agents by slug or pick from the suggestions. The URL is
          shareable — copy it once you've got a comparison you want to
          come back to.
        </p>
      </div>

      <div ref={comboWrapRef} className="max-w-xl">
        <SearchCombobox
          className="block w-full"
          inputClassName="h-10 text-sm"
          placeholder="Type a name (e.g. claude, autogpt, llama)…"
          agentsOnly
          excludeSlugs={excludeSlugs}
          onSelectAgent={addSlug}
          onEnter={(q) => addSlug(q.trim())}
        />
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          Pick from the suggestions, or hit Enter on a typed slug to add directly.
        </p>
      </div>

      {slugs.length === 0 && suggestions?.items && (
        <section>
          <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Quick start — top stocks
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.items.slice(0, 8).map((a) => (
              <button
                key={a.slug}
                type="button"
                onClick={() => setSlugs([a.slug])}
                className="rounded-full border border-border bg-card px-3 py-1 text-xs hover:bg-subtle"
              >
                {a.name}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Overlay chart */}
      {slugs.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              AgentScore · 30 days
            </div>
            <div className="text-[10px] text-muted-foreground">
              {series.length} of {slugs.length} loaded
            </div>
          </div>
          <CompareChart series={series} height={320} />
        </section>
      )}

      {/* Cards grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {detailQueries.map((q, i) => {
          const a = q.data;
          if (!a) {
            return (
              <div
                key={slugs[i] ?? `loading-${i}`}
                className="flex min-h-[220px] items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground"
              >
                {q.isLoading ? "Loading…" : "Failed to load"}
              </div>
            );
          }
          const verdict = verdicts[a.slug];
          return (
            <div
              key={a.slug}
              className="flex flex-col gap-3 rounded-md border border-border bg-card p-4"
            >
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {a.entity_kind === "foundation_model" ? "model" : "agent"}
                    {" · "}
                    {a.discovered_via.replace(/_/g, " ")}
                  </div>
                  <div className="truncate text-sm font-medium">{a.name}</div>
                </div>
                <button
                  type="button"
                  aria-label="Remove"
                  onClick={() => setSlugs(slugs.filter((s) => s !== a.slug))}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="flex items-end gap-3">
                <div className="text-stat-md font-semibold num">
                  {formatScore(a.score?.agent_score ?? null)}
                </div>
                {a.score?.delta_24h != null && (
                  <MoverChip
                    delta={a.score.delta_24h}
                    unit="score"
                    variant="outline"
                    className="mb-1"
                  />
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span>Rank</span>
                <span className="num font-medium text-foreground">
                  {a.score?.rank_now ?? "—"}
                </span>
                <RankArrow
                  delta={a.score?.rank_delta_24h ?? null}
                  rankNow={a.score?.rank_now ?? null}
                />
              </div>
              <PillarBar
                score={{
                  adoption: a.score?.adoption ?? null,
                  quality: a.score?.quality ?? null,
                  momentum: a.score?.momentum ?? null,
                  community: a.score?.community ?? null,
                }}
                variant="compact"
              />
              {verdict && (
                <div className="hairline pt-3 text-xs text-foreground/85">
                  <span className="mr-1.5 inline-block rounded-sm bg-primary/10 px-1.5 py-0.5 font-mono uppercase tracking-wider text-primary">
                    Best at
                  </span>
                  {verdict}
                </div>
              )}
            </div>
          );
        })}
        {Array.from({ length: Math.max(0, MAX - slugs.length) }).map((_, i) => (
          <button
            key={`empty-${i}`}
            type="button"
            onClick={focusDraftInput}
            aria-label="Add an agent to compare"
            className="group flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:bg-subtle hover:text-foreground"
          >
            <Plus className="h-5 w-5 transition-transform group-hover:scale-110" />
            <span>add an agent</span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70">
              type a slug above
            </span>
          </button>
        ))}
      </div>

      {/* Side-by-side scorecard — pillars-as-rows matrix. Best cell
          per row gets a primary highlight so a quick scan shows
          which agent wins each pillar. Clicking a pillar row drills
          down into its underlying signals (GitHub stars, downloads,
          etc.) so the verdict is fully traceable. */}
      {slugs.length >= 2 && (
        <ScorecardMatrix
          agents={detailQueries
            .map((q) => q.data)
            .filter((a): a is NonNullable<typeof a> => Boolean(a))}
          signalsByAgent={Object.fromEntries(
            slugs.map((slug, i) => [slug, signalQueries[i]?.data ?? []]),
          )}
        />
      )}

      {/* Verdicts — one line per pillar that names the driving
          signal AND its values per agent. Answers "Momentum in
          what?" rather than just "X wins Momentum". */}
      {slugs.length >= 2 && (
        <DrivingSignalVerdicts
          agents={detailQueries
            .map((q) => q.data)
            .filter((a): a is NonNullable<typeof a> => Boolean(a))}
          signalsByAgent={Object.fromEntries(
            slugs.map((slug, i) => [slug, signalQueries[i]?.data ?? []]),
          )}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- matrix

type ScorecardAgent = {
  slug: string;
  name: string;
  entity_kind: string;
  score: {
    agent_score: number | null;
    adoption: number | null;
    quality: number | null;
    momentum: number | null;
    community: number | null;
  };
};

type SignalSeries = Array<{
  source: string;
  points: { captured_at: string; value: number }[];
}>;

function ScorecardMatrix({
  agents,
  signalsByAgent,
}: {
  agents: ScorecardAgent[];
  signalsByAgent: Record<string, SignalSeries>;
}) {
  // Pillar rows can be expanded to show the underlying signals
  // (GitHub stars, downloads, etc.) so a user who's curious *why*
  // Foundation Model A wins Adoption can drill in without leaving
  // the page. AgentScore is not expandable since it's an aggregate
  // of all four pillars below it.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (agents.length === 0) return null;

  const rows: {
    key: keyof ScorecardAgent["score"];
    label: string;
    expandable: boolean;
  }[] = [
    { key: "agent_score", label: "AgentScore", expandable: false },
    { key: "adoption", label: "Adoption", expandable: true },
    { key: "quality", label: "Quality", expandable: true },
    { key: "momentum", label: "Momentum", expandable: true },
    { key: "community", label: "Community", expandable: true },
  ];

  function toggle(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <section>
      <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Side-by-side scorecard
      </div>
      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr className="border-b border-border bg-subtle/40 text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 text-left font-medium">Pillar</th>
              {agents.map((a) => (
                <th
                  key={a.slug}
                  className="px-3 py-2 text-right font-medium"
                  title={a.name}
                >
                  <span className="truncate">{a.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const values = agents.map((a) => a.score?.[row.key] ?? null);
              const max = Math.max(
                ...values.filter((v): v is number => v != null),
              );
              const isOpen = expanded.has(row.key);
              return (
                <Fragment key={row.key}>
                  <tr
                    className={
                      row.key === "agent_score"
                        ? "border-b border-border bg-subtle/20 font-medium"
                        : "border-b border-border last:border-b-0"
                    }
                  >
                    <td className="px-3 py-2 text-foreground/85">
                      {row.expandable ? (
                        <button
                          type="button"
                          onClick={() => toggle(row.key)}
                          aria-expanded={isOpen}
                          className="inline-flex items-center gap-1.5 text-foreground/85 hover:text-foreground"
                        >
                          <ChevronDown
                            className={`h-3.5 w-3.5 transition-transform ${isOpen ? "" : "-rotate-90"}`}
                          />
                          {row.label}
                        </button>
                      ) : (
                        row.label
                      )}
                    </td>
                    {agents.map((a, i) => {
                      const v = values[i];
                      const isBest =
                        v != null && Number.isFinite(max) && v === max && agents.length > 1;
                      return (
                        <td
                          key={a.slug}
                          className={`num px-3 py-2 text-right tabular-nums ${
                            isBest ? "text-primary font-semibold" : ""
                          }`}
                        >
                          {v == null ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            v.toFixed(1)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                  {row.expandable && isOpen && (
                    <PillarSignalRows
                      pillar={row.key as Exclude<keyof ScorecardAgent["score"], "agent_score">}
                      agents={agents}
                      signalsByAgent={signalsByAgent}
                    />
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Highest value per row in the primary colour. "—" means the
        pillar is Unrated for that agent. Click a pillar to drill into
        its underlying signals.
      </p>
    </section>
  );
}

// Expanded sub-rows for a pillar — one row per contributing signal.
// A signal only appears if at least one agent has a reading for it.
// Best cell in each row gets the primary colour, mirroring the parent
// matrix.
function PillarSignalRows({
  pillar,
  agents,
  signalsByAgent,
}: {
  pillar: "adoption" | "quality" | "momentum" | "community";
  agents: ScorecardAgent[];
  signalsByAgent: Record<string, SignalSeries>;
}) {
  // Pick source list per kind. If the comparison mixes app agents and
  // foundation models we union both lists so we don't accidentally
  // hide a signal that one side has and the other doesn't.
  const hasFM = agents.some((a) => a.entity_kind === "foundation_model");
  const hasApp = agents.some((a) => a.entity_kind !== "foundation_model");
  const sources = Array.from(
    new Set([
      ...(hasApp ? PILLAR_SOURCES_APP[pillar] : []),
      ...(hasFM ? PILLAR_SOURCES_FM[pillar] : []),
    ]),
  );

  const rows = sources
    .map((source) => {
      const values = agents.map((a) => latestValue(signalsByAgent[a.slug] ?? [], source));
      const anyValue = values.some((v) => v != null);
      return { source, values, anyValue };
    })
    .filter((r) => r.anyValue);

  if (rows.length === 0) {
    return (
      <tr className="border-b border-border bg-subtle/10 text-xs">
        <td
          colSpan={agents.length + 1}
          className="px-6 py-2 text-muted-foreground"
        >
          No raw signals on file for this pillar yet.
        </td>
      </tr>
    );
  }

  return (
    <>
      {rows.map(({ source, values }) => {
        const max = Math.max(...values.filter((v): v is number => v != null));
        return (
          <tr
            key={`${pillar}-${source}`}
            className="border-b border-border bg-subtle/10 text-xs"
          >
            <td className="px-6 py-1.5 text-muted-foreground">
              {SIGNAL_LABEL[source] ?? source}
            </td>
            {agents.map((a, i) => {
              const v = values[i];
              const isBest =
                v != null && Number.isFinite(max) && v === max && agents.length > 1;
              return (
                <td
                  key={a.slug}
                  className={`num px-3 py-1.5 text-right tabular-nums ${
                    isBest ? "text-primary font-medium" : ""
                  }`}
                >
                  {v == null ? (
                    <span className="text-muted-foreground/60">—</span>
                  ) : (
                    fmtCount(v)
                  )}
                </td>
              );
            })}
          </tr>
        );
      })}
    </>
  );
}

// ----------------------------------------------------------- verdicts

const PILLAR_SOURCES_APP: Record<string, string[]> = {
  adoption: [
    "github_stars",
    "hf_downloads_30d",
    "npm_weekly",
    "pypi_monthly",
    "stackoverflow_questions_7d",
    "producthunt_upvotes",
    "docker_pulls_30d",
    "crates_downloads_90d",
    "news_mentions_30d",
  ],
  quality: [
    "benchmark_score",
    "github_issue_close_rate_30d",
    "github_first_response_hours_30d",
  ],
  momentum: [
    "github_stars",
    "hf_downloads_30d",
    "npm_weekly",
    "pypi_monthly",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
    "mastodon_mentions_7d",
    "github_releases_90d",
    "google_trends_score",
  ],
  community: [
    "github_contributors",
    "github_forks",
    "hn_points_7d",
    "reddit_points_7d",
    "bluesky_mentions_7d",
    "mastodon_mentions_7d",
    "hf_likes",
    "discord_members",
  ],
};
const PILLAR_SOURCES_FM: Record<string, string[]> = {
  adoption: [
    "hf_downloads_30d",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
    "mastodon_mentions_7d",
    "github_stars",
    "github_mentions_7d",
    "wikipedia_views_30d",
    "openrouter_token_volume_30d",
    "github_repos_using_model",
    "news_mentions_30d",
  ],
  quality: ["benchmark_score", "arxiv_citations"],
  momentum: [
    "hf_downloads_30d",
    "hn_mentions_7d",
    "reddit_mentions_7d",
    "bluesky_mentions_7d",
    "mastodon_mentions_7d",
    "github_mentions_7d",
    "google_trends_score",
    "openrouter_token_volume_30d",
  ],
  // Each FM signal lives in exactly one pillar so the mean-of-scaled-
  // signals math stays clean. github_repos_using_model is in Adoption
  // (ecosystem reach), Bluesky is Adoption + Momentum.
  community: ["hf_likes", "github_contributors", "reddit_points_7d"],
};
const SIGNAL_LABEL: Record<string, string> = {
  github_stars: "GitHub stars",
  github_forks: "GitHub forks",
  github_contributors: "Contributors",
  github_mentions_7d: "GitHub mentions (7d)",
  hf_downloads_30d: "HF downloads (30d)",
  hf_likes: "HF likes",
  npm_weekly: "npm weekly",
  pypi_monthly: "PyPI monthly",
  hn_mentions_7d: "HN mentions (7d)",
  hn_points_7d: "HN points (7d)",
  reddit_mentions_7d: "Reddit mentions (7d)",
  reddit_points_7d: "Reddit points (7d)",
  bluesky_mentions_7d: "Bluesky mentions (7d)",
  stackoverflow_questions_7d: "Stack Overflow (7d)",
  producthunt_upvotes: "Product Hunt upvotes",
  benchmark_score: "Benchmark score",
  arxiv_citations: "arXiv citations",
  docker_pulls_30d: "Docker Hub pulls",
  crates_downloads_90d: "Crates.io downloads (90d)",
  github_releases_90d: "GitHub releases (90d)",
  github_issue_close_rate_30d: "Issue close rate (30d)",
  wikipedia_views_30d: "Wikipedia views (30d)",
  discord_members: "Discord members",
  google_trends_score: "Google Trends",
  openrouter_token_volume_30d: "OpenRouter tokens (30d)",
  github_first_response_hours_30d: "First-response hours (30d, median)",
  github_repos_using_model: "GitHub repos using this model",
  news_mentions_30d: "Tech-news mentions (30d)",
  mastodon_mentions_7d: "Mastodon mentions (7d)",
};

function fmtCount(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

function latestValue(
  signals: Array<{ source: string; points: { captured_at: string; value: number }[] }>,
  source: string,
): number | null {
  const s = signals.find((x) => x.source === source);
  if (!s || s.points.length === 0) return null;
  // points are captured ascending by query default; take the last.
  return s.points[s.points.length - 1].value;
}

function DrivingSignalVerdicts({
  agents,
  signalsByAgent,
}: {
  agents: Array<{
    slug: string;
    name: string;
    entity_kind: string;
    score: {
      adoption: number | null;
      quality: number | null;
      momentum: number | null;
      community: number | null;
    };
  }>;
  signalsByAgent: Record<
    string,
    Array<{ source: string; points: { captured_at: string; value: number }[] }>
  >;
}) {
  if (agents.length < 2) return null;

  const PILLAR_KEYS = ["adoption", "quality", "momentum", "community"] as const;
  const PILLAR_LABELS: Record<(typeof PILLAR_KEYS)[number], string> = {
    adoption: "Adoption",
    quality: "Quality",
    momentum: "Momentum",
    community: "Community",
  };

  return (
    <section>
      <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Why each pillar moves
      </div>
      <ul className="divide-y divide-border rounded-md border border-border bg-card">
        {PILLAR_KEYS.map((pillar) => {
          // Pick the agent that wins this pillar by score.
          const ranked = [...agents].sort(
            (a, b) =>
              (b.score?.[pillar] ?? -Infinity) -
              (a.score?.[pillar] ?? -Infinity),
          );
          const winner = ranked[0];
          const winnerScore = winner.score?.[pillar];
          if (winnerScore == null) {
            return (
              <li key={pillar} className="px-4 py-3 text-sm">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground w-24">
                    {PILLAR_LABELS[pillar]}
                  </span>
                  <span className="text-muted-foreground">
                    Unrated for every agent in this comparison.
                  </span>
                </div>
              </li>
            );
          }

          // Find the highest-value source across all agents for the
          // pillar — that's the "driving" signal that explains why
          // someone wins. Falls back to "no underlying signals
          // contributed" when nothing concrete is on file.
          const isFM = winner.entity_kind === "foundation_model";
          const sources = isFM
            ? PILLAR_SOURCES_FM[pillar]
            : PILLAR_SOURCES_APP[pillar];

          let driving: { source: string; total: number } | null = null;
          for (const src of sources) {
            let total = 0;
            let any = false;
            for (const a of agents) {
              const v = latestValue(signalsByAgent[a.slug] ?? [], src);
              if (v != null) {
                total += v;
                any = true;
              }
            }
            if (!any) continue;
            if (driving == null || total > driving.total) {
              driving = { source: src, total };
            }
          }

          return (
            <li key={pillar} className="px-4 py-3 text-sm">
              <div className="flex flex-wrap items-baseline gap-3">
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground w-24">
                  {PILLAR_LABELS[pillar]}
                </span>
                <span className="font-medium">
                  {winner.name} wins
                </span>
                <span className="num text-xs text-muted-foreground">
                  {winnerScore.toFixed(1)} vs{" "}
                  {ranked
                    .slice(1)
                    .map((a) => a.score?.[pillar]?.toFixed(1) ?? "—")
                    .join(", ")}
                </span>
              </div>
              {driving ? (
                <div className="mt-2 text-xs text-muted-foreground">
                  <span className="font-mono uppercase tracking-wider text-foreground/70">
                    Driving signal
                  </span>{" "}
                  · {SIGNAL_LABEL[driving.source] ?? driving.source}:{" "}
                  {agents
                    .map((a) => {
                      const v = latestValue(
                        signalsByAgent[a.slug] ?? [],
                        driving!.source,
                      );
                      return `${a.name} ${v == null ? "—" : fmtCount(v)}`;
                    })
                    .join(" · ")}
                </div>
              ) : (
                <div className="mt-2 text-xs text-muted-foreground">
                  No raw signals for this pillar are on file yet —
                  the score is a fallback.
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// "Best at X" verdict per agent — whichever pillar is highest among the
// loaded set earns that pillar's name. Ties show no badge for any side.
function computeVerdicts(
  agents: Array<
    | {
        slug: string;
        score?: {
          adoption: number | null;
          quality: number | null;
          momentum: number | null;
          community: number | null;
        } | null;
      }
    | null
    | undefined
  >,
): Record<string, string> {
  const valid = agents.filter(
    (a): a is { slug: string; score: NonNullable<typeof a>["score"] } =>
      !!a && !!a.score,
  );
  if (valid.length < 2) return {};

  const PILLAR_LABELS = {
    adoption: "Adoption",
    quality: "Quality",
    momentum: "Momentum",
    community: "Community",
  } as const;

  const winners: Record<string, string[]> = {};
  for (const slug of valid.map((a) => a.slug)) winners[slug] = [];

  for (const pillar of ["adoption", "quality", "momentum", "community"] as const) {
    let best = -Infinity;
    let bestSlugs: string[] = [];
    for (const a of valid) {
      const v = a.score?.[pillar];
      if (v == null) continue;
      if (v > best) {
        best = v;
        bestSlugs = [a.slug];
      } else if (v === best) {
        bestSlugs.push(a.slug);
      }
    }
    if (bestSlugs.length === 1) {
      winners[bestSlugs[0]].push(PILLAR_LABELS[pillar]);
    }
  }

  const verdicts: Record<string, string> = {};
  for (const [slug, pillars] of Object.entries(winners)) {
    if (pillars.length > 0) verdicts[slug] = pillars.join(", ");
  }
  return verdicts;
}
