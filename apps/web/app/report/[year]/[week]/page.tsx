import Link from "next/link";
import { api } from "@/lib/api-client";
import { Sparkline } from "@/components/sparkline";
import { formatScore } from "@/lib/format";

// /report/<year>/<week> — the weekly editorial.
//
// Findings are computed deterministically from the past week's
// movers + sector verdicts + recent admissions. No prose is invented
// here. If you want LLM-written narrative on top, point this at the
// /admin/weekly-report endpoint (env-flagged ANTHROPIC_API_KEY) — see
// the methodology page for the wiring details. Until that endpoint
// exists, the deterministic copy below is the source of truth.

export const dynamic = "force-dynamic";

interface PageParams {
  params: Promise<{ year: string; week: string }>;
}

export async function generateMetadata({ params }: PageParams) {
  const { year, week } = await params;
  return { title: `Week ${week}, ${year}` };
}

export default async function WeeklyReport({ params }: PageParams) {
  const { year, week } = await params;
  const [movers, indexes, recent, capabilitySectors] = await Promise.all([
    api.movers("7d", 12),
    api.listIndexes(),
    api.recentDiscoveries(50).catch(() => []),
    api.sectors("capability", "7d").catch(() => []),
  ]);

  const tape = indexes.find((i) => i.slug === "tape-100");
  const tapeHistory = tape
    ? await api.indexHistory(tape.slug, "30d").catch(() => [])
    : [];

  const findings = computeFindings({
    movers,
    indexes,
    recent,
    capabilitySectors,
  });

  return (
    <article className="container py-12 md:py-20 max-w-4xl">
      {/* Cover */}
      <header className="mb-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Week {week} · {year}
        </div>
        <h1 className="editorial mt-3 text-4xl font-semibold leading-[1.05] md:text-6xl">
          The week in agents.
        </h1>
        <p className="editorial mt-6 max-w-2xl text-xl leading-relaxed text-muted-foreground md:text-2xl">
          Findings derived from this week's movers, sector verdicts and new
          admissions. Numbers come straight from the indexes.
        </p>
      </header>

      {/* Hero chart */}
      {tape && tapeHistory.length > 0 && (
        <section className="mb-16">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            TAPE-100 · 30d
          </div>
          <div className="mt-2 flex items-end justify-between gap-4">
            <div className="text-stat-xl font-semibold num">
              {formatScore(tape.composite_value)}
            </div>
          </div>
          <div className="mt-6">
            <Sparkline
              values={tapeHistory.map((s) => s.composite_value)}
              width={920}
              height={180}
              color="primary"
            />
          </div>
        </section>
      )}

      {/* Three data-derived findings */}
      <section className="mb-16 grid gap-12 md:grid-cols-3">
        {findings.map((f, i) => (
          <Finding key={i} number={i + 1} title={f.title} body={f.body} />
        ))}
      </section>

      {/* Movers table */}
      <section className="mb-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Top movers · 7 days
        </div>
        <ul className="mt-4 divide-y divide-border rounded-md border border-border bg-card">
          {movers.slice(0, 8).map((m) => (
            <li
              key={m.agent.slug}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-4 px-4 py-3"
            >
              <Link
                href={`/agents/${m.agent.slug}`}
                className="truncate text-sm font-medium hover:text-primary"
              >
                {m.agent.name}
              </Link>
              <span className="num text-sm font-semibold">
                {formatScore(m.score_now)}
              </span>
              <span
                className={`num text-xs ${m.delta >= 0 ? "text-gain" : "text-loss"}`}
              >
                {m.delta > 0 ? "+" : ""}
                {m.delta.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <p className="mt-16 text-xs text-muted-foreground">
        Reports are versioned at /report/[year]/[week]. Earlier:{" "}
        <Link href="/report" className="text-primary hover:underline">
          archive
        </Link>
        .
      </p>
    </article>
  );
}

interface FindingPart {
  title: string;
  body: string;
}

function computeFindings({
  movers,
  indexes,
  recent,
  capabilitySectors,
}: {
  movers: { agent: { name: string }; delta: number }[];
  indexes: { name: string; composite_value: number | null; members_count: number }[];
  recent: { discovered_at: string }[];
  capabilitySectors: {
    display_name: string;
    delta: number | null;
    verdict: string;
  }[];
}): FindingPart[] {
  const out: FindingPart[] = [];

  // 1. Strongest mover narrative.
  const top = [...movers].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))[0];
  if (top && Math.abs(top.delta) >= 0.5) {
    const dir = top.delta >= 0 ? "added" : "lost";
    out.push({
      title: `${top.agent.name} ${dir} ${Math.abs(top.delta).toFixed(1)} points`,
      body: `The biggest single move on the tape this week. The headline change feeds into Monday's TAPE-100 rebalance — see the rebalance log on /indexes/tape-100 for the diff.`,
    });
  } else {
    out.push({
      title: "Quiet tape",
      body: "No headline moves above one point this week. Recompute frequency means signal-stable agents look flat; consult /trending if you want the underlying ROC numbers.",
    });
  }

  // 2. Hot sector narrative.
  const hot = capabilitySectors
    .filter((s) => s.verdict === "booming" || s.verdict === "growing")
    .sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0))[0];
  if (hot && hot.delta != null) {
    out.push({
      title: `${hot.display_name} agents are ${hot.verdict}`,
      body: `Average AgentScore in the cohort moved ${hot.delta >= 0 ? "+" : ""}${hot.delta.toFixed(2)} points over the window. /sectors keeps a live read on whether this lasts.`,
    });
  } else {
    const cooling = capabilitySectors
      .filter((s) => s.verdict === "cooling" || s.verdict === "declining")
      .sort((a, b) => (a.delta ?? 0) - (b.delta ?? 0))[0];
    if (cooling && cooling.delta != null) {
      out.push({
        title: `${cooling.display_name} cohort is cooling`,
        body: `Average AgentScore here moved ${cooling.delta.toFixed(2)} points. Worth a closer look — sometimes that's a single dominant agent, sometimes the whole shape.`,
      });
    } else {
      out.push({
        title: "Sector rotation steady",
        body: "No capability cohort booming or cooling beyond ±0.5 points this week. Watch /sectors for the first move.",
      });
    }
  }

  // 3. Discovery activity.
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const newThisWeek = recent.filter(
    (r) => new Date(r.discovered_at).getTime() >= cutoff,
  ).length;
  out.push({
    title:
      newThisWeek > 0
        ? `${newThisWeek} new agents listed`
        : "Quiet on discovery",
    body:
      newThisWeek > 0
        ? `The discovery service admitted ${newThisWeek} new entries over the past week. Browse /new for the full feed — most have GitHub repos and homepages one click away.`
        : "Discovery emitted no admissions this week — usually a sign of a slow week upstream rather than a system pause. /new will fill again as new GitHub topics and HF trending entries surface.",
  });

  return out;
}

function Finding({
  number,
  title,
  body,
}: {
  number: number;
  title: string;
  body: string;
}) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Finding {number}
      </div>
      <h3 className="editorial mt-2 text-xl font-semibold leading-snug">{title}</h3>
      <p className="editorial mt-3 text-base leading-relaxed text-foreground/85">
        {body}
      </p>
    </div>
  );
}
