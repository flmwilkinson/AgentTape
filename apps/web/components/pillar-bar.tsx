"use client";

import { cn } from "@/lib/utils";

// Four pillars laid out horizontally as one stacked bar where each
// segment width is the pillar's *contribution* to the headline (its
// score * its weight). The widths sum to the headline visually, so the
// bar reads like a recipe.
//
// Quality is special: when null we render the slot as an "Unrated"
// hatch instead of a colored segment — the design rule "never 0".

// Pillar colours come from --pillar-* CSS tokens defined in globals.css
// so they stay in lock-step with the score-breakdown chart and the
// per-signal chart. If you change the tokens, every pillar surface
// updates automatically — never hardcode a pillar HSL.
const PILLARS: {
  key: "adoption" | "quality" | "momentum" | "community";
  label: string;
  weight: number; // matches scoring service config defaults
  color: string;
}[] = [
  { key: "adoption", label: "Adoption", weight: 0.35, color: "hsl(var(--pillar-adoption))" },
  { key: "quality", label: "Quality", weight: 0.3, color: "hsl(var(--pillar-quality))" },
  { key: "momentum", label: "Momentum", weight: 0.2, color: "hsl(var(--pillar-momentum))" },
  { key: "community", label: "Community", weight: 0.15, color: "hsl(var(--pillar-community))" },
];

interface Score {
  adoption: number | null;
  quality: number | null;
  momentum: number | null;
  community: number | null;
}

interface PillarBarProps {
  score: Score;
  // Compact: just the bar, no label legend (used in TickerCards).
  variant?: "compact" | "full";
  className?: string;
}

export function PillarBar({ score, variant = "full", className }: PillarBarProps) {
  // Each segment width = (pillar value / 100) * weight, normalized so
  // the four segments fill the bar at full pillar score.
  const segments = PILLARS.map((p) => {
    const v = score[p.key];
    return {
      ...p,
      value: v,
      // Bar contribution: the pillar's weighted slice on the 0-100 scale,
      // already represented as a percentage of the bar's total width.
      width: v == null ? 0 : (v / 100) * p.weight * 100,
    };
  });

  const usedWeight = segments
    .filter((s) => s.value !== null)
    .reduce((acc, s) => acc + s.weight, 0);

  return (
    <div className={cn("space-y-2", className)}>
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
        {segments.map((s, i) => {
          // Position each segment by accumulated offset so they render
          // side-by-side along the bar.
          const left = segments.slice(0, i).reduce((acc, prev) => acc + prev.width, 0);
          if (s.value === null) {
            // Unrated quality slot — diagonal hatch over the slot width
            // we'd give a perfect quality (so the row stays the same
            // shape across rated and unrated agents).
            const slotWidth = (1 / 100) * s.weight * 100 * 100;
            return (
              <div
                key={s.key}
                className="absolute inset-y-0"
                style={{
                  left: `${left}%`,
                  width: `${slotWidth}%`,
                  backgroundImage:
                    "repeating-linear-gradient(45deg, hsl(var(--muted-foreground) / 0.18) 0 4px, transparent 4px 8px)",
                }}
                title={`${s.label}: Unrated`}
              />
            );
          }
          return (
            <div
              key={s.key}
              className="absolute inset-y-0"
              style={{
                left: `${left}%`,
                width: `${s.width}%`,
                backgroundColor: s.color,
              }}
              title={`${s.label}: ${s.value.toFixed(1)}`}
            />
          );
        })}
      </div>

      {variant === "full" && (
        <div className="grid grid-cols-4 gap-2 text-[11px] text-muted-foreground">
          {segments.map((s) => (
            <div key={s.key} className="flex items-center gap-1.5">
              <span
                className="block h-2 w-2 rounded-sm"
                style={{
                  backgroundColor: s.value === null ? "transparent" : s.color,
                  borderColor: s.color,
                  borderWidth: s.value === null ? 1 : 0,
                  borderStyle: "solid",
                }}
              />
              <span className="uppercase tracking-wider">{s.label}</span>
              <span className="num ml-auto text-foreground">
                {s.value === null ? "—" : s.value.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}

      {variant === "full" && usedWeight < 1 && (
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          Quality unrated · weight redistributed
        </div>
      )}
    </div>
  );
}
