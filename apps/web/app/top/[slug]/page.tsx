import Link from "next/link";
import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api, ApiError } from "@/lib/api-client";
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

// Copy is written to answer the questions people actually ask search
// engines and AI assistants ("what's the best X", "X vs Y", "is X
// safe"). Each answer leads with a direct, self-contained sentence so
// it can be quoted on its own. Facts about scoring must match
// /methodology (pillar weights, hourly/daily refresh, Monday
// rebalance); update both together.
//
// The ranking is live, so answers never carry a date or a hard-coded
// winner: anything the data can answer ("best right now", "which are
// open source", "what's gaining") is computed from the live index on
// each render; anything it can't points at the live charts and score
// breakdowns. `{year}` in title/h1 is replaced at render time.

interface Leaders {
  // Pulled from the live index on every render (5-minute ISR), best
  // first. Empty before the first rebalance.
  top: { name: string; score: string }[];
  // Biggest positive 24h AgentScore move in this ranking, if any.
  mover: { name: string; delta: string } | null;
  // Members carrying an OSI-approved license tag.
  open: { count: number; total: number; names: string[] };
  indexPath: string;
}

interface SectorDef {
  slug: string;
  index_slug: string;
  title: string;
  h1: string;
  // Plural noun used in the generated quick answer: "the top-ranked
  // {noun} on AgentTape are…"
  noun: string;
  description: string;
  intro: string;
  faqs: { q: string; a: string | ((l: Leaders) => string) }[];
}

const APP_SCORING =
  "AgentScore is a 0–100 composite of four pillars: adoption (40%), community (30%), quality (20%, from benchmarks where they exist) and momentum (10%). GitHub stars are one adoption signal among many, alongside package downloads, mentions, contributors and release activity. A pillar with no data counts as zero rather than being re-weighted, so thinly documented projects can't score high by accident.";

const CADENCE =
  "Most signals (GitHub, package downloads, Hacker News and Bluesky mentions) refresh hourly; benchmarks and slower sources refresh daily. The index membership rebalances every Monday at 03:00 UTC.";

const OSI_LICENSES = new Set(["mit", "apache-2.0", "bsd", "mpl", "gpl", "agpl"]);

function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function bestNow(noun: string) {
  return (l: Leaders) => {
    const [a, ...rest] = l.top;
    if (!a) {
      return `This ranking is still filling in. The live chart at ${l.indexPath} shows current members as they're admitted.`;
    }
    const followers = rest.map((x) => `${x.name} (${x.score})`);
    return `Right now it's ${a.name}, with an AgentScore of ${a.score}${
      followers.length ? `, followed by ${listNames(followers)}` : ""
    }. This changes as new signals arrive: the table above is live, and each agent's page charts its score over time. The best ${noun} for you depends on your task, so shortlist two or three and put them side by side on the Compare page.`;
  };
}

function openSourceNow(noun: string) {
  return (l: Leaders) => {
    if (!l.open.total) {
      return "Each agent's page shows its license once the ranking fills in. /top/open-source-ai-agents ranks open-source agents only.";
    }
    const led = l.open.names.length ? `, led by ${listNames(l.open.names)}` : "";
    return `Right now ${l.open.count} of the ${l.open.total} ${noun} in this ranking carry an OSI-approved license (MIT, Apache 2.0, BSD, MPL, GPL or AGPL)${led}. Each agent's page shows its license, and /top/open-source-ai-agents ranks open-source agents only. Open-source agents still need a model, through an API key or a local model.`;
  };
}

function gainingNow(l: Leaders): string {
  const tail =
    "/trending shows every mover over 24 hours, 7 days or 30 days, and each agent's page breaks the move down by signal.";
  return l.mover
    ? `Right now the biggest 24-hour gain in this ranking is ${l.mover.name}, up ${l.mover.delta} points. ${tail}`
    : `Nothing in this ranking has gained in the last 24 hours. ${tail}`;
}

const SEE_THE_DATA =
  " Open any agent to see its score chart and a per-pillar breakdown down to each raw signal; /methodology has the full formula.";

const SECTORS: SectorDef[] = [
  {
    slug: "coding-agents",
    index_slug: "code-25",
    title: "Best AI Coding Agents ({year}): Live Ranking",
    h1: "The 25 best AI coding agents, ranked live.",
    noun: "AI coding agents",
    description:
      "The best AI coding agents right now, ranked by AgentScore from public adoption, community, quality and momentum signals. Open-source and commercial. Updated hourly.",
    intro:
      "AI coding agents go beyond autocomplete: they plan a change, edit several files, run commands and tests, and iterate on failures. This is a live ranking of the coding agents with the strongest public signals, ordered by AgentScore, with each one's 24-hour move.",
    faqs: [
      { q: "What is the best AI coding agent right now?", a: bestNow("coding agent") },
      {
        q: "What's the difference between an AI coding agent and code autocomplete?",
        a: "Autocomplete suggests the next few lines as you type. A coding agent takes a goal (\"add pagination to this endpoint\", \"fix the failing test\"), works out the steps, edits multiple files, runs your build or tests, and tries again when something fails. You review the result instead of writing every line.",
      },
      { q: "Which AI coding agents are open source?", a: openSourceNow("coding agents") },
      { q: "Which AI coding agents are gaining fastest right now?", a: gainingNow },
      {
        q: "How do I choose between coding agents?",
        a: "Start with the top of this table, then open each candidate's page: its score chart shows whether it's still climbing, and the pillar breakdown shows whether that's driven by real adoption, an active community or benchmark results. Check it supports the model and editor you already use, then put two side by side on the Compare page.",
      },
      { q: "How is this ranking calculated?", a: APP_SCORING + SEE_THE_DATA },
      { q: "How often is it updated?", a: CADENCE },
    ],
  },
  {
    slug: "browser-agents",
    index_slug: "web-25",
    title: "Best AI Browser Agents ({year}): Live Ranking",
    h1: "The 25 best AI browser agents, ranked live.",
    noun: "AI browser agents",
    description:
      "The best AI browser agents right now: in-browser extensions and headless automation agents that browse, click, fill forms and scrape. Ranked live by AgentScore.",
    intro:
      "AI browser agents use a language model to operate a web browser for you: they read the page, decide what to click or type, and keep going until the task is done, whether that's research, form filling, scraping or checkout. Some run inside your own browser as an extension; others drive a headless browser through Playwright, Puppeteer or the Chrome DevTools Protocol. This is the live ranking of the ones with the strongest public signals.",
    faqs: [
      { q: "What is the best AI browser agent right now?", a: bestNow("browser agent") },
      {
        q: "What is an AI browser agent?",
        a: "An AI browser agent is software that lets a language model control a web browser. It reads the page (as HTML, an accessibility tree or screenshots), chooses an action such as click, type or scroll, observes the result and repeats until the goal is met. Unlike a chatbot, it can actually use websites rather than just describe them.",
      },
      {
        q: "In-browser vs headless: which kind of browser agent do I need?",
        a: "In-browser agents run as an extension in the browser you already use, so they can work with sites you're logged into; they suit personal tasks. Headless agents run a separate browser on your machine or in the cloud, usually via Playwright or Puppeteer; they suit automation, scraping and running many tasks in parallel. Each agent's page here links to its repo, which says which kind it is.",
      },
      {
        q: "How are AI browser agents different from Selenium or Playwright scripts?",
        a: "A script follows fixed selectors and breaks when a page changes. A browser agent decides each step from what it sees, so it can handle sites it has never seen before. The trade-off is that agents are slower, cost model tokens per step and are less predictable, so many teams use scripts for fixed flows and agents for the long tail.",
      },
      {
        q: "Are AI browser agents safe to use?",
        a: "Treat a browser agent like handing someone your keyboard. Web pages can contain hidden instructions (prompt injection) that try to redirect the agent. Use a separate browser profile, avoid running it on email or banking sessions, require confirmation before purchases or form submissions, and read the source of open-source agents before trusting them.",
      },
      { q: "Which AI browser agents are open source?", a: openSourceNow("browser agents") },
      { q: "Which AI browser agents are gaining fastest right now?", a: gainingNow },
      { q: "How is this ranking calculated?", a: APP_SCORING + SEE_THE_DATA },
    ],
  },
  {
    slug: "foundation-models",
    index_slug: "fm-50",
    title: "Best Foundation Models and LLMs ({year}): Live Ranking",
    h1: "The 50 best foundation models, ranked live.",
    noun: "foundation models",
    description:
      "The best LLMs and foundation models right now, ranked live by AgentScore from benchmarks, real usage, cost and speed. Open-weights and proprietary, with pricing and context length.",
    intro:
      "Foundation models are the large language models that power agents. FM-50 ranks them with a version of AgentScore that weights quality (benchmark performance) most heavily and adds an efficiency pillar for cost and speed. The catalogue comes from OpenRouter, with benchmarks from Artificial Analysis, LMArena, SWE-bench and others, refreshed daily.",
    faqs: [
      { q: "What is the best foundation model right now?", a: bestNow("foundation model") },
      {
        q: "Which LLM is best for building AI agents?",
        a: "For agents, look past headline benchmarks to reliable tool calling, a long enough context window for your task, and cost per token, since agents make many calls per task. Each model's page here shows its quality, efficiency and adoption scores, and the Compare page puts two models side by side.",
      },
      {
        q: "Should I use Claude, GPT or Gemini?",
        a: "It depends on the task, budget and latency you need. Put the specific versions you're considering into the Compare page to see their quality, efficiency, adoption and momentum side by side, then test the top two on your own prompts.",
      },
      { q: "Which models are gaining fastest right now?", a: gainingNow },
      {
        q: "Are open-weights models included?",
        a: "Yes. Llama, Mistral, Qwen, DeepSeek and other open-weights models are ranked alongside proprietary ones; anything in the OpenRouter catalogue is eligible.",
      },
      {
        q: "How is this ranking calculated?",
        a: "Foundation models use five pillars: quality (35%, from benchmarks), adoption (25%), efficiency (20%, cost and speed), momentum (10%) and community (10%). A pillar with no data counts as zero, so only fully rated models can reach 100." + SEE_THE_DATA,
      },
    ],
  },
  {
    slug: "open-source-ai-agents",
    index_slug: "oss-50",
    title: "Best Open-Source AI Agents ({year}): Live Ranking",
    h1: "The 50 best open-source AI agents, ranked live.",
    noun: "open-source AI agents",
    description:
      "The best open-source AI agents right now: MIT, Apache, BSD, GPL and other OSI-licensed agents you can self-host and fork. Ranked live by AgentScore, updated hourly.",
    intro:
      "Every agent here has an OSI-approved license (MIT, Apache 2.0, BSD, MPL, GPL or AGPL), so you can read the code, self-host it and fork it. This is the live ranking of the open-source agents with the strongest adoption, community, quality and momentum signals.",
    faqs: [
      { q: "What is the best open-source AI agent right now?", a: bestNow("open-source AI agent") },
      { q: "Which open-source AI agents are gaining fastest right now?", a: gainingNow },
      {
        q: "Why choose an open-source AI agent?",
        a: "The three reasons people cite most: no vendor lock-in, the ability to audit the code before it touches your data, and self-hosting so data stays on your own infrastructure.",
      },
      {
        q: "Are open-source AI agents free?",
        a: "The code is free. Running it usually isn't: most agents call a paid model API such as Claude, GPT or Gemini. Many also work with local open-weights models, which removes the API cost if you have suitable hardware.",
      },
      {
        q: "What are good open-source alternatives to Devin, Cursor or Claude Code?",
        a: "See the guide at /articles/open-source-alternatives-devin-cursor-claude-code, and the live coding ranking at /top/coding-agents, where the license on each agent's page shows which are open source.",
      },
      { q: "How is this ranking calculated?", a: APP_SCORING + SEE_THE_DATA },
    ],
  },
  {
    slug: "mcp-servers",
    index_slug: "mcp-25",
    title: "Best MCP Servers ({year}): Live Ranking",
    h1: "The 25 best MCP servers, ranked live.",
    noun: "MCP servers",
    description:
      "The best Model Context Protocol (MCP) servers right now for Claude, Cursor, VS Code and other MCP clients, ranked live by adoption, community and momentum.",
    intro:
      "Model Context Protocol (MCP) is an open standard, introduced by Anthropic, for connecting AI assistants and agents to tools and data: files, GitHub, databases, browsers, search and more. These are the MCP servers with the strongest public adoption right now, ready to add to Claude Desktop, Claude Code, Cursor, VS Code or any other MCP client.",
    faqs: [
      { q: "What are the best MCP servers right now?", a: bestNow("MCP server") },
      { q: "Which MCP servers are gaining fastest right now?", a: gainingNow },
      {
        q: "What is an MCP server?",
        a: "An MCP server is a small program that exposes tools or data to an AI client over the Model Context Protocol. The client (for example Claude Desktop or Cursor) discovers the server's tools and the model can call them, such as reading a file, querying a database or opening a pull request. The specification is at modelcontextprotocol.io.",
      },
      {
        q: "How do I install an MCP server?",
        a: "Add the server to your client's MCP configuration: claude_desktop_config.json for Claude Desktop, the MCP settings in Cursor or VS Code, or the claude mcp add command in Claude Code. Each server's README gives the exact command; its AgentTape page links to the repo.",
      },
      {
        q: "Are MCP servers safe?",
        a: "AgentTape doesn't audit MCP servers. A server can run code and see whatever data you send it, and tool results can carry prompt-injection text. Read the source, prefer servers with active maintenance, and grant only the permissions a task needs.",
      },
      { q: "How is this ranking calculated?", a: APP_SCORING + SEE_THE_DATA },
    ],
  },
];

const BY_SLUG = Object.fromEntries(SECTORS.map((s) => [s.slug, s]));

// Turn on-site paths mentioned in FAQ copy ("/top/coding-agents",
// "the Compare page") into links. The JSON-LD keeps the plain text.
function linkify(text: string): ReactNode[] {
  return text
    .split(/(\/(?:top|articles|compare|methodology|indexes|trending)(?:\/[\w-]+)?|the Compare page|the search page)/)
    .map((part, i) => {
      if (i % 2 === 0) return part;
      const href =
        part === "the Compare page" ? "/compare" : part === "the search page" ? "/search" : part;
      return (
        <Link key={i} href={href} className="text-primary hover:underline">
          {part}
        </Link>
      );
    });
}

function withYear(text: string): string {
  return text.replace("{year}", String(new Date().getUTCFullYear()));
}

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
  const title = withYear(def.title);
  return {
    title,
    description: def.description,
    alternates: { canonical: `/top/${def.slug}` },
    openGraph: {
      title,
      description: def.description,
      images: [{ url: `/api/og/index/${def.index_slug}` }],
    },
  };
}

// 5-minute ISR. SEO landings stay visible during backend outages.
export const revalidate = 300;

export default async function SectorLandingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const def = BY_SLUG[slug];
  if (!def) notFound();

  // Only treat real 404s as "not found". Transient errors get
  // re-thrown so ISR doesn't cache the page as 404 and serve it
  // for 5 minutes after the API recovers.
  let detail;
  try {
    detail = await api.getIndex(def.index_slug);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound();
    }
    throw e;
  }

  // Rank by AgentScore so the table, the quick answer and the
  // structured data always agree on who is #1.
  const ranked = [...detail.constituents].sort(
    (x, y) => (y.agent.score?.agent_score ?? -1) - (x.agent.score?.agent_score ?? -1),
  );
  const now = new Date();
  const moverRow = ranked
    .filter((c) => (c.agent.score?.delta_24h ?? 0) > 0)
    .sort((x, y) => (y.agent.score?.delta_24h ?? 0) - (x.agent.score?.delta_24h ?? 0))[0];
  const openRows = ranked.filter((c) =>
    c.agent.tags.some((t) => t.kind === "license" && OSI_LICENSES.has(t.value)),
  );
  const leaders: Leaders = {
    top: ranked.slice(0, 3).map((c) => ({
      name: c.agent.name,
      score: formatScore(c.agent.score?.agent_score ?? null),
    })),
    mover: moverRow
      ? { name: moverRow.agent.name, delta: (moverRow.agent.score?.delta_24h ?? 0).toFixed(1) }
      : null,
    open: {
      count: openRows.length,
      total: ranked.length,
      names: openRows.slice(0, 3).map((c) => c.agent.name),
    },
    indexPath: `/indexes/${def.index_slug}`,
  };
  const faqs = def.faqs.map((f) => ({
    q: f.q,
    a: typeof f.a === "function" ? f.a(leaders) : f.a,
  }));
  const h1 = withYear(def.h1);
  const [first, second, third] = leaders.top;

  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: h1,
    description: def.description,
    dateModified: now.toISOString(),
    numberOfItems: Math.min(ranked.length, 25),
    itemListElement: ranked.slice(0, 25).map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `https://agenttape.com/agents/${c.agent.slug}`,
      name: c.agent.name,
    })),
  };

  return (
    <article className="container py-10 md:py-14 max-w-5xl space-y-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <BackLink href="/" label="Floor" className="-mb-2" />

      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Top · {detail.name}
        </div>
        <h1 className="editorial mt-3 text-4xl font-semibold leading-tight md:text-6xl md:leading-[1.05]">
          {h1}
        </h1>
        {/* Live, self-contained answer naming the current leaders,
            recomputed on every ISR refresh. No date: the page is the
            live source, not a snapshot. */}
        {first && (
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-foreground md:text-lg">
            Right now, the top-ranked {def.noun} on AgentTape are{" "}
            <strong className="font-semibold">{first.name}</strong> (AgentScore{" "}
            {first.score})
            {second && (
              <>
                {third ? ", " : " and "}
                <strong className="font-semibold">{second.name}</strong> ({second.score})
              </>
            )}
            {third && (
              <>
                {" "}and <strong className="font-semibold">{third.name}</strong> ({third.score})
              </>
            )}
            .
            {leaders.mover && (
              <>
                {" "}Biggest 24-hour gain:{" "}
                <strong className="font-semibold">{leaders.mover.name}</strong>, up{" "}
                {leaders.mover.delta} points.
              </>
            )}
          </p>
        )}
        <p className="editorial mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground md:text-xl">
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

      {/* The ranked list — the actual content for the page. Five
          numeric-light columns fit on a 320px phone naturally; the
          old min-w-[640px] forced horizontal scroll for no benefit. */}
      <section className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full text-sm">
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
            {ranked.length === 0 && (
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
            {ranked.slice(0, 25).map((c, i) => (
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

      {/* FAQ: answers the questions people ask search engines and AI
          assistants. Mirrored in FAQPage JSON-LD above. */}
      <section>
        <h2 className="editorial text-2xl font-semibold leading-tight md:text-3xl">
          Common questions
        </h2>
        {/* Collapsed by default so the ranking stays the focus; the
            questions scan quickly and answers open on demand. Search
            engines still index the collapsed text. */}
        <div className="mt-4 divide-y divide-border rounded-md border border-border bg-card">
          {faqs.map((f, i) => (
            <details key={i} className="group px-4 py-3" open={i === 0}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-foreground [&::-webkit-details-marker]:hidden">
                {f.q}
                <span
                  aria-hidden
                  className="shrink-0 text-muted-foreground transition-transform group-open:rotate-45"
                >
                  +
                </span>
              </summary>
              <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground md:text-base">
                {linkify(f.a)}
              </p>
            </details>
          ))}
        </div>
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
