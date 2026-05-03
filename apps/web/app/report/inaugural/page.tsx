import Link from "next/link";
import fs from "node:fs/promises";
import path from "node:path";
import { Sparkline } from "@/components/sparkline";
import { formatScore } from "@/lib/format";

// Web mirror of scripts/launch_report.py.
// Reads apps/web/public/launch-report.json — the script writes that file
// every time it runs, so this page is always in lockstep with the PDF.

export const metadata = {
  title: "TAPE-100 — Inaugural Report",
  description:
    "The first published edition of the AgentTape inaugural index. Every constituent admitted by software, without a curated seed list.",
  openGraph: {
    title: "AgentTape · TAPE-100 Inaugural Report",
    images: [{ url: "/api/og/index/tape-100" }],
  },
};

export const dynamic = "force-static";
export const revalidate = 3600;

type Tape100Row = {
  rank: number;
  slug: string;
  name: string;
  score: number | null;
  adoption: number | null;
  quality: number | null;
  momentum: number | null;
  community: number | null;
  discovered_via: string;
  github_repo: string | null;
  discovered_at: string | null;
};

type Findings = {
  surprising_leader: {
    rank: number;
    slug: string;
    name: string;
    score: number;
    discovered_via: string;
    discovered_at: string | null;
  } | null;
  notable_decline: {
    slug: string;
    name: string;
    then_score: number | null;
    now_score: number | null;
    delta: number | null;
  } | null;
  concentration: {
    top_10_share: number;
    top_10_total: number;
    tape_total: number;
    n_with_quality: number;
    n_unrated: number;
  } | null;
};

type ReportData = {
  generated_at: string;
  tape100: Tape100Row[];
  composite_history: { captured_at: string; composite_value: number }[];
  score_distribution: number[];
  discovered_via_breakdown: Record<string, number>;
  findings: Findings;
};

async function loadReport(): Promise<ReportData | null> {
  try {
    const file = path.join(process.cwd(), "public", "launch-report.json");
    const raw = await fs.readFile(file, "utf8");
    return JSON.parse(raw) as ReportData;
  } catch {
    return null;
  }
}

export default async function InauguralReportPage() {
  const data = await loadReport();
  if (!data) {
    return (
      <article className="container py-20 max-w-3xl">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Inaugural · AgentTape
        </div>
        <h1 className="editorial mt-3 text-4xl font-semibold">TAPE-100</h1>
        <p className="mt-6 text-muted-foreground">
          The inaugural report has not been generated yet. Run{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">python -m scripts.launch_report</code>
          {" "}against a populated database to produce it.
        </p>
      </article>
    );
  }

  const composite = data.composite_history.map((p) => p.composite_value);
  const generated = new Date(data.generated_at);
  const f = data.findings;

  return (
    <article className="container py-12 md:py-20 max-w-4xl">
      <header className="mb-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Inaugural · AgentTape
        </div>
        <h1 className="editorial mt-3 text-5xl font-semibold leading-[0.95] md:text-7xl">
          TAPE-100
        </h1>
        <p className="editorial mt-6 max-w-2xl text-xl leading-relaxed text-muted-foreground md:text-2xl">
          The first published edition of the AgentTape inaugural index. Every
          constituent on this page was admitted by software, without a curated
          seed list, in the days leading up to this report.
        </p>

        <div className="mt-10 grid grid-cols-2 gap-8 md:grid-cols-3">
          <div>
            <div className="text-stat-xl font-semibold num text-primary">
              {data.tape100.length}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Constituents reporting
            </div>
          </div>
          <div>
            <div className="text-stat-xl font-semibold num text-primary">
              {data.tape100[0]?.score != null
                ? data.tape100[0].score.toFixed(1)
                : "—"}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Highest AgentScore
            </div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="text-sm text-muted-foreground">
              Generated{" "}
              {generated.toLocaleString("en-US", {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                timeZone: "UTC",
                timeZoneName: "short",
              })}
            </div>
            <a
              href="/launch-report.pdf"
              className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
            >
              Download PDF →
            </a>
          </div>
        </div>
      </header>

      {/* Hero composite chart */}
      {composite.length > 0 && (
        <section className="mb-16">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            TAPE-100 composite · 30 days
          </div>
          <div className="mt-2 text-stat-lg font-semibold num">
            {composite.length > 0
              ? composite[composite.length - 1].toFixed(1)
              : "—"}
          </div>
          <div className="mt-6">
            <Sparkline values={composite} width={920} height={180} color="primary" />
          </div>
        </section>
      )}

      {/* Three findings */}
      <section className="mb-20 grid gap-12 md:grid-cols-3">
        {f.surprising_leader && (
          <Finding number={1} title="A new entrant in the top quartile">
            <strong>{f.surprising_leader.name}</strong> ranked #
            {f.surprising_leader.rank} this week with an AgentScore of{" "}
            {f.surprising_leader.score.toFixed(1)}, despite being admitted only
            recently — surfacing via{" "}
            <em>{f.surprising_leader.discovered_via.replace(/_/g, " ")}</em>.
          </Finding>
        )}
        {f.notable_decline ? (
          <Finding number={2} title="The biggest 7-day drawdown">
            <strong>{f.notable_decline.name}</strong> shed{" "}
            {Math.abs(f.notable_decline.delta ?? 0).toFixed(2)} points over the
            last week — falling from{" "}
            {f.notable_decline.then_score?.toFixed(1) ?? "—"} to{" "}
            {f.notable_decline.now_score?.toFixed(1) ?? "—"}.
          </Finding>
        ) : (
          <Finding number={2} title="Drawdowns were small this week">
            No agent in the index lost more than a single AgentScore point over
            the past seven days. A slow, broad market — no benchmark releases
            have shifted the quality pillar yet.
          </Finding>
        )}
        {f.concentration && (
          <Finding number={3} title="Concentration in the top 10">
            The top 10 constituents account for{" "}
            <strong>{(f.concentration.top_10_share * 100).toFixed(1)}%</strong> of
            total AgentScore in TAPE-100. Quality coverage is uneven:{" "}
            {f.concentration.n_with_quality} agents have benchmark results;{" "}
            {f.concentration.n_unrated} are still Unrated.
          </Finding>
        )}
      </section>

      {/* The full TAPE-100 */}
      <section className="mb-16">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          The TAPE-100
        </div>
        <h2 className="editorial mt-2 text-3xl font-semibold leading-snug md:text-4xl">
          Constituents in full.
        </h2>
        <div className="mt-6 overflow-hidden rounded-md border border-border">
          <table className="num w-full text-sm">
            <thead className="bg-subtle text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-right">#</th>
                <th className="px-3 py-2 text-left">Agent</th>
                <th className="px-3 py-2 text-left">Via</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Adoption</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Quality</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Momentum</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Community</th>
              </tr>
            </thead>
            <tbody>
              {data.tape100.map((r) => (
                <tr key={r.slug} className="border-t border-border">
                  <td className="px-3 py-2 text-right text-muted-foreground">{r.rank}</td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/agents/${r.slug}`}
                      className="font-sans font-medium hover:text-primary"
                    >
                      {r.name}
                    </Link>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {r.slug}
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                    {r.discovered_via.replace(/_/g, " ")}
                  </td>
                  <td className="px-3 py-2 text-right font-semibold">
                    {formatScore(r.score)}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell">
                    {r.adoption?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell text-muted-foreground">
                    {r.quality === null ? "Unrated" : r.quality.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell">
                    {r.momentum?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell">
                    {r.community?.toFixed(1) ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="hairline pt-6 text-xs text-muted-foreground">
        Re-generate at any time with{" "}
        <code className="rounded bg-muted px-1 py-0.5 font-mono">python -m scripts.launch_report</code>.
        The PDF and this page read from the same source of truth.
      </div>
    </article>
  );
}

function Finding({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Finding {number}
      </div>
      <h3 className="editorial mt-2 text-xl font-semibold leading-snug">{title}</h3>
      <p className="editorial mt-3 text-base leading-relaxed text-foreground/85">
        {children}
      </p>
    </div>
  );
}
