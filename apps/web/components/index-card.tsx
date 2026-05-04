"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import type { IndexSummary } from "@/lib/api-client";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { Sparkline } from "@/components/sparkline";

interface IndexCardProps {
  index: IndexSummary;
  // History for the index composite — drawn as a sparkline.
  history?: number[];
  // Top 3 constituents (slug + name) — surfaced in the card body.
  topThree?: { slug: string; name: string; score: number | null }[];
  className?: string;
}

export function IndexCard({ index, history, topThree, className }: IndexCardProps) {
  const composite = index.composite_value;
  const delta =
    history && history.length >= 2
      ? composite !== null && history[0] !== 0
        ? composite - history[0]
        : null
      : null;

  return (
    <Link
      href={`/indexes/${index.slug}`}
      className={cn(
        "group flex h-full flex-col gap-3 rounded-md border border-border bg-card p-4 transition-colors hover:border-foreground/20 hover:bg-subtle",
        className,
      )}
    >
      <div className="flex items-baseline justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Index
          </div>
          <div className="text-base font-medium leading-tight">
            {index.name}
          </div>
        </div>
        <div className="text-right">
          <NumberTick
            value={composite}
            format={(v) => formatScore(v)}
            className="text-stat-lg font-semibold"
          />
          {delta !== null && (
            <div className="mt-0.5">
              <MoverChip delta={delta} unit="score" variant="outline" />
            </div>
          )}
        </div>
      </div>

      {history && history.length > 0 && (
        <Sparkline values={history} width={264} height={48} />
      )}

      {topThree && topThree.length > 0 && (
        <ul className="hairline pt-3 text-xs">
          {topThree.slice(0, 3).map((c) => (
            <li
              key={c.slug}
              className="flex items-center justify-between py-1 text-muted-foreground"
            >
              <span className="truncate text-foreground/90">{c.name}</span>
              <span className="num">{formatScore(c.score)}</span>
            </li>
          ))}
        </ul>
      )}
      {(!topThree || topThree.length === 0) && (
        <div className="hairline pt-3 text-xs text-muted-foreground">
          {index.members_count} constituents
        </div>
      )}
    </Link>
  );
}
