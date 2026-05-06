"use client";

import { Plus, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CompareChart } from "@/components/compare-chart";
import { MoverChip } from "@/components/mover-chip";
import { PillarBar } from "@/components/pillar-bar";
import { RankArrow } from "@/components/rank-arrow";

// /compare — up to 5 agents side by side, with an overlay score chart,
// per-agent cards, a "Best at X" verdict per agent, and a side-by-side
// scorecard matrix that breaks each pillar into its contributing
// signals so the comparison is fully traceable.
//
// URL is the canonical state: /compare?slugs=foo,bar,baz — shareable.
// Old /compare?a=foo&b=bar URLs are still honoured so existing links
// don't break.

const MAX = 5;

export default function ComparePage() {
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
  const [draft, setDraft] = useState("");

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

      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!draft || slugs.includes(draft) || slugs.length >= MAX) return;
          setSlugs([...slugs, draft]);
          setDraft("");
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="agent-slug (e.g. autogpt, browser-use, anthropic-claude-haiku-latest)"
          className="flex-1 min-w-[260px] rounded-md border border-border bg-card px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          disabled={!draft || slugs.length >= MAX}
        >
          <Plus className="h-4 w-4" /> Add
        </button>
      </form>

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
          <div
            key={`empty-${i}`}
            className="flex min-h-[220px] items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground"
          >
            add an agent
          </div>
        ))}
      </div>

      {/* Side-by-side scorecard — pillars-as-rows matrix. Best cell
          per row gets a primary highlight so a quick scan shows
          which agent wins each pillar. */}
      {slugs.length >= 2 && (
        <ScorecardMatrix
          agents={detailQueries
            .map((q) => q.data)
            .filter((a): a is NonNullable<typeof a> => Boolean(a))}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- matrix

function ScorecardMatrix({
  agents,
}: {
  agents: Array<{
    slug: string;
    name: string;
    score: {
      agent_score: number | null;
      adoption: number | null;
      quality: number | null;
      momentum: number | null;
      community: number | null;
    };
  }>;
}) {
  if (agents.length === 0) return null;

  const rows: { key: keyof typeof agents[0]["score"]; label: string }[] = [
    { key: "agent_score", label: "AgentScore" },
    { key: "adoption", label: "Adoption" },
    { key: "quality", label: "Quality" },
    { key: "momentum", label: "Momentum" },
    { key: "community", label: "Community" },
  ];

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
              return (
                <tr
                  key={row.key}
                  className={
                    row.key === "agent_score"
                      ? "border-b border-border bg-subtle/20 font-medium"
                      : "border-b border-border last:border-b-0"
                  }
                >
                  <td className="px-3 py-2 text-foreground/85">{row.label}</td>
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
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Highest value per row in the primary colour. "—" means the
        pillar is Unrated for that agent.
      </p>
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
