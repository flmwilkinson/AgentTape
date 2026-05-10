import { execSync } from "node:child_process";
import path from "node:path";
import Link from "next/link";

export const metadata = {
  title: "Methodology",
  description:
    "How AgentTape discovers, scores, and indexes AI agents and foundation models — the formula, the pillar weights, the signal anchors, and the manipulation rules.",
};

// Resolve the methodology page's last commit timestamp at build time.
// `git log -1 --format=%cI` gives an ISO-8601 string. We try git
// because file mtime on Vercel is the build time, not the meaningful
// "when was this rule last changed" answer. Falls back gracefully:
// outside a git repo, in a sandboxed CI without .git, or when the
// path query fails, we render a generic "current" line instead of
// crashing the page.
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

// ----------------------------------------------------------- data tables
//
// These constants drive the on-page tables. Keeping them at module
// scope makes the JSX below readable and gives one place to edit when
// the underlying scoring rules change. Anchors must stay in lock-step
// with apps/scoring/src/scoring/compute.py:ANCHORS, and pillar source
// lists with PILLAR_SOURCES_APPLICATION / PILLAR_SOURCES_FOUNDATION_MODEL
// in the same file.

interface AnchorRow {
  signal: string;
  anchor: string;
  notes?: string;
}

const ANCHOR_ROWS: AnchorRow[] = [
  // Adoption-shaped signals.
  { signal: "GitHub stars", anchor: "1,000" },
  { signal: "GitHub forks", anchor: "200" },
  { signal: "GitHub contributors", anchor: "30" },
  { signal: "GitHub commits (7d)", anchor: "50" },
  { signal: "GitHub mentions (7d)", anchor: "20" },
  { signal: "GitHub releases (90d)", anchor: "6", notes: "≈ one every 2 weeks" },
  { signal: "GitHub issue close rate (30d)", anchor: "100", notes: "1:1 close-to-open ratio" },
  {
    signal: "GitHub first-response hours (30d)",
    anchor: "24",
    notes: "inverted — lower is better; 24h ≈ 50",
  },
  { signal: "GitHub repos using model", anchor: "100", notes: "FM only — cumulative count" },
  { signal: "HF downloads (30d)", anchor: "100,000" },
  { signal: "HF likes", anchor: "200" },
  {
    signal: "HF trending rank",
    anchor: "rank 10",
    notes: "inverted — rank 1 ≈ 85, rank 10 = 50, rank 100 ≈ 0",
  },
  { signal: "npm weekly installs", anchor: "1,000" },
  { signal: "PyPI monthly installs", anchor: "10,000" },
  { signal: "Docker pulls (30d)", anchor: "100,000" },
  { signal: "Crates.io downloads (90d)", anchor: "10,000" },
  { signal: "OpenRouter token volume (30d)", anchor: "1,000,000,000", notes: "FM production traffic proxy" },
  // Conversation / interest signals.
  { signal: "HN mentions (7d)", anchor: "10" },
  { signal: "HN points (7d)", anchor: "100" },
  { signal: "Reddit mentions (7d)", anchor: "10" },
  { signal: "Reddit points (7d)", anchor: "100" },
  { signal: "Bluesky mentions (7d)", anchor: "10" },
  {
    signal: "Mastodon mentions (7d)",
    anchor: "5",
    notes: "federated; sums unique status URLs across mastodon.social, infosec.exchange, hachyderm.io, sigmoid.social, fosstodon.org",
  },
  { signal: "Stack Overflow questions (7d)", anchor: "5" },
  { signal: "Product Hunt upvotes", anchor: "100" },
  {
    signal: "Tech-news mentions (30d)",
    anchor: "30",
    notes: "GDELT primary (~150k outlets); curated RSS scan as fallback",
  },
  { signal: "Wikipedia views (30d)", anchor: "100,000" },
  { signal: "Discord members", anchor: "5,000" },
  { signal: "Google Trends score", anchor: "30", notes: "input is already 0-100; anchor is the value-where-score-is-50" },
  // Quality-shaped signals.
  { signal: "Benchmark score", anchor: "no transform", notes: "already on 0-100; clipped to that range" },
  { signal: "arXiv citations", anchor: "100", notes: "FM only" },
  // Special-case binary.
  {
    signal: "MCP registry listed",
    anchor: "binary",
    notes: "0 → 0, 1 → 75 (a hand-picked credibility bonus, not log-scaled)",
  },
];

interface PillarSource {
  pillar: string;
  application: string[];
  foundation_model: string[];
}

const PILLAR_SOURCES: PillarSource[] = [
  {
    pillar: "Adoption",
    application: [
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
    foundation_model: [
      "HF downloads (30d)",
      "GitHub stars",
      "GitHub mentions (7d)",
      "GitHub repos using model",
      "OpenRouter token volume (30d)",
      "HN mentions (7d)",
      "Reddit mentions (7d)",
      "Bluesky mentions (7d)",
      "Mastodon mentions (7d)",
      "Wikipedia views (30d)",
      "Tech-news mentions (30d)",
    ],
  },
  {
    pillar: "Quality",
    application: [
      "Benchmark score",
      "GitHub issue close rate (30d)",
      "GitHub first-response hours (30d)",
    ],
    foundation_model: ["Benchmark score", "arXiv citations"],
  },
  {
    pillar: "Momentum",
    application: [
      "GitHub stars (7d ROC)",
      "HF downloads (7d ROC)",
      "npm weekly (7d ROC)",
      "PyPI monthly (7d ROC)",
      "GitHub releases (90d)",
      "HN mentions (7d ROC)",
      "Reddit mentions (7d ROC)",
      "Bluesky mentions (7d ROC)",
      "Mastodon mentions (7d ROC)",
      "Google Trends",
    ],
    foundation_model: [
      "HF downloads (7d ROC)",
      "GitHub mentions (7d ROC)",
      "OpenRouter tokens (7d ROC)",
      "HN mentions (7d ROC)",
      "Reddit mentions (7d ROC)",
      "Bluesky mentions (7d ROC)",
      "Mastodon mentions (7d ROC)",
      "Google Trends",
    ],
  },
  {
    pillar: "Community",
    application: [
      "GitHub contributors",
      "GitHub forks",
      "HN points (7d)",
      "Reddit points (7d)",
      "Bluesky mentions (7d)",
      "Mastodon mentions (7d)",
      "HF likes",
      "Discord members",
    ],
    foundation_model: ["HF likes", "GitHub contributors", "Reddit points (7d)"],
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
        AI-agent ecosystem and admits things on the day they start to
        matter. No curated seed list. Every input published.
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

      {/* Table of contents — purely an at-a-glance anchor map for a
          long page. Numbers match the H2s below so a reader can
          scan and click. */}
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
            ["3", "AgentScore — quick version", "score-quick"],
            ["4", "Scoring math — full version", "score-math"],
            ["5", "Anchor table", "anchors"],
            ["6", "Pillar sources, by kind", "pillar-sources"],
            ["7", "Worked examples", "worked-examples"],
            ["8", "Why some agents are Unrated", "unrated"],
            ["9", "Tags — capability, deployment, model_dep", "tags"],
            ["10", "Manipulation resistance", "manipulation"],
            ["11", "Indexes", "indexes"],
            ["12", "Show your work", "show-your-work"],
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
          Nothing on AgentTape was added by hand. The discovery service
          sweeps a fixed list of public sources on its own schedule and
          opens a candidate row for anything that matches an
          AI-agent-shaped pattern. A second pass — the promoter —
          scores each candidate and either admits it, rejects it, or
          leaves it pending for weekly review.
        </p>
        <H3>Sources we sweep</H3>
        <ul className="list-disc pl-6">
          <li>
            <strong>GitHub search</strong> for repos matching agent-frame
            patterns (agent / autogen / langchain / llamaindex / mcp).
          </li>
          <li>
            <strong>Hugging Face trending</strong> models and orgs.
          </li>
          <li>
            <strong>OpenRouter</strong> models catalogue — every
            published foundation model. Routing aliases (`:nitro`,
            `:fast`, `:online`, `:beta`, `:extended`) are skipped on
            sight; they are speed-routing variants of a canonical model,
            not separate models. `:free` is preserved (it's a real
            distinct billing tier).
          </li>
          <li>
            <strong>MCP registries</strong> — the official MCP server
            directory plus a few community lists.
          </li>
          <li>
            <strong>npm and PyPI</strong> for packages whose names or
            keywords match agent vocabulary.
          </li>
          <li>
            <strong>arXiv</strong> for papers introducing named agents.
          </li>
          <li>
            <strong>Hacker News firehose</strong> for Show-HN posts that
            link to agent-shaped repos.
          </li>
        </ul>
        <H3>Promotion</H3>
        <p>
          Each candidate gets an admission score on five axes (LLM
          dependency, agent-vocabulary match, popularity floor,
          maintenance, packaged distribution). Candidates clearing the
          auto-admit threshold are admitted and flow into the scoring
          pipeline. Below the auto-reject threshold are dropped.
          Anything in between waits for weekly review. Discovered-but-
          unadmitted candidates appear as audit-only rows; admitted
          agents are what the rest of the site shows.
        </p>

        {/* ---------- 2. Refresh tiers ---------- */}
        <H2 id="refresh-tiers">2. Refresh tiers — how often signals update</H2>
        <p>
          Once an agent is admitted, signals refresh on three cadences.
          The split is a balance between freshness for the live ticker
          and respect for upstream rate limits.
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
                <td className="px-3 py-2 text-muted-foreground">~5 min</td>
                <td className="px-3 py-2 text-muted-foreground">
                  GitHub stars · HN mentions (7d) · HF trending rank ·
                  Bluesky mentions (7d). Drives the ticker tape.
                </td>
              </tr>
              <tr className="border-b border-border align-top">
                <td className="px-3 py-2 font-medium">Medium</td>
                <td className="px-3 py-2 text-muted-foreground">~1 hour</td>
                <td className="px-3 py-2 text-muted-foreground">
                  GitHub forks / contributors / 7-day commits · HF
                  downloads + likes · npm + PyPI counts · Docker /
                  Crates downloads · Reddit mentions + points ·
                  Mastodon mentions (federated) · Stack Overflow
                  questions · Product Hunt upvotes · MCP registry
                  presence · arXiv citations.
                </td>
              </tr>
              <tr className="align-top">
                <td className="px-3 py-2 font-medium">Slow</td>
                <td className="px-3 py-2 text-muted-foreground">daily</td>
                <td className="px-3 py-2 text-muted-foreground">
                  Benchmark scores (Galileo, HAL, LLM-Stats) · FM
                  leaderboards · GitHub releases (90d) · GitHub issue
                  close-rate / first-response hours · GitHub repos
                  using model (FM only) · Wikipedia views · Discord
                  members · Google Trends · OpenRouter token volume ·
                  Tech-news mentions (GDELT, ~150k outlets).
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* ---------- 3. AgentScore — quick version ---------- */}
        <H2 id="score-quick">3. The AgentScore — quick version</H2>
        <p>
          Every agent has a single 0-100 headline backed by four
          pillars. Each pillar is independently computed; the headline
          is a flat weighted sum of the four. Weights differ by entity
          kind because the question "what makes a coding tool good" is
          not the same question as "what makes a foundation model good".
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-md border border-border bg-card p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Application weights
            </div>
            <ul className="mt-2 space-y-0.5 text-sm">
              <li>
                <span className="font-mono num">0.40</span>{" "}
                <strong>Adoption</strong>{" "}
                <span className="text-muted-foreground">
                  — install counts, registry presence
                </span>
              </li>
              <li>
                <span className="font-mono num">0.20</span>{" "}
                <strong>Quality</strong>{" "}
                <span className="text-muted-foreground">
                  — benchmarks, issue health
                </span>
              </li>
              <li>
                <span className="font-mono num">0.10</span>{" "}
                <strong>Momentum</strong>{" "}
                <span className="text-muted-foreground">— 7-day growth</span>
              </li>
              <li>
                <span className="font-mono num">0.30</span>{" "}
                <strong>Community</strong>{" "}
                <span className="text-muted-foreground">
                  — contributors, forks, points
                </span>
              </li>
            </ul>
          </div>
          <div className="rounded-md border border-border bg-card p-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Foundation model weights
            </div>
            <ul className="mt-2 space-y-0.5 text-sm">
              <li>
                <span className="font-mono num">0.30</span>{" "}
                <strong>Adoption</strong>{" "}
                <span className="text-muted-foreground">
                  — repos using it, traffic
                </span>
              </li>
              <li>
                <span className="font-mono num">0.40</span>{" "}
                <strong>Quality</strong>{" "}
                <span className="text-muted-foreground">
                  — benchmarks, citations
                </span>
              </li>
              <li>
                <span className="font-mono num">0.10</span>{" "}
                <strong>Momentum</strong>{" "}
                <span className="text-muted-foreground">— 7-day growth</span>
              </li>
              <li>
                <span className="font-mono num">0.20</span>{" "}
                <strong>Community</strong>{" "}
                <span className="text-muted-foreground">
                  — contributors, points, likes
                </span>
              </li>
            </ul>
          </div>
        </div>
        <p>
          A pillar with no signals contributes <strong>zero</strong> to
          the headline (no redistribution, no re-normalisation). That
          is the only mechanism by which "more data wins" — there is
          no separate coverage multiplier on top.
        </p>
        <p className="rounded-md border border-border bg-subtle/40 p-4 text-sm">
          <strong>Cap-by-coverage corollary.</strong> Because each
          pillar can only buy you up to its own weight, an Adoption-only
          application caps at 40 (0.40 × 100), an Adoption + Community
          application at 70, a 3-pillar application at 80, and only a
          fully-rated 4-pillar agent can reach 100. Less data is
          mathematically a lower ceiling.
        </p>
        <p>
          Because weights differ by entity kind, two scores are{" "}
          <em>not</em> directly comparable across kinds. A 70 for an
          application means something different than a 70 for a
          foundation model. Use the per-kind boards (the{" "}
          <Link href="/models" className="text-primary hover:underline">
            Models
          </Link>{" "}
          page, the{" "}
          <Link href="/sectors" className="text-primary hover:underline">
            Sectors
          </Link>{" "}
          tabs) when you want a fair comparison.
        </p>

        {/* ---------- 4. Scoring math — full version ---------- */}
        <H2 id="score-math">4. Scoring math — full version</H2>

        <H3>4.1 How a raw signal becomes a 0-100 score</H3>
        <p>
          For a count-shaped signal with raw value <em>v</em> and an
          absolute anchor (the value at which the signal scores
          exactly 50):
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`scaled(v, anchor) = min(100, 50 × log₁₀(v + 1) / log₁₀(anchor + 1))`}
        </pre>
        <p>
          A log curve so a project with 1,000 stars scores 50 and a
          project with 100,000 stars doesn't get 100× the credit. The
          ceiling at 100 prevents any single signal from dominating.
        </p>
        <H3>4.2 Special cases</H3>
        <ul className="list-disc pl-6">
          <li>
            <strong>Benchmark score</strong> — already on a 0-100
            scale. Pass through, clipped to range.
          </li>
          <li>
            <strong>MCP registry listed</strong> — binary signal: not
            listed → 0, listed → 75. The 75 is a credibility bonus, not
            a log curve.
          </li>
          <li>
            <strong>HF trending rank</strong> — inverted: rank 1 ≈ 85,
            rank 10 = 50, rank 100 ≈ 0.
          </li>
          <li>
            <strong>GitHub first-response hours (30d)</strong> —
            inverted: 0 hours ≈ 100 (instant), 24h = 50, &gt; 7 days ≈ 0.
          </li>
          <li>
            <strong>Momentum signals</strong> — use{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-sm">scaled_roc</code>{" "}
            (see 4.4) instead of the standard log-anchor.
          </li>
        </ul>

        <H3>4.3 Pillar = mean of available scaled signals</H3>
        <p>
          For each pillar, take the scaled value of every signal in
          the pillar's source list that has a reading on file. The
          pillar score is the arithmetic mean of those values. If no
          source in the pillar has a reading, the pillar is{" "}
          <em>Unrated</em> — at the pillar level it's null, and at
          the headline-math level it contributes 0.
        </p>
        <p className="text-sm text-muted-foreground">
          The two statements ("Unrated" and "contributes 0") look like
          a contradiction but they describe different layers. The
          pillar's own card on an agent page reads <em>Unrated</em>{" "}
          (because there is genuinely no signal). The same pillar's
          contribution to the headline is computed as 0 (because the
          headline is a sum, and you can't add an unknown to a sum).
        </p>

        <H3>4.4 Momentum specifics</H3>
        <p>
          For each momentum source where a current reading and a
          7-day-old reading both exist:
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`roc_7d     = (now − then) / max(then, 1)
scaled_roc = clamp(50 + 50 × roc_7d, 0, 100)`}
        </pre>
        <p>
          0% growth → 50, +100% → 100, −50% → 0. If a signal first
          arrived inside the 7-day window (no "then" reading),
          scaled_roc = 60 — a small positive bias for "newly visible"
          rather than the punitive 0 a missing-then would otherwise
          imply.
        </p>

        <H3>4.5 Headline = weighted sum of non-null pillars</H3>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed">
{`Application:      AgentScore = 0.40·adoption + 0.20·quality
                              + 0.10·momentum + 0.30·community
Foundation model: AgentScore = 0.30·adoption + 0.40·quality
                              + 0.10·momentum + 0.20·community

(missing pillar contributes 0)`}
        </pre>
        <p>
          Both weight sets sum to 1.0 so headlines stay on the 0-100
          scale. If every pillar is Unrated, the agent is Unrated
          overall — its page shows the metadata sidebar but no
          composite, and it doesn't appear in score-ranked lists.
        </p>

        {/* ---------- 5. Anchors ---------- */}
        <H2 id="anchors">5. Anchor table</H2>
        <p>
          Each anchor is the raw value at which the signal scores 50.
          Numbers chosen so the median agent in each population lands
          near 50 on each axis.
        </p>
        <div className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full text-sm [&_td]:break-words [&_th]:break-words">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Signal</th>
                <th className="px-3 py-2 text-right font-medium">
                  Anchor (= 50)
                </th>
                <th className="px-3 py-2 text-left font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {ANCHOR_ROWS.map((r) => (
                <tr
                  key={r.signal}
                  className="border-b border-border last:border-b-0 align-top"
                >
                  <td className="px-3 py-2">{r.signal}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {r.anchor}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {r.notes ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ---------- 6. Pillar source lists ---------- */}
        <H2 id="pillar-sources">6. Pillar sources, by kind</H2>
        <p>
          Same formula in section 4 applies to both kinds. The source
          list per pillar differs because the signals that matter for
          an LLM and the signals that matter for an application agent
          are not the same — and they shouldn't be forced into the
          same column.
        </p>
        {PILLAR_SOURCES.map((p) => (
          <div
            key={p.pillar}
            className="rounded-md border border-border bg-card p-4"
          >
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {p.pillar}
            </div>
            <div className="mt-2 grid gap-3 text-sm md:grid-cols-2">
              <div>
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Application
                </div>
                <ul className="space-y-0.5 text-foreground/85">
                  {p.application.map((src) => (
                    <li key={src} className="font-mono text-xs">
                      {src}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  Foundation model
                </div>
                <ul className="space-y-0.5 text-foreground/85">
                  {p.foundation_model.map((src) => (
                    <li key={src} className="font-mono text-xs">
                      {src}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}

        {/* ---------- 7. Worked examples ---------- */}
        <H2 id="worked-examples">7. Worked examples</H2>

        <H3>7.1 Foundation model — Claude Opus 4.7</H3>
        <p>
          Suppose recent signals: HN 47 mentions (7d), Bluesky 18,
          Reddit 12, GitHub repos using model 420, benchmark Open LLM
          Average 87.6, 240 Reddit points (7d), no HF mirror, no news
          mentions in the latest sweep.
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-xs leading-relaxed">
{`Adoption sources (FM):
  hn_mentions_7d              scaled(47, 10)      = 80.7
  bluesky_mentions_7d         scaled(18, 10)      = 63.0
  reddit_mentions_7d          scaled(12, 10)      = 53.6
  github_repos_using_model    scaled(420, 100)    = 81.3
  hf_downloads_30d            no reading          → skipped
  github_stars                no reading          → skipped
  github_mentions_7d          no reading          → skipped
  wikipedia_views_30d         no reading          → skipped
  openrouter_token_volume_30d no reading          → skipped
  news_mentions_30d           no reading          → skipped
  → Adoption = mean(80.7, 63.0, 53.6, 81.3) = 69.7

Quality sources:
  benchmark_score = 87.6  → 87.6 (no transform)
  arxiv_citations no reading → skipped
  → Quality = 87.6

Momentum (7d ROC, hypothetical +20% mention growth):
  → ~58.8

Community sources (FM):
  reddit_points_7d            scaled(240, 100)    = 59.4
  hf_likes                    no reading          → skipped
  github_contributors         no reading          → skipped
  → Community = 59.4

Headline (FM weights 0.30 / 0.40 / 0.10 / 0.20):
  0.30 × 69.7 + 0.40 × 87.6 + 0.10 × 58.8 + 0.20 × 59.4
  = 20.91 + 35.04 + 5.88 + 11.88
  = 73.7`}
        </pre>

        <H3>7.2 Application — claude-code</H3>
        <p>
          GitHub stars 122k, npm install volume reflected, contributors
          52, forks 20.2k, no benchmark on file.
        </p>
        <pre className="rounded-md border border-border bg-card p-4 font-mono text-xs leading-relaxed">
{`Adoption sources (App):
  github_stars            scaled(122k, 1k)    = 100.0
  npm_weekly              scaled(50k, 1k)     = 87.5
  stackoverflow_q_7d      scaled(2, 5)        = 30.7
  producthunt_upvotes     scaled(412, 100)    = 80.8
  hf_downloads / pypi / docker / crates / mcp / news → skipped
  → Adoption = mean(100.0, 87.5, 30.7, 80.8) = 74.8

Quality:
  no benchmark / issue-rate / response-hours on file
  → Quality = Unrated → contributes 0

Momentum (7d ROC, ~5% star growth on a mature project):
  → ~52.5

Community sources (App):
  github_contributors     scaled(52, 30)      = 73.6
  github_forks            scaled(20.2k, 200)  = 100.0
  hn_points_7d            scaled(180, 100)    = 56.9
  → Community = mean(73.6, 100.0, 56.9) = 76.8

Headline (App weights 0.40 / 0.20 / 0.10 / 0.30):
  0.40 × 74.8 + 0.20 × 0 + 0.10 × 52.5 + 0.30 × 76.8
  = 29.92 + 0 + 5.25 + 23.04
  = 58.2`}
        </pre>

        {/* ---------- 8. Why some agents are Unrated ---------- */}
        <H2 id="unrated">8. Why some agents are Unrated</H2>
        <p>
          A score requires at least one signal reading on file. A model
          launched yesterday with no HN mentions, no HF mirror, no
          benchmark match and no Bluesky chatter has nothing to score.
          Its page renders metadata (context length, pricing, modality)
          but the composite is honestly absent rather than padded. As
          signals arrive, the pillars light up one by one.
        </p>

        {/* ---------- 9. Tags ---------- */}
        <H2 id="tags">9. Tags — capability, deployment, model_dep</H2>
        <p>
          Every agent carries up to four kinds of tag. Tags are
          author-asserted where possible (GitHub topics, HF tags, npm
          keywords) and rule-derived from the agent's name + description
          where they aren't.
        </p>
        <ul className="list-disc pl-6">
          <li>
            <strong>capability</strong> — what the agent does
            (code-generation, browsing, research, RAG, multi-agent,
            automation, tool-use, memory, vision, voice).
          </li>
          <li>
            <strong>deployment</strong> — how it ships (library, CLI,
            SaaS, IDE plugin, browser extension, MCP server).
          </li>
          <li>
            <strong>license</strong> — SPDX (mit, apache-2.0, agpl,
            etc.), normalised from the source repo.
          </li>
          <li>
            <strong>maturity</strong> — experimental / beta / stable,
            inferred from age + release cadence.
          </li>
          <li>
            <strong>model_dep</strong> — only on application agents.
            Indicates which foundation-model family the app is built
            on (claude / gpt / gemini / deepseek / llama / mistral /
            qwen / grok). Auto-detected from descriptions ("powered by
            Claude", "built on GPT-4") and supplemented by a small
            seed list for the high-profile apps. The "Built on Claude"
            chips on agent pages link to{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-sm">
              /sectors/model_dep/&lt;family&gt;
            </code>{" "}
            so a reader can cross-reference all apps using the same
            family.
          </li>
        </ul>

        {/* ---------- 10. Manipulation resistance ---------- */}
        <H2 id="manipulation">10. Manipulation resistance</H2>
        <p>
          Three patterns trigger automatic flags. Flagged signals are
          excluded from that day's score and the agent's record carries
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
            star jump in 24 hours with very few distinct contributors
            on the repo. Excludes <code>github_stars</code> for that
            tick.
          </li>
          <li>
            <strong>hf_surge_no_github</strong> — a Hugging Face
            download surge unaccompanied by any GitHub activity.
            Excludes <code>hf_downloads_30d</code>.
          </li>
          <li>
            <strong>coordinated_hn_posting</strong> — a burst of
            Hacker News mentions with low account-age diversity.
            Excludes <code>hn_mentions_7d</code> and{" "}
            <code>hn_points_7d</code>.
          </li>
        </ul>

        {/* ---------- 11. Indexes ---------- */}
        <H2 id="indexes">11. Indexes</H2>
        <p>
          Six indexes at launch — each with eligibility rules
          published in code, equal-weight v1, rebalanced Mondays at
          03:00 UTC. Every diff is logged with a short narrative
          explaining the largest changes.
        </p>
        <ul className="list-disc pl-6">
          <li>
            <strong>TAPE-100</strong> — top 100 across both kinds.
          </li>
          <li>
            <strong>FM-50</strong> — top 50 foundation models.
          </li>
          <li>
            <strong>CODE-25</strong> — top 25 coding agents
            (capability:code-generation, application).
          </li>
          <li>
            <strong>WEB-25</strong> — top 25 browser agents
            (capability:browsing, application).
          </li>
          <li>
            <strong>OSS-50</strong> — top 50 open-source applications
            (license = mit / apache / agpl / gpl / bsd / mpl).
          </li>
          <li>
            <strong>MCP-25</strong> — top 25 MCP servers
            (deployment:mcp-server).
          </li>
        </ul>

        {/* ---------- 12. Show your work ---------- */}
        <H2 id="show-your-work">12. Show your work</H2>
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
          ; corrections are welcome via{" "}
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
