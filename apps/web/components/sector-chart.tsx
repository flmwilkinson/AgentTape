"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Single-series time chart for the sector detail page.
//
// We use Recharts (already in the bundle for /compare and the agent
// breakdown chart) instead of the bare Sparkline so the x-axis can
// carry actual dates — readers want to know whether a +2 move
// happened over a week or three weeks.

interface Point {
  captured_at: string;
  avg_score: number | null;
  agents: number;
}

interface Props {
  history: Point[];
  height?: number;
}

export function SectorChart({ history, height = 200 }: Props) {
  const data = history
    .filter((p) => p.avg_score != null)
    .map((p) => ({
      t: new Date(p.captured_at).getTime(),
      avg: p.avg_score as number,
      agents: p.agents,
    }));

  if (data.length < 2) {
    return (
      <div className="rounded-md border border-dashed border-border bg-card p-6 text-center text-xs text-muted-foreground">
        Waiting for enough score history to plot a chart. Sectors populate
        as the daily scoring cron accumulates readings.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="t"
          type="number"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(t) =>
            new Date(t as number).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })
          }
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
          tickLine={false}
          axisLine={false}
          minTickGap={32}
        />
        <YAxis
          domain={["auto", "auto"]}
          stroke="hsl(var(--muted-foreground))"
          fontSize={10}
          tickLine={false}
          axisLine={false}
          width={32}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: 6,
            fontSize: 12,
          }}
          labelFormatter={(t) =>
            new Date(t as number).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
            })
          }
          formatter={(v, name) => {
            if (name === "avg") {
              const num = typeof v === "number" ? v.toFixed(1) : "—";
              return [num, "Avg score"];
            }
            return [String(v), "Agents"];
          }}
        />
        <Line
          type="monotone"
          dataKey="avg"
          name="avg"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
