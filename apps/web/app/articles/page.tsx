import Link from "next/link";
import type { Metadata } from "next";
import { ARTICLES } from "@/lib/articles";

export const metadata: Metadata = {
  title: "Articles — AgentTape",
  description:
    "Long-form analysis of the AI agent and foundation-model landscape. Deep dives, comparisons, and ranked guides.",
  alternates: { canonical: "/articles" },
};

export default function ArticlesIndexPage() {
  return (
    <article className="container py-10 md:py-14 max-w-4xl space-y-10">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Articles
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          Field notes from the floor.
        </h1>
        <p className="editorial mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
          Deep dives and ranked guides written against the same live data
          that drives the indexes. Use them to choose well and stay current.
        </p>
      </header>

      {/* The articles list — newest first. */}
      <ul className="divide-y divide-border rounded-md border border-border bg-card">
        {ARTICLES.map((a) => (
          <li key={a.slug}>
            <Link
              href={`/articles/${a.slug}`}
              className="block px-5 py-5 hover:bg-subtle"
            >
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                {new Date(a.published_at).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
                {a.author && (
                  <>
                    <span className="mx-2 text-muted-foreground/40">·</span>
                    {a.author}
                  </>
                )}
              </div>
              <div className="mt-1 text-lg font-medium leading-snug">
                {a.title}
              </div>
              <p className="mt-1 max-w-prose text-sm text-muted-foreground">
                {a.description}
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {/* Writer's room — these are the prompts to feed Claude.ai when
          drafting an article. They live on-page so you don't have to
          dig them up later. */}
      <section id="prompts" className="rounded-md border border-dashed border-border bg-editorial p-6 md:p-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Writer's room
        </div>
        <h2 className="editorial mt-2 text-2xl font-semibold md:text-3xl">
          Prompts for drafting articles.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Paste one of these into Claude.ai with the agents/indexes
          you want covered. When the draft comes back, paste the body
          into{" "}
          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
            apps/web/lib/articles.ts
          </code>
          .
        </p>
        <div className="mt-6 space-y-6 text-sm">
          {PROMPTS.map((p) => (
            <details
              key={p.title}
              className="rounded-md border border-border bg-background p-4"
            >
              <summary className="cursor-pointer font-medium">
                {p.title}{" "}
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  · {p.target}
                </span>
              </summary>
              <pre className="mt-3 whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-foreground/85">
                {p.prompt}
              </pre>
            </details>
          ))}
        </div>
      </section>
    </article>
  );
}

interface PromptDef {
  title: string;
  target: string; // search-intent label
  prompt: string;
}

// Each prompt should produce a body that pastes directly into
// articles.ts. They share a common voice and constraints — short
// paragraphs, lots of named agents, no marketing speak — so the
// articles read as one publication.
const PROMPTS: PromptDef[] = [
  {
    title: "Best AI coding agents — ranked",
    target: '"best ai coding agents" / "best ai for coding" / "claude code vs cursor"',
    prompt: `You are writing a 1,200-word article for AgentTape titled "The best AI coding agents in 2026 — ranked, live".

Goals
- Rank the top 8 AI agents for software engineering, naming each by its actual product name (Cursor, Claude Code, Aider, Devin, Cline, Continue, Sourcegraph Cody, Replit Agent, etc.).
- Anchor every ranking choice in something verifiable — GitHub stars, SWE-bench scores, public benchmarks, real-world engineering reports.
- Cover trade-offs honestly: which agent is best at refactors, which at greenfield, which at code review, which when you have to keep humans in the loop.
- Recommend a default for three personas: solo indie dev, in-house team at a mid-stage startup, and a dev at a large regulated enterprise.
- End with "How AgentTape's CODE-25 ranks them right now" referencing live numbers; tell readers to open /indexes/code-25 to see the live ranking.

Voice
- Direct and specific. No "in today's fast-moving landscape" filler.
- Short paragraphs (2–4 sentences). No bullet-soup until the trade-off section.
- Cite numbers with units ("8.3% lift on SWE-bench Verified" not "much better").
- No emojis.

Format the output exactly so it can be pasted into the AgentTape articles.ts body field:
- Use blank lines between paragraphs.
- Use "## " for H2 section headings.
- Use "- " for bullet lists where appropriate.
- Use "[label](url)" for inline links.
- Use "**bold**" sparingly for product names on first mention.

Keywords to weave in naturally (not stuffed): best ai coding agents, best ai for coding, claude code vs cursor, ai code review tool, ai for refactoring, swe-bench leader.`,
  },
  {
    title: "Best foundation models for agents",
    target: '"best llm for agents" / "claude vs gpt for agents" / "best model for tool use"',
    prompt: `You are writing a 1,000-word article for AgentTape titled "The best foundation models for AI agents in 2026".

Goals
- Rank the top 8 foundation models for *agent workloads* (tool use, long horizon plans, multi-step reasoning) — not for general chat.
- Cover Claude (Anthropic), GPT (OpenAI), Gemini (Google), Llama (Meta), Mistral, Qwen, DeepSeek and one open-weights challenger.
- Each model section: who makes it, the tier you should care about (e.g. Claude Opus 4.7 vs Sonnet 4.6), best-on-X, where it loses, the one number that matters most.
- Compare on three axes the reader actually cares about when they're building: tool-use reliability, long-context recall, cost-per-task at production volume.
- End with "Where to compare them live" pointing to /compare and /indexes/fm-50.

Voice
- Confident, technical, no hedging. If a model is bad at something, say so.
- Short paragraphs. Use "## " for section headings, one per model plus an opener and a "How to choose" closer.
- Cite real benchmarks (SWE-bench, MMLU-Pro, AgentBench, BFCL).
- No emojis.

Format using the same lightweight markdown syntax as the AgentTape articles.ts: blank-line paragraphs, ## H2, ### H3, [label](url), **bold** for first-mention product names.

Keywords to weave in: best llm for agents, claude vs gpt for agents, best foundation model 2026, agentbench leader, swe-bench foundation models.`,
  },
  {
    title: "Open-source alternatives to Devin / Cursor / Claude Code",
    target: '"open source devin" / "self-hosted ai coding agent"',
    prompt: `You are writing a 1,000-word article for AgentTape titled "Open-source alternatives to Devin, Cursor and Claude Code (and when each one wins)".

Goals
- Cover the leading open-source replacements for the named proprietary agents — OpenDevin / OpenHands, Aider, SWE-agent, Continue, Tabby, etc.
- For each, answer: who self-hosts it, which proprietary product it most closely replaces, and where it falls short.
- Spend one section on the *real reasons* readers care about OSS here — vendor lock-in, audit, data residency, cost — and which apply to which audiences.
- Cite license, GitHub stars, and the underlying model each one defaults to.
- End with "Live OSS ranking" pointing to /indexes/oss-50.

Voice
- Pragmatic, not ideological. Don't pretend OSS is always better.
- Short paragraphs, ## H2 per section.
- No emojis.

Format using AgentTape's lightweight markdown (blank-line paragraphs, ## H2, ### H3, "- " bullets, [label](url), **bold**).

Keywords: open source devin, self-hosted ai coding agent, opendevin vs devin, alternatives to cursor.`,
  },
  {
    title: "How to choose an AI agent (a buyer's guide)",
    target: '"how to choose ai agent" / "ai agent buying guide"',
    prompt: `You are writing a 900-word buyer's guide for AgentTape titled "How to actually choose an AI agent in 2026".

Goals
- A practical decision flow for someone evaluating agents. Sections: define the job, pick the substrate, prototype, measure, lock-in.
- Provide concrete checks ("If your team produces >100 PRs/week, your bottleneck isn't autocomplete; it's review").
- Include a clear table of trade-offs (cost vs reliability vs control vs speed-to-prototype).
- Direct readers into the AgentTape product as the *measurement* layer: ## "Use AgentScore as your shortlist" with a sentence on what it does.
- End with a 6-step checklist they can paste into a doc.

Voice
- Editorial, opinionated. Avoid "it depends".
- Short, scannable paragraphs.

Format using AgentTape lightweight markdown. Bullets allowed for the closing checklist only. No emojis.

Keywords: how to choose ai agent, ai agent buying guide, evaluate ai agents, ai agent rfp.`,
  },
];
