"use client";

import { ChevronDown, ChevronUp, Minus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

// Tiny visual cue beside a rank number showing how far the agent has
// moved in the last 24 hours.
//
//   ▲ 5   — climbed five positions
//   ▼ 3   — dropped three
//   ●     — held
//   ★ NEW — too new to compare (rank_24h_ago is null)

interface Props {
  delta: number | null | undefined;
  // For the "no history" case the parent passes null. We render a small
  // "NEW" badge so users know it's not "0 movement" but "no comparison".
  rankNow?: number | null;
  className?: string;
  size?: "sm" | "md";
}

export function RankArrow({ delta, rankNow, className, size = "sm" }: Props) {
  const iconSize = size === "md" ? "h-3.5 w-3.5" : "h-3 w-3";
  const textSize = size === "md" ? "text-xs" : "text-[11px]";

  if (delta === null || delta === undefined) {
    // No 24h history — render NEW badge.
    return (
      <span
        className={cn(
          "inline-flex items-center gap-0.5 rounded-sm border border-primary/30 bg-primary/5 px-1.5 py-px font-mono uppercase tracking-wider",
          textSize,
          "text-primary",
          className,
        )}
        title="No 24h ranking history"
      >
        <Sparkles className={iconSize} strokeWidth={2.25} />
        NEW
      </span>
    );
  }

  if (delta === 0) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-0.5 num text-muted-foreground",
          textSize,
          className,
        )}
        title="Rank unchanged"
      >
        <Minus className={iconSize} strokeWidth={2.5} />
      </span>
    );
  }

  const up = delta > 0;
  const Icon = up ? ChevronUp : ChevronDown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 num font-medium",
        textSize,
        up ? "text-gain" : "text-loss",
        className,
      )}
      title={
        up
          ? `Climbed ${delta} ${delta === 1 ? "place" : "places"} in 24h`
          : `Dropped ${Math.abs(delta)} in 24h`
      }
    >
      <Icon className={iconSize} strokeWidth={2.5} />
      {Math.abs(delta)}
    </span>
  );
}
