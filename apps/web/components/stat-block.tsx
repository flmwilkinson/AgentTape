"use client";

import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { Sparkline } from "@/components/sparkline";

// Big-number unit. Used on the dashboard hero, agent header, and any
// "single key metric" tile.

interface StatBlockProps {
  label: string;
  value: number | null | undefined;
  format: (v: number | null | undefined) => string;
  delta?: number | null;
  deltaUnit?: "score" | "pct";
  sparkline?: number[];
  size?: "md" | "lg" | "xl";
  caption?: string;
  trailing?: ReactNode;
  className?: string;
}

const SIZE_CLASS = {
  md: "text-stat-md",
  lg: "text-stat-lg",
  xl: "text-stat-xl",
};

export function StatBlock({
  label,
  value,
  format,
  delta,
  deltaUnit = "score",
  sparkline,
  size = "lg",
  caption,
  trailing,
  className,
}: StatBlockProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        <span>{label}</span>
        {trailing}
      </div>
      <div className="flex items-end gap-3">
        <NumberTick
          value={value}
          format={format}
          className={cn("font-semibold", SIZE_CLASS[size])}
        />
        {delta !== undefined && delta !== null && (
          <MoverChip delta={delta} unit={deltaUnit} />
        )}
        {sparkline && sparkline.length > 0 && (
          <Sparkline values={sparkline} width={88} height={28} className="ml-auto" />
        )}
      </div>
      {caption && (
        <div className="text-xs text-muted-foreground">{caption}</div>
      )}
    </div>
  );
}
