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
  IndexSnapshot,
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

// Articles registry.
//
// Each entry pairs ArticleMeta (used for /articles list + SEO) with a
// React body node composed of the shared article-blocks components.
// The blocks all use design-system tokens (bg-card, text-primary,
// hsl(var(--gain))) so every article ships in one consistent visual
// vocabulary regardless of how funky the layout is.

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
    "A live comparison of the top AI coding agents — Claude Code, Cursor, Codex, Devin, Cline and more — ranked by AgentScore and real benchmark deltas.",
  published_at: "2026-05-04",
  keywords: [
    "best ai coding agents",
    "ai code generation tools",
    "claude code vs cursor",
    "best ai for coding",
    "swe-bench leader",
  ],
  body: (
    <>
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
          The benchmark question settles fast. Claude is the SWE-bench leader,
          with Opus 4.7 at 87.6% on SWE-bench Verified and the Mythos Preview
          at 93.9%. But Verified is a floor, not a ceiling — the same Opus 4.5
          model that scores 80.9% on Verified drops to 45.9% on SWE-bench Pro,
          the contamination-resistant version Scale AI maintains.
        </p>
        <p>
          So this ranking weighs four things: SWE-bench Verified and Pro deltas,
          real PR merge rates, GitHub stars and install counts, and how the
          scaffolding moves the score. Three frameworks running the same
          underlying model finished 17 issues apart on the same 731-task
          evaluation in February. Architecture is doing real work.
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
          <strong>Claude Code</strong> takes the top slot on raw capability.
          With Opus 4.6 underneath, the model scores 80.8% on SWE-bench
          Verified, and independent runs show Claude Code uses 5.5× fewer
          tokens per task than Cursor on identical work — 33K versus 188K
          tokens on the same benchmark. The 200K standard context (1M in beta)
          is the reason it wins multi-file work.
        </p>
        <p>
          The pain is cost. Heavy users hit $150–$200/month on the Max plan,
          and rate limits bite even there. The recurring pattern on r/ClaudeCode
          is using Cursor for daily flow and switching to Claude Code on the
          hard problems. That's the right way to run it.
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
          <strong>Cursor</strong> owns the IDE category: $1.2B ARR, 1M+ daily
          active users, Composer for multi-file edits, sub-100ms Supermaven
          Tab. For developers who want AI without leaving their editor, nothing
          else feels this native. Cursor's agent scores 67.2% on SWE-bench
          Verified.
        </p>
        <p>
          The June 2025 switch to credit-based billing damaged trust, and Pro+
          at $60 plus Ultra at $200 still feel opaque at scale. The "Claude
          Code vs Cursor" question isn't really a debate — most productive
          teams run both.
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
          <strong>Codex</strong> is the comeback. GPT-5.3-Codex hits 77.3% on
          Terminal-Bench 2.0 and leads SWE-bench Pro at 56.8%; the Spark variant
          runs on Cerebras WSE-3 at 1,000+ tokens/sec. The cloud-task-runner
          model — submit a spec, get a sandboxed PR — is now Codex's calling
          card.
        </p>
        <p>
          Despite not existing during the last Stack Overflow survey, Codex
          already has roughly 60% of Cursor's usage. The Rust CLI is open
          source under Apache-2.0 with 62k+ stars. Pricing rides on ChatGPT
          Plus or Pro message windows.
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
        source="Source: BenchLM / llm-stats live leaderboard. Same models drop 30–35 points on SWE-bench Pro."
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
          <strong>Devin</strong> is the most autonomous agent shipping.
          Cognition reports a 67% PR merge rate on well-defined tasks, and
          Goldman Sachs is running Devin across its 12,000-engineer programming
          team with reported 3–4× productivity gains versus prior tooling.
          Pricing fell from $500/month to $20 Core plus $2.25 per Agent Compute
          Unit.
        </p>
        <p>
          It's narrow but powerful: bug backlogs, migration work, repetitive
          features. Open-ended tasks still expose the autonomy ceiling —
          Trustpilot sits at 3.0/5. Use it where success criteria are
          verifiable.
        </p>
      </Prose>

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
          <strong>Cline</strong> is the open-source flagship: 61.3k GitHub
          stars, 5M+ installs, BYOM across 30+ providers including Anthropic,
          OpenAI, Bedrock, Cerebras, and local Ollama. The Plan/Act split —
          read-only reasoning before any file edits — is the cleanest oversight
          pattern in the category.
        </p>
        <p>
          You pay only for tokens. A typical feature implementation runs
          50K–200K tokens, or roughly $0.50–$2.00 with Sonnet 4.7. The April
          2026 spend-limit UI keeps runaway sessions from quietly draining your
          account.
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
          <strong>Aider</strong> is the terminal-and-git purist's pick: 40k+
          stars, automatic commits with sensible messages, and a repo map that
          scales to large codebases. It speaks 100+ languages and connects to
          almost any LLM — Claude, GPT, Gemini, DeepSeek, local.
        </p>
        <p>
          If you want an inspectable CLI agent that has survived multiple model
          cycles and never locks you in, Aider belongs in the shortlist
          alongside Claude Code and Cline. The git-native workflow makes it the
          safest tool here for refactoring across an unfamiliar repo.
        </p>
      </Prose>

      <ProductHeading rank={7} name="Sourcegraph Amp (formerly Cody)" />
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
          <strong>Sourcegraph Amp</strong> is the enterprise pick. Cody Free
          and Pro retired in July 2025; Cody Enterprise ($59/user/month)
          remains, indexing 300,000+ repositories with verified SOC 2 Type II
          and ISO 27001:2022 certifications. Amp is the agentic successor —
          terminal, VS Code, Cursor, JetBrains, Neovim.
        </p>
        <p>
          If your codebase spans hundreds of microservices and procurement
          requires audit trails, this is the only tool here with indexing
          infrastructure built for the scale.
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
          <strong>Replit Agent 3</strong> wins the greenfield and non-engineer
          corner. It runs autonomously for up to 200 minutes per session,
          provisions databases, scaffolds full-stack apps with auth, and ships
          to a public URL in one click. Replit raised $250M at a $3B valuation
          in January 2026.
        </p>
        <p>
          It's the wrong tool for large codebases and regulated production.
          It's the right tool for prototypes, internal tools, and getting a
          working URL in front of a stakeholder within an hour.
        </p>
      </Prose>

      <H2>Trade-offs by job</H2>
      <TradeoffTable
        rows={[
          { job: "Greenfield apps", pick: "Replit Agent 3", why: "Browser-first, deploys in one click" },
          { job: "Multi-file refactors", pick: "Claude Code", why: "Long-context wins; 5.5× fewer tokens" },
          { job: "AI code review tool", pick: "Augment Code · Continue", why: "70% win rate vs Copilot; CI checks as code" },
          { job: "Human-in-the-loop", pick: "Cline · Aider", why: "Plan/Act split; per-commit diffs" },
          { job: "Async delegation", pick: "Devin", why: "End-state-only review for backlogs" },
        ]}
      />

      <H2>What to default to, by persona</H2>
      <PersonaCards
        items={[
          {
            audience: "Solo indie dev",
            pick: "Cursor + Claude Code",
            body: "$40/month before usage. Cursor for daily flow, Claude Code for hard problems. The most-cited combo on r/ClaudeCode.",
          },
          {
            audience: "Mid-stage startup",
            pick: "Cursor + Claude Code + Devin Core",
            body: "Two interactive agents plus one async — Devin wired into Linear or Jira for the bug backlog.",
          },
          {
            audience: "Regulated enterprise",
            pick: "Sourcegraph Amp + Devin Enterprise",
            body: "Audit posture and codebase indexing as defaults. Add Devin where async ROI is clear.",
          },
        ]}
      />

      <H2>How AgentTape's CODE-25 ranks them right now</H2>
      <Prose>
        <p>
          CODE-25 watches a different slice of the same fight. The index holds
          the top 25 application agents carrying a{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[12px]">
            code-generation
          </code>{" "}
          capability tag — the underlying engines builders point harnesses at,
          not the proprietary editors that wrap them. It's equal-weighted v1
          and rebalances Mondays at 03:00 UTC.
        </p>
      </Prose>

      <IndexSnapshot
        index_slug="code-25"
        caption="CODE-25 · Composite"
        composite={52.7}
        delta_label="▲ vs 30d"
        rows={[
          { rank: 1, name: "Gemini 2.5 Pro Preview 05-06", score: 76.4 },
          { rank: 2, name: "GPT-5.3-Codex", score: 68.8 },
          { rank: 3, name: "GPT-5", score: 68.2 },
          { rank: 4, name: "everything-claude-code", score: 65.9, delta: 4.1 },
          { rank: 5, name: "dify", score: 63.0, delta: 5.46 },
          { rank: 6, name: "hermes-agent", score: 62.4, delta: 6.2 },
        ]}
      />

      <Prose>
        <p>
          Gemini 2.5 Pro Preview 05-06 leads the engines. On the OSS-harness
          side, everything-claude-code (65.9) tops the application-agent
          constituents with dify (63.0) and hermes-agent (62.4) climbing. The
          signal CODE-25 picks up that the ranking above misses: which
          underlying engines and OSS harnesses are gaining momentum{" "}
          <em>before</em> they reach Cursor or Claude Code parity.
        </p>
        <p>
          The static ranking tells you what to install on Monday. CODE-25 tells
          you what's moving by Friday.
        </p>
      </Prose>
    </>
  ),
};

// ----------------------------------------------------------- article 2

const ossAlternatives: Article = {
  slug: "open-source-alternatives-devin-cursor-claude-code",
  title: "Open-source alternatives to Devin, Cursor and Claude Code",
  description:
    "An honest map of the leading self-hosted AI coding agents — who runs each one, which proprietary product it really replaces, and where it actually falls short.",
  published_at: "2026-05-04",
  keywords: [
    "open source devin",
    "self-hosted ai coding agent",
    "opendevin vs devin",
    "alternatives to cursor",
    "open source claude code",
  ],
  body: (
    <>
      <TickerTable
        caption="Live · OSS coding agents"
        asof="Stars as of 04 May 2026"
        rows={[
          { symbol: "OPENHANDS", stars: "72.6K", license: "MIT", default_model: "BYO via LiteLLM", replaces: "Devin", trend: "up" },
          { symbol: "CLINE", stars: "~58K", license: "Apache 2.0", default_model: "BYO key", replaces: "Cursor agent", trend: "up" },
          { symbol: "AIDER", stars: "~41K", license: "Apache 2.0", default_model: "Claude / DeepSeek / GPT", replaces: "Claude Code", trend: "up" },
          { symbol: "TABBY", stars: "~33K", license: "Apache 2.0", default_model: "Qwen2.5-Coder / StarCoder", replaces: "Copilot (self-hosted)", trend: "up" },
          { symbol: "CONTINUE", stars: "~31K", license: "Apache 2.0", default_model: "BYO key", replaces: "Cursor in-IDE", trend: "up" },
          { symbol: "SWE-AGENT", stars: "research", license: "MIT", default_model: "Claude / GPT (any)", replaces: "Devin (headless)" },
        ]}
      />

      <Lede>
        The proprietary AI coding stack moves fast. Devin still bills per seat,
        Cursor changes its pricing every quarter, and Claude Code lives entirely
        inside one vendor's API. None of that is a problem — until your CFO,
        your compliance team, or an air-gapped environment makes it one.
      </Lede>

      <Prose>
        <p>
          The OSS ecosystem matured enough in 2026 that "self-hosted AI coding
          agent" stopped being a downgrade. It's a different set of trade-offs.
          Below is an honest map of the leading open-source replacements for
          Devin, Cursor and Claude Code, who actually self-hosts each one, and
          where each falls short.
        </p>
      </Prose>

      <SectionDivider number="01" label="Autonomous agent" />
      <Section>
        <SectionContent>
          <h2 className="editorial mt-0 text-2xl font-semibold leading-tight md:text-3xl">
            OpenHands — the real open-source Devin
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Formerly OpenDevin · All-Hands-AI
          </div>
          <p>
            If you want a direct <strong>OpenDevin vs Devin</strong> answer,
            OpenHands is it. The All-Hands-AI project rebranded from OpenDevin
            and now sits at <strong>72,607 stars</strong> on the main repo as
            of today, under MIT. It runs autonomous agents that plan, edit
            code, run tests, browse the web, and open PRs from inside a
            sandboxed Docker container.
          </p>
          <p>
            The hosted free tier defaults to a Minimax model; the best published
            numbers come from{" "}
            <strong>Claude Sonnet 4.5 at roughly 77% on SWE-Bench Verified</strong>.
          </p>
          <p>
            <strong>Who self-hosts it:</strong> teams with hard data residency
            rules, anyone allergic to per-seat pricing, and engineers who want
            to read the agent's source.
          </p>
          <p>
            <strong>Where it falls short:</strong> setup is real DevOps work,
            and a SWE-bench-style real fix runs $0.50–$3 per task on a frontier
            model. You're trading one bill for another.
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
            Aider — the open-source Claude Code
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Apache 2.0 · ~41K stars · 5.3M+ PyPI installs
          </div>
          <p>
            Aider is a terminal-native pair programmer that edits your local
            git repo and auto-commits each change. If your daily driver is
            Claude Code, Aider ports across with the least friction.
          </p>
          <p>
            It works best with{" "}
            <strong>
              Claude 3.7 Sonnet, DeepSeek R1 and Chat V3, OpenAI o1, o3-mini
              and GPT-4o
            </strong>
            , and connects to almost any LLM — including local models via
            LiteLLM.
          </p>
          <p>
            <strong>Strengths:</strong> a tree-sitter repo map, surgical diffs,
            and every change landing as a real git commit you can review or
            revert.
          </p>
          <p>
            <strong>Weakness:</strong> Aider only edits files. It cannot run
            commands, install packages, or execute tests. For a Devin-style
            "fire and forget" loop, you need OpenHands. For a precision tool
            that respects your git history, Aider is hard to beat.
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
            SWE-agent — the issue-to-patch baseline
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Princeton + Stanford · MIT · NeurIPS 2024
          </div>
          <p>
            SWE-agent is the academic project that put open source on the
            SWE-bench leaderboard. Configuration lives in a single YAML file.
            Its smaller sibling,{" "}
            <strong>
              mini-SWE-agent, scores over 74% on SWE-bench Verified in roughly
              100 lines of Python
            </strong>
            .
          </p>
          <p>
            Default model: bring your own — Claude Sonnet, GPT, or any LiteLLM
            target.
          </p>
          <p>
            <strong>Best for:</strong> running headless on a queue of GitHub
            issues, benchmarking, or building your own agent on top of a clean
            baseline.
          </p>
          <p>
            <strong>Weak for:</strong> day-to-day "help me with this file"
            coding. There's no chat polish, no IDE plugin — it's a research
            artifact you point at a problem.
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
            Continue &amp; Cline — alternatives to Cursor
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            VS Code &amp; JetBrains extensions · Apache 2.0
          </div>
          <p>
            Cursor's pitch is a VS Code fork with AI baked in everywhere. The
            OSS answer is to keep stock VS Code and bolt on the same primitives.
          </p>
          <p>
            <strong>Continue</strong> (~31K stars, Apache 2.0) handles
            autocomplete and chat across VS Code and JetBrains. Model-agnostic
            — pair it with Claude, GPT-4o, or a local Ollama model.
          </p>
          <p>
            <strong>Cline</strong> (~58K stars including its Roo Code and Kilo
            Code forks, Apache 2.0) is the agentic VS Code extension closest in
            feel to Cursor's agent mode. It approves edits step-by-step rather
            than running fully autonomous.
          </p>
          <p>
            <strong>Where they fall short of Cursor:</strong> the editor itself
            isn't custom-tuned. You don't get Cursor's tab-completion model or
            the same end-to-end latency. If those specific UX wins are why you
            pay Cursor today, no extension will fully replicate them.
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
            Tabby — the self-hosted Copilot
          </h2>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            ~33K stars · Apache 2.0 (open-core) · Docker-native
          </div>
          <p>
            Tabby is the only tool on this list designed primarily for an
            air-gapped team server, not a single developer's laptop. It ships
            as a Docker container with a built-in admin panel, LDAP auth,
            per-user API keys and usage analytics.
          </p>
          <p>
            Default models: open-weight coders — StarCoder, Qwen2.5-Coder,
            DeepSeek Coder.{" "}
            <strong>
              A single A100 80GB running Qwen2.5-Coder 32B 4-bit serves 15–25
              concurrent developers
            </strong>{" "}
            with Tabby's request queuing.
          </p>
          <p>
            <strong>Replaces:</strong> GitHub Copilot for completion, plus a
            basic chat panel.
          </p>
          <p>
            <strong>Doesn't replace:</strong> Cursor's agent mode or
            Devin-style autonomous execution. Tabby is autocomplete-and-chat,
            not an autonomous engineer.
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

      <QuadGrid
        title={<>Why <em>OSS</em> here, really</>}
        deck="Most 'open beats closed' pieces collapse four very different reasons into one. They aren't the same buyer. Match the reason to the right audience and the right tool falls out."
        items={[
          {
            number: "01",
            name: "Vendor lock-in",
            who: "Platform engineering leads · multi-year roadmaps",
            body: "OSS lets you swap the underlying model when prices move. The relevant tools are model-agnostic by default — Aider, OpenHands, Continue.",
          },
          {
            number: "02",
            name: "Audit & IP",
            who: "Legal teams · security review",
            body: "When you need to prove which code touched a third-party model, OpenHands or Aider give you a paper trail down to the byte. Closed agents can't.",
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
                A single A100 80GB at $1.04/hour is roughly $749/month — about{" "}
                <strong>39 GitHub Copilot Business seats at $19 each</strong>.
                Below ~40 developers, Copilot is genuinely cheaper.
              </>
            ),
          },
        ]}
      />

      <PullQuote>
        If your reason is ideology, none of these tools win on their own merits.
      </PullQuote>

      <CTAPanel
        tag="Live Index"
        title={<>The OSS-50 — <em>tracked daily</em></>}
        body="Star counts, benchmarks and pricing shift weekly. For the live picture — including which open-source agent is gaining momentum on AgentTape this week — see the leaderboard."
        href="/indexes/oss-50"
        cta_label="View the OSS-50"
      />
    </>
  ),
};

// ----------------------------------------------------------- article 3

const buyersGuide: Article = {
  slug: "how-to-choose-ai-agent-2026",
  title: "How to actually choose an AI agent in 2026",
  description:
    "A practical decision flow for evaluating agents — without falling for the demo, the deck, or the dashboard.",
  published_at: "2026-05-04",
  keywords: [
    "how to choose ai agent",
    "ai agent buying guide",
    "evaluate ai agents",
    "ai agent rfp",
  ],
  body: (
    <>
      <Lede>
        Most teams pick agents the way they pick SaaS in 2018: a demo, a
        champion, a credit card. That worked when the worst case was a dead
        Slack integration. It does not work when the agent writes production
        code, replies to customers, or moves money.
      </Lede>

      <Prose>
        <p>
          This is a working buyer's guide. Use it as a sequence, not a
          checklist. Skip a step and you will pay for it in the next one.
        </p>
      </Prose>

      <StepHeader number="01" eyebrow="Step One" title="Define the job, not the agent" />
      <Prose>
        <p>
          Start with the unit of work, not the vendor. Write down a single
          sentence:{" "}
          <em>
            "This agent will turn X into Y, N times per week, with failure
            cost Z."
          </em>{" "}
          If you cannot fill in those four variables, you are not ready to buy.
        </p>
        <p>
          Then run a bottleneck check. If your team produces more than 100 PRs
          per week, your bottleneck is not autocomplete; it is review. If
          support tickets cluster around three intents, you do not need a
          general-purpose agent; you need three workflows. If your sales reps
          spend 40% of their time on CRM hygiene, the agent's job is data
          entry, not outreach.
        </p>
      </Prose>

      <PullQuote>
        This step kills roughly half of agent purchases. That is the point.
      </PullQuote>

      <StepHeader number="02" eyebrow="Step Two" title="Pick the substrate before the surface" />
      <Prose>
        <p>
          Every agent is a stack: a model, a scaffold (memory, tools,
          planning), and a UI. The marketing is almost always about the UI.
          The performance is almost entirely about the substrate.
        </p>
        <p>
          Before evaluating product features, decide which substrate fits the
          job. Long-horizon coding agents need strong tool use and large
          context. Customer-facing agents need latency below two seconds and
          tight refusal behaviour. Research agents need browsing and citation.
          Don't let a glossy interface convince you the underlying capability
          is there.
        </p>
        <p>
          Ask vendors which model they use, whether you can swap it, and what
          happens when the underlying model is deprecated.{" "}
          <strong>
            A vendor who cannot answer the third question has not been in
            production long enough to matter.
          </strong>
        </p>
      </Prose>

      <StepHeader
        number="03"
        eyebrow="Step Three"
        title="Prototype against your worst data, not your best"
      />
      <Prose>
        <p>
          The number-one failure mode in agent evaluation: teams demo with
          cherry-picked inputs. The agent looks brilliant. It ships. It meets
          the long tail. It collapses.
        </p>
        <p>
          Build an eval set of 50 to 200 real cases from your own logs,
          weighted toward edge cases, ambiguous instructions, and adversarial
          users. Run every shortlisted agent against that set.
        </p>
      </Prose>

      <PullQuote>
        If a vendor will not let you run your own evals, walk away. They are
        selling vibes.
      </PullQuote>

      <Prose>
        <p>
          Two weeks of prototyping should cost less than a month of the
          vendor's contract minimum. If it doesn't, the contract is the wrong
          shape.
        </p>
      </Prose>

      <StepHeader number="04" eyebrow="Step Four" title="Measure on four axes, not one" />
      <Prose>
        <p>
          Most buyers optimise on a single axis (usually cost or demo polish)
          and discover the others in production. Use this trade-off frame.
        </p>
      </Prose>

      <TradeoffTable
        rows={[
          {
            job: "Cost",
            pick: "Dollars per successful task",
            why: "High-volume, low-margin workflows where unit economics decide whether you ship.",
          },
          {
            job: "Reliability",
            pick: "End-to-end without rescue",
            why: "Customer-facing or revenue-critical work where one failure undoes a hundred wins.",
          },
          {
            job: "Control",
            pick: "Inspect, route, override, audit",
            why: "Compliance regimes, multi-team rollouts, or anything a lawyer will eventually read about.",
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
          A cheap agent with great speed-to-prototype will lose on control. A
          highly reliable enterprise agent will lose on speed. Pick the two
          that match the job you defined in step one, then forgive the others.
        </p>
      </Prose>

      <CTAPanel
        tag="The shortcut · AgentTape"
        title={<>Use <em>AgentScore</em> as your shortlist</>}
        body="AgentScore is the measurement layer for this process. It runs standardised evals across reliability, cost-per-success, latency, and tool-use accuracy, and publishes a comparable score per agent so you can shortlist three to five candidates in an afternoon instead of three to five weeks. AgentScore replaces the RFP for the first round; it does not replace your data for the final round."
        href="/methodology"
        cta_label="Read the methodology"
      />

      <StepHeader number="05" eyebrow="Step Five" title="Plan for lock-in before you sign" />
      <Prose>
        <p>
          Every agent contract has three lock-in surfaces: the prompts and
          tool definitions you wrote, the memory and history accumulated in
          the vendor's storage, and the integrations wired into your stack.
          The first is portable. The second usually is not. The third is the
          most expensive to rebuild.
        </p>
        <p>
          Before signing, ask: can I export memory and traces in a standard
          format? Can I bring my own model keys? If the vendor disappears in
          18 months, what do I keep?
        </p>
      </Prose>

      <PullQuote>
        An agent that locks your conversation history behind a proprietary
        schema is not a tool. It is a hostage situation.
      </PullQuote>

      <Prose>
        <p>
          Negotiate eval access, data export, and a model-swap clause into the
          contract. Vendors who refuse on all three are telling you something.
        </p>
      </Prose>

      <ChecklistBox
        tearout_label="Tear out — paste into your RFP doc"
        title="The 6-step checklist"
        items={[
          <><strong>Write the one-sentence job definition.</strong> Input, output, frequency, failure cost.</>,
          <><strong>Identify the actual bottleneck.</strong> Confirm an agent solves <em>that</em>, not the adjacent task.</>,
          <><strong>Pick the substrate before the UX.</strong> Model and scaffold first; product polish second.</>,
          <><strong>Build an eval set of 50–200 real cases.</strong> Weight toward edge cases. Run it before any demo.</>,
          <><strong>Score finalists on four axes.</strong> Cost-per-success, reliability, control, speed-to-prototype.</>,
          <><strong>Negotiate portability into the contract.</strong> Data export, eval access, model-swap clause — before signing.</>,
        ]}
      />

      <Closer>
        Choosing an AI agent in 2026 is not a procurement problem.{" "}
        <em>It is a measurement problem.</em> Teams that treat it that way
        ship working agents. Teams that don't end up with a very expensive
        Slack bot.
      </Closer>
    </>
  ),
};

// ----------------------------------------------------------- article 4

const fmRanking: Article = {
  slug: "best-foundation-models-for-ai-agents-2026",
  title: "The best foundation models for AI agents in 2026",
  description:
    "The eight foundation models that actually ship agent workloads in production, ranked on tool-use reliability, long-context recall, and cost-per-task.",
  published_at: "2026-05-04",
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
        Picking the best foundation model for agents in 2026 is not the same
        question as picking the best chatbot. Agents fail on three axes
        humans don't: brittle tool calls, context that rots after 80k tokens,
        and dollar-per-task economics that explode at 10M runs.
      </Lede>

      <Prose>
        <p>
          We ranked the eight models actually shipping agent workloads in
          production. Numbers below are from public leaderboards as of 4 May
          2026 — no vendor self-reports.
        </p>
      </Prose>

      <AxesGrid
        items={[
          {
            label: "Tool-use reliability",
            body: "BFCL v4 and stability across multi-turn loops.",
          },
          {
            label: "Long-context recall",
            body: "Effective recall past 200K, not just window size.",
          },
          {
            label: "Cost per task",
            body: "Blended price per 1M I/O tokens at production volume.",
          },
        ]}
      />

      <ModelCard
        rank={1}
        name="Claude Opus 4.7"
        maker="Anthropic"
        badge="Top pick"
        tag={
          <>
            The default answer to "best LLM for agents" in 2026. Opus 4.7 leads
            every public agent harness eval since February. Pair it with
            Sonnet 4.6 for the 80% of steps that don't need flagship
            reasoning — routing is table stakes.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Long-horizon plans, recoverable tool failures, code editing.",
          },
          {
            label: "Where it loses",
            body: "$5/$25 per 1M makes it 2× GPT-5.4. 200K context.",
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
            The "Claude vs GPT for agents" debate splits by use case. GPT-5.4
            at $2.50/$15 is the price-performance frontier; GPT-5.3 Codex hits
            85% SWE-bench Verified at half of Opus's cost. The native
            function-calling schema is still the cleanest in the industry.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Cost-quality balance, broad framework support, single-turn tool calls.",
          },
          {
            label: "Where it loses",
            body: "Drifts more than Claude past ~50 tool calls. 270K context cap.",
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
            The AgentBench leader on long-context multimodal tasks. 2M
            tokens — the largest production context from any Tier-1 provider —
            and a 90% cache discount that makes it the cheapest flagship for
            repeat-prompt agents.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "RAG over codebases, hour-long video, document corpora.",
          },
          {
            label: "Where it loses",
            body: "SWE-bench ~78% trails Claude and GPT. Function-calling has more edges.",
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
            The open-weights challenger that matters. 1T-parameter MoE (32B
            active) trained with PARL to orchestrate up to 1,500 coordinated
            tool calls across self-spawned sub-agents. Documented 13-hour
            multi-tool sessions without context collapse.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Parallel agent swarms, polyglot codebases, frontier capability self-hosted.",
          },
          {
            label: "Where it loses",
            body: "BFCL v4 trails closed labs by 4–6 points. Vision below Gemini.",
          },
        ]}
        stat={{ label: "Parallel tool calls per session", value: "1,500" }}
      />

      <ModelCard
        rank={5}
        name="DeepSeek V4"
        maker="DeepSeek · open weights"
        tag={
          <>
            The open-weight model that closed the raw-capability gap. 80.6%
            SWE-bench Verified, 1M context, ~1T parameters. On a per-token
            basis it's the cheapest frontier-class model on the market.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Reasoning at open-weights pricing, dense math and science.",
          },
          {
            label: "Where it loses",
            body: "Self-hosting needs serious GPU. Hosted latency 2–3× Claude on short tool loops.",
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
            The multilingual default and the only open-weight model shipping a
            real 1M-token context. Dominant on Chinese-language coding,
            Apache 2.0 on smaller variants.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Multilingual agents, long-context open-weights, broad ecosystem.",
          },
          {
            label: "Where it loses",
            body: "English reasoning trails DeepSeek V4. Flagship under Tongyi Qianwen, not Apache.",
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
            The model you pick when fine-tuning rights and ecosystem maturity
            matter more than peak capability. Largest deployment footprint of
            any open model — every framework, every cloud, every fine-tuning
            library targets it first.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "Enterprise fine-tuning, broad tooling, permissive license.",
          },
          {
            label: "Where it loses",
            body: "No longer competitive on agent benchmarks vs Kimi K2.6 or DeepSeek V4.",
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
            The EU-friendly bet. 77.6% SWE-bench Verified from a 128B dense
            model — strong efficiency, Apache 2.0, the only frontier-tier lab
            outside the US/China duopoly.
          </>
        }
        splits={[
          {
            label: "Best at",
            body: "EU data sovereignty, dense efficiency, Apache fine-tuning.",
          },
          {
            label: "Where it loses",
            body: "BFCL v4 below Qwen and closed labs. Long-context past 128K unreliable.",
          },
        ]}
        stat={{ label: "SWE-bench Verified", value: "77.6%" }}
      />

      <H2>How to choose</H2>
      <ChooseGrid
        items={[
          {
            heading: "Agents that must work",
            body: "Claude Opus 4.7. No close second on long-horizon reliability.",
          },
          {
            heading: "Cost-quality sweet spot",
            body: "GPT-5.4. The right default if you're not bottlenecked on hardest tasks.",
          },
          {
            heading: "Context is the bottleneck",
            body: "Gemini 3.1 Pro. 2M tokens, 90% cache discount, RAG-friendly pricing.",
          },
          {
            heading: "Self-hosting or budget",
            body: "Kimi K2.6 for orchestration, DeepSeek V4 for raw reasoning per dollar.",
          },
        ]}
      />

      <Closer>
        The agent stack of 2026 is not single-model. Route hard reasoning to
        Opus, bulk tool calls to Sonnet 4.6 or GPT-5.4, RAG-over-corpus to
        Gemini, and long-running orchestration to Kimi K2.6. Anyone betting on
        one model is leaving 30–40% on the table.
      </Closer>

      <CTAButtonRow
        items={[
          { label: "Run head-to-head agent evals", href: "/compare" },
          { label: "View the FM-50 index", href: "/indexes/fm-50" },
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
