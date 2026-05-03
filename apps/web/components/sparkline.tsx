"use client";

import { useId } from "react";
import { cn } from "@/lib/utils";

// Hand-rolled SVG sparkline.
//
// - Color is a deterministic function of the first→last delta, so a row
//   of sparklines reads as red/green/neutral at a glance.
// - The fill is a soft gradient under the line, alpha low enough to
//   layer cleanly on the card background.
// - We render the line+fill from the same path so seam-less.

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  // Override the auto color (e.g. a neutral history chart on a hero).
  color?: "auto" | "gain" | "loss" | "neutral" | "primary";
  strokeWidth?: number;
  className?: string;
  // Force inclusion of zero in the y-range (useful for absolute counts).
  includeZero?: boolean;
}

export function Sparkline({
  values,
  width = 96,
  height = 28,
  color = "auto",
  strokeWidth = 1.5,
  className,
  includeZero = false,
}: SparklineProps) {
  const id = useId();
  if (!values || values.length < 2) {
    // Empty state — a thin baseline to preserve the row's height.
    return (
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className={cn("text-muted-foreground/40", className)}
      >
        <line
          x1={0}
          x2={width}
          y1={height / 2}
          y2={height / 2}
          stroke="currentColor"
          strokeWidth={1}
          strokeDasharray="2 3"
        />
      </svg>
    );
  }

  const min = Math.min(...values, includeZero ? 0 : Infinity);
  const max = Math.max(...values, includeZero ? 0 : -Infinity);
  const range = max - min || 1;
  const stepX = width / (values.length - 1);

  const points = values.map((v, i) => {
    const x = i * stepX;
    // SVG y is inverted — high values draw at the top (small y).
    const y = height - ((v - min) / range) * (height - strokeWidth) - strokeWidth / 2;
    return [x, y] as const;
  });

  const linePath = points
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`)
    .join(" ");
  const areaPath = `${linePath} L ${width.toFixed(2)} ${height} L 0 ${height} Z`;

  const delta = values[values.length - 1] - values[0];
  const palette =
    color === "auto"
      ? delta > 0
        ? "gain"
        : delta < 0
          ? "loss"
          : "neutral"
      : color;
  const stroke =
    palette === "gain"
      ? "hsl(var(--gain))"
      : palette === "loss"
        ? "hsl(var(--loss))"
        : palette === "primary"
          ? "hsl(var(--primary))"
          : "hsl(var(--neutral))";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      className={className}
    >
      <defs>
        <linearGradient id={`sg-${id}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.32} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#sg-${id})`} />
      <path
        d={linePath}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
