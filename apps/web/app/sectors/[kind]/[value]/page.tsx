import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { MoverChip } from "@/components/mover-chip";
import { SectorChart } from "@/components/sector-chart";
import { SectorMembersPanel } from "@/components/sector-members-panel";
import { LiveFaq, QuickAnswer } from "@/components/live-answers";
import {
  APP_SCORING,
  FM_SCORING,
  SEE_THE_DATA,
  bestNow,
  computeLeaders,
  gainingNow,
  openSourceNow,
  rankByScore,
  resolveFaqs,
  withYear,
  type Faq,
} from "@/lib/live-answers";

// Sector detail — like an index page but rolled up by tag.
//
// Shows:
//   - cohort headline (avg AgentScore, member count, verdict)
//   - 30d composite chart (avg score over time)
//   - members table, ranked by score, with watch toggles
// The same shape as /indexes/[slug] so the mental model stays
// consistent: "another index, just one rolled up by capability".

const VALID_KINDS = [
  "capability",
  "deployment",
  "maturity",
  "domain",
  "license",
  // model_dep — family-level "Built on" sector. Apps tagged with
  // model_dep:claude end up listed at /sectors/model_dep/claude, the
  // landing reachable from the chip on each agent header.
  "model_dep",
];

// 5-minute ISR. Cached HTML keeps serving when the backend is slow or
// unreachable. Trade-off: a 5-minute lag on cohort moves vs a hard
// outage when Hetzner blips.
export const revalidate = 300;

interface PageParams {
  params: Promise<{ kind: string; value: string }>;
  searchParams: Promise<{ ek?: string }>;
}

// Capability / deployment / maturity / model_dep sectors mix
// applications and foundation models in principle, but the user's
// question on these pages is almost always "what app should I use" —
// so they default to apps. model_dep tags only ever apply to
// applications anyway (an FM doesn't depend on itself), so the
// default is correct on that page. License / domain pages don't
// have that bias and stay all-kinds.
const APPS_DEFAULT_KINDS = new Set([
  "capability",
  "deployment",
  "maturity",
  "model_dep",
]);

type EkFilter = "application" | "foundation_model" | "all";

function parseEk(raw: string | undefined, kind: string): EkFilter {
  if (raw === "application" || raw === "foundation_model" || raw === "all") {
    return raw;
  }
  return APPS_DEFAULT_KINDS.has(kind) ? "application" : "all";
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { kind, value } = await params;
  const noun = sectorNoun(kind, value, "application");
  // Where a /top/* page already targets "best X", this page takes the
  // "every X" angle so the two don't compete for the same search.
  const title = TOP_COVERED.has(`${kind}:${value}`)
    ? `All ${titleCase(noun)}, Ranked Live`
    : withYear(`Best ${titleCase(noun)} ({year}): Live Ranking`);
  return {
    // Absolute: the /sectors layout sets a plain title, which stops the
    // root "%s | AgentTape" template reaching this segment.
    title: { absolute: `${title} | AgentTape` },
    description: `Live ranking of the best ${noun}, ordered by AgentScore from public adoption, community, quality and momentum signals. Score history, 24-hour movers and every member, updated hourly.`,
    alternates: { canonical: `/sectors/${kind}/${value}` },
  };
}

export default async function SectorDetailPage({ params, searchParams }: PageParams) {
  const { kind, value } = await params;
  const sp = await searchParams;
  const ek = parseEk(sp.ek, kind);
  if (!VALID_KINDS.includes(kind)) notFound();

  // Members are server-loaded; the chart is now a client component
  // that fetches history per chosen window. We still pull a quick
  // 7d slice here just to compute the headline composite + delta.
  const [history, members] = await Promise.all([
    api.sectorHistory(kind, value, "7d").catch(() => []),
    api.listAgents({
      tag_kind: kind,
      tag_value: value,
      sort: "score",
      limit: 100,
      entity_kind: ek === "all" ? undefined : ek,
    }).catch(() => null),
  ]);

  // Empty sector — no admitted agents carry this tag yet. Render an
  // explainer + a route back to /sectors instead of a hard 404. Bad
  // 404s look like a broken site to users who clicked from a chip.
  if (!members || members.items.length === 0) {
    return (
      <article>
        <div className="border-b border-border bg-card">
          <div className="container py-10">
            <BackLink href="/sectors" label="All sectors" className="mb-4" />
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Sector · {kind}
            </div>
            <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
              {pretty(value)}
            </h1>
            <p className="mt-2 max-w-prose text-sm text-muted-foreground">
              No admitted agents are tagged{" "}
              <span className="font-mono">{kind}:{value}</span> yet. The
              discovery service tags agents as it admits them — check
              back, or browse the sectors that already have members.
            </p>
            <div className="mt-6">
              <Link
                href="/sectors"
                className="text-sm font-medium text-primary hover:underline"
              >
                Browse sectors with members →
              </Link>
            </div>
          </div>
        </div>
      </article>
    );
  }

  const noun = sectorNoun(kind, value, ek);
  const leaders = computeLeaders(rankByScore(members.items), `/sectors/${kind}/${value}`);
  const faqs = resolveFaqs(sectorFaqs(kind, ek, noun), leaders);

  const composite =
    history.length > 0 ? history.at(-1)?.avg_score ?? null : null;
  const first = history.length > 0 ? history[0]?.avg_score ?? null : null;
  const delta =
    composite != null && first != null ? composite - first : null;

  return (
    <article>
      <div className="border-b border-border bg-card">
        <div className="container py-10">
          <BackLink href="/sectors" label="All sectors" className="mb-4" />
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Sector · {kind}
          </div>
          <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
            {sentenceCase(noun)}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cohort of {members.total} admitted agents tagged{" "}
            <span className="font-mono">{kind}:{value}</span>. Composite
            below is the cohort's average AgentScore.
          </p>
          <QuickAnswer noun={noun} leaders={leaders} className="mt-4" />

          <div className="mt-6 grid gap-6 md:grid-cols-[auto_1fr]">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Avg AgentScore
              </div>
              <div className="mt-1 text-stat-xl font-semibold num">
                {formatScore(composite)}
              </div>
              {delta !== null && (
                <div className="mt-1">
                  <MoverChip delta={delta} unit="score" />
                  <span className="ml-2 text-xs text-muted-foreground">
                    vs 30d ago
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <SectorChart kind={kind} value={value} />
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8 md:py-12 space-y-8 pb-24 md:pb-12">
        {APPS_DEFAULT_KINDS.has(kind) && (
          <KindTabs kind={kind} value={value} active={ek} />
        )}
        <SectorMembersPanel members={members.items} />

        <LiveFaq faqs={faqs} />

        <p className="hairline pt-6 text-xs text-muted-foreground">
          Browse all sectors at{" "}
          <Link href="/sectors" className="text-primary hover:underline">
            /sectors
          </Link>
          .
        </p>
      </div>
    </article>
  );
}

// Search-friendly plural noun for a sector, used in the title, h1 and
// live answers ("the top-ranked AI research agents on AgentTape are…").
// Falls back to a generic form for tags without a hand-written name.
const CAPABILITY_NOUNS: Record<string, string> = {
  "code-generation": "AI coding agents",
  browsing: "AI browser agents",
  research: "AI research agents",
  rag: "RAG agents",
  "multi-agent": "multi-agent frameworks",
  automation: "AI automation agents",
  "tool-use": "tool-using AI agents",
  memory: "AI agent memory tools",
  vision: "vision AI agents",
  voice: "voice AI agents",
};
const DEPLOYMENT_NOUNS: Record<string, string> = {
  library: "AI agent libraries",
  cli: "CLI AI agents",
  saas: "SaaS AI agents",
  "ide-plugin": "AI coding IDE plugins",
  "browser-extension": "AI browser extensions",
  "mcp-server": "MCP servers",
};
const LICENSE_NAMES: Record<string, string> = {
  mit: "MIT",
  "apache-2.0": "Apache 2.0",
  bsd: "BSD",
  mpl: "MPL",
  gpl: "GPL",
  agpl: "AGPL",
};
const MODEL_NAMES: Record<string, string> = {
  claude: "Claude",
  gpt: "GPT",
  openai: "OpenAI",
  gemini: "Gemini",
  llama: "Llama",
  deepseek: "DeepSeek",
  qwen: "Qwen",
  mistral: "Mistral",
};

function sectorNoun(kind: string, value: string, ek: EkFilter): string {
  if (ek === "foundation_model") {
    return kind === "license"
      ? `${LICENSE_NAMES[value] ?? pretty(value)}-licensed foundation models`
      : `${pretty(value).toLowerCase()} foundation models`;
  }
  switch (kind) {
    case "capability":
      return CAPABILITY_NOUNS[value] ?? `${pretty(value).toLowerCase()} AI agents`;
    case "deployment":
      return DEPLOYMENT_NOUNS[value] ?? `${pretty(value)} AI agents`;
    case "license":
      if (value === "proprietary") return "proprietary AI agents";
      if (value === "unknown") return "AI agents with no declared license";
      return `${LICENSE_NAMES[value] ?? pretty(value)}-licensed AI agents`;
    case "model_dep":
      return `AI agents built on ${MODEL_NAMES[value] ?? pretty(value)}`;
    case "domain":
      return `AI agents for ${pretty(value).toLowerCase()}`;
    default:
      return `${pretty(value).toLowerCase()} AI agents`;
  }
}

// Every sector gets the questions the live data can answer, plus how
// the score works with a pointer to the charts and breakdowns.
function sectorFaqs(kind: string, ek: EkFilter, noun: string): Faq[] {
  // Singular of the head noun only ("AI agents for sales" → "AI agent
  // for sales"), so tag words ending in "s" are left alone.
  const one = noun.replace(
    /\b(agents|frameworks|tools|servers|plugins|extensions|models|libraries)\b/,
    (w) => (w === "libraries" ? "library" : w.slice(0, -1)),
  );
  const faqs: Faq[] = [
    { q: `What is the best ${one} right now?`, a: bestNow(one) },
    { q: `Which ${noun} are gaining fastest right now?`, a: gainingNow },
  ];
  if (kind !== "license" && ek !== "foundation_model") {
    faqs.push({ q: `Which ${noun} are open source?`, a: openSourceNow(noun) });
  }
  faqs.push({
    q: "How is this ranking calculated?",
    a:
      (ek === "foundation_model" ? FM_SCORING : APP_SCORING) +
      " The headline above is the cohort's average AgentScore; the chart shows how it has moved." +
      SEE_THE_DATA,
  });
  return faqs;
}

const TOP_COVERED = new Set([
  "capability:code-generation",
  "capability:browsing",
  "deployment:mcp-server",
]);

const SMALL_WORDS = new Set(["on", "for", "with", "no", "and", "of"]);

function titleCase(text: string): string {
  return text
    .split(" ")
    .map((w, i) => (i > 0 && SMALL_WORDS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

function sentenceCase(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function pretty(value: string): string {
  return value
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}

// Kind tabs — let the reader switch between Apps (default), Foundation
// models, or All without leaving the page. URL-driven via ?ek= so the
// chosen view is shareable. Plain links rather than client state so
// the page stays a server component and the back button works.
function KindTabs({
  kind,
  value,
  active,
}: {
  kind: string;
  value: string;
  active: EkFilter;
}) {
  const opts: { v: EkFilter; label: string }[] = [
    { v: "application", label: "Applications" },
    { v: "foundation_model", label: "Foundation models" },
    { v: "all", label: "All" },
  ];
  return (
    <div className="inline-flex rounded-md border border-border bg-card p-0.5">
      {opts.map((o) => {
        const href = `/sectors/${kind}/${value}${
          o.v === "application" ? "" : `?ek=${o.v}`
        }`;
        return (
          <Link
            key={o.v}
            href={href}
            className={`rounded-sm px-3 py-1 text-xs font-mono uppercase tracking-wider transition-colors ${
              active === o.v
                ? "bg-subtle text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {o.label}
          </Link>
        );
      })}
    </div>
  );
}
