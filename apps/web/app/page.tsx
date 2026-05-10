import { Suspense } from "react";
import Link from "next/link";
import { api } from "@/lib/api-client";
import type { IndexSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import {
  CapabilityRail,
  CapabilityRailSkeleton,
  type CapabilityGroup,
} from "@/components/capability-rail";
import { IndexCard } from "@/components/index-card";
import { MoverChip } from "@/components/mover-chip";
import { TickerCard } from "@/components/ticker-card";
import { TickerTape } from "@/components/ticker-tape";
import { WelcomeBanner } from "@/components/welcome-banner";
import { CAPABILITIES } from "@/lib/taxonomy";

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

// 60-second ISR for the Floor. Shorter than other pages because the
// Floor is a "live ticker" — staleness > 1 minute is visible to
// users. Each ISR regen now gets an 8-second SSR fetch budget (see
// api-client.ts) instead of 2s, so flaky cache-regens that used to
// produce empty pages are much rarer. Combined with the
// throw-on-all-empty guard below, a transient API blip can no
// longer poison the cache for 5 minutes.
export const revalidate = 60;

// Fallbacks rendered when the API is unreachable or returns an
// unexpected shape. Each top-level fetch is wrapped with .catch so
// a single dead endpoint doesn't take the page down.
const EMPTY_AGENTS_PAGE = { items: [], total: 0, limit: 60, offset: 0 };

export default async function FloorPage() {
  // Each call independently catches — if the backend is down, the
  // page still renders, just with empty sections that show
  // "temporarily unavailable" hints. We fan out in parallel and let
  // each piece succeed or fail on its own.
  const [agentsPage, indexes, movers24h, recent] = await Promise.all([
    api.listAgents({ sort: "score", limit: 60 }).catch(() => EMPTY_AGENTS_PAGE),
    api.listIndexes().catch(() => []),
    api.movers("1d", 60).catch(() => []),
    api.recentDiscoveries(8).catch(() => []),
  ]);

  const apiOffline =
    agentsPage.items.length === 0 &&
    indexes.length === 0 &&
    movers24h.length === 0 &&
    recent.length === 0;

  // ISR cache hygiene: when all four top-level fetches come back
  // empty, the upstream is broken — and this render would otherwise
  // replace the good previous cache. Throwing inside the handler at
  // RUNTIME makes Next.js keep the previous cached HTML during ISR
  // revalidation. But throwing at BUILD time (when Vercel
  // pre-renders the route) fails the deploy outright. The
  // NEXT_PHASE check threads the needle: bail at runtime, render
  // the gracefully-degraded "Backend unreachable" banner at build
  // (when there's no good cache to fall back on anyway).
  if (apiOffline && process.env.NEXT_PHASE !== "phase-production-build") {
    throw new Error("Floor regen aborted: all top-level fetches empty");
  }

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

  // Index sparklines + capability rail are deferred to <Suspense>
  // boundaries below so their fetch latency doesn't gate first-byte.
  // Without that, a cold-cache render serialises:
  //   main Promise.all (~2s)
  //   → indexHistories Promise.all (~2s)
  //   → CapabilityRail's internal Promise.all (~2s)
  // = up to 6 s of dead time before any HTML reaches the browser.
  // With Suspense, only the main Promise.all gates first byte; the
  // other two stream in over the same connection.

  return (
    <div>
      <TickerTape initial={agents.slice(0, 30)} />
      <WelcomeBanner />

      {apiOffline && (
        <div className="border-b border-loss/30 bg-loss-subtle">
          <div className="container py-3 text-sm">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-loss">
              Backend unreachable
            </span>{" "}
            Live data refresh is paused. The cached page below may be a few
            minutes stale, and auto-recovers when the backend reconnects.
          </div>
        </div>
      )}

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

        {/* Trending Up + Trending Down. */}
        <section>
          <BigHead
            kicker="Trending"
            title="Biggest 24h moves."
            hint="Top gainers and decliners over the last 24 hours, by AgentScore."
            trailingHref="/trending"
            trailingLabel="Full feed →"
          />
          <div className="grid gap-3 md:grid-cols-2">
            <MoverList title="Gainers · 24h" items={top24h} emptyHint="No upward movement yet today." />
            <MoverList title="Decliners · 24h" items={drops24h} emptyHint="No declines today." />
          </div>
        </section>

        {/* Find-an-agent surface — capability rail with chip shortcuts
            up top. One section instead of two: the chips give a
            10-capability overview, the rail below shows the leading
            stocks in each. Click "All →" on any rail to drill into
            the full sector page (filters + compare). */}
        <section>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Find the right agent
              </div>
              <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
                What do you need an agent for?
              </h2>
              <p className="mt-1 max-w-prose text-sm text-muted-foreground">
                Pick a capability to see the live ranking with filters
                for license, deployment and maturity. Tick the{" "}
                <span className="font-mono text-primary">+</span> on any
                row to add it to your compare tray (up to 5).
              </p>
            </div>
            <Link
              href="/search"
              className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
            >
              Full search →
            </Link>
          </div>
          <div className="mb-4 flex flex-wrap gap-2">
            {CAPABILITIES.map((c) => (
              <Link
                key={c.slug}
                href={`/sectors/capability/${c.slug}`}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm hover:border-primary/40 hover:bg-subtle"
              >
                {c.label}
              </Link>
            ))}
          </div>
          {/* CapabilityRail is server-rendered through one
              /sectors/top fetch — wrapped in Suspense so its
              latency doesn't gate first-byte. The CapabilityRailLoader
              below distinguishes "still loading" / "fetch errored" /
              "no data" so the user always knows whether to wait or to
              click through to a sector page. */}
          <Suspense fallback={<CapabilityRailSkeleton />}>
            <CapabilityRailLoader />
          </Suspense>
        </section>

        {/* New listings. */}
        <section>
          <BigHead
            kicker="New listings"
            title="Just admitted."
            hint={`The ${recent.length} most recent agents the discovery service picked up.`}
            trailingHref="/new"
            trailingLabel="Live feed →"
          />
          {/* Horizontal-scroll row of new-listing cards. Wrapped in
              overflow-x-clip so the scroll behaviour stays inside
              the section rather than pushing the page wider than the
              viewport (which on mobile would throw off the fixed
              bottom nav). */}
          <div className="overflow-x-clip">
            <div className="flex gap-3 overflow-x-auto pb-2">
              {recent.length === 0 && (
                <div className="px-4 py-6 text-xs text-muted-foreground">
                  No admissions yet. The discovery service is on its first sweep.
                </div>
              )}
              {recent.map((a) => (
                <TickerCard key={a.id} agent={a} className="shrink-0 basis-[260px]" />
              ))}
            </div>
          </div>
        </section>

        {/* Indexes (sector + foundation-model baskets). */}
        <section>
          <BigHead
            kicker="Indexes"
            title="Sector and foundation-model baskets."
            hint="Curated baskets that track a slice of the market: top coding agents, the FM-50 model board, MCP servers, and more."
            trailingHref="/indexes"
            trailingLabel="All indexes →"
          />
          <Suspense fallback={<IndexesGridSkeleton count={Math.max(indexes.length, 6)} />}>
            <IndexesGrid indexes={indexes} />
          </Suspense>
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

// ---------------------------------------------------------------- streamed sub-trees
//
// These render under <Suspense>. While their data is in flight Next
// streams the parent shell + skeleton fallbacks; the sub-tree HTML
// arrives as a follow-up chunk on the same response. Net effect on a
// cold render: TTFB drops from ~6s to ~2s when the backend is slow,
// because indexHistories and the capability rail no longer serialise
// behind the main Promise.all.

async function IndexesGrid({ indexes }: { indexes: IndexSummary[] }) {
  const indexHistories = await Promise.all(
    indexes.map((i) =>
      api
        .indexHistory(i.slug, "30d")
        .then((rows) => ({
          slug: i.slug,
          values: rows.map((r) => r.composite_value),
        }))
        .catch(() => ({ slug: i.slug, values: [] as number[] })),
    ),
  );
  const histBySlug = Object.fromEntries(
    indexHistories.map((h) => [h.slug, h.values]),
  );
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {indexes.map((i) => (
        <IndexCard
          key={i.id}
          index={i}
          history={histBySlug[i.slug] ?? []}
        />
      ))}
    </div>
  );
}

function IndexesGridSkeleton({ count }: { count: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-40 animate-pulse rounded-md border border-border bg-card"
        />
      ))}
    </div>
  );
}


// ----------------------------------------------- CapabilityRailLoader

// Async server component that does the one /sectors/top fetch and
// hands the result to <CapabilityRail/>. Two failure modes:
//
//   • Endpoint not deployed yet (the API hasn't been redeployed
//     since /sectors/top was added) — fetch throws ApiError(404).
//   • Endpoint deployed but DB returned nothing (no agents tagged) —
//     fetch returns an empty array.
//
// We pass `null` for the first case and `[]` for the second. The
// rail renders different copy for each so the user knows whether to
// wait for a deploy to finish or to come back when discovery has
// admitted more agents.
async function CapabilityRailLoader() {
  let groups: CapabilityGroup[] | null;
  try {
    groups = await api.sectorsTop("capability", 3);
  } catch (e) {
    console.error("CapabilityRailLoader: /sectors/top failed", e);
    groups = null;
  }
  return <CapabilityRail groups={groups} />;
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
  // Tiered language so we don't oversell a 1-point move as the
  // "biggest" of the day when scores routinely shift by 5+.
  //
  //   ≥ 5 points:  "biggest move" — genuinely notable
  //   ≥ 2 points:  "notable move"
  //   ≥ 1 point :  "today's top mover" (no superlative)
  //   < 1 point :  fall through to a new listing or quiet-floor copy
  const gain = top24h[0];
  if (gain && gain.delta >= 1.0) {
    const headline =
      gain.delta >= 5
        ? "Today's biggest move in AgentScore, by a wide margin."
        : gain.delta >= 2
          ? "A notable move on the floor today."
          : "Today's top mover. Other moves are smaller.";
    return {
      title: `${gain.agent.name} climbs ${gain.delta.toFixed(1)} points to ${gain.score_now.toFixed(1)}.`,
      body: `${headline} Tap to see the signals driving it.`,
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
        body: "Most recent admission. The discovery service wasn't told to look for this; it found it.",
        linkSlug: newest.slug,
      };
    }
  }

  const drop = drops24h[0];
  if (drop && Math.abs(drop.delta) >= 1.0) {
    const mag = Math.abs(drop.delta);
    const headline =
      mag >= 5
        ? "Biggest decline today."
        : mag >= 2
          ? "A notable decline today."
          : "Today's top decliner.";
    return {
      title: `${drop.agent.name} falls ${mag.toFixed(1)} points.`,
      body: headline,
      linkSlug: drop.agent.slug,
    };
  }

  return {
    title: "Quiet floor today.",
    body: "Score moves under one point across the board. Pull up an agent's ticker page to see signals.",
  };
}

// Strong section heading: mono kicker, editorial title, body hint,
// optional trailing action link. Mirrors the "Find the right agent"
// block so every section reads at the same weight on the Floor.
function BigHead({
  kicker,
  title,
  hint,
  trailingHref,
  trailingLabel,
}: {
  kicker: string;
  title: string;
  hint?: string;
  trailingHref?: string;
  trailingLabel?: string;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {kicker}
        </div>
        <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
          {title}
        </h2>
        {hint && (
          <p className="mt-1 max-w-prose text-sm text-muted-foreground">
            {hint}
          </p>
        )}
      </div>
      {trailingHref && trailingLabel && (
        <Link
          href={trailingHref}
          className="text-xs font-mono uppercase tracking-wider text-primary hover:underline"
        >
          {trailingLabel}
        </Link>
      )}
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
