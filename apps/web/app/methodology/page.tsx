import { execSync } from "node:child_process";
import path from "node:path";
import Link from "next/link";

export const metadata = {
  title: "Methodology",
  description:
    "How AgentTape discovers, scores, and indexes AI agents and foundation models — the pillars, the weights, the formulas.",
};

// Resolve the methodology page's last commit timestamp at build time.
// `git log -1 --format=%cI` gives an ISO-8601 string. We try git
// because file mtime on Vercel is the build time, not the meaningful
// "when was this rule last changed" answer.
function lastRevisedISO(): string | null {
  try {
    const here = path.dirname(__filename);
    const stdout = execSync('git log -1 --format=%cI -- "page.tsx"', {
      cwd: here,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return stdout || null;
  } catch {
    return null;
  }
}

const LAST_REVISED = lastRevisedISO();

// Per-pillar story content. Co-located here so the rendered prose
// stays in lock-step with the source lists. Each entry says what
// question the pillar answers, then names the signals that feed it
// for each entity kind.
interface PillarStory {
  pillar: string;
  question: string;
  app_intro: string;
  app_signals: string[];
  fm_intro: string;
  fm_signals: string[];
}

const PILLARS: PillarStory[] = [
  {
    pillar: "Adoption",
    question: "Is anyone actually using this?",
    app_intro:
      "Installs, registry presence, real-world distribution. The signals where a builder has actively chosen to ship this tool somewhere.",
    app_signals: [
      "GitHub stars",
      "HF downloads (30d)",
      "npm weekly",
      "PyPI monthly",
      "Docker pulls (30d)",
      "Crates.io downloads (90d)",
      "MCP registry listed",
      "Stack Overflow questions (7d)",
      "Product Hunt upvotes",
      "Tech-news mentions (30d)",
    ],
    fm_intro:
      "Production traffic and where the model's name shows up across the developer ecosystem. OpenRouter token volume is the closest public proxy for real billable usage.",
    fm_signals: [
      "OpenRouter token volume (30d)",
      "HF downloads (30d)",
      "GitHub repos using model",
      "GitHub mentions (7d)",
      "GitHub stars",
      "HN / Reddit / Bluesky / Mastodon mentions (7d)",
      "Wikipedia views (30d)",
      "Tech-news mentions (30d)",
    ],
  },
  {
    pillar: "Quality",
    question: "How capable is this on the work that matters?",
    app_intro:
      "For applications, capability blends benchmark performance (when published) with maintainer responsiveness — issue close-rate and first-response hours, both of which separate active projects from abandonware.",
    app_signals: [
      "Benchmark score (mean of normalised results)",
      "GitHub issue close rate (30d)",
      "GitHub first-response hours (30d, inverted)",
    ],
    fm_intro:
      "Mean percentile rank across the canonical FM benchmarks (SWE-bench, GPQA Diamond, MMLU-Pro, AIME, MMMU, Terminal-Bench Hard, HLE, lmarena, etc.). Percentile rank is coverage-robust: what matters is consistently beating peers on the benchmarks tested, not the absolute number on a longer-or-shorter list. A minimum of three benchmarks is required for a model to be rated — below that floor the model stays Unrated rather than carrying a misleading single-source score.",
    fm_signals: [
      "Benchmark percentile rank across the FM benchmark suite",
      "Sources: Artificial Analysis API, lmarena-ai HF dataset, SWE-bench, TIGER-Lab MMLU-Pro, Open LLM Leaderboard",
    ],
  },
  {
    pillar: "Momentum",
    question: "Is interest in this growing or fading?",
    app_intro:
      "Rate of change on the adoption signals plus release cadence and Google Trends. Flat usage = score 50, doubling = 100, halving = 0.",
    app_signals: [
      "GitHub stars · HF downloads · npm · PyPI (7-day ROC)",
      "HN / Reddit / Bluesky / Mastodon mentions (7-day ROC)",
      "GitHub releases (90d)",
      "Google Trends",
    ],
    fm_intro:
      "Same rate-of-change treatment applied to FM-shaped signals. Includes academic mindshare via arXiv citation velocity — moved here from Quality because citation count is an interest signal, not a capability one.",
    fm_signals: [
      "OpenRouter tokens · HF downloads (7-day ROC)",
      "HN / Reddit / Bluesky / Mastodon / GitHub mentions (7-day ROC)",
      "Google Trends",
      "arXiv citations (7-day ROC)",
    ],
  },
  {
    pillar: "Community",
    question: "Who's engaging beyond just using it?",
    app_intro:
      "Contributors, forks, points and likes — signals of investment, not just consumption. An app with 1k contributors is structurally different from one with 1k downloads.",
    app_signals: [
      "GitHub contributors",
      "GitHub forks",
      "HN points (7d)",
      "Reddit points (7d)",
      "Bluesky / Mastodon mentions (7d)",
      "HF likes",
      "Discord members",
    ],
    fm_intro:
      "Genuinely sparse for foundation models, especially closed-weight ones. We keep the pillar but Unrated is the honest answer for most Anthropic and OpenAI flagships — they don't have contributor lists or forks because there's nothing to fork.",
    fm_signals: [
      "HF likes",
      "GitHub contributors (open-weight FMs only)",
      "Reddit points (7d)",
    ],
  },
  {
    pillar: "Efficiency",
    question: "How practical is this to ship in production?",
    app_intro:
      "Not used for applications — apps run on the user's hardware and their cost/speed depends on the model they're configured with, not the tool itself.",
    app_signals: ["— (Application entity kind has no Efficiency pillar)"],
    fm_intro:
      "Cost and speed via the Artificial Analysis API. Blended $/M tokens (input + output, inverse-anchored so cheaper scores higher) and median output tokens/sec. Lets a buyer see that, say, Claude Opus 4.7 and GPT-5.1 are at similar capability but very different price points.",
    fm_signals: [
      "Blended price (input + output $/M tokens, lower is better)",
      "Median output tokens/sec",
    ],
  },
];


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
        The index is autonomously populated by software that watches the
        AI ecosystem and admits things on the day they start to matter.
        No curated seed list. Every input published.
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

      <nav
        aria-label="Methodology contents"
        className="mt-10 rounded-md border border-border bg-card p-4"
      >
        <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Contents
        </div>
        <ol className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
          {[
            ["1", "Discovery", "discovery"],
            ["2", "Refresh tiers", "refresh-tiers"],
            ["3", "The AgentScore", "score"],
            ["4", "The pillars", "pillars"],
            ["5", "Scoring formulas", "formulas"],
            ["6", "Why some agents are Unrated", "unrated"],
            ["7", "Manipulation resistance", "manipulation"],
            ["8", "Indexes", "indexes"],
            ["9", "Show your work", "show-your-work"],
          ].map(([num, label, anchor]) => (
            <li key={anchor} className="font-mono text-foreground/80">
              <a href={`#${anchor}`} className="hover:text-primary">
                <span className="text-muted-foreground">{num}.</span>{" "}
                <span className="font-sans">{label}</span>
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <section className="prose prose-zinc mt-12 max-w-none editorial space-y-5 text-base leading-relaxed text-foreground/90 md:text-lg">
        {/* ---------- 1. Discovery ---------- */}
        <H2 id="discovery">1. Discovery — how agents enter the index</H2>
        <p>
          Nothing on AgentTape was added by hand. A discovery service
          sweeps a fixed list of public sources on its own schedule and
          opens a candidate row for anything matching an AI-agent or
          foundation-model pattern. A second pass scores each candidate
          and either admits it, rejects it, or leaves it pending for
          weekly review.
        </p>
        <p>
          <strong>Sources swept:</strong> GitHub search (repos matching
          agent-frame patterns), Hugging Face trending, OpenRouter
          models catalogue (every published foundation model), MCP
          registries, npm and PyPI, arXiv, and the Hacker News
          firehose. Each source ingests on its own cadence — none of
          them gate on the others.
        </p>
        <p>
          Promotion scores each candidate on five axes: LLM dependency,
          agent-vocabulary match, popularity floor, maintenance, and
          packaged distribution. Four small substance bonuses (each
          capped at 0.05) tip borderline cases — declared topics,
          description length, multi-ecosystem packaging, recent commit
          activity. Archived or disabled GitHub repos are
          hard-rejected.
        </p>

        {/* ---------- 2. Refresh tiers ---------- */}
        <H2 id="refresh-tiers">2. Refresh tiers — how often signals update</H2>
        <p>
          Signals refresh on three cadences. The split balances ticker
          freshness against upstream rate limits.
        </p>
        <div className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full text-sm [&_td]:break-words [&_th]:break-words">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Tier</th>
                <th className="px-3 py-2 text-left font-medium">Cadence</th>
                <th className="px-3 py-2 text-left font-medium">What runs</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border align-top">
                <td className="px-3 py-2 font-medium">Fast</td>
                <td className="px-3 py-2 text-muted-foreground">~1 hour</td>
                <td className="px-3 py-2 text-muted-foreground">
                  GitHub stars · HN mentions · HF trending rank · Bluesky
                  mentions. Drives the ticker tape. Inserts are deduped
                  per signal — the ticker only refreshes cells that
                  actually changed.
                </td>
              </tr>
              <tr className="border-b border-border align-top">
                <td className="px-3 py-2 font-medium">Medium</td>
                <td className="px-3 py-2 text-muted-foreground">~1 hour</td>
                <td className="px-3 py-2 text-muted-foreground">
                  GitHub forks / contributors / commits · HF downloads + likes ·
                  npm + PyPI · Docker / Crates · Reddit · Mastodon · Stack
                  Overflow · Product Hunt · MCP registry · arXiv citations.
                </td>
              </tr>
              <tr className="align-top">
                <td className="px-3 py-2 font-medium">Slow</td>
                <td className="px-3 py-2 text-muted-foreground">daily</td>
                <td className="px-3 py-2 text-muted-foreground">
                  Artificial Analysis API (10+ canonical FM benchmarks,
                  cost, speed) · FM leaderboards (lmarena, SWE-bench,
                  MMLU-Pro, Open LLM) · llm-stats per-benchmark pages ·
                  GitHub releases · issue close-rate · first-response hours ·
                  repos using model · Wikipedia · Discord · Google Trends ·
                  Tech-news mentions (GDELT).
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---------- 3. The AgentScore ---------- */}
        <H2 id="score">3. The AgentScore</H2>
        <p>
          One number, 0-100, computed as a weighted sum of pillar
          scores. Applications have four pillars; foundation models
          have five (Efficiency adds cost + speed, which doesn't apply
          to apps that run on user hardware).
        </p>
        <p>
          Weights differ by entity kind because the question "what
          makes a coding tool good" is not the question "what makes a
          foundation model good". A 70 for an app and a 70 for an FM
          are not directly comparable — use the per-kind boards (
          <Link href="/models" className="text-primary hover:underline">Models</Link>,{" "}
          <Link href="/sectors" className="text-primary hover:underline">Sectors</Link>)
          when you want a fair comparison.
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-md border border-border bg-card p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Application — 4 pillars
            </div>
            <ul className="mt-2 space-y-0.5 text-sm">
              <li><span className="font-mono num">0.40</span> <strong>Adoption</strong></li>
              <li><span className="font-mono num">0.20</span> <strong>Quality</strong></li>
              <li><span className="font-mono num">0.10</span> <strong>Momentum</strong></li>
              <li><span className="font-mono num">0.30</span> <strong>Community</strong></li>
            </ul>
          </div>
          <div className="rounded-md border border-border bg-card p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Foundation model — 5 pillars
            </div>
            <ul className="mt-2 space-y-0.5 text-sm">
              <li><span className="font-mono num">0.25</span> <strong>Adoption</strong></li>
              <li><span className="font-mono num">0.35</span> <strong>Quality</strong></li>
              <li><span className="font-mono num">0.20</span> <strong>Efficiency</strong></li>
              <li><span className="font-mono num">0.10</span> <strong>Momentum</strong></li>
              <li><span className="font-mono num">0.10</span> <strong>Community</strong></li>
            </ul>
          </div>
        </div>
        <p>
          A pillar with no signals contributes zero to the headline (no
          redistribution, no re-normalisation). Less data is a lower
          ceiling, not a re-weighted average — a 3-pillar FM caps at
          80, a 4-pillar one at 90, only a fully-rated model can reach
          100. That keeps coverage honest. Models board lets you
          click any column header to re-sort by that single pillar.
        </p>

        {/* ---------- 4. The pillars ---------- */}
        <H2 id="pillars">4. The pillars</H2>
        <p>
          What each pillar answers, and the signals that drive it for
          each entity kind. Signal lists below are the source of truth
          — they're co-located with the source code in{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">
            apps/scoring/compute.py
          </code>{" "}
          and the page renders straight from that list.
        </p>
        {PILLARS.map((p) => (
          <div
            key={p.pillar}
            className="rounded-md border border-border bg-card p-5"
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {p.pillar}
            </div>
            <p className="mt-1 editorial text-lg font-medium text-foreground">
              {p.question}
            </p>
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Application
                </div>
                <p className="text-sm text-muted-foreground">{p.app_intro}</p>
                <ul className="mt-2 space-y-0.5 text-xs text-foreground/85">
                  {p.app_signals.map((src) => (
                    <li key={src} className="font-mono">
                      {src}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Foundation model
                </div>
                <p className="text-sm text-muted-foreground">{p.fm_intro}</p>
                <ul className="mt-2 space-y-0.5 text-xs text-foreground/85">
                  {p.fm_signals.map((src) => (
                    <li key={src} className="font-mono">
                      {src}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}

        {/* ---------- 5. Scoring formulas ---------- */}
        <H2 id="formulas">5. Scoring formulas</H2>
        <p>
          Three families of formula, applied per signal kind. Each
          produces a 0-100 contribution; the pillar score is the
          arithmetic mean of available contributions.
        </p>
        <H3>Counts (most signals)</H3>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`scaled(v, anchor) = min(100, 50 × log₁₀(v + 1) / log₁₀(anchor + 1))`}
        </pre>
        <p>
          A log curve so a project with 1,000 stars scores 50 and one
          with 100,000 stars doesn't get 100× the credit. Each anchor
          is the value at which the signal scores exactly 50 — chosen
          so the median agent in each population lands near the middle
          of the scale. Anchor table lives in source at{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">
            apps/scoring/compute.py:ANCHORS
          </code>
          .
        </p>
        <H3>Benchmarks (Quality pillar)</H3>
        <p>
          Mean <strong>percentile rank</strong> across the agent's
          benchmark coverage. For each benchmark the agent has been
          scored on, its score is ranked against every other agent on
          that benchmark and converted to a 0-100 percentile. The
          pillar score is the mean of those percentiles.
        </p>
        <p>
          Percentile rank is coverage-robust: a model with 5
          benchmarks all at the 95th percentile beats a model with 10
          benchmarks averaging the 70th. It's also head-to-head
          consistent — if A strictly beats B on every shared
          benchmark, A's mean percentile is ≥ B's. The previous
          formula (mean of normalised scores) failed this: a model
          could outrank a strictly-better competitor just by having
          extra easy benchmarks pulling its mean up.
        </p>
        <p>
          A coverage floor of three distinct benchmarks is required to
          rate a model on Quality — below it the model stays Unrated.
        </p>
        <H3>Momentum (7-day rate of change)</H3>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`roc_7d     = (now − then) / max(then, 1)
scaled_roc = clamp(50 + 50 × roc_7d, 0, 100)`}
        </pre>
        <p>
          0% growth → 50, +100% → 100, −50% → 0. A signal first seen
          inside the 7-day window (no "then" reading) gets a 60 — a
          small "newly arrived" bias, not the punitive 0 a missing
          baseline would otherwise imply.
        </p>
        <H3>Special cases</H3>
        <p>
          A handful of signals don't fit the count log-curve.{" "}
          <strong>MCP registry listed</strong> is binary (0 → 0, 1 →
          75 — a hand-picked credibility bonus).{" "}
          <strong>HF trending rank</strong> and{" "}
          <strong>GitHub first-response hours</strong> are inverted:
          lower input = higher score, with the same log shape mirrored.{" "}
          <strong>Cost (blended price)</strong> is also inverted —
          cheaper scores higher, anchored at $5/M tokens.
        </p>

        {/* ---------- 6. Unrated ---------- */}
        <H2 id="unrated">6. Why some agents are Unrated</H2>
        <p>
          A pillar with no signals on file is Unrated rather than zero.
          The pillar's card on an agent page reads "Unrated" (no data),
          while at the headline level that pillar contributes zero
          (because the headline is a weighted sum and you can't add an
          unknown to a sum). The two read like a contradiction; they
          describe different layers.
        </p>
        <p>
          Quality has the additional coverage floor — fewer than three
          benchmarks means Unrated rather than a noisy single-source
          score. New flagship releases often sit Unrated on Quality for
          a few days until enough leaderboards pick them up.
        </p>

        {/* ---------- 7. Manipulation ---------- */}
        <H2 id="manipulation">7. Manipulation resistance</H2>
        <p>
          Three patterns trigger automatic flags. Flagged signals are
          excluded from that day's score; the agent's record carries
          the reason. The{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm">
            manipulation_resistance
          </code>{" "}
          confidence on every score envelope reflects how clean the
          inputs were.
        </p>
        <ul className="list-disc pl-6">
          <li>
            <strong>star_spike_no_contrib_diversity</strong> — a 10×
            star jump in 24 hours from very few distinct contributors.
            Excludes <code>github_stars</code> for that tick.
          </li>
          <li>
            <strong>hf_surge_no_github</strong> — a Hugging Face
            download surge with no accompanying GitHub activity.
            Excludes <code>hf_downloads_30d</code>.
          </li>
          <li>
            <strong>coordinated_hn_posting</strong> — a burst of HN
            mentions with low account-age diversity. Excludes{" "}
            <code>hn_mentions_7d</code> and <code>hn_points_7d</code>.
          </li>
        </ul>

        {/* ---------- 8. Indexes ---------- */}
        <H2 id="indexes">8. Indexes</H2>
        <p>
          Six indexes at launch — each with eligibility rules
          published in code, equal-weight v1, rebalanced Mondays at
          03:00 UTC. Every diff is logged with a short narrative.
        </p>
        <ul className="list-disc pl-6">
          <li><strong>TAPE-100</strong> — top 100 across both kinds.</li>
          <li><strong>FM-50</strong> — top 50 foundation models.</li>
          <li>
            <strong>CODE-25</strong> — top 25 coding agents
            (capability:code-generation, application).
          </li>
          <li>
            <strong>WEB-25</strong> — top 25 browser agents
            (capability:browsing, application).
          </li>
          <li>
            <strong>OSS-50</strong> — top 50 open-source applications.
          </li>
          <li>
            <strong>MCP-25</strong> — top 25 MCP servers
            (deployment:mcp-server).
          </li>
        </ul>

        {/* ---------- 9. Show your work ---------- */}
        <H2 id="show-your-work">9. Show your work</H2>
        <p>
          Every agent page exposes its raw signals as a downloadable
          CSV. Every index page links its rebalance log. Methodology
          changes are versioned in the{" "}
          <a
            className="text-primary underline-offset-2 hover:underline"
            href="https://github.com/flmwilkinson/AgentTape"
          >
            repository
          </a>
          ; corrections welcome via{" "}
          <a
            href="https://github.com/flmwilkinson/AgentTape/issues"
            className="text-primary hover:underline"
          >
            Issues
          </a>{" "}
          or{" "}
          <a
            href="https://github.com/flmwilkinson/AgentTape/discussions"
            className="text-primary hover:underline"
          >
            Discussions
          </a>
          .
        </p>
      </section>

      <hr className="my-16 border-border" />
      <p className="text-xs text-muted-foreground">
        Last revised{" "}
        {LAST_REVISED ? (
          <time dateTime={LAST_REVISED}>
            {new Date(LAST_REVISED).toLocaleDateString("en-GB", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </time>
        ) : (
          "on the most recent deploy"
        )}
        . Comments and corrections at{" "}
        <a
          href="https://github.com/flmwilkinson/AgentTape/issues"
          className="text-primary hover:underline"
        >
          github.com/flmwilkinson/AgentTape/issues
        </a>
        .
      </p>
    </article>
  );
}

function H2({
  id,
  children,
}: {
  id?: string;
  children: React.ReactNode;
}) {
  return (
    <h2
      id={id}
      className="editorial mt-12 scroll-mt-24 text-2xl font-semibold leading-snug text-foreground md:text-3xl"
    >
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
