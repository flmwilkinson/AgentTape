"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  history: { captured_at: string; composite_value: number }[];
}

export function IndexHistoryChart({ history }: Props) {
  const data = history.map((h) => ({
    ts: new Date(h.captured_at).getTime(),
    composite: h.composite_value,
  }));
  return (
    <div className="h-72 w-full rounded-md border border-border bg-card p-2">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 4 }}>
          <defs>
            <linearGradient id="composite-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.32} />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
            </linearGradient>
          </defs>
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
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} width={48} />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 4,
              fontSize: 12,
            }}
            labelFormatter={(t) => new Date(t).toLocaleString()}
            formatter={(v: number) => [v.toFixed(2), "Composite"]}
          />
          <Area
            type="monotone"
            dataKey="composite"
            stroke="hsl(var(--primary))"
            strokeWidth={1.75}
            fill="url(#composite-fill)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
