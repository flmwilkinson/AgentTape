import Link from "next/link";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";

// SEO landing page. The methodology page is the journalist screenshot;
// this is the page Google sends searchers to. Title + description +
// h1 + h2 are loaded with the queries we want to rank for.
//
// The page is also genuinely useful — it's not a doorway. It explains
// what AgentTape is, links to the surfaces a visitor wants ("top
// coding agents", "compare AI agents", "biggest movers"), and shows
// the live top stocks so the page is fresh on every Google recrawl.

export const metadata: Metadata = {
  title:
    "AgentTape: Top AI Agents Tracked Live. Score, Rank, Compare.",
  description:
    "A live index of every public AI agent and foundation model. Compare the best AI agents for coding or browsing. Free to read, scored by an open formula.",
  keywords: [
    "top AI agents",
    "best AI agents",
    "AI agent comparison",
    "AI agent leaderboard",
    "best foundation models",
    "compare GPT vs Claude",
    "best coding AI agent",
    "best browser AI agent",
    "open source AI agents",
    "MCP servers",
  ],
  alternates: { canonical: "/about" },
  openGraph: {
    title: "AgentTape: top AI agents and foundation models, live.",
    description:
      "A free, transparent index of every public AI agent and foundation model. Built on autonomous discovery. Agents appear here the day they start to matter.",
    images: [{ url: "/api/og/index/tape-100" }],
  },
};

export const dynamic = "force-dynamic";

export default async function AboutPage() {
  // Live top-5 application + foundation-model — keeps the page fresh
  // for crawlers and useful for visitors landing here.
  const [top, indexes] = await Promise.all([
    api.listAgents({ sort: "score", limit: 8 }),
    api.listIndexes(),
  ]);

  // JSON-LD: WebSite + ItemList of top agents. Helps rich snippets.
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "WebSite",
      name: "AgentTape",
      url: "https://agenttape.com",
      description: metadata.description,
      potentialAction: {
        "@type": "SearchAction",
        target: "https://agenttape.com/search?q={search_term_string}",
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      name: "Top AI Agents Today",
      itemListElement: top.items.slice(0, 10).map((a, i) => ({
        "@type": "ListItem",
        position: i + 1,
        item: {
          "@type": "SoftwareApplication",
          name: a.name,
          url: `https://agenttape.com/agents/${a.slug}`,
          applicationCategory: "AIApplication",
          aggregateRating: a.score?.agent_score
            ? {
                "@type": "AggregateRating",
                ratingValue: a.score.agent_score,
                bestRating: 100,
                worstRating: 0,
                ratingCount: 1,
              }
            : undefined,
        },
      })),
    },
  ];

  return (
    <article className="container py-12 md:py-16 max-w-4xl space-y-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          About AgentTape
        </div>
        <h1 className="editorial mt-3 text-4xl font-semibold leading-[1.05] md:text-6xl">
          The live index of every public AI agent.
        </h1>
        <p className="editorial mt-6 max-w-2xl text-xl leading-relaxed text-muted-foreground md:text-2xl">
          Find and compare the best AI agents and foundation models
          as they emerge. Scored by an open formula. Free to read,
          no login needed.
        </p>
      </header>

      <section className="grid gap-8 md:grid-cols-2">
        <Link
          href="/indexes/tape-100"
          className="group rounded-md border border-border bg-card p-6 transition-colors hover:border-foreground/20 hover:bg-subtle"
        >
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            TAPE-100
          </div>
          <h2 className="editorial mt-2 text-2xl font-semibold leading-tight">
            The 100 best AI agents, ranked.
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Top 100 application agents by AgentScore. Auto-rebalanced
            weekly. Sortable by movement, filterable by capability.
          </p>
          <p className="mt-3 text-xs text-primary">Open the index →</p>
        </Link>
        <Link
          href="/indexes/fm-50"
          className="group rounded-md border border-border bg-card p-6 transition-colors hover:border-foreground/20 hover:bg-subtle"
        >
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            FM-50
          </div>
          <h2 className="editorial mt-2 text-2xl font-semibold leading-tight">
            The 50 best foundation models.
          </h2>
          <p className="mt-3 text-sm text-muted-foreground">
            Claude, GPT, Llama, Gemini, Mistral, DeepSeek and more,
            tracked as their own asset class. Compare GPT vs Claude
            directly with an overlaid chart.
          </p>
          <p className="mt-3 text-xs text-primary">Open the model board →</p>
        </Link>
      </section>

      <section>
        <h2 className="editorial text-3xl font-semibold leading-tight md:text-4xl">
          What is AgentTape?
        </h2>
        <div className="prose prose-zinc mt-4 max-w-none editorial space-y-4 text-base leading-relaxed text-foreground/90 md:text-lg">
          <p>
            AgentTape is a live, autonomously-populated index of every
            public AI agent. Each agent is its own stock ticker with a
            transparent 0-100 AgentScore, four pillar scores (Adoption,
            Quality, Momentum, Community), and a chart of how it has
            moved over time. Click any agent to see why its score is
            what it is. Every input is published.
          </p>
          <p>
            We do not curate. The discovery service watches{" "}
            <strong>GitHub</strong>, <strong>Hugging Face</strong>,{" "}
            <strong>MCP registries</strong>, <strong>npm</strong> and{" "}
            <strong>PyPI</strong>, <strong>arXiv</strong>, and{" "}
            <strong>Hacker News</strong>, plus the{" "}
            <strong>OpenRouter</strong> model catalogue, then admits
            agents on its own schedule. If a project starts gaining
            real traction, it shows up here without anyone asking.
          </p>
        </div>
      </section>

      <section>
        <h2 className="editorial text-3xl font-semibold leading-tight md:text-4xl">
          What can I use this for?
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <UseCase
            title="Pick the best AI agent for my use case"
            href="/search"
            body="Filter by capability (code generation, browsing, research, RAG, multi-agent) and see the top stocks ranked by AgentScore. Then drop the top 2-4 onto the comparison page and decide."
          />
          <UseCase
            title="Compare two foundation models"
            href="/compare"
            body="Stick Claude and GPT side-by-side on the compare page. You get an overlay chart of their AgentScore over 30 days, pillar bars next to each other, plus a clean 'best at X' verdict per model."
          />
          <UseCase
            title="See which agents are gaining traction"
            href="/trending"
            body="Trending shows the biggest score moves over 1h / 24h / 7d / 30d, split by application agents vs foundation models. Rank-movement arrows show who climbed and how far."
          />
          <UseCase
            title="Track newly-released agents and models"
            href="/new"
            body="The discovery feed surfaces new admissions in real time, the day they're noticed by GitHub, npm, Hugging Face or OpenRouter. Catch the next AutoGPT before everyone else has heard of it."
          />
        </div>
      </section>

      <section>
        <h2 className="editorial text-3xl font-semibold leading-tight md:text-4xl">
          Today's top stocks
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Live snapshot. Refreshes whenever the page is recrawled.
        </p>
        <ul className="mt-4 divide-y divide-border rounded-md border border-border bg-card">
          {top.items.slice(0, 8).map((a, i) => (
            <li
              key={a.slug}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3"
            >
              <span className="num text-sm text-muted-foreground">{i + 1}</span>
              <Link
                href={`/agents/${a.slug}`}
                className="min-w-0 truncate text-sm font-medium hover:text-primary"
              >
                {a.name}
                <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {a.entity_kind === "foundation_model" ? "model" : "agent"}
                </span>
              </Link>
              <span className="num text-sm font-semibold">
                {a.score?.agent_score?.toFixed(1) ?? "—"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="editorial text-3xl font-semibold leading-tight md:text-4xl">
          How the AgentScore works
        </h2>
        <div className="prose prose-zinc mt-4 max-w-none editorial space-y-4 text-base leading-relaxed text-foreground/90 md:text-lg">
          <p>
            A 0-100 headline backed by four pillars. The weights below
            are the defaults and they sum to 1.0. The headline is a
            flat weighted sum: a pillar with no signals contributes
            zero, no redistribution. That's deliberate — more
            evidence has to mean a higher score. An agent with only
            Adoption tops out at 35; only the broadly-covered ones
            reach the high 60s and 70s.
          </p>
          <ul className="list-disc pl-6">
            <li>
              <strong>Adoption (35%)</strong>: z-score across stars,
              downloads, package counts, registry presence
            </li>
            <li>
              <strong>Quality (30%)</strong>: mean z-score across
              benchmark results. <em>Unrated</em> when no benchmark
              exists, never zero
            </li>
            <li>
              <strong>Momentum (20%)</strong>: 7-day and 30-day
              rate-of-change blend on adoption signals
            </li>
            <li>
              <strong>Community (15%)</strong>: contributors, HN
              points, Reddit points
            </li>
          </ul>
          <p>
            Manipulation rules (star spike without contributor diversity,
            HF download surge without matching GitHub activity, coordinated
            HN posting) exclude implicated signals from that day's score.
            Read the full{" "}
            <Link
              href="/methodology"
              className="text-primary underline-offset-2 hover:underline"
            >
              methodology
            </Link>
            .
          </p>
        </div>
      </section>

      <section>
        <h2 className="editorial text-3xl font-semibold leading-tight md:text-4xl">
          Browse by category
        </h2>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {indexes.map((i) => (
            <li key={i.slug}>
              <Link
                href={`/indexes/${i.slug}`}
                className="flex items-center justify-between rounded-md border border-border bg-card px-4 py-2 text-sm hover:bg-subtle"
              >
                <span>
                  <span className="font-medium">{i.name}</span>{" "}
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {i.members_count} members
                  </span>
                </span>
                <span className="num text-muted-foreground">
                  {i.composite_value?.toFixed(1) ?? "—"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <hr className="border-border" />
      <p className="text-xs text-muted-foreground">
        AgentTape is open source and built in public. Read the{" "}
        <Link href="/methodology" className="text-primary hover:underline">
          methodology
        </Link>{" "}
        for the math, or the{" "}
        <a
          href="https://github.com/flmwilkinson/AgentTape"
          className="text-primary hover:underline"
        >
          repo
        </a>{" "}
        for the source. No login. No paywall. No newsletter wall.
      </p>
    </article>
  );
}

function UseCase({
  title,
  body,
  href,
}: {
  title: string;
  body: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-md border border-border bg-card p-5 transition-colors hover:border-foreground/20 hover:bg-subtle"
    >
      <h3 className="font-medium leading-snug group-hover:text-primary">
        {title}
      </h3>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
    </Link>
  );
}
