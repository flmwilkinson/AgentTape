"use client";

import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

// The compact red/green pill used in tape rows and movers tables.
// Always shows sign + arrow; the value is monospace so a column of
// chips lines up cleanly.

interface MoverChipProps {
  delta: number | null | undefined;
  // What the delta represents — pass "score" to render as score points,
  // or "pct" to show percent.
  unit?: "score" | "pct";
  // Subdued: outlined treatment for dense lists.
  variant?: "filled" | "outline";
  className?: string;
}

export function MoverChip({
  delta,
  unit = "score",
  variant = "filled",
  className,
}: MoverChipProps) {
  const sign = delta == null || isNaN(delta) ? "flat" : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const Icon = sign === "up" ? ArrowUp : sign === "down" ? ArrowDown : Minus;

  const palette =
    sign === "up"
      ? variant === "filled"
        ? "bg-gain text-gain-foreground"
        : "text-gain border-gain/30 bg-gain-subtle"
      : sign === "down"
        ? variant === "filled"
          ? "bg-loss text-loss-foreground"
          : "text-loss border-loss/30 bg-loss-subtle"
        : "text-muted-foreground border-border bg-muted";

  const pretty =
    delta == null
      ? "—"
      : unit === "pct"
        ? `${delta > 0 ? "+" : ""}${delta.toFixed(2)}%`
        : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium num",
        variant === "outline" && "border",
        palette,
        className,
      )}
    >
      <Icon className="h-3 w-3" strokeWidth={2.5} />
      {pretty}
    </span>
  );
}
