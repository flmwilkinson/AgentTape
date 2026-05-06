import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CapabilityRail } from "@/components/capability-rail";
import { IndexCard } from "@/components/index-card";
import { MoverChip } from "@/components/mover-chip";
import { TickerCard } from "@/components/ticker-card";
import { TickerTape } from "@/components/ticker-tape";

// The Floor — overview page.
//
// Order is deliberate: people opening this page want, in order,
//   1) what's happening right now (live ticker tape)
//   2) the headline — one sentence that summarizes the day
//   3) what's gaining (Trending Up: 24h biggest movers)
//   4) what just listed (newly admitted agents)
//   5) the indexes (sector + foundation-model baskets)
//
// The methodology / sector heatmap / weekly editorial come below the
// fold — useful context but not what someone showing up for the first
// time needs to see first.

export const dynamic = "force-dynamic";

export default async function FloorPage() {
  // /movers ranks by absolute delta. We pull a wide slice (60) so
  // both gainers and decliners are visible — if we only fetched 8
  // and all eight were big drops (e.g. after a formula recalibration),
  // the gainers panel would falsely look empty.
  const [agentsPage, indexes, movers24h, recent] = await Promise.all([
    api.listAgents({ sort: "score", limit: 60 }),
    api.listIndexes(),
    api.movers("1d", 60),
    api.recentDiscoveries(8),
  ]);

  const agents = agentsPage.items;
  const top24h = movers24h
    .filter((m) => m.delta > 0)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 3);
  const drops24h = movers24h
    .filter((m) => m.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 3);
  const headline = pickHeadline({ top24h, drops24h, recent });

  // For the index cards: pull a thin history per index in parallel so
  // each card has a sparkline.
  const indexHistories = await Promise.all(
    indexes.map((i) =>
      api
        .indexHistory(i.slug, "30d")
        .then((rows) => ({ slug: i.slug, values: rows.map((r) => r.composite_value) }))
        .catch(() => ({ slug: i.slug, values: [] as number[] })),
    ),
  );
  const histBySlug = Object.fromEntries(indexHistories.map((h) => [h.slug, h.values]));

  return (
    <div>
      <TickerTape initial={agents.slice(0, 30)} />

      <div className="container py-8 md:py-12 space-y-12">
        {/* Headline of the day — auto-picked, never stale. */}
        {headline && (
          <section>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Today
            </div>
            <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
              {headline.title}
            </h1>
            {headline.body && (
              <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
                {headline.body}
              </p>
            )}
            {headline.linkSlug && (
              <div className="mt-4">
                <Link
                  href={`/agents/${headline.linkSlug}`}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Open ticker page →
                </Link>
              </div>
            )}
          </section>
        )}

        {/* Trending Up + Trending Down — the "what's gaining" surface. */}
        <section>
          <SectionHead
            label="Trending"
            hint="Biggest 24h moves in AgentScore"
            trailing={
              <Link href="/trending" className="text-xs text-primary hover:underline">
                Full feed →
              </Link>
            }
          />
          <div className="grid gap-3 md:grid-cols-2">
            <MoverList title="Gainers · 24h" items={top24h} emptyHint="No upward movement yet today." />
            <MoverList title="Decliners · 24h" items={drops24h} emptyHint="No declines today." />
          </div>
        </section>

        {/* Find-an-agent shortcut — the buyer's primary entry point.
            Big chips deep-link straight into the sector pages where
            filters and multi-select compare live. Below it, the
            capability rail keeps the top-3 visible for the impatient. */}
        <section className="rounded-md border border-border bg-card p-5 md:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Find the right agent
              </div>
              <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
                What do you need an agent for?
              </h2>
            </div>
            <Link
              href="/search"
              className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
            >
              Full search →
            </Link>
          </div>
          <p className="mt-2 max-w-prose text-sm text-muted-foreground">
            Pick a capability to see the live ranking with filters for
            license, deployment and maturity. Tick the agents you want
            and compare up to five side by side.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              { slug: "code-generation", label: "Coding" },
              { slug: "browsing", label: "Browser" },
              { slug: "rag", label: "RAG" },
              { slug: "multi-agent", label: "Multi-agent" },
              { slug: "research", label: "Research" },
              { slug: "automation", label: "Automation" },
              { slug: "tool-use", label: "Tool use" },
              { slug: "vision", label: "Vision" },
              { slug: "memory", label: "Memory" },
              { slug: "voice", label: "Voice" },
            ].map((c) => (
              <Link
                key={c.slug}
                href={`/sectors/capability/${c.slug}`}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:border-primary/40 hover:bg-subtle"
              >
                {c.label}
              </Link>
            ))}
          </div>
        </section>

        {/* Top by capability — keeps the "leading three stocks per
            category" view available without forcing a click into a
            sector page. */}
        <section>
          <SectionHead
            label="Top by capability"
            hint="The leading three stocks per category"
            trailing={
              <Link href="/search" className="text-xs text-primary hover:underline">
                Browse all →
              </Link>
            }
          />
          <CapabilityRail />
        </section>

        {/* New listings — the "rush to compare new releases" surface. */}
        <section>
          <SectionHead
            label="New listings"
            hint={`Most recent admissions · ${recent.length} latest`}
            trailing={
              <Link href="/new" className="text-xs text-primary hover:underline">
                Live feed →
              </Link>
            }
          />
          <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0">
            {recent.length === 0 && (
              <div className="px-4 py-6 text-xs text-muted-foreground">
                No admissions yet — the discovery service is on its first sweep.
              </div>
            )}
            {recent.map((a) => (
              <TickerCard key={a.id} agent={a} className="shrink-0 basis-[260px]" />
            ))}
          </div>
        </section>

        {/* Indexes — sector + foundation-model baskets. */}
        <section>
          <SectionHead
            label="Indexes"
            hint="Top stocks grouped by sector or foundation model"
            trailing={
              <Link href="/indexes" className="text-xs text-primary hover:underline">
                All indexes →
              </Link>
            }
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {indexes.map((i) => (
              <IndexCard key={i.id} index={i} history={histBySlug[i.slug] ?? []} />
            ))}
          </div>
        </section>

        {/* Methodology callout — short, links to the full page. */}
        <section className="rounded-md border border-border bg-editorial p-8 md:p-10">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            How it works
          </div>
          <h2 className="editorial mt-3 text-2xl font-semibold leading-tight md:text-3xl">
            Every stock here was admitted by software.
          </h2>
          <p className="editorial mt-4 max-w-prose text-base leading-relaxed text-foreground/85">
            No curated seed list. The discovery service watches GitHub,
            Hugging Face, MCP registries, npm/PyPI, arXiv, and Hacker News,
            and admits agents on its own schedule. AgentScore is a 0–100
            headline backed by four pillars (Adoption, Quality, Momentum,
            Community). Every input is published.
          </p>
          <p className="mt-6 text-xs">
            <Link href="/methodology" className="text-primary underline-offset-2 hover:underline">
              Read the methodology →
            </Link>
          </p>
        </section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- helpers


function pickHeadline({
  top24h,
  drops24h,
  recent,
}: {
  top24h: { agent: { slug: string; name: string }; delta: number; score_now: number }[];
  drops24h: { agent: { slug: string; name: string }; delta: number; score_now: number }[];
  recent: { slug: string; name: string; discovered_at: string }[];
}): { title: string; body?: string; linkSlug?: string } | null {
  // Priority order:
  //   1. A meaningful gainer (>= 1 point in 24h)
  //   2. A new listing within last 24h
  //   3. A meaningful decliner
  //   4. Something neutral
  const gain = top24h[0];
  if (gain && gain.delta >= 1.0) {
    return {
      title: `${gain.agent.name} climbs ${gain.delta.toFixed(1)} points to ${gain.score_now.toFixed(1)}.`,
      body: "Today's biggest move in AgentScore. Tap to see the signals driving it.",
      linkSlug: gain.agent.slug,
    };
  }

  const newest = recent[0];
  if (newest) {
    const ageHours = Math.max(
      0,
      (Date.now() - new Date(newest.discovered_at).getTime()) / 3_600_000,
    );
    if (ageHours <= 24) {
      return {
        title: `${newest.name} just listed.`,
        body: "Most recent admission. The discovery service hasn't been told to look for this — it found it.",
        linkSlug: newest.slug,
      };
    }
  }

  const drop = drops24h[0];
  if (drop && Math.abs(drop.delta) >= 1.0) {
    return {
      title: `${drop.agent.name} falls ${Math.abs(drop.delta).toFixed(1)} points.`,
      body: "Biggest decline today.",
      linkSlug: drop.agent.slug,
    };
  }

  return {
    title: "Quiet floor today.",
    body: "Score moves under one point across the board. Pull up an agent's ticker page to see signals.",
  };
}

function SectionHead({
  label,
  hint,
  trailing,
}: {
  label: string;
  hint?: string;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-end justify-between">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </div>
        {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
      </div>
      {trailing}
    </div>
  );
}

function MoverList({
  title,
  items,
  emptyHint,
}: {
  title: string;
  items: { agent: { slug: string; name: string }; delta: number; score_now: number }[];
  emptyHint: string;
}) {
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {title}
        </div>
      </div>
      <ul>
        {items.length === 0 && (
          <li className="px-4 py-4 text-xs text-muted-foreground">{emptyHint}</li>
        )}
        {items.map((m) => (
          <li
            key={m.agent.slug}
            className="flex items-center gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
          >
            <Link
              href={`/agents/${m.agent.slug}`}
              className="min-w-0 flex-1 truncate text-sm hover:text-primary"
            >
              {m.agent.name}
            </Link>
            <span className="num text-sm font-semibold">{formatScore(m.score_now)}</span>
            <MoverChip delta={m.delta} unit="score" />
          </li>
        ))}
      </ul>
    </div>
  );
}
