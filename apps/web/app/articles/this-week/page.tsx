import Link from "next/link";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore, relativeTime } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { MoverChip } from "@/components/mover-chip";

// /articles/this-week — the auto-generated weekly recap.
//
// Rebuilt every visit (5-minute revalidate) against live data so it
// always reflects the actual past 7 days. Treats the published_at
// as "most recent Monday UTC" so the heading reads "this week".
//
// Why dynamic instead of a written article: weekly editorial would
// drift away from the live data the moment you wrote it. The recap's
// only job is to surface the seven-day shape of the floor — which
// the API already knows perfectly.

export const dynamic = "force-dynamic";
export const revalidate = 300;

export const metadata: Metadata = {
  title: "This week on AgentTape",
  description:
    "Weekly recap: biggest movers, new admissions, hot sectors. Auto-generated from the live index.",
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

export default async function WeeklyRecapPage() {
  const week = recentMonday();
  const [movers, recent, sectors] = await Promise.all([
    api.movers("7d", 50).catch(() => []),
    api.recentDiscoveries(12).catch(() => []),
    api.sectors("capability", "7d").catch(() => []),
  ]);

  const gainers = [...movers]
    .filter((m) => m.delta > 0)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 5);
  const decliners = [...movers]
    .filter((m) => m.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 5);

  const sectorsByVerdict = {
    booming: sectors.filter((s) => s.verdict === "booming"),
    growing: sectors.filter((s) => s.verdict === "growing"),
    cooling: sectors.filter((s) => s.verdict === "cooling"),
    declining: sectors.filter((s) => s.verdict === "declining"),
  };

  const newAdmissions = recent.filter((a) => {
    const ageDays =
      (Date.now() - new Date(a.discovered_at).getTime()) / 86_400_000;
    return ageDays <= 7;
  });

  return (
    <article className="container py-10 md:py-14 max-w-4xl">
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
          Auto-generated from the past seven days of signal traffic — biggest
          score moves, new admissions, hot sectors. Recomputed each visit, so
          it never lags the data.
        </p>
      </header>

      {/* Movers */}
      <section className="mb-12">
        <h2 className="editorial mb-4 text-2xl font-semibold leading-tight md:text-3xl">
          What moved
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <MoverColumn
            title="Climbers · 7d"
            items={gainers}
            emptyHint="No upward moves above the noise this week."
          />
          <MoverColumn
            title="Decliners · 7d"
            items={decliners}
            emptyHint="No declines above the noise this week."
          />
        </div>
      </section>

      {/* Sectors */}
      <section className="mb-12">
        <h2 className="editorial mb-4 text-2xl font-semibold leading-tight md:text-3xl">
          Sector heat
        </h2>
        {sectors.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No sector data this week — agents need tags first.
          </p>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            <SectorBlock
              title="Booming · this week"
              tone="text-gain"
              items={sectorsByVerdict.booming.slice(0, 4)}
            />
            <SectorBlock
              title="Cooling · this week"
              tone="text-loss"
              items={[
                ...sectorsByVerdict.cooling,
                ...sectorsByVerdict.declining,
              ].slice(0, 4)}
            />
          </div>
        )}
      </section>

      {/* New admissions */}
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

// ----------------------------------------------------------------- atoms

function MoverColumn({
  title,
  items,
  emptyHint,
}: {
  title: string;
  items: { agent: { slug: string; name: string }; delta: number; score_now: number }[];
  emptyHint: string;
}) {
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
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

function SectorBlock({
  title,
  tone,
  items,
}: {
  title: string;
  tone: string;
  items: { value: string; display_name: string; members: number; delta: number | null }[];
}) {
  return (
    <div className="rounded-md border border-border bg-card">
      <div
        className={`border-b border-border px-4 py-2 font-mono text-[10px] uppercase tracking-wider ${tone}`}
      >
        {title}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-4 text-xs text-muted-foreground">
          Nothing notable this week.
        </div>
      ) : (
        <ul>
          {items.map((s) => (
            <li
              key={s.value}
              className="flex items-center gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
            >
              <Link
                href={`/sectors/capability/${s.value}`}
                className="min-w-0 flex-1 truncate text-sm hover:text-primary"
              >
                {s.display_name}
              </Link>
              <span className="text-xs text-muted-foreground">
                {s.members} agents
              </span>
              {s.delta != null && (
                <span className={`num text-xs font-mono ${tone}`}>
                  {s.delta >= 0 ? "+" : ""}
                  {s.delta.toFixed(2)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
