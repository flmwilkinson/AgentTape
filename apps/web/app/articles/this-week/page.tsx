import Link from "next/link";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatCompact, formatScore, relativeTime } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { HeatmapCell } from "@/components/heatmap-cell";
import { IndexHistoryChart } from "@/components/index-history-chart";
import { MoverChip } from "@/components/mover-chip";
import { Sparkline } from "@/components/sparkline";

// /articles/this-week — the auto-generated weekly recap.
//
// Rebuilt every visit (5-minute revalidate) against live data so it
// always reflects the actual past 7 days. Heading reads "Week of
// <most recent Monday UTC>".
//
// The page is a server component that fans out a single Promise.all
// of API calls (each with a .catch fallback) and assembles a small
// editorial page out of the responses. Sections are progressive — if
// an upstream call fails or returns empty, the whole section is
// dropped rather than rendering a half-empty placeholder.

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "This week on AgentTape",
  description:
    "Weekly recap: index pulse, biggest movers, sector heatmap, foundation-model leaders, and new admissions. Auto-generated from the live floor.",
  alternates: { canonical: "/articles/this-week" },
};

function recentMonday(): Date {
  const now = new Date();
  const day = now.getUTCDay();
  const diff = (day + 6) % 7;
  return new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate() - diff,
    ),
  );
}

const EMPTY_AGENTS_PAGE = { items: [], total: 0, limit: 1, offset: 0 };

export default async function WeeklyRecapPage() {
  const week = recentMonday();

  // Pull indexes first so we can fan out the headline-index calls in
  // the same parallel batch as everything else (one extra round-trip
  // is fine — listIndexes is a cheap query and the rest of the page
  // depends on it).
  const indexes = await api.listIndexes().catch(() => []);
  const headline = indexes[0] ?? null;

  const [
    movers,
    fmMovers,
    recent,
    sectors,
    indexHistory,
    rebalances,
    agentsPage,
  ] = await Promise.all([
    api.movers("7d", 50).catch(() => []),
    api
      .movers("7d", 5, { entity_kind: "foundation_model" })
      .catch(() => []),
    api.recentDiscoveries(20).catch(() => []),
    api.sectors("capability", "7d").catch(() => []),
    headline
      ? api.indexHistory(headline.slug, "30d").catch(() => [])
      : Promise.resolve([]),
    headline
      ? api.indexRebalances(headline.slug, 5).catch(() => [])
      : Promise.resolve([]),
    api.listAgents({ limit: 1 }).catch(() => EMPTY_AGENTS_PAGE),
  ]);

  // ---------------------------------------------------------- mover splits
  const gainers = [...movers]
    .filter((m) => m.delta > 0)
    .sort((a, b) => b.delta - a.delta);
  const decliners = [...movers]
    .filter((m) => m.delta < 0)
    .sort((a, b) => a.delta - b.delta);
  const topMover = gainers[0] ?? null;

  // ---------------------------------------------------------- sector heat
  const sortedSectors = [...sectors]
    .filter((s) => s.delta != null)
    .sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0));
  const hottestSector = sortedSectors[0] ?? null;

  // ---------------------------------------------------------- new on floor
  const newAdmissions = recent.filter((a) => {
    const ageDays =
      (Date.now() - new Date(a.discovered_at).getTime()) / 86_400_000;
    return ageDays <= 7;
  });

  // ---------------------------------------------------------- index pulse
  const indexValues = indexHistory.map((h) => h.composite_value);
  const indexNow =
    indexHistory[indexHistory.length - 1]?.composite_value ??
    headline?.composite_value ??
    null;
  // Snap to the closest snapshot ~7 days ago for the week-over-week
  // delta, falling back to the chart's left edge if history is shorter.
  const sevenDaysAgo = Date.now() - 7 * 86_400_000;
  const closestToWeekAgo = indexHistory.reduce<
    { captured_at: string; composite_value: number } | null
  >((best, h) => {
    const t = new Date(h.captured_at).getTime();
    if (!best) return h;
    const bestDist = Math.abs(new Date(best.captured_at).getTime() - sevenDaysAgo);
    const thisDist = Math.abs(t - sevenDaysAgo);
    return thisDist < bestDist ? h : best;
  }, null);
  const indexThen =
    closestToWeekAgo?.composite_value ??
    indexHistory[0]?.composite_value ??
    null;
  const indexDelta =
    indexNow != null && indexThen != null ? indexNow - indexThen : null;

  // Surface a rebalance only if it landed within the past 7 days.
  const recentRebalance =
    rebalances.find((r) => {
      const ageDays =
        (Date.now() - new Date(r.run_at).getTime()) / 86_400_000;
      return ageDays <= 7;
    }) ?? null;

  return (
    <article className="container py-10 md:py-14 max-w-5xl">
      <BackLink href="/articles" label="All articles" className="mb-6" />

      <header className="mb-10 border-b border-border pb-8">
        <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          <span className="rounded-full border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[9px] text-primary">
            Live
          </span>
          <span>
            Week of{" "}
            {week.toLocaleDateString(undefined, {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </span>
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          This week on AgentTape
        </h1>
        <p className="editorial mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground md:text-xl">
          Auto-generated from the past seven days of signal traffic — index
          pulse, biggest score moves, capability heat, foundation-model
          leaders, and what just landed on the floor. Recomputed each visit,
          so it never lags the data.
        </p>
      </header>

      {/* ---------------------------------------------- KPI strip */}
      <section className="mb-12 grid gap-3 md:grid-cols-4">
        <Kpi
          label="Top index"
          value={indexNow != null ? formatScore(indexNow) : "—"}
          delta={indexDelta}
          sparkline={indexValues}
          caption={headline?.name ?? "—"}
          href={headline ? `/indexes/${headline.slug}` : undefined}
        />
        <Kpi
          label="Tracked agents"
          value={formatCompact(agentsPage.total)}
          caption={
            newAdmissions.length > 0
              ? `+${newAdmissions.length} this week`
              : "Steady this week"
          }
        />
        <Kpi
          label="Top mover · 7d"
          value={topMover ? formatScore(topMover.score_now) : "—"}
          delta={topMover?.delta ?? null}
          caption={topMover?.agent.name ?? "No moves above the noise"}
          href={topMover ? `/agents/${topMover.agent.slug}` : undefined}
        />
        <Kpi
          label="Hottest sector"
          value={
            hottestSector?.delta != null
              ? `${hottestSector.delta > 0 ? "+" : ""}${hottestSector.delta.toFixed(2)}`
              : "—"
          }
          caption={hottestSector?.display_name ?? "No sector heat"}
          href={
            hottestSector
              ? `/sectors/capability/${hottestSector.value}`
              : undefined
          }
        />
      </section>

      {/* ---------------------------------------------- index pulse */}
      {headline && indexHistory.length > 1 && (
        <section className="mb-12">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Index pulse · 30 days
              </div>
              <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
                {headline.name}
              </h2>
            </div>
            <Link
              href={`/indexes/${headline.slug}`}
              className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
            >
              Open index →
            </Link>
          </div>
          <IndexHistoryChart history={indexHistory} />
          {recentRebalance && (
            <RebalanceCard rebalance={recentRebalance} />
          )}
        </section>
      )}

      {/* ---------------------------------------------- movers */}
      <section className="mb-12">
        <h2 className="editorial mb-4 text-2xl font-semibold leading-tight md:text-3xl">
          What moved
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <MoverColumn
            title="Climbers · 7d"
            items={gainers.slice(0, 6)}
            emptyHint="No upward moves above the noise this week."
          />
          <MoverColumn
            title="Decliners · 7d"
            items={decliners.slice(0, 6)}
            emptyHint="No declines above the noise this week."
          />
        </div>
      </section>

      {/* ---------------------------------------------- foundation models */}
      {fmMovers.length > 0 && (
        <section className="mb-12">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Foundation models · 7d
              </div>
              <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
                Where the models moved
              </h2>
            </div>
            <Link
              href="/models"
              className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
            >
              All models →
            </Link>
          </div>
          <MoverColumn
            title="Top FM moves"
            items={[...fmMovers]
              .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
              .slice(0, 5)}
            emptyHint="No FM moves above the noise this week."
          />
        </section>
      )}

      {/* ---------------------------------------------- sector heatmap */}
      {sectors.length > 0 && (
        <section className="mb-12">
          <div className="mb-4 flex items-end justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Capability heatmap · 7-day delta
              </div>
              <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
                Where the heat is
              </h2>
            </div>
            <Link
              href="/sectors"
              className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
            >
              All sectors →
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {sortedSectors.slice(0, 12).map((s) => (
              <HeatmapCell
                key={s.value}
                label={s.display_name}
                value={s.delta}
                sublabel={`${s.members} agents`}
                href={`/sectors/capability/${s.value}`}
              />
            ))}
          </div>
        </section>
      )}

      {/* ---------------------------------------------- new admissions */}
      <section className="mb-12">
        <h2 className="editorial mb-4 text-2xl font-semibold leading-tight md:text-3xl">
          New on the floor
        </h2>
        {newAdmissions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No admissions in the past 7 days — the discovery service is between
            sweeps.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border bg-card">
            {newAdmissions.map((a) => (
              <li
                key={a.id}
                className="flex items-baseline justify-between gap-3 px-4 py-3 text-sm"
              >
                <Link
                  href={`/agents/${a.slug}`}
                  className="min-w-0 flex-1 truncate hover:text-primary"
                >
                  <span className="font-medium">{a.name}</span>
                  <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {a.discovered_via.replace(/_/g, " ")}
                  </span>
                </Link>
                <span className="num text-sm font-semibold">
                  {formatScore(a.score?.agent_score ?? null)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {relativeTime(a.discovered_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="hairline mt-12 pt-6 text-xs text-muted-foreground">
        Recomputed each visit from{" "}
        <Link href="/trending" className="text-primary hover:underline">
          /trending
        </Link>
        ,{" "}
        <Link href="/sectors" className="text-primary hover:underline">
          /sectors
        </Link>
        ,{" "}
        <Link href="/indexes" className="text-primary hover:underline">
          /indexes
        </Link>{" "}
        and{" "}
        <Link href="/new" className="text-primary hover:underline">
          /new
        </Link>
        . Methodology lives at{" "}
        <Link href="/methodology" className="text-primary hover:underline">
          /methodology
        </Link>
        .
      </div>
    </article>
  );
}

// =============================================================== atoms

interface KpiProps {
  label: string;
  value: string;
  delta?: number | null;
  sparkline?: number[];
  caption?: string;
  href?: string;
}

function Kpi({ label, value, delta, sparkline, caption, href }: KpiProps) {
  const inner = (
    <>
      <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1.5 flex items-end gap-2">
        <span className="num text-2xl font-semibold leading-none">
          {value}
        </span>
        {delta !== undefined && delta !== null && (
          <MoverChip delta={delta} unit="score" />
        )}
      </div>
      {sparkline && sparkline.length >= 2 && (
        <Sparkline values={sparkline} width={120} height={28} className="mt-2" />
      )}
      {caption && (
        <div className="mt-2 truncate text-xs text-muted-foreground">
          {caption}
        </div>
      )}
    </>
  );
  const cls =
    "block rounded-md border border-border bg-card p-4 transition-colors";
  return href ? (
    <Link href={href} className={`${cls} hover:border-foreground/20 hover:bg-subtle`}>
      {inner}
    </Link>
  ) : (
    <div className={cls}>{inner}</div>
  );
}

function RebalanceCard({
  rebalance,
}: {
  rebalance: {
    run_at: string;
    additions: unknown[] | null;
    removals: unknown[] | null;
    weight_changes: unknown[] | null;
    narrative_md: string | null;
  };
}) {
  const adds = rebalance.additions?.length ?? 0;
  const removes = rebalance.removals?.length ?? 0;
  const reweights = rebalance.weight_changes?.length ?? 0;
  return (
    <div className="mt-4 rounded-md border border-border bg-card p-4 text-sm">
      <div className="flex items-baseline justify-between gap-3 font-mono text-[10px] uppercase tracking-wider">
        <span className="text-muted-foreground">
          Rebalance · {relativeTime(rebalance.run_at)}
        </span>
        <span className="text-foreground/70">
          {adds} added · {removes} removed · {reweights} reweighted
        </span>
      </div>
      {rebalance.narrative_md && (
        <p className="mt-2 text-muted-foreground">{rebalance.narrative_md}</p>
      )}
    </div>
  );
}

function MoverColumn({
  title,
  items,
  emptyHint,
}: {
  title: string;
  items: {
    agent: { slug: string; name: string };
    delta: number;
    score_now: number;
  }[];
  emptyHint: string;
}) {
  return (
    <div className="rounded-md border border-border bg-card">
      {title && (
        <div className="border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {title}
        </div>
      )}
      {items.length === 0 ? (
        <div className="px-4 py-4 text-xs text-muted-foreground">
          {emptyHint}
        </div>
      ) : (
        <ul>
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
      )}
    </div>
  );
}
