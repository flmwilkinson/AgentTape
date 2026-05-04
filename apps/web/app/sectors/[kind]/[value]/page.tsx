import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { SectorChart } from "@/components/sector-chart";
import { WatchToggle } from "@/components/watch-toggle";

// Sector detail — like an index page but rolled up by tag.
//
// Shows:
//   - cohort headline (avg AgentScore, member count, verdict)
//   - 30d composite chart (avg score over time)
//   - members table, ranked by score, with watch toggles
// The same shape as /indexes/[slug] so the mental model stays
// consistent: "another index, just one rolled up by capability".

const VALID_KINDS = ["capability", "deployment", "maturity", "domain", "license"];

export const dynamic = "force-dynamic";

interface PageParams {
  params: Promise<{ kind: string; value: string }>;
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { kind, value } = await params;
  return {
    title: `${pretty(value)} agents — ${kind} sector`,
    description: `Live ranking of agents tagged ${kind}:${value}. Composite chart, member list, AgentScore.`,
    alternates: { canonical: `/sectors/${kind}/${value}` },
  };
}

export default async function SectorDetailPage({ params }: PageParams) {
  const { kind, value } = await params;
  if (!VALID_KINDS.includes(kind)) notFound();

  // Default window is 7d so the chart fills with hourly buckets
  // backed by the 5-min heartbeat. The chart endpoint accepts 1d
  // (5-min buckets), 7d (hourly), 30d / 90d / all (daily) — the
  // current page only requests 7d but the API can serve any.
  const [history, members] = await Promise.all([
    api.sectorHistory(kind, value, "7d").catch(() => []),
    api.listAgents({
      tag_kind: kind,
      tag_value: value,
      sort: "score",
      limit: 100,
    }).catch(() => null),
  ]);

  if (!members || members.items.length === 0) {
    notFound();
  }

  const composite =
    history.length > 0 ? history.at(-1)?.avg_score ?? null : null;
  const first = history.length > 0 ? history[0]?.avg_score ?? null : null;
  const delta =
    composite != null && first != null ? composite - first : null;

  return (
    <article>
      <div className="border-b border-border bg-card">
        <div className="container py-10">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Sector · {kind}
          </div>
          <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
            {pretty(value)}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cohort of {members.total} admitted agents tagged{" "}
            <span className="font-mono">{kind}:{value}</span>. Composite
            below is the cohort's average AgentScore.
          </p>

          <div className="mt-6 grid gap-6 md:grid-cols-[auto_1fr]">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Avg AgentScore
              </div>
              <div className="mt-1 text-stat-xl font-semibold num">
                {formatScore(composite)}
              </div>
              {delta !== null && (
                <div className="mt-1">
                  <MoverChip delta={delta} unit="score" />
                  <span className="ml-2 text-xs text-muted-foreground">
                    vs 30d ago
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <SectorChart history={history} />
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8 md:py-12 space-y-8">
        <section>
          <div className="mb-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Members
            </div>
            <div className="text-xs text-muted-foreground">
              {members.items.length} shown · ranked by AgentScore
            </div>
          </div>
          <div className="overflow-x-auto rounded-md border border-border bg-card">
            <table className="num w-full min-w-[640px] text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-3 py-2 text-right">Rank</th>
                  <th className="px-3 py-2 text-left">Agent</th>
                  <th className="px-3 py-2 text-right">24h</th>
                  <th className="px-3 py-2 text-right">Score</th>
                  <th className="px-3 py-2 text-right">Δ24h</th>
                  <th className="px-3 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {members.items.map((a, i) => (
                  <tr key={a.id} className="border-b border-border last:border-b-0">
                    <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                      #{a.score?.rank_now ?? i + 1}
                    </td>
                    <td className="px-3 py-2">
                      <Link
                        href={`/agents/${a.slug}`}
                        className="font-sans font-medium hover:text-primary"
                      >
                        {a.name}
                      </Link>
                      {a.description && (
                        <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                          {a.description}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <RankArrow
                        delta={a.score?.rank_delta_24h ?? null}
                        rankNow={a.score?.rank_now ?? null}
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-semibold">
                      {formatScore(a.score?.agent_score ?? null)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {a.score?.delta_24h != null ? (
                        <MoverChip
                          delta={a.score.delta_24h}
                          unit="score"
                          variant="outline"
                        />
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <WatchToggle slug={a.slug} size="sm" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <p className="hairline pt-6 text-xs text-muted-foreground">
          Browse all sectors at{" "}
          <Link href="/sectors" className="text-primary hover:underline">
            /sectors
          </Link>
          .
        </p>
      </div>
    </article>
  );
}

function pretty(value: string): string {
  return value
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}
