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

        <H2>The AgentScore — the equation</H2>
        <p>
          Every agent has a single 0–100 headline backed by four pillars
          (Adoption 35%, Quality 30%, Momentum 20%, Community 15%). The
          formula is identical for application agents and foundation
          models, so any two scores compare directly.
        </p>

        <H3>Scaling a raw signal to 0–100</H3>
        <p>
          For a count-shaped signal with raw value <em>v</em> and an
          absolute anchor (the value at which the signal scores exactly
          50):
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`scaled(v, anchor) = min(100, 50 × log₁₀(v + 1) / log₁₀(anchor + 1))`}
        </pre>
        <p>
          The curve flattens toward 100 as <em>v</em> grows. A signal
          with no reading contributes nothing; pillars with no
          contributing reading are <em>Unrated</em>, never zero.
        </p>

        <H3>Anchor table</H3>
        <p>
          Each anchor is the raw value at which the signal scores 50.
          Numbers chosen so the median agent in each population lands
          near 50 on each axis.
        </p>
        <div className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full min-w-[420px] text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Signal</th>
                <th className="px-3 py-2 text-right font-medium">Anchor (= 50)</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["GitHub stars", "1,000"],
                ["GitHub forks", "200"],
                ["GitHub contributors", "30"],
                ["GitHub commits (7d)", "50"],
                ["GitHub mentions (7d)", "20"],
                ["HF downloads (30d)", "100,000"],
                ["HF likes", "200"],
                ["HF trending rank", "rank 10"],
                ["npm weekly installs", "1,000"],
                ["PyPI monthly installs", "10,000"],
                ["HN mentions (7d)", "10"],
                ["HN points (7d)", "100"],
                ["Reddit mentions (7d)", "10"],
                ["Reddit points (7d)", "100"],
                ["Bluesky mentions (7d)", "10"],
                ["Stack Overflow questions (7d)", "5"],
                ["Product Hunt upvotes", "100"],
                ["arXiv citations", "100"],
                ["MCP registry listed", "binary: 0 → 0, 1 → 75"],
                ["Benchmark score", "no transform (0–100 already)"],
              ].map(([label, anchor]) => (
                <tr key={label} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2">{label}</td>
                  <td className="px-3 py-2 text-right font-mono">{anchor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <H3>Pillar = mean of available scaled signals</H3>
        <p>
          For each pillar, take the scaled value of every signal in the
          pillar's source list that has a reading on file. The pillar
          score is the arithmetic mean. If no signal has a reading, the
          pillar is <em>Unrated</em>.
        </p>

        <H3>Headline AgentScore</H3>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`weights = { adoption: 0.35, quality: 0.30, momentum: 0.20, community: 0.15 }
non_null = pillars where pillar ≠ Unrated
total_w  = Σ weights[p] for p in non_null
AgentScore = Σ (weights[p] / total_w) × pillar[p]   for p in non_null`}
        </pre>
        <p>
          A pillar that's Unrated drops out of the blend; the remaining
          weights re-normalize so the headline stays on the 0–100 scale.
          If all four pillars are Unrated, the agent is Unrated overall —
          its page shows the metadata sidebar but no composite.
        </p>

        <H3>Source list per kind</H3>
        <p>
          The formula is identical for both kinds. The source list
          differs because the signals that matter for an LLM and the
          signals that matter for an application agent are not the same
          — and they shouldn't be forced into the same column.
        </p>
        <div className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Pillar</th>
                <th className="px-3 py-2 text-left font-medium">Application</th>
                <th className="px-3 py-2 text-left font-medium">Foundation model</th>
              </tr>
            </thead>
            <tbody>
              {[
                [
                  "Adoption",
                  "stars · HF dl · npm · PyPI · MCP · SO · PH",
                  "HF dl · HN · Reddit · Bluesky · stars · GH mentions",
                ],
                ["Quality", "benchmark_score", "benchmark_score"],
                [
                  "Momentum",
                  "7-day ROC of: stars · HF dl · npm · PyPI · HN · Reddit · Bluesky",
                  "7-day ROC of: HF dl · HN · Reddit · Bluesky · GH mentions",
                ],
                [
                  "Community",
                  "contributors · forks · HN pts · Reddit pts · Bluesky · HF likes",
                  "HF likes · contributors · Bluesky · Reddit pts",
                ],
              ].map(([pillar, app, fm]) => (
                <tr key={pillar as string} className="border-b border-border last:border-b-0 align-top">
                  <td className="px-3 py-2 font-medium">{pillar}</td>
                  <td className="px-3 py-2 text-muted-foreground">{app}</td>
                  <td className="px-3 py-2 text-muted-foreground">{fm}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <H3>Momentum specifics</H3>
        <p>
          For each source where a current and a 7-day-old reading both
          exist:
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`roc_7d     = (now − then) / max(then, 1)
scaled_roc = clamp(50 + 50 × roc_7d, 0, 100)`}
        </pre>
        <p>
          0% growth maps to 50, +100% to 100, −50% to 0. If a signal
          first arrived inside the 7-day window, scaled_roc = 60 — a
          small positive bias for "newly visible".
        </p>

        <H3>Worked example: Claude Opus 4.7</H3>
        <p>
          Suppose latest signals: HN 47 mentions (7d), Bluesky 18, Reddit
          12, benchmark Open LLM Average 87.6, no HF mirror.
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-xs leading-relaxed">
{`Adoption sources (FM):
  hn_mentions_7d        scaled(47, 10)      = 80.7
  bluesky_mentions_7d   scaled(18, 10)      = 63.0
  reddit_mentions_7d    scaled(12, 10)      = 53.6
  hf_downloads_30d      no reading          → skipped
  github_stars          no reading          → skipped
  github_mentions_7d    no reading          → skipped
  → Adoption = mean(80.7, 63.0, 53.6) = 65.8

Quality sources:
  benchmark_score = 87.6  → 87.6 (no transform)
  → Quality = 87.6

Momentum (7d ROC, hypothetical +20% mention growth):
  → ~58.8

Community sources (FM):
  bluesky_mentions_7d   scaled(18, 10)      = 63.0
  reddit_points_7d      scaled(240, 100)    = 59.4
  → Community = 61.2

Headline (all four pillars present):
  0.35 × 65.8 + 0.30 × 87.6 + 0.20 × 58.8 + 0.15 × 61.2
  = 23.0 + 26.3 + 11.8 + 9.2
  = 70.3`}
        </pre>

        <H3>Why some agents are Unrated</H3>
        <p>
          A score requires at least one signal reading on file. A model
          launched yesterday with no HN mentions, no HF mirror, no
          benchmark match and no Bluesky chatter has nothing to score.
          Its page renders metadata (context length, pricing, modality)
          but the composite is honestly absent rather than padded. As
          signals arrive, the pillars light up one by one.
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

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="editorial mt-8 text-xl font-semibold leading-snug text-foreground md:text-2xl">
      {children}
    </h3>
  );
}
