import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatScore, relativeTime } from "@/lib/format";
import { IndexCard } from "@/components/index-card";
import { MoverChip } from "@/components/mover-chip";
import { Sparkline } from "@/components/sparkline";
import { TickerCard } from "@/components/ticker-card";
import { TickerTape } from "@/components/ticker-tape";
import { HeatmapCell } from "@/components/heatmap-cell";

// Server-rendered initial paint. Client components ride on top for the
// live ticker tape (WS) and number animations.

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [agentsPage, indexes, movers7d, movers1d, recent, tags] =
    await Promise.all([
      api.listAgents({ sort: "score", limit: 60 }),
      api.listIndexes(),
      api.movers("7d", 12),
      api.movers("1d", 6),
      api.recentDiscoveries(8),
      api.tags(),
    ]);

  const agents = agentsPage.items;
  const heroMover = movers7d[0];

  // For the index cards: pull a thin history per index in parallel.
  const indexHistories = await Promise.all(
    indexes.map((i) =>
      api
        .indexHistory(i.slug, "30d")
        .then((rows) => ({ slug: i.slug, values: rows.map((r) => r.composite_value) }))
        .catch(() => ({ slug: i.slug, values: [] as number[] })),
    ),
  );
  const histBySlug = Object.fromEntries(indexHistories.map((h) => [h.slug, h.values]));

  // Sector heatmap: aggregate by capability tags. Light approximation —
  // counts agents with each capability tag and uses the average score
  // delta as the heat. When no tagged agents exist (current local
  // state — Claude enrichment off), the cells are present but neutral.
  const capabilityTags = tags.filter((t) => t.kind === "capability").slice(0, 12);

  return (
    <div>
      {/* Live ticker tape — feeds itself from /ws/ticker. */}
      <TickerTape initial={agents.slice(0, 30)} />

      <div className="container py-8 md:py-12">
        {/* Hero mover */}
        {heroMover && (
          <section className="mb-12">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Hero · 7d
            </div>
            <h1 className="editorial mt-1 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
              {heroMover.agent.name}{" "}
              <span className="text-muted-foreground">
                {heroMover.delta >= 0 ? "extends" : "gives back"}{" "}
                <span className="num">
                  {heroMover.delta >= 0 ? "+" : ""}
                  {heroMover.delta.toFixed(2)}
                </span>{" "}
                points this week
              </span>
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
              {heroMover.agent.description ?? "—"}
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <div className="rounded-md border border-border bg-card p-4">
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  AgentScore
                </div>
                <div className="mt-1 text-stat-xl font-semibold num">
                  {formatScore(heroMover.score_now)}
                </div>
                <div className="mt-1">
                  <MoverChip delta={heroMover.delta} unit="score" />
                </div>
              </div>
              <Link
                href={`/agents/${heroMover.agent.slug}`}
                className="text-sm font-medium text-primary hover:underline"
              >
                See ticker page →
              </Link>
            </div>
          </section>
        )}

        {/* Index cards — 5 launch indexes */}
        <section className="mb-12">
          <SectionHead label="Indexes" hint="Equal-weight v1 · weekly rebalance" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {indexes.map((i) => (
              <IndexCard
                key={i.id}
                index={i}
                history={histBySlug[i.slug] ?? []}
              />
            ))}
          </div>
        </section>

        {/* Movers row */}
        <section className="mb-12">
          <SectionHead
            label="Movers"
            trailing={
              <Link
                href="/movers"
                className="text-xs text-primary hover:underline"
              >
                Full table →
              </Link>
            }
          />
          <div className="grid gap-3 md:grid-cols-2">
            <MoversList title="Today" items={movers1d} />
            <MoversList title="7 days" items={movers7d.slice(0, 6)} />
          </div>
        </section>

        {/* Sector heatmap (capability axis) */}
        {capabilityTags.length > 0 && (
          <section className="mb-12">
            <SectionHead label="Heatmap" hint="Capability sectors" />
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
              {capabilityTags.map((t) => (
                <HeatmapCell
                  key={`${t.kind}:${t.value}`}
                  label={t.display_name}
                  sublabel={`${t.count} agents`}
                  value={null /* avg momentum unknown without full series */}
                />
              ))}
            </div>
          </section>
        )}

        {/* Just Discovered rail */}
        <section className="mb-12">
          <SectionHead
            label="Just Discovered"
            hint={`Admitted by the discovery service · ${recent.length} latest`}
            trailing={
              <Link
                href="/discovery"
                className="text-xs text-primary hover:underline"
              >
                Live feed →
              </Link>
            }
          />
          <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0">
            {recent.map((a) => (
              <TickerCard
                key={a.id}
                agent={a}
                className="shrink-0 basis-[260px]"
              />
            ))}
          </div>
        </section>

        {/* This Week — editorial block */}
        <section className="rounded-md border border-border bg-editorial p-8 md:p-12">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            This Week
          </div>
          <h2 className="editorial mt-3 text-2xl font-semibold leading-tight md:text-3xl">
            Browser agents push into the index
          </h2>
          <p className="editorial mt-4 max-w-prose text-base leading-relaxed text-foreground/85">
            The number of admitted agents tagged with{" "}
            <span className="font-semibold">browsing</span> is up week-over-week,
            displacing two single-purpose code-generation tools from the
            top quartile of TAPE-100. The full report is published every Monday
            at 03:00 UTC.
          </p>
          <p className="mt-6 text-xs text-muted-foreground">
            Reports are auto-generated from the rebalance diff and edited by
            Claude. See{" "}
            <Link href="/methodology" className="text-primary underline-offset-2 hover:underline">
              methodology
            </Link>
            .
          </p>
        </section>
      </div>
    </div>
  );
}

function SectionHead({
  label,
  hint,
  trailing,
}: {
  label: string;
  hint?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </div>
      {trailing}
    </div>
  );
}

function MoversList({
  title,
  items,
}: {
  title: string;
  items: { agent: { slug: string; name: string }; delta: number; score_now: number }[];
}) {
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {title}
        </div>
      </div>
      <ul>
        {items.length === 0 && (
          <li className="px-4 py-3 text-xs text-muted-foreground">No movers yet.</li>
        )}
        {items.map((m) => (
          <li
            key={m.agent.slug}
            className="flex items-center gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
          >
            <Link
              href={`/agents/${m.agent.slug}`}
              className="min-w-0 flex-1 truncate text-sm hover:text-primary"
            >
              {m.agent.name}
            </Link>
            <span className="num text-sm font-semibold">
              {formatScore(m.score_now)}
            </span>
            <MoverChip delta={m.delta} unit="score" />
          </li>
        ))}
      </ul>
    </div>
  );
}
