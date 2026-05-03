"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";

// Sector heatmap cell. Color is a continuous interpolation from loss
// (negative momentum) → neutral (zero) → gain (positive momentum). We
// clamp the input range to [-30, +30] points so a runaway agent
// doesn't washout the whole sector.

interface HeatmapCellProps {
  label: string;
  // Pillar value or score-delta in [-100, +100] — converted to a hue.
  value: number | null;
  // Optional: a sub-label like the count of agents in this sector.
  sublabel?: string;
  href?: string;
  className?: string;
}

const CAP = 30;

function colorFor(v: number | null): string {
  if (v === null || isNaN(v)) return "hsl(var(--muted))";
  const clamped = Math.max(-CAP, Math.min(CAP, v));
  const t = clamped / CAP; // -1..+1
  if (t === 0) return "hsl(var(--muted))";
  // Take the gain/loss base hue and modulate alpha by magnitude.
  const alpha = Math.max(0.1, Math.abs(t));
  return t > 0
    ? `hsl(var(--gain) / ${alpha.toFixed(2)})`
    : `hsl(var(--loss) / ${alpha.toFixed(2)})`;
}

export function HeatmapCell({
  label,
  value,
  sublabel,
  href,
  className,
}: HeatmapCellProps) {
  const cls = cn(
    "group flex h-20 flex-col justify-between rounded-md border border-border p-2.5 transition-transform hover:scale-[1.01]",
    className,
  );
  const style = { backgroundColor: colorFor(value) };
  const inner = (
    <>
      <div className="text-xs font-medium text-foreground/90 line-clamp-2 leading-tight">
        {label}
      </div>
      <div className="flex items-end justify-between text-[11px]">
        <span className="text-muted-foreground">{sublabel}</span>
        <span className="num font-medium text-foreground">
          {value === null
            ? "—"
            : `${value > 0 ? "+" : ""}${value.toFixed(1)}`}
        </span>
      </div>
    </>
  );
  return href ? (
    <Link href={href} className={cls} style={style}>
      {inner}
    </Link>
  ) : (
    <div className={cls} style={style}>
      {inner}
    </div>
  );
}
