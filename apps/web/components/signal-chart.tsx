"use client";

import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";

// Multi-source signal time-series for the agent ticker page.
// Pass it the SignalSeries[] from /agents/{slug}/signals — each
// source becomes a toggleable line. Brush at the bottom for zooming.

interface Series {
  source: string;
  points: { captured_at: string; value: number }[];
}

interface SignalChartProps {
  series: Series[];
  active: string[]; // sources currently visible
  onToggle: (src: string) => void;
  className?: string;
}

const PALETTE = [
  "hsl(var(--primary))",
  "hsl(var(--gain))",
  "hsl(var(--loss))",
  "hsl(var(--neutral))",
  "hsl(217 91% 60%)",
  "hsl(38 92% 50%)",
];

export function SignalChart({
  series,
  active,
  onToggle,
  className,
}: SignalChartProps) {
  // Recharts wants one row per timestamp with each source as a column.
  // The series can have non-aligned timestamps so we union and forward-fill.
  const allTs = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.captured_at))),
  ).sort();
  const data = allTs.map((ts) => {
    const row: Record<string, number | string> = { captured_at: ts, ts: new Date(ts).getTime() };
    for (const s of series) {
      const point = s.points.find((p) => p.captured_at === ts);
      if (point) row[s.source] = point.value;
    }
    return row;
  });

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap gap-2 text-xs">
        {series.map((s, i) => {
          const on = active.includes(s.source);
          const color = PALETTE[i % PALETTE.length];
          return (
            <button
              key={s.source}
              type="button"
              onClick={() => onToggle(s.source)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 transition-colors",
                on
                  ? "border-foreground/30 bg-subtle text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                className="block h-2 w-2 rounded-full"
                style={{ backgroundColor: on ? color : "transparent", borderColor: color, borderWidth: 1, borderStyle: "solid" }}
              />
              <span className="font-mono uppercase tracking-wider">
                {s.source.replace(/_/g, " ")}
              </span>
            </button>
          );
        })}
      </div>
      <div className="h-72 w-full rounded-md border border-border bg-card p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 4 }}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="ts"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t) =>
                new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" })
              }
              stroke="hsl(var(--muted-foreground))"
              fontSize={11}
            />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              fontSize={11}
              width={48}
              tickFormatter={(v) =>
                Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toString()
              }
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 4,
                fontSize: 12,
              }}
              labelFormatter={(t) => new Date(t).toLocaleString()}
            />
            {series.map((s, i) =>
              active.includes(s.source) ? (
                <Line
                  key={s.source}
                  type="monotone"
                  dataKey={s.source}
                  stroke={PALETTE[i % PALETTE.length]}
                  strokeWidth={1.75}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ) : null,
            )}
            <Brush
              dataKey="ts"
              height={20}
              stroke="hsl(var(--border))"
              fill="hsl(var(--subtle))"
              tickFormatter={() => ""}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
