import Link from "next/link";

export const metadata = {
  title: "Methodology",
  description:
    "How AgentTape discovers, scores, and indexes AI agents. The page journalists screenshot.",
};

export default function MethodologyPage() {
  return (
    <article className="container py-12 md:py-20 max-w-3xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Methodology
      </div>
      <h1 className="editorial mt-3 text-4xl font-semibold leading-[1.05] md:text-6xl">
        How AgentTape works.
      </h1>
      <p className="editorial mt-6 text-xl leading-relaxed text-muted-foreground md:text-2xl">
        We do not curate. The index is autonomously populated by software that
        watches the AI-agent ecosystem and admits things on the day they start
        to matter.
      </p>
      <p className="mt-4 text-sm text-muted-foreground">
        Every change to scoring, weights, or index rules ships as a commit —
        see the{" "}
        <Link
          href="/methodology/changelog"
          className="text-primary hover:underline"
        >
          methodology changelog
        </Link>
        .
      </p>

      <section className="prose prose-zinc mt-12 max-w-none editorial space-y-5 text-base leading-relaxed text-foreground/90 md:text-lg">
        <H2>No seed list</H2>
        <p>
          A seed list would bias the index toward whatever the maintainers
          already knew about. The point of AgentTape is the opposite — to
          surface the things you have not heard of yet, the morning they start
          to matter. The <Link href="/new" className="text-primary underline-offset-2 hover:underline">discovery service</Link> sweeps GitHub,
          Hugging Face, MCP registries, npm and PyPI, arXiv, and Hacker News
          on its own schedule. Admitted agents appear in the index without
          human intervention.
        </p>

        <H2>Three ingestion tiers</H2>
        <p>
          Once an agent is admitted, signals refresh on a tiered cadence to
          balance freshness against rate limits.
        </p>
        <ul className="list-disc pl-6">
          <li><strong>Fast (~5 min)</strong> — GitHub stars, HN mention velocity, HF trending rank. Drives the ticker.</li>
          <li><strong>Medium (~1 hour)</strong> — forks, contributors, 7-day commits, HF downloads, npm/PyPI counts, Reddit, MCP registry presence.</li>
          <li><strong>Slow (daily)</strong> — benchmark scores from Galileo, HAL, AstaBench, LLM-Stats, Steel WebVoyager; arXiv citations.</li>
        </ul>

        <H2>The AgentScore</H2>
        <p>
          Every agent has a single 0–100 headline backed by four pillars,
          equally visible in every UI surface:
        </p>
        <ul className="list-disc pl-6">
          <li><strong>Adoption (35%)</strong> — z-score across stars, downloads, package counts, MCP registry presence.</li>
          <li><strong>Quality (30%)</strong> — mean z-score across benchmark results. <em>Unrated</em> when no benchmark data is available; never zero.</li>
          <li><strong>Momentum (20%)</strong> — 7-day and 30-day rate-of-change blend over adoption signals.</li>
          <li><strong>Community (15%)</strong> — contributors, HN points, Reddit points.</li>
        </ul>
        <p>
          Quality's 30% weight is redistributed pro-rata when an agent is
          unrated, so a young project is not penalized for the absence of
          benchmark coverage.
        </p>

        <H2>Manipulation resistance</H2>
        <p>
          Three patterns trigger automatic flags: a star spike of 10× in 24
          hours with low contributor diversity, a Hugging Face download surge
          unaccompanied by GitHub activity, and coordinated Hacker News
          posting bursts. Flagged signals are excluded from that day's score
          and the agent's record carries the reason. The
          <code className="mx-1 rounded bg-muted px-1 py-0.5 font-mono text-sm">manipulation_resistance</code>
          confidence on every score envelope reflects how clean the inputs
          were.
        </p>

        <H2>Indexes</H2>
        <p>
          Five indexes at launch — TAPE-100, CODE-25, WEB-25, OSS-50, MCP-25 —
          each with eligibility rules published in code. Equal-weight v1.
          Rebalances run Mondays at 03:00 UTC; every diff is logged with a
          short narrative explaining the largest changes.
        </p>

        <H2>Show your work</H2>
        <p>
          Every agent page exposes its raw signals as a downloadable CSV.
          Every index page links its rebalance log. Methodology changes are
          versioned in the
          <a className="ml-1 text-primary underline-offset-2 hover:underline" href="https://github.com/flmwilkinson/AgentTape">repository</a>.
        </p>
      </section>

      <hr className="my-16 border-border" />
      <p className="text-xs text-muted-foreground">
        Last revised on rebalance. Comments and corrections at{" "}
        <a href="https://github.com/flmwilkinson/AgentTape/issues" className="text-primary hover:underline">github.com/flmwilkinson/AgentTape/issues</a>.
      </p>
    </article>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="editorial mt-12 text-2xl font-semibold leading-snug text-foreground md:text-3xl">
      {children}
    </h2>
  );
}
