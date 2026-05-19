"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import { CompareTrayToggle } from "@/components/compare-tray";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// Mobile-first card layout for rank tables. Below md the wide
// `<table>` wrappers force horizontal scroll on every page; this
// component is the md-and-below fallback. One stacked card per agent
// with name + label on top, score + delta in the middle, action
// icons + rank arrow at the bottom — easy to scan on a 360 px screen
// without dragging the layout sideways.

export interface MobileRankItem {
  slug: string;
  name: string;
  // Small mono label rendered under the name. Examples: "model · openrouter",
  // "agent · github", "+33% open · multimodal". Kept caller-provided so the
  // same card works for Models, Trending, Indexes detail, Watchlist, Sector
  // members.
  label?: string;
  rank?: number | null;
  score: number | null;
  delta24h: number | null;
  rankDelta24h?: number | null;
  // Optional context-specific extras: e.g. weight % on the index page.
  meta?: string | null;
  // Optional pillar chip rendered next to the headline score. Used by
  // the Models board when the user has chosen a single-pillar sort —
  // showing "Q 87" next to AgentScore lets the user see *why* the
  // model is in that position even though the headline column shows
  // composite. Format: short uppercase label + value or "Unrated".
  pillarLabel?: string;
  pillarValue?: number | null;
  // Right-side action toggles. Default: compare + watch.
  showCompare?: boolean;
  showWatch?: boolean;
}

interface Props {
  items: MobileRankItem[];
  // Hide on >= md so the parent <table> shows instead.
  className?: string;
}

export function MobileRankList({ items, className }: Props) {
  if (items.length === 0) return null;
  return (
    <ul className={cn("space-y-2 md:hidden", className)}>
      {items.map((it) => {
        const showCompare = it.showCompare !== false;
        const showWatch = it.showWatch !== false;
        return (
          <li
            key={it.slug}
            // ``overflow-hidden`` on the card keeps any malformed
            // long-string content from spilling out of the rounded
            // border at narrow widths (a defensive backstop — every
            // child below already truncates).
            className="overflow-hidden rounded-md border border-border bg-card p-3"
          >
            <div className="flex items-start justify-between gap-3">
              {/* ``min-w-0`` on this flex child is what lets the
                  truncate inside actually clip — without it the child
                  defaults to ``min-width: auto`` (= the intrinsic
                  width of its longest text), which pushes the trailing
                  icon cluster off-screen on long names. */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  {it.rank != null && (
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                      #{it.rank}
                    </span>
                  )}
                  <Link
                    href={`/agents/${it.slug}`}
                    className="min-w-0 truncate text-sm font-medium hover:text-primary"
                  >
                    {it.name}
                  </Link>
                </div>
                {it.label && (
                  <div className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {it.label}
                  </div>
                )}
                {it.meta && (
                  <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    {it.meta}
                  </div>
                )}
              </div>
              {/* ``shrink-0`` so the trailing icon cluster never
                  competes with the name for width. The Compare and
                  Watch toggles render as fixed-width buttons. */}
              <div className="flex shrink-0 items-center gap-1.5">
                {showCompare && <CompareTrayToggle slug={it.slug} />}
                {showWatch && <WatchToggle slug={it.slug} size="sm" />}
              </div>
            </div>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="num text-base font-semibold">
                {formatScore(it.score)}
              </span>
              {/* Pillar chip — only rendered when the caller has
                  chosen a single-pillar sort. Tells the user "this
                  is the pillar value driving the current sort"
                  alongside the composite AgentScore. */}
              {it.pillarLabel && (
                <span className="rounded border border-border bg-subtle/60 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-foreground/85">
                  {it.pillarLabel}{" "}
                  <span className="num text-foreground">
                    {it.pillarValue == null
                      ? "Unrated"
                      : it.pillarValue.toFixed(1)}
                  </span>
                </span>
              )}
              {it.delta24h != null && (
                <MoverChip delta={it.delta24h} unit="score" variant="outline" />
              )}
              {it.rankDelta24h != null && (
                <RankArrow delta={it.rankDelta24h} rankNow={it.rank ?? null} />
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
