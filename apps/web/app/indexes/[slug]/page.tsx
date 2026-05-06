import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore, relativeTime } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { CompareTrayToggle } from "@/components/compare-tray";
import { IndexHistoryChart } from "@/components/index-history-chart";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const i = await api.getIndex(slug);
    return {
      title: i.name,
      description: `${i.name} — ${i.members_count} constituents.`,
      openGraph: {
        title: `${i.name} — AgentTape`,
        images: [{ url: `/api/og/index/${i.slug}` }],
      },
    };
  } catch {
    return { title: slug };
  }
}

export default async function IndexDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let detail;
  try {
    detail = await api.getIndex(slug);
  } catch {
    notFound();
  }
  const [history, rebalances] = await Promise.all([
    api.indexHistory(slug, "30d").catch(() => []),
    api.indexRebalances(slug, 6).catch(() => []),
  ]);

  const composite = detail.composite_value;
  const first = history[0]?.composite_value ?? null;
  const delta = composite != null && first != null ? composite - first : null;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: detail.name,
    description: detail.methodology_md ?? `${detail.name} index`,
    identifier: detail.slug,
    url: `/indexes/${detail.slug}`,
  };

  return (
    <article>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <div className="border-b border-border bg-card">
        <div className="container py-10">
          <BackLink href="/indexes" label="All indexes" className="mb-4" />
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Index
          </div>
          <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
            {detail.name}
          </h1>
          <p className="mt-2 text-xs text-muted-foreground">
            <a href="#rebalance-log" className="text-primary hover:underline">
              Rebalance log
            </a>{" "}
            · <a href="#methodology" className="text-primary hover:underline">Methodology</a>
          </p>
          <div className="mt-6 grid gap-6 md:grid-cols-[auto_1fr]">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Composite
              </div>
              <div className="mt-1 text-stat-xl font-semibold num">
                {formatScore(composite)}
              </div>
              {delta !== null && (
                <div className="mt-1">
                  <MoverChip delta={delta} unit="score" />
                  <span className="ml-2 text-xs text-muted-foreground">vs 30d ago</span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <IndexHistoryChart history={history} />
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8 md:py-12 space-y-12">
        {/* Constituents */}
        <section>
          <SectionHead label="Constituents" hint={`${detail.members_count} agents`} />
          <div className="overflow-x-auto rounded-md border border-border bg-card">
            <table className="num w-full min-w-[640px] text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="px-3 py-2 text-right">Rank</th>
                  <th className="px-3 py-2 text-left">Agent</th>
                  <th className="px-3 py-2 text-right">24h</th>
                  <th className="px-3 py-2 text-right">Score</th>
                  <th className="px-3 py-2 text-right">Δ24h</th>
                  <th className="px-3 py-2 text-right hidden md:table-cell">Weight</th>
                  <th className="px-3 py-2 text-right hidden md:table-cell">Added</th>
                  <th className="px-3 py-2 w-8"></th>
                </tr>
              </thead>
              <tbody>
                {detail.constituents.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-6 text-center text-xs text-muted-foreground"
                    >
                      No agents in this index yet — index hasn't rebalanced.
                    </td>
                  </tr>
                )}
                {detail.constituents.map((c, i) => (
                  <tr
                    key={c.agent.slug}
                    className="border-b border-border last:border-b-0"
                  >
                    <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                      #{c.agent.score?.rank_now ?? i + 1}
                    </td>
                    <td className="px-3 py-2">
                      <Link
                        href={`/agents/${c.agent.slug}`}
                        className="font-sans font-medium hover:text-primary"
                      >
                        {c.agent.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <RankArrow
                        delta={c.agent.score?.rank_delta_24h ?? null}
                        rankNow={c.agent.score?.rank_now ?? null}
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-semibold">
                      {formatScore(c.agent.score?.agent_score ?? null)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {c.agent.score?.delta_24h != null ? (
                        <span
                          className={
                            c.agent.score.delta_24h > 0
                              ? "text-gain"
                              : c.agent.score.delta_24h < 0
                                ? "text-loss"
                                : "text-muted-foreground"
                          }
                        >
                          {c.agent.score.delta_24h > 0 ? "+" : ""}
                          {c.agent.score.delta_24h.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-muted-foreground hidden md:table-cell">
                      {(c.weight * 100).toFixed(2)}%
                    </td>
                    <td className="px-3 py-2 text-right text-muted-foreground hidden md:table-cell">
                      {relativeTime(c.added_at)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <CompareTrayToggle slug={c.agent.slug} />
                        <WatchToggle slug={c.agent.slug} size="sm" />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Rebalance log */}
        <section id="rebalance-log" className="scroll-mt-16">
          <SectionHead label="Rebalance log" />
          <ol className="space-y-4">
            {rebalances.length === 0 && (
              <li className="text-xs text-muted-foreground">
                No rebalances yet.
              </li>
            )}
            {rebalances.map((r) => (
              <li
                key={r.id}
                className="rounded-md border border-border bg-card p-4 text-sm"
              >
                <div className="flex flex-wrap items-baseline gap-3">
                  <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    {new Date(r.run_at).toLocaleString()}
                  </span>
                  <span className="text-muted-foreground">·</span>
                  <span className="num">
                    +{(r.additions?.length ?? 0)} added
                  </span>
                  <span className="num">−{(r.removals?.length ?? 0)} removed</span>
                  <span className="num text-muted-foreground">
                    ~{(r.weight_changes?.length ?? 0)} reweights
                  </span>
                </div>
                {r.narrative_md && (
                  <p className="editorial mt-3 max-w-prose text-base leading-relaxed text-foreground/90">
                    {r.narrative_md}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* Methodology */}
        {detail.methodology_md && (
          <section id="methodology" className="scroll-mt-16">
            <SectionHead label="Methodology" />
            <div className="rounded-md border border-border bg-editorial p-6 md:p-8">
              <pre className="editorial whitespace-pre-wrap font-serif text-base leading-relaxed text-foreground/90">
                {detail.methodology_md}
              </pre>
            </div>
          </section>
        )}
      </div>
    </article>
  );
}

function SectionHead({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="mb-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
