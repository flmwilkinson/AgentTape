import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";

// SEO landing pages keyed by high-intent search queries.
//
// /top/coding-agents          → CODE-25
// /top/browser-agents         → WEB-25
// /top/foundation-models      → FM-50
// /top/open-source-ai-agents  → OSS-50
// /top/mcp-servers            → MCP-25
//
// Each is a thin SEO wrapper around the canonical index. Same data,
// different URL + metadata + h1 + intro paragraph optimised for search
// queries the keyword tools say people actually type.

interface SectorDef {
  slug: string;
  index_slug: string;
  title: string;
  h1: string;
  description: string;
  intro: string;
  faqs: { q: string; a: string }[];
}

const SECTORS: SectorDef[] = [
  {
    slug: "coding-agents",
    index_slug: "code-25",
    title: "Top Coding AI Agents — Ranked Live | AgentTape",
    h1: "The 25 best AI agents for coding.",
    description:
      "The top AI agents for software engineering, ranked by AgentScore. Compare AutoGPT, crewAI, Cursor and more. Updated continuously, free to read.",
    intro:
      "These are the AI agents most-used by software engineers right now. They write code, review PRs, run test suites, and orchestrate multi-step development tasks. Every entry is ranked by AgentScore — a 0–100 composite of adoption, quality, momentum and community signals — and the table shows how each has moved in the last 24 hours.",
    faqs: [
      {
        q: "What's the best AI agent for coding right now?",
        a: "The top of CODE-25 changes weekly. The agent at rank 1 in the table below has the highest AgentScore right now. Use the Compare page to put your top 2–3 candidates head-to-head.",
      },
      {
        q: "Is this just GitHub stars rearranged?",
        a: "No. AgentScore weights adoption (35%), quality (30%, when benchmark data exists), momentum (20%), and community (15%). GitHub stars are one of several adoption signals.",
      },
      {
        q: "How often does this update?",
        a: "Adoption signals (stars, mentions) refresh every 5 minutes. Quality (benchmarks) refreshes daily. The CODE-25 index rebalances every Monday at 03:00 UTC.",
      },
    ],
  },
  {
    slug: "browser-agents",
    index_slug: "web-25",
    title: "Top Browser AI Agents — Ranked Live | AgentTape",
    h1: "The 25 best AI browser agents.",
    description:
      "AI agents that browse the web and operate browsers — browser-use, MultiOn, Steel WebVoyager and more. Ranked by AgentScore. Compare any two side-by-side.",
    intro:
      "Browser agents drive a real Chromium / Playwright instance to complete tasks for you — search, fill forms, scrape pages, transact. This is the live ranking of the most-used and fastest-moving ones.",
    faqs: [
      {
        q: "What's a browser agent?",
        a: "An AI agent that controls a real browser. Most use Playwright or Puppeteer under the hood. They differ from chat agents in that they can click, type, and navigate websites.",
      },
      {
        q: "Open-source or commercial?",
        a: "Both. The license tag on each entry tells you which. For open-source-only see /top/open-source-ai-agents.",
      },
    ],
  },
  {
    slug: "foundation-models",
    index_slug: "fm-50",
    title: "Top Foundation Models — Ranked Live | AgentTape",
    h1: "The 50 best foundation models.",
    description:
      "Claude, GPT, Llama, Gemini, Mistral, DeepSeek and 45+ more — the live ranking of foundation models. Compare context, pricing and quality scores side-by-side.",
    intro:
      "Foundation models are the LLMs that power agents — the raw intelligence layer. FM-50 ranks them with the same AgentScore formula tuned so quality (benchmark performance) carries more weight than for application agents. Sourced from the OpenRouter catalogue, refreshed daily.",
    faqs: [
      {
        q: "Should I use Claude or GPT?",
        a: "Depends on the task. Use the Compare page (/compare) — drop both in and see the overlay chart, pillar bars, and 'best at X' verdict. The fastest way to a justified pick.",
      },
      {
        q: "Are open-weights models in here?",
        a: "Yes — Llama, Mistral, Qwen, DeepSeek and others. Anything OpenRouter exposes shows up. Filter by license tag to see only open-weights.",
      },
    ],
  },
  {
    slug: "open-source-ai-agents",
    index_slug: "oss-50",
    title: "Top Open-Source AI Agents — Ranked Live | AgentTape",
    h1: "The 50 best open-source AI agents.",
    description:
      "AI agents released under MIT, Apache, BSD or other OSI-approved licenses. Self-host, fork, and deploy without a vendor in the loop. Live AgentScore ranking.",
    intro:
      "Every agent here has an OSI-approved license — MIT, Apache 2.0, BSD, MPL, GPL or AGPL. You can self-host, fork, and run on your own infrastructure with no API key requirement.",
    faqs: [
      {
        q: "Why pick an open-source agent?",
        a: "Three reasons people most often cite: no vendor lock-in, full code visibility (audit before you ship), and self-hosting (data stays in your VPC).",
      },
      {
        q: "Are these as good as proprietary alternatives?",
        a: "Some are, some aren't. Use the AgentScore plus the Compare page to evaluate against proprietary alternatives. The methodology page documents how the scores are computed.",
      },
    ],
  },
  {
    slug: "mcp-servers",
    index_slug: "mcp-25",
    title: "Top MCP Servers — Ranked Live | AgentTape",
    h1: "The 25 best MCP servers.",
    description:
      "Model Context Protocol servers ranked by adoption. The tools every agent should have access to — file system, GitHub, Postgres, search, browser and more.",
    intro:
      "Model Context Protocol (MCP) is Anthropic's open standard for letting AI agents call external tools. These are the most-used MCP servers — drop them into Claude Desktop, Cursor, or any MCP-aware client.",
    faqs: [
      {
        q: "What is MCP?",
        a: "Model Context Protocol — an open standard from Anthropic that lets AI agents connect to tools (files, GitHub, databases, browsers) over a clean interface. See modelcontextprotocol.io for spec.",
      },
      {
        q: "Are these audited?",
        a: "AgentTape doesn't audit MCP servers. Read the source before connecting any MCP server to a session that has access to data you care about. Most are MIT-licensed and on GitHub.",
      },
    ],
  },
];

const BY_SLUG = Object.fromEntries(SECTORS.map((s) => [s.slug, s]));

export function generateStaticParams() {
  return SECTORS.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const def = BY_SLUG[slug];
  if (!def) return { title: "Not found" };
  return {
    title: def.title,
    description: def.description,
    alternates: { canonical: `/top/${def.slug}` },
    openGraph: {
      title: def.title,
      description: def.description,
      images: [{ url: `/api/og/index/${def.index_slug}` }],
    },
  };
}

export const dynamic = "force-dynamic";

export default async function SectorLandingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const def = BY_SLUG[slug];
  if (!def) notFound();

  const detail = await api.getIndex(def.index_slug).catch(() => null);
  if (!detail) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: def.h1,
    description: def.description,
    itemListElement: detail.constituents.slice(0, 25).map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `https://agenttape.io/agents/${c.agent.slug}`,
      name: c.agent.name,
    })),
  };

  return (
    <article className="container py-10 md:py-14 max-w-5xl space-y-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <BackLink href="/" label="Floor" className="-mb-2" />

      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Top · {detail.name}
        </div>
        <h1 className="editorial mt-3 text-4xl font-semibold leading-tight md:text-6xl md:leading-[1.05]">
          {def.h1}
        </h1>
        <p className="editorial mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground md:text-xl">
          {def.intro}
        </p>
        <p className="mt-4 text-xs text-muted-foreground">
          Read the full{" "}
          <Link
            href={`/indexes/${def.index_slug}`}
            className="text-primary hover:underline"
          >
            {detail.name} index
          </Link>{" "}
          or jump to{" "}
          <Link href="/compare" className="text-primary hover:underline">
            comparison
          </Link>
          .
        </p>
      </header>

      {/* The ranked list — the actual content for the page. */}
      <section className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full min-w-[640px] text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-right">#</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-right">24h</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Δ24h</th>
            </tr>
          </thead>
          <tbody>
            {detail.constituents.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-xs text-muted-foreground"
                >
                  This index hasn't rebalanced yet — check back after Monday's
                  rebalance.
                </td>
              </tr>
            )}
            {detail.constituents.slice(0, 25).map((c, i) => (
              <tr
                key={c.agent.slug}
                className="border-b border-border last:border-b-0"
              >
                <td className="px-3 py-2 text-right text-muted-foreground">
                  {i + 1}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/agents/${c.agent.slug}`}
                    className="font-sans font-medium hover:text-primary"
                  >
                    {c.agent.name}
                  </Link>
                  {c.agent.description && (
                    <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                      {c.agent.description}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2 text-right">
                  <RankArrow
                    delta={c.agent.score?.rank_delta_24h ?? null}
                    rankNow={c.agent.score?.rank_now ?? null}
                  />
                </td>
                <td className="px-3 py-2 text-right font-semibold">
                  {formatScore(c.agent.score?.agent_score ?? null)}
                </td>
                <td className="px-3 py-2 text-right">
                  {c.agent.score?.delta_24h != null ? (
                    <MoverChip
                      delta={c.agent.score.delta_24h}
                      unit="score"
                      variant="outline"
                    />
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* FAQ — pure SEO play, plain readable prose helps too. */}
      <section>
        <h2 className="editorial text-2xl font-semibold leading-tight md:text-3xl">
          Common questions
        </h2>
        <dl className="mt-4 space-y-5">
          {def.faqs.map((f, i) => (
            <div key={i}>
              <dt className="font-medium text-foreground">{f.q}</dt>
              <dd className="mt-1 max-w-prose text-sm text-muted-foreground md:text-base">
                {f.a}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="text-xs text-muted-foreground">
        Methodology and source code are public — read{" "}
        <Link href="/methodology" className="text-primary hover:underline">
          how AgentScore works
        </Link>
        .
      </p>
    </article>
  );
}
