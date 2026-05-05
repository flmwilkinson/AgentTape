import type { ReactNode } from "react";
import {
  AxesGrid,
  Badges,
  ChecklistBox,
  ChooseGrid,
  Closer,
  CTAButtonRow,
  CTAPanel,
  H2,
  Lede,
  ModelCard,
  PersonaCards,
  ProductHeading,
  Prose,
  PullQuote,
  QuadGrid,
  ScoreBars,
  Section,
  SectionContent,
  SectionDivider,
  SpecCard,
  StatGrid,
  StepHeader,
  TickerTable,
  TradeoffTable,
} from "@/components/article-blocks";
import { LiveIndexSnapshot } from "@/components/live-index-snapshot";

// Articles registry.
//
// Every article follows the same structural scaffold so the
// publication reads like one publication, not four:
//   1. <Lede>            opener with drop cap
//   2. summary visual    StatGrid / AxesGrid / ScoreBars / TickerTable
//   3. body              varies — product cards, ranked entries, steps
//   4. <PullQuote>       one mid-article breath
//   5. wrap-up           H2 + ChooseGrid / PersonaCards / Closer
//   6. CTA               CTAPanel or CTAButtonRow
//
// Prose discipline: vary sentence length, avoid em-dash overload, keep
// real opinions framed as opinions, drop performative-honesty markers.

export interface ArticleMeta {
  slug: string;
  title: string;
  description: string;
  published_at: string;
  author?: string;
  keywords: string[];
}

export interface Article extends ArticleMeta {
  body: ReactNode;
}

// ----------------------------------------------------------- article 1

const codingAgents2026: Article = {
  slug: "best-ai-coding-agents-2026",
  title: "The best AI coding agents in 2026 — ranked, live",
  description:
    "Eight tools, four trade-offs, and one honest admission: no single agent wins every job. Ranked from real benchmarks and merge rates as of May 2026.",
  published_at: "2026-05-05",
  keywords: [
    "best ai coding agents",
    "ai code generation tools",
    "claude code vs cursor",
    "best ai for coding",
    "swe-bench leader",
  ],
  body: (
    <>
      <Lede>
        The benchmark question moves quickly. Claude Opus 4.7 leads SWE-bench
        Verified at 87.6%, and the unreleased Mythos Preview is closer to 94.
        That is the floor of what these tools can do, not the ceiling. The
        same model drops thirty points on SWE-bench Pro, which Scale AI
        rebuilds every month to keep the test set fresh.
      </Lede>

      <StatGrid
        items={[
          { label: "SWE-Bench Leader", name: "Claude Opus 4.7", detail: "87.6% Verified" },
          { label: "Highest ARR", name: "Cursor", detail: "$1.2B · 1M+ DAU" },
          { label: "OSS Star Leader", name: "Cline", detail: "61.3k ★ · 5M+ installs" },
          { label: "Async Workhorse", name: "Devin", detail: "67% PR merge rate" },
        ]}
      />

      <Prose>
        <p>
          So the ranking below weighs four things, not one: Verified scores,
          Pro scores, real-world PR merge rates, and how much the surrounding
          scaffolding lifts or drags the underlying model. In February three
          frameworks pointing at the same Anthropic model finished 17 issues
          apart on the same 731-task evaluation. The wrapper does work.
        </p>
      </Prose>

      <ProductHeading rank={1} name="Claude Code" />
      <Badges
        items={[
          "Anthropic",
          "Terminal",
          { label: "SWE-Verified 80.8%", tone: "gain" },
          "Pro $20 · Max $100/$200",
        ]}
      />
      <Prose>
        <p>
          Top of the list on raw capability. Opus 4.6 underneath; 80.8% on
          Verified; 200K standard context with a 1M-token beta for the largest
          refactors. The number that surprised me most: identical-task runs
          show Claude Code using 33K tokens where Cursor uses 188K. Five and a
          half times fewer.
        </p>
        <p>
          The downside is the bill. Heavy daily use lands at $150–200/month on
          the Max plan, and the rate limit still bites at that tier. The
          pattern that keeps showing up on r/ClaudeCode: Cursor for daily
          flow, Claude Code for the problems Cursor cannot finish. Run them
          together rather than choose.
        </p>
      </Prose>

      <ProductHeading rank={2} name="Cursor" />
      <Badges
        items={[
          "Anysphere",
          "IDE",
          { label: "SWE-Verified 67.2%", tone: "gain" },
          "$20 / $60 / $200",
        ]}
      />
      <Prose>
        <p>
          Cursor sits where you actually work. $1.2B ARR, north of a million
          daily users, Composer for multi-file edits, and the Supermaven Tab
          completion model still under 100ms. The agent itself scores 67.2%
          on Verified. The IDE polish is what people pay for, not the agent.
        </p>
        <p>
          The June 2025 switch to credit-based billing damaged trust that
          Cursor has not yet rebuilt. Pro+ at $60 and Ultra at $200 still
          read as opaque to anyone tracking actual usage. Keep an eye on the
          token meter and you'll be fine.
        </p>
      </Prose>

      <ProductHeading rank={3} name="OpenAI Codex" />
      <Badges
        items={[
          "OpenAI",
          "CLI + Cloud",
          { label: "SWE-Pro 56.8%", tone: "gain" },
          "62k ★ · ChatGPT $20/$200",
        ]}
      />
      <Prose>
        <p>
          The unexpected comeback story. GPT-5.3-Codex is at 77.3% on
          Terminal-Bench 2.0 and leads SWE-bench Pro at 56.8%; the Spark
          variant runs on Cerebras WSE-3 silicon at over a thousand tokens a
          second. The cloud-task-runner pattern is the part that's new: write
          a spec, get back a sandboxed PR an hour later.
        </p>
        <p>
          A year ago Codex did not exist. Today it has roughly 60% of Cursor's
          install base. The Rust CLI is open source under Apache-2.0, sitting
          at 62k stars. Pricing rides the ChatGPT Plus or Pro message budget
          rather than charging per call.
        </p>
      </Prose>

      <ScoreBars
        caption="SWE-Bench Verified · Top 5 (May 1, 2026)"
        rows={[
          { label: "Claude Mythos Preview", value: 93.9 },
          { label: "Claude Opus 4.7", value: 87.6 },
          { label: "GPT-5.3-Codex", value: 85.0 },
          { label: "Claude Opus 4.5", value: 80.9 },
          { label: "Claude Opus 4.6", value: 80.8 },
        ]}
        source="Source: BenchLM / llm-stats live leaderboard. The same models drop 30–35 points on SWE-bench Pro."
      />

      <ProductHeading rank={4} name="Devin" />
      <Badges
        items={[
          "Cognition",
          "Async cloud",
          { label: "67% merge rate", tone: "gain" },
          "$20 + $2.25/ACU",
        ]}
      />
      <Prose>
        <p>
          The most autonomous tool here, on its best days. Cognition reports
          a 67% PR merge rate on well-defined tasks, and Goldman Sachs is
          running Devin across its 12,000-engineer programming team with
          claimed 3–4× productivity. Treat the productivity number with
          caution; the merge rate is the one I trust more.
        </p>
        <p>
          The pricing dropped from $500/month to a $20 base plus $2.25 per
          Agent Compute Unit, which makes Devin a tool you can experiment
          with before committing. Bug backlogs, schema migrations, and
          repetitive feature work are where it shines. Open-ended product
          design is where it still loses.
        </p>
      </Prose>

      <PullQuote>
        Three different agents pointing at the same Anthropic model finished
        17 issues apart on the same 731-task evaluation. Architecture is
        doing real work.
      </PullQuote>

      <ProductHeading rank={5} name="Cline" />
      <Badges
        items={[
          "Apache-2.0",
          "VS Code extension",
          { label: "61.3k ★ · 5M installs", tone: "gain" },
          "BYOK · 30+ providers",
        ]}
      />
      <Prose>
        <p>
          Cline is the open-source headline at 61.3k stars and 5M installs,
          with bring-your-own-model across more than 30 providers. The
          Plan/Act split is the cleanest oversight pattern in the category:
          Plan reads files and reasons about them, Act is what touches disk.
          You approve the boundary.
        </p>
        <p>
          You pay only for tokens, which puts a typical feature at
          $0.50–$2.00 against Sonnet 4.7. The April 2026 spend-limit UI is
          the small change that mattered most: agents quietly draining your
          account in a runaway loop is no longer a failure mode you have to
          worry about.
        </p>
      </Prose>

      <ProductHeading rank={6} name="Aider" />
      <Badges
        items={[
          "Apache-2.0",
          "Terminal · git-native",
          { label: "40k+ ★", tone: "gain" },
          "100+ languages · BYOK",
        ]}
      />
      <Prose>
        <p>
          Forty-plus thousand stars and several model cycles of survival
          gives Aider an unusual property: every change becomes a real git
          commit you can read or revert. Repo map via tree-sitter scales to
          large codebases. The interface is a terminal prompt and your diff.
        </p>
        <p>
          For unfamiliar repos and refactors that need to be reviewable
          afterwards, this is the safest tool in the list. It is also the
          dullest one to demo, which is part of why it works.
        </p>
      </Prose>

      <ProductHeading rank={7} name="Sourcegraph Amp" />
      <Badges
        items={[
          "Sourcegraph",
          "Enterprise",
          { label: "SOC 2 · ISO 27001", tone: "gain" },
          "$59/user/mo",
        ]}
      />
      <Prose>
        <p>
          Cody Free and Cody Pro retired in July 2025; Cody Enterprise
          continues at $59 per user per month. Amp is the agentic successor,
          shipping in terminal, VS Code, Cursor, JetBrains and Neovim, with
          indexing across 300,000+ repositories under SOC 2 Type II and ISO
          27001:2022.
        </p>
        <p>
          If procurement requires audit trails and your codebase is
          measured in hundreds of microservices, this is the only tool here
          built for that scale. Smaller teams will find the price hard to
          justify.
        </p>
      </Prose>

      <ProductHeading rank={8} name="Replit Agent 3" />
      <Badges
        items={[
          "Replit",
          "Browser · full-stack",
          { label: "200-min sessions", tone: "gain" },
          "$25 Core · $100 Pro",
        ]}
      />
      <Prose>
        <p>
          Replit raised $250M at a $3B valuation in January, and Agent 3 is
          the reason. Two-hundred-minute autonomous sessions, database
          provisioning, full-stack scaffolding with auth, and a public URL
          one click after the model finishes. For getting something in front
          of a stakeholder before lunch, nothing else is close.
        </p>
        <p>
          For regulated production code on an existing codebase: the wrong
          tool. That is fine. Replit is not pretending otherwise.
        </p>
      </Prose>

      <H2>Trade-offs by job</H2>
      <TradeoffTable
        rows={[
          { job: "Greenfield apps", pick: "Replit Agent 3", why: "Browser-first, deploys in one click." },
          { job: "Multi-file refactors", pick: "Claude Code", why: "Long context wins; 5.5× fewer tokens than Cursor on identical work." },
          { job: "AI code review", pick: "Augment Code · Continue", why: "70% win rate against Copilot in head-to-head; CI checks defined as code." },
          { job: "Human-in-the-loop", pick: "Cline · Aider", why: "Plan/Act split or per-commit diffs make every step inspectable." },
          { job: "Async delegation", pick: "Devin", why: "End-state-only review for issues with verifiable success criteria." },
        ]}
      />

      <H2>What to default to, by team shape</H2>
      <PersonaCards
        items={[
          {
            audience: "Solo indie dev",
            pick: "Cursor + Claude Code",
            body: "Forty dollars before usage. Cursor for the editor, Claude Code for the hard problems Cursor can't finish.",
          },
          {
            audience: "Mid-stage startup",
            pick: "Cursor + Claude Code + Devin Core",
            body: "Two interactive agents and one async. Wire Devin into Linear or Jira and let the bug backlog work itself down overnight.",
          },
          {
            audience: "Regulated enterprise",
            pick: "Sourcegraph Amp + Devin Enterprise",
            body: "Audit posture and codebase indexing as defaults. Add Devin where async ROI is clearly verifiable.",
          },
        ]}
      />

      <H2>How CODE-25 ranks them right now</H2>
      <Prose>
        <p>
          The list above is a snapshot of how the editors stack up. CODE-25
          is the moving picture: the top 25 admitted agents carrying a{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[12px]">
            code-generation
          </code>{" "}
          tag — the underlying engines that builders point harnesses at,
          not the editors wrapping them. Equal-weight v1, rebalances Mondays
          at 03:00 UTC. The numbers below come live from the index right now.
        </p>
      </Prose>

      <LiveIndexSnapshot
        index_slug="code-25"
        caption="CODE-25 · Composite"
        limit={6}
      />

      <Closer>
        The ranking above tells you what to install on Monday. CODE-25 tells
        you what's moving by Friday. Both are useful; neither is the whole
        answer.
      </Closer>

      <CTAPanel
        tag="Live Index"
        title={<>The CODE-25, <em>tracked daily</em></>}
        body="Stars, benchmarks, mentions and merge rates all shift week to week. The CODE-25 index is the live tape: which coding engine is gaining momentum on AgentTape this week, which has stalled, and which just entered the basket on Monday's rebalance."
        href="/indexes/code-25"
        cta_label="View the CODE-25"
      />
    </>
  ),
};

// ----------------------------------------------------------- article 2

const fmRanking: Article = {
  slug: "best-foundation-models-for-ai-agents-2026",
  title: "The best foundation models for AI agents in 2026",
  description:
    "Eight foundation models that ship agent workloads in production, ranked on tool-use reliability, long-context recall, and cost-per-task at volume.",
  published_at: "2026-05-05",
  keywords: [
    "best llm for agents",
    "claude vs gpt for agents",
    "best foundation model 2026",
    "agentbench leader",
    "swe-bench foundation models",
  ],
  body: (
    <>
      <Lede>
        Picking a model for an agent is not the same task as picking a model
        for chat. Agents fail on three axes humans don't notice: brittle tool
        calls, context that quietly rots after eighty thousand tokens, and a
        per-task cost line that explodes when you scale to ten million runs.
        Pick on those three, not on the demo.
      </Lede>

      <AxesGrid
        items={[
          {
            label: "Tool-use reliability",
            body: "BFCL v4 plus stability across multi-turn loops once the model has been on a task an hour.",
          },
          {
            label: "Long-context recall",
            body: "Effective recall past 200K tokens. Window size on the spec sheet is a different number.",
          },
          {
            label: "Cost per successful task",
            body: "Blended price per million I/O tokens, multiplied by how many turns you actually need to ship.",
          },
        ]}
      />

      <Prose>
        <p>
          What follows is a ranking of the eight models that actually run
          agent workloads in production today, ordered against those three
          axes. Numbers come from public leaderboards; vendor self-reports
          aren't quoted here.
        </p>
      </Prose>

      <SectionDivider number="I" label="Closed-source frontier" />

      <ModelCard
        rank={1}
        name="Claude Opus 4.7"
        maker="Anthropic"
        badge="Top pick"
        tag={
          <>
            Opus 4.7 has led every public agent harness benchmark since
            February. Long-horizon plans, recoverable tool failures, code
            edits across many files — it stays coherent where the others
            drift. Pair it with Sonnet 4.6 for the routine 80% of steps and
            you get most of the quality at a fraction of the cost.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Multi-hour agent runs that have to recover from their own mistakes.",
          },
          {
            label: "Where it loses",
            body: "Twice the price of GPT-5.4 at $5/$25 per million. 200K context, not 1M.",
          },
        ]}
        stat={{ label: "SWE-bench Verified", value: "87.6%" }}
      />

      <ModelCard
        rank={2}
        name="GPT-5.4 / GPT-5.3 Codex"
        maker="OpenAI"
        tag={
          <>
            The price-performance frontier. GPT-5.4 at $2.50/$15 sits at
            roughly half Opus pricing for most tasks; GPT-5.3 Codex hits 85%
            on SWE-bench Verified. The function-calling schema is still the
            cleanest in the industry — every agent framework targets it
            first.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Single-turn tool calls, broad framework support, sensible cost-quality default.",
          },
          {
            label: "Where it loses",
            body: "Drifts more than Claude past ~50 sequential tool calls. 270K context cap.",
          },
        ]}
        stat={{ label: "SWE-bench Verified · Codex", value: "85%" }}
      />

      <ModelCard
        rank={3}
        name="Gemini 3.1 Pro"
        maker="Google"
        tag={
          <>
            Two million tokens of usable context, the largest production
            window any Tier-1 lab is shipping. The 90% cache discount on
            repeated prompts makes it the cheapest flagship in the field for
            RAG-heavy workloads. Strong on multimodal, AgentBench-leading on
            long-context tasks specifically.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "RAG over codebases, hour-long video, document corpora that don't fit anywhere else.",
          },
          {
            label: "Where it loses",
            body: "SWE-bench around 78% trails Claude and GPT. The function-calling has more sharp edges.",
          },
        ]}
        stat={{ label: "Context window", value: "2,000,000 tokens" }}
      />

      <ModelCard
        rank={4}
        name="Kimi K2.6"
        maker="Moonshot AI · open weights"
        tag={
          <>
            The open-weights challenger you can self-host on serious
            hardware. Trillion-parameter MoE with 32B active, trained with
            PARL to coordinate up to 1,500 tool calls across self-spawned
            sub-agents. There are documented thirteen-hour multi-tool runs
            without context collapse, which is the part that earns it this
            rank.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Parallel agent swarms, polyglot codebases, frontier capability you control.",
          },
          {
            label: "Where it loses",
            body: "BFCL v4 trails closed labs by 4–6 points. Vision is below Gemini.",
          },
        ]}
        stat={{ label: "Parallel tool calls per session", value: "1,500" }}
      />

      <PullQuote>
        Window size on the spec sheet is one number. Effective recall past
        200K tokens is a different number, and it's the one that actually
        matters.
      </PullQuote>

      <SectionDivider number="II" label="Open-weight challengers" />

      <ModelCard
        rank={5}
        name="DeepSeek V4"
        maker="DeepSeek · open weights"
        tag={
          <>
            On a per-token basis, the cheapest frontier-class model on the
            market. 80.6% on SWE-bench Verified, one million tokens of
            context, around a trillion parameters. The reasoning-per-dollar
            number is unmatched.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Dense math and science work where the bottleneck is raw reasoning, not tool ergonomics.",
          },
          {
            label: "Where it loses",
            body: "Self-hosting needs serious GPU. Hosted latency is 2–3× Claude on short tool loops.",
          },
        ]}
        stat={{ label: "MMLU-Pro", value: "92.8%" }}
      />

      <ModelCard
        rank={6}
        name="Qwen 3.6 Plus"
        maker="Alibaba · open weights"
        tag={
          <>
            The multilingual default. Qwen 3.6 ships a one-million-token
            context as actual open weights, dominates Chinese-language
            coding, and Apache 2.0 covers the smaller variants. The flagship
            sits under Tongyi Qianwen rather than Apache, which matters if
            you need to fine-tune.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Multilingual agents, long-context open-weights work, broad ecosystem fit.",
          },
          {
            label: "Where it loses",
            body: "English reasoning trails DeepSeek V4. Flagship licensing is non-Apache.",
          },
        ]}
        stat={{ label: "SWE-bench Verified", value: "73–77%" }}
      />

      <ModelCard
        rank={7}
        name="Llama 4 Maverick"
        maker="Meta · open weights"
        tag={
          <>
            Pick this one when fine-tuning rights and ecosystem maturity
            outrank peak capability. Every framework targets Llama first,
            every cloud has a Llama endpoint, every fine-tuning library
            assumes it. On agent benchmarks specifically, Kimi K2.6 and
            DeepSeek V4 have moved past it.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Enterprise fine-tuning, broad tooling support, the most permissive license here.",
          },
          {
            label: "Where it loses",
            body: "No longer the strongest open model on agent benchmarks.",
          },
        ]}
        stat={{ label: "LiveCodeBench", value: "43.4%" }}
      />

      <ModelCard
        rank={8}
        name="Mistral Medium 3.5"
        maker="Mistral · open weights"
        tag={
          <>
            77.6% on SWE-bench Verified from a 128B dense model — efficient,
            Apache 2.0, and the only frontier-tier lab outside the US/China
            duopoly. If EU data sovereignty matters to your buyer, this is
            the answer that matters most.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "EU data sovereignty, dense efficiency, Apache fine-tuning.",
          },
          {
            label: "Where it loses",
            body: "BFCL v4 below Qwen and the closed labs. Long-context past 128K is unreliable.",
          },
        ]}
        stat={{ label: "SWE-bench Verified", value: "77.6%" }}
      />

      <H2>How to choose</H2>
      <ChooseGrid
        items={[
          {
            heading: "Agents that must work",
            body: "Claude Opus 4.7. Nothing else is close on long-horizon reliability.",
          },
          {
            heading: "Cost-quality default",
            body: "GPT-5.4. The right pick when you aren't bottlenecked on the hardest tasks.",
          },
          {
            heading: "Context is the bottleneck",
            body: "Gemini 3.1 Pro. Two million tokens, 90% cache discount, RAG-friendly pricing.",
          },
          {
            heading: "Self-hosting or budget",
            body: "Kimi K2.6 for orchestration, DeepSeek V4 for reasoning per dollar.",
          },
        ]}
      />

      <Closer>
        The agent stack of 2026 is not a single-model decision. Routing hard
        reasoning to Opus, bulk tool calls to Sonnet 4.6 or GPT-5.4,
        RAG-over-corpus to Gemini, and long-running orchestration to Kimi
        K2.6 leaves something like 30–40% of the wins on the table for teams
        that pick one model and stop.
      </Closer>

      <CTAPanel
        tag="Live Index"
        title={<>The FM-50, <em>tracked daily</em></>}
        body="Foundation models reshuffle every time a new release lands or a benchmark refreshes. The FM-50 is the live tape — context windows, pricing, modality, and Open LLM Leaderboard scores ranked into one composite that moves with the field."
        href="/indexes/fm-50"
        cta_label="View the FM-50"
      />
    </>
  ),
};

// ----------------------------------------------------------- article 3

const ossAlternatives: Article = {
  slug: "open-source-alternatives-devin-cursor-claude-code",
  title: "Open-source alternatives to Devin, Cursor and Claude Code",
  description:
    "An honest map of the leading self-hosted AI coding agents. Who runs each one, which proprietary product it actually replaces, and where it falls short.",
  published_at: "2026-05-05",
  keywords: [
    "open source devin",
    "self-hosted ai coding agent",
    "opendevin vs devin",
    "alternatives to cursor",
    "open source claude code",
  ],
  body: (
    <>
      <Lede>
        Devin still bills per seat. Cursor changes its pricing every quarter.
        Claude Code lives entirely inside one vendor's API. None of that is
        a problem until your CFO, your compliance team, or an air-gapped
        environment makes it one. By 2026 the open-source stack is mature
        enough that "self-hosted" stopped being a downgrade.
      </Lede>

      <TickerTable
        caption="Live · OSS coding agents"
        asof="Stars as of 05 May 2026"
        rows={[
          { symbol: "OPENHANDS", stars: "72.6K", license: "MIT", default_model: "BYO via LiteLLM", replaces: "Devin", trend: "up" },
          { symbol: "CLINE", stars: "~58K", license: "Apache 2.0", default_model: "BYO key", replaces: "Cursor agent", trend: "up" },
          { symbol: "AIDER", stars: "~41K", license: "Apache 2.0", default_model: "Claude / DeepSeek / GPT", replaces: "Claude Code", trend: "up" },
          { symbol: "TABBY", stars: "~33K", license: "Apache 2.0", default_model: "Qwen2.5-Coder / StarCoder", replaces: "Copilot (self-hosted)", trend: "up" },
          { symbol: "CONTINUE", stars: "~31K", license: "Apache 2.0", default_model: "BYO key", replaces: "Cursor in-IDE", trend: "up" },
          { symbol: "SWE-AGENT", stars: "research", license: "MIT", default_model: "Claude / GPT (any)", replaces: "Devin (headless)" },
        ]}
      />

      <Prose>
        <p>
          What follows is the map. Five tools, one section each, with the
          part most reviews skip: where each one falls short of the closed
          equivalent it claims to replace.
        </p>
      </Prose>

      <SectionDivider number="01" label="Autonomous agent" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            OpenHands
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Formerly OpenDevin · All-Hands-AI
          </div>
          <p>
            The All-Hands-AI team rebranded the OpenDevin project last year
            and the main repo now sits at 72,607 stars under MIT. The
            architecture is straightforward: an autonomous agent that plans,
            edits, runs tests, browses the web and opens PRs from inside a
            sandboxed Docker container.
          </p>
          <p>
            On its hosted free tier it defaults to a Minimax model, but the
            published numbers people actually quote come from Claude Sonnet
            4.5, which sits at roughly 77% on SWE-Bench Verified.
          </p>
          <p>
            <strong>Who self-hosts it.</strong> Teams with hard data
            residency rules; engineers who want to read the agent's own
            source; anyone allergic to per-seat pricing.
          </p>
          <p>
            <strong>Where it falls short.</strong> The setup is real DevOps
            work, not a docker run. A single SWE-bench-style fix runs
            $0.50–$3 against a frontier model, so you trade a vendor bill
            for an inference bill.
          </p>
        </SectionContent>
        <SpecCard
          title="OpenHands"
          badge="OSS"
          rows={[
            { key: "Stars", value: "72.6K", big: true },
            { key: "License", value: "MIT" },
            { key: "Default", value: "Any LiteLLM" },
            { key: "Replaces", value: "Devin" },
            { key: "Falls short", value: "DevOps lift" },
          ]}
        />
      </Section>

      <SectionDivider number="02" label="Terminal pair programmer" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            Aider
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Apache 2.0 · ~41K stars · 5.3M+ PyPI installs
          </div>
          <p>
            Aider is a terminal pair programmer that edits your local git
            repo and auto-commits each change. The repo map is built on
            tree-sitter, the diffs are surgical, and every edit becomes a
            real git commit you can review or revert.
          </p>
          <p>
            It handles Claude 3.7 Sonnet, DeepSeek R1 and Chat V3, OpenAI's
            o-series and GPT-4o cleanly, and connects to almost anything
            else via LiteLLM. Local models work too if you don't mind the
            latency.
          </p>
          <p>
            <strong>Where it falls short.</strong> Aider only edits files.
            It cannot run commands, install packages, or execute tests. For
            a fire-and-forget loop you need OpenHands. For a precise tool
            that respects your git history, this is hard to beat.
          </p>
        </SectionContent>
        <SpecCard
          title="Aider"
          badge="CLI · GIT"
          rows={[
            { key: "Stars", value: "~41K", big: true },
            { key: "License", value: "Apache 2.0" },
            { key: "Default", value: "Sonnet / DeepSeek" },
            { key: "Replaces", value: "Claude Code" },
            { key: "Falls short", value: "No shell exec" },
          ]}
        />
      </Section>

      <SectionDivider number="03" label="Research-grade fixer" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            SWE-agent
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Princeton + Stanford · MIT · NeurIPS 2024
          </div>
          <p>
            SWE-agent is the academic project that put open source on the
            SWE-bench leaderboard, with everything configured in a single
            YAML file. The smaller mini-SWE-agent variant scores above 74%
            on Verified in roughly a hundred lines of Python, which is the
            kind of result that gets people to read the codebase.
          </p>
          <p>
            Default model is bring-your-own. Claude Sonnet, GPT, anything
            LiteLLM speaks.
          </p>
          <p>
            <strong>Best for.</strong> Running headless on a queue of GitHub
            issues, benchmarking, building your own agent on top of a clean
            baseline.
          </p>
          <p>
            <strong>Weak for.</strong> Day-to-day "help me with this file"
            coding. There's no chat polish, no IDE plugin, and the
            documentation assumes you'll read the source.
          </p>
        </SectionContent>
        <SpecCard
          title="SWE-agent"
          badge="research"
          rows={[
            { key: "Bench", value: "74%", big: true },
            { key: "License", value: "MIT" },
            { key: "Origin", value: "Princeton / Stanford" },
            { key: "Replaces", value: "Devin (headless)" },
            { key: "Falls short", value: "No daily UX" },
          ]}
        />
      </Section>

      <SectionDivider number="04" label="IDE-native" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            Continue and Cline
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            VS Code &amp; JetBrains extensions · Apache 2.0
          </div>
          <p>
            Cursor's pitch is a VS Code fork with AI baked in. The OSS
            answer is the inverse: keep stock VS Code, add the same
            primitives via extensions.
          </p>
          <p>
            Continue at around 31k stars handles autocomplete and chat
            across VS Code and JetBrains, model-agnostic against Claude,
            GPT-4o, or a local Ollama target. Cline at roughly 58k stars
            (counting its Roo Code and Kilo Code forks) is the agentic
            extension closest in feel to Cursor's agent mode, with edits
            approved step by step rather than running fully autonomous.
          </p>
          <p>
            <strong>Where they fall short.</strong> The editor itself is
            stock VS Code. You don't get Cursor's tab-completion model or
            the same end-to-end latency. If those specific UX wins are why
            you pay Cursor today, no extension matches them.
          </p>
        </SectionContent>
        <SpecCard
          title="Cline / Continue"
          badge="VS Code"
          rows={[
            { key: "Cline ★", value: "~58K", big: true },
            { key: "Continue ★", value: "~31K" },
            { key: "License", value: "Apache 2.0" },
            { key: "Replaces", value: "Cursor" },
            { key: "Falls short", value: "No custom editor" },
          ]}
        />
      </Section>

      <SectionDivider number="05" label="Team server" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            Tabby
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            ~33K stars · Apache 2.0 (open-core) · Docker-native
          </div>
          <p>
            Tabby is the only tool here designed first for an air-gapped
            team server, not a single laptop. It ships as a Docker container
            with admin panel, LDAP auth, per-user API keys, and usage
            analytics built in.
          </p>
          <p>
            Defaults are open-weight coders: StarCoder, Qwen2.5-Coder,
            DeepSeek Coder. A single A100 80GB running Qwen2.5-Coder 32B at
            4-bit quantization serves 15–25 concurrent developers with
            Tabby's request queueing.
          </p>
          <p>
            <strong>Replaces.</strong> GitHub Copilot for completion, plus a
            basic chat panel.
          </p>
          <p>
            <strong>Doesn't replace.</strong> Cursor's agent mode or
            Devin-style autonomy. Tabby is autocomplete plus chat, not an
            engineer.
          </p>
        </SectionContent>
        <SpecCard
          title="Tabby"
          badge="On-prem"
          rows={[
            { key: "Stars", value: "~33K", big: true },
            { key: "License", value: "Apache 2.0" },
            { key: "Default", value: "Qwen2.5-Coder" },
            { key: "Replaces", value: "Copilot" },
            { key: "Falls short", value: "No agent mode" },
          ]}
        />
      </Section>

      <PullQuote>
        Most "open beats closed" pieces collapse four very different
        reasons into one. They are not the same buyer.
      </PullQuote>

      <QuadGrid
        title={<>Why <em>OSS</em>, really</>}
        deck="Match the reason to the audience and the right tool falls out. Run the wrong reason against the right buyer and you'll lose the procurement meeting."
        items={[
          {
            number: "01",
            name: "Vendor lock-in",
            who: "Platform engineering leads · multi-year roadmaps",
            body: "OSS lets you swap the model when prices move. The relevant tools here are model-agnostic by default: Aider, OpenHands, Continue.",
          },
          {
            number: "02",
            name: "Audit and IP",
            who: "Legal teams · security review",
            body: "When you need to prove which code touched a third-party model, OpenHands or Aider give you the paper trail down to the byte. Closed agents cannot.",
          },
          {
            number: "03",
            name: "Data residency",
            who: "EU public sector · healthcare · defense",
            body: "A hard regulatory line. Tabby and self-hosted OpenHands are the only options that satisfy strict on-prem and air-gap requirements.",
          },
          {
            number: "04",
            name: "Cost",
            who: "Engineering finance · 40+ seats",
            body: (
              <>
                A single A100 80GB at $1.04/hour runs $749/month, roughly{" "}
                <strong>39 GitHub Copilot Business seats at $19 each</strong>.
                Below ~40 developers, Copilot is genuinely cheaper.
              </>
            ),
          },
        ]}
      />

      <CTAPanel
        tag="Live Index"
        title={<>The OSS-50, <em>tracked daily</em></>}
        body="Star counts, benchmarks, pricing — all of it shifts week to week. The leaderboard is where you check which open-source agent is gaining momentum on AgentTape this week, and which is quietly losing ground."
        href="/indexes/oss-50"
        cta_label="View the OSS-50"
      />
    </>
  ),
};

// ----------------------------------------------------------- article 4

const buyersGuide: Article = {
  slug: "how-to-choose-ai-agent-2026",
  title: "How to actually choose an AI agent in 2026",
  description:
    "A working decision flow for evaluating agents. Five steps, four trade-offs, one checklist you can paste into your RFP doc.",
  published_at: "2026-05-05",
  keywords: [
    "how to choose ai agent",
    "ai agent buying guide",
    "evaluate ai agents",
    "ai agent rfp",
  ],
  body: (
    <>
      <Lede>
        Most teams pick agents the way they picked SaaS in 2018. A demo, a
        champion, a credit card. That worked when the worst case was a dead
        Slack integration. It does not work when the agent writes production
        code, replies to your customers, or moves money on your behalf.
      </Lede>

      <AxesGrid
        items={[
          {
            label: "Where teams fail",
            body: "Picking by demo, not by data. The shortest path to a wrong choice.",
          },
          {
            label: "Where teams should focus",
            body: "Cost-per-success, reliability, control, speed-to-prototype. Pick two.",
          },
          {
            label: "What this guide is",
            body: "A five-step sequence. Skip a step and pay for it in the next one.",
          },
        ]}
      />

      <Prose>
        <p>
          Use what follows as a sequence rather than a checklist. The order
          matters: each step makes the next one cheaper.
        </p>
      </Prose>

      <StepHeader number="01" eyebrow="Step One" title="Define the job, not the agent" />
      <Prose>
        <p>
          Start with the unit of work, not the vendor. Write down a single
          sentence. <em>"This agent will turn X into Y, N times per week,
          with failure cost Z."</em> If you cannot fill in those four
          variables, you are not ready to buy.
        </p>
        <p>
          Then run a bottleneck check. If your team produces more than 100
          PRs a week, your bottleneck is not autocomplete; it is review. If
          support tickets cluster around three intents, you don't need a
          general-purpose agent; you need three workflows. If your sales
          reps spend 40% of their time on CRM hygiene, the agent's job is
          data entry, not outreach.
        </p>
      </Prose>

      <PullQuote>
        This step kills roughly half of agent purchases. That's the point.
      </PullQuote>

      <StepHeader number="02" eyebrow="Step Two" title="Pick the substrate before the surface" />
      <Prose>
        <p>
          Every agent is a stack of three layers: a model, a scaffold
          (memory, tools, planning), and a UI. The marketing is almost
          always about the UI. The performance is almost entirely about
          what's underneath.
        </p>
        <p>
          Long-horizon coding agents need strong tool use and large context.
          Customer-facing agents need latency below two seconds and tight
          refusal behaviour. Research agents need browsing and citation. A
          glossy interface doesn't tell you whether any of those are present.
        </p>
        <p>
          Three questions to ask the vendor. Which model do you use. Can I
          swap it. What happens when that model is deprecated. Vendors who
          can't answer the third one have not been in production long enough
          for it to matter to you.
        </p>
      </Prose>

      <StepHeader
        number="03"
        eyebrow="Step Three"
        title="Prototype against your worst data, not your best"
      />
      <Prose>
        <p>
          The most common failure mode in agent evaluation is the cherry-
          picked demo. The agent looks brilliant. It ships. It hits the long
          tail. It collapses.
        </p>
        <p>
          Build an eval set of 50 to 200 real cases pulled from your own
          logs, weighted toward edge cases, ambiguous instructions, and
          adversarial users. Run every shortlisted agent against that set
          before signing anything.
        </p>
      </Prose>

      <PullQuote>
        If a vendor will not let you run your own evals, walk away.
      </PullQuote>

      <Prose>
        <p>
          Two weeks of prototyping should cost less than a month of the
          vendor's contract minimum. If it doesn't, the contract is the
          wrong shape and the negotiation hasn't started.
        </p>
      </Prose>

      <StepHeader number="04" eyebrow="Step Four" title="Measure on four axes, not one" />
      <Prose>
        <p>
          Most buyers optimise on a single axis (usually cost or demo
          polish) and find the others in production. Use this frame instead.
          No agent wins all four. Pick the two that match the job and forgive
          the rest.
        </p>
      </Prose>

      <TradeoffTable
        rows={[
          {
            job: "Cost",
            pick: "Dollars per successful task",
            why: "High-volume, low-margin workflows where unit economics decide whether you ship at all.",
          },
          {
            job: "Reliability",
            pick: "End-to-end without rescue",
            why: "Customer-facing or revenue-critical work. One failure undoes a hundred wins.",
          },
          {
            job: "Control",
            pick: "Inspect, route, override, audit",
            why: "Compliance regimes and multi-team rollouts. Anything a lawyer will eventually read about.",
          },
          {
            job: "Speed-to-prototype",
            pick: "Days, not weeks",
            why: "Exploratory work and internal tools, where being wrong fast beats being right slowly.",
          },
        ]}
      />

      <Prose>
        <p>
          A cheap agent with great speed-to-prototype loses on control. A
          highly reliable enterprise agent loses on speed. Both can be the
          right answer; neither covers all four.
        </p>
      </Prose>

      <CTAPanel
        tag="The shortcut · AgentTape"
        title={<>Use <em>AgentScore</em> as your shortlist</>}
        body="AgentScore runs standardised evals across reliability, cost-per-success, latency, and tool-use accuracy, and publishes a single comparable composite per agent. Use it to cut the field to three to five candidates in an afternoon, then run your own data through them. AgentScore replaces the RFP for the first round, not the final one."
        href="/methodology"
        cta_label="Read the methodology"
      />

      <StepHeader number="05" eyebrow="Step Five" title="Plan for lock-in before you sign" />
      <Prose>
        <p>
          Every agent contract has three lock-in surfaces. The prompts and
          tool definitions you write. The memory and history accumulated in
          the vendor's storage. The integrations wired into the rest of
          your stack. The first is portable, the second usually isn't, and
          the third is the most expensive to rebuild.
        </p>
        <p>
          Three questions to negotiate before signing. Can I export memory
          and traces in a standard format. Can I bring my own model keys.
          If the vendor disappears in eighteen months, what do I keep.
        </p>
      </Prose>

      <PullQuote>
        An agent that locks your conversation history behind a proprietary
        schema is not a tool. It is a hostage situation.
      </PullQuote>

      <Prose>
        <p>
          Negotiate eval access, data export, and a model-swap clause. A
          vendor who refuses on all three is telling you something useful
          about how the partnership is going to feel in twelve months.
        </p>
      </Prose>

      <ChecklistBox
        tearout_label="Tear out — paste into your RFP doc"
        title="The 6-step checklist"
        items={[
          <><strong>Write the one-sentence job definition.</strong> Input, output, frequency, failure cost.</>,
          <><strong>Identify the actual bottleneck.</strong> Confirm an agent solves <em>that</em>, not the adjacent task.</>,
          <><strong>Pick the substrate before the UX.</strong> Model and scaffold first, product polish second.</>,
          <><strong>Build an eval set of 50–200 real cases.</strong> Weight toward edge cases and run it before any demo.</>,
          <><strong>Score finalists on four axes.</strong> Cost-per-success, reliability, control, speed-to-prototype.</>,
          <><strong>Negotiate portability into the contract.</strong> Data export, eval access, model-swap clause.</>,
        ]}
      />

      <Closer>
        Choosing an AI agent is a measurement problem dressed up as a
        procurement problem. Teams that treat it that way ship working
        agents. Teams that don't end up with a very expensive Slack bot.
      </Closer>

      <CTAButtonRow
        items={[
          { label: "Run head-to-head agent evals", href: "/compare" },
          { label: "Read the AgentScore methodology", href: "/methodology" },
        ]}
      />
    </>
  ),
};

// ----------------------------------------------------------- registry

export const ARTICLES: Article[] = [
  codingAgents2026,
  fmRanking,
  ossAlternatives,
  buyersGuide,
];

export const ARTICLE_BY_SLUG: Record<string, Article> = Object.fromEntries(
  ARTICLES.map((a) => [a.slug, a]),
);
