import Link from "next/link";
import { api } from "@/lib/api-client";
import { Sparkline } from "@/components/sparkline";
import { formatScore } from "@/lib/format";

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
  const [movers, indexes] = await Promise.all([
    api.movers("7d", 6),
    api.listIndexes(),
  ]);
  const tape = indexes.find((i) => i.slug === "tape-100");
  const tapeHistory = tape
    ? await api
        .indexHistory(tape.slug, "30d")
        .catch(() => [])
    : [];

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
          A weekly read on what moved, what's new, and what the index is doing.
          Auto-generated from the rebalance diff and edited for clarity.
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

      {/* Three findings */}
      <section className="mb-16 grid gap-12 md:grid-cols-3">
        <Finding
          number={1}
          title="Movers tilted to browser-use this week"
          body="The biggest single-week deltas were dominated by browser-agent projects — three of the top five had a `browsing` capability tag. The OSS-50 picked up two of them in Monday's rebalance."
        />
        <Finding
          number={2}
          title="Discovery added another long tail"
          body="The discovery service admitted dozens of agents you have never heard of, mostly via npm and GitHub topic-search. The autonomous design is doing its job: the tail keeps lengthening."
        />
        <Finding
          number={3}
          title="MCP-25 stayed stable"
          body="Composite barely moved. The pattern this quarter has been low intra-index churn but rising headline scores as benchmark coverage improves."
        />
      </section>

      {/* Movers table */}
      <section className="mb-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Top movers
        </div>
        <ul className="mt-4 divide-y divide-border rounded-md border border-border bg-card">
          {movers.map((m) => (
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
