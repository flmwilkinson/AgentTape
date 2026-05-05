import type { AgentDetail, SignalSeries } from "@/lib/api-client";

// Latest value of a given source from the signal series payload.
function latest(signals: SignalSeries[], source: string): number | null {
  const s = signals.find((x) => x.source === source);
  if (!s || s.points.length === 0) return null;
  const sorted = [...s.points].sort(
    (a, b) =>
      new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime(),
  );
  return sorted[0]?.value ?? null;
}

// "Why is each pillar what it is?" — surfaces the formula behind the
// four pillar scores so the agent page is self-explanatory rather
// than a black box. The logic mirrors what scoring/compute.py does
// in code; if either side changes, both must update.
//
// Two paths:
//   - foundation_model: derived from OpenRouter facts
//                       (context_length, provider tier, modality, price)
//   - application:      z-scored against the admitted population from
//                       latest signal readings
//
// Numbers shown match the persisted score rows. For FMs we reproduce
// the formula client-side using `agent.facts`; for application agents
// we list the signals that fed into each pillar with their latest
// values pulled from the existing /signals endpoint.

interface Props {
  agent: AgentDetail;
  signals: SignalSeries[];
}

// Open LLM Leaderboard match — when present, Quality is real benchmark
// data, not the heuristic. Surfaced via the agent.facts dict on FMs.
const HF_LEADERBOARD_NOTE =
  "Open LLM Leaderboard composite (Average ⬆️ across IFEval, BBH, MATH, GPQA, MUSR, MMLU-PRO).";

const ADOPTION_SOURCES = [
  "github_stars",
  "hf_downloads_30d",
  "npm_weekly",
  "pypi_monthly",
  "mcp_registry_listed",
  "stackoverflow_questions_7d",
  "producthunt_upvotes",
];

const COMMUNITY_SOURCES = [
  "github_contributors",
  "hn_points_7d",
  "reddit_points_7d",
  "bluesky_mentions_7d",
];

const MOMENTUM_SOURCES = ADOPTION_SOURCES; // rate-of-change of adoption

const SOURCE_LABELS: Record<string, string> = {
  github_stars: "GitHub stars",
  github_forks: "GitHub forks",
  github_commits_7d: "Commits (7d)",
  github_contributors: "Contributors",
  hf_downloads_30d: "HF downloads (30d)",
  hf_likes: "HF likes",
  hf_trending_rank: "HF trending rank",
  npm_weekly: "npm weekly installs",
  pypi_monthly: "PyPI monthly installs",
  mcp_registry_listed: "MCP registry listing",
  hn_points_7d: "Hacker News points (7d)",
  hn_mentions_7d: "Hacker News mentions (7d)",
  reddit_points_7d: "Reddit points (7d)",
  reddit_mentions_7d: "Reddit mentions (7d)",
  bluesky_mentions_7d: "Bluesky mentions (7d)",
  stackoverflow_questions_7d: "Stack Overflow questions (7d)",
  producthunt_upvotes: "Product Hunt upvotes",
  benchmark_score: "Benchmark score",
  arxiv_citations: "arXiv citations",
};

export function PillarExplanations({ agent, signals }: Props) {
  if (agent.entity_kind === "foundation_model") {
    return <FoundationModelExplanation agent={agent} signals={signals} />;
  }
  return <ApplicationExplanation agent={agent} signals={signals} />;
}

function FoundationModelExplanation({
  agent,
  signals,
}: {
  agent: AgentDetail;
  signals: SignalSeries[];
}) {
  const facts = (agent.facts ?? {}) as {
    openrouter_id?: string;
    context_length?: number;
    modality?: string;
    input_price_per_million?: number;
    output_price_per_million?: number;
  };
  const ctx = facts.context_length ?? 0;
  const provider = (facts.openrouter_id ?? "").split("/", 1)[0];
  const modality = (facts.modality ?? "").toLowerCase();
  const isFrontier = ["openai", "anthropic", "google", "meta-llama", "mistralai"].includes(
    provider,
  );
  const blendedPrice =
    facts.input_price_per_million != null && facts.output_price_per_million != null
      ? (facts.input_price_per_million + facts.output_price_per_million) / 2
      : facts.input_price_per_million ?? null;

  // Real signals that may have been ingested for this FM. When
  // present, they explain the score; when absent, the metadata-only
  // reasoning takes over.
  const hnNow = latest(signals, "hn_mentions_7d");
  const bskyNow = latest(signals, "bluesky_mentions_7d");
  const benchmarkNow = latest(signals, "benchmark_score");

  const rows: { pillar: string; score: number | null | undefined; rule: string }[] = [
    {
      pillar: "Adoption",
      score: agent.score?.adoption,
      rule: [
        ctx ? `${formatTokens(ctx)} context window` : null,
        hnNow != null && hnNow > 0
          ? `${formatCount(hnNow)} HN mentions in 7d`
          : null,
      ]
        .filter(Boolean)
        .join(" + ") || "No context length on file.",
    },
    {
      pillar: "Quality",
      score: agent.score?.quality,
      rule:
        benchmarkNow != null
          ? `${benchmarkNow.toFixed(1)} on the Open LLM Leaderboard composite (Average across IFEval / BBH / MATH / GPQA / MUSR / MMLU-PRO).`
          : [
              isFrontier ? "Frontier-tier provider" : "Non-frontier provider",
              modality.includes("image") || modality.includes("vision")
                ? "+ multimodal"
                : null,
              " · heuristic until benchmark data lands.",
            ]
              .filter(Boolean)
              .join(" "),
    },
    {
      pillar: "Momentum",
      score: agent.score?.momentum,
      rule:
        hnNow != null || bskyNow != null
          ? `7d rate-of-change in mentions: ${[
              hnNow != null ? `HN ${formatCount(hnNow)}` : null,
              bskyNow != null ? `Bluesky ${formatCount(bskyNow)}` : null,
            ]
              .filter(Boolean)
              .join(", ")}.`
          : "Slug-based recency heuristic — replaced by real mention deltas once HN / Bluesky pick the model up.",
    },
    {
      pillar: "Community",
      score: agent.score?.community,
      rule:
        blendedPrice != null
          ? `Blended price ${blendedPrice === 0 ? "free" : `$${blendedPrice.toFixed(2)}/M tokens`} — cheaper = wider community access.`
          : "No pricing on file.",
    },
  ];

  return (
    <Panel
      title="How this score was computed"
      subtitle="Foundation models score against OpenRouter metadata, not GitHub/HF signals — the inputs that move LLMs are different."
      rows={rows}
    />
  );
}

function ApplicationExplanation({
  agent,
  signals,
}: {
  agent: AgentDetail;
  signals: SignalSeries[];
}) {
  const latestBySource: Record<string, number | null> = {};
  for (const s of signals) {
    const points = s.points ?? [];
    if (points.length === 0) {
      latestBySource[s.source] = null;
      continue;
    }
    const sorted = [...points].sort(
      (a, b) =>
        new Date(b.captured_at).getTime() - new Date(a.captured_at).getTime(),
    );
    latestBySource[s.source] = sorted[0].value;
  }

  function lineFor(sources: string[]): string {
    const present = sources
      .map((s) => ({ s, v: latestBySource[s] }))
      .filter((x) => x.v != null);
    if (present.length === 0) {
      return "No signals yet — pillar uses neutral baseline.";
    }
    return present
      .map((x) => `${SOURCE_LABELS[x.s] ?? x.s}: ${formatCount(x.v as number)}`)
      .join(" · ");
  }

  const benchmarkValue = latestBySource["benchmark_score"];
  const rows = [
    {
      pillar: "Adoption",
      score: agent.score?.adoption,
      rule: lineFor(ADOPTION_SOURCES),
    },
    {
      pillar: "Quality",
      score: agent.score?.quality,
      rule:
        agent.score?.quality == null
          ? "Unrated — no benchmark results on file. Quality's 30% weight is redistributed pro-rata to the other three pillars."
          : benchmarkValue != null
            ? `Benchmark score ${benchmarkValue.toFixed(2)} (z-scored against the rated population).`
            : "Benchmark data exists but wasn't loaded into this view.",
    },
    {
      pillar: "Momentum",
      score: agent.score?.momentum,
      rule: `7d/30d rate-of-change blend over: ${MOMENTUM_SOURCES.map((s) => SOURCE_LABELS[s] ?? s).join(", ")}.`,
    },
    {
      pillar: "Community",
      score: agent.score?.community,
      rule: lineFor(COMMUNITY_SOURCES),
    },
  ];

  return (
    <Panel
      title="How this score was computed"
      subtitle="Each pillar z-scores its source signals against the admitted-agent population, clamps to ±3σ, and maps to 0–100."
      rows={rows}
    />
  );
}

function Panel({
  title,
  subtitle,
  rows,
}: {
  title: string;
  subtitle: string;
  rows: { pillar: string; score: number | null | undefined; rule: string }[];
}) {
  return (
    <section className="rounded-md border border-border bg-card">
      <div className="border-b border-border px-4 py-2.5">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {title}
        </div>
        <div className="text-[11px] text-muted-foreground">{subtitle}</div>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => (
          <li key={r.pillar} className="grid grid-cols-[80px_60px_1fr] gap-3 px-4 py-2.5 text-sm md:grid-cols-[100px_70px_1fr]">
            <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              {r.pillar}
            </span>
            <span className="num font-semibold">
              {r.score == null ? "—" : r.score.toFixed(1)}
            </span>
            <span className="text-foreground/85">{r.rule}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function formatCount(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}
