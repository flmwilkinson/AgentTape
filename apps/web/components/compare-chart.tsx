"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Overlay chart for the /compare page. Each agent's score history is a
// line; the union of timestamps becomes the x-axis. We use the same
// brand-blue + gain/loss palette so the chart doesn't compete with the
// rest of the UI.

interface Series {
  slug: string;
  name: string;
  points: { captured_at: string; agent_score: number }[];
}

const PALETTE = [
  "hsl(var(--primary))",
  "hsl(var(--gain))",
  "hsl(var(--loss))",
  "hsl(var(--neutral))",
];

interface Props {
  series: Series[];
  height?: number;
}

export function CompareChart({ series, height = 300 }: Props) {
  // Recharts wants one row per timestamp with each series as a column.
  // Build the union timestamp set and forward-fill missing points so
  // lines are continuous rather than gappy.
  const allTs = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.captured_at))),
  ).sort();

  const lastSeen: Record<string, number | null> = {};
  for (const s of series) lastSeen[s.slug] = null;

  const data = allTs.map((ts) => {
    const row: Record<string, number | string> = {
      ts: new Date(ts).getTime(),
      captured_at: ts,
    };
    for (const s of series) {
      const point = s.points.find((p) => p.captured_at === ts);
      if (point) {
        lastSeen[s.slug] = point.agent_score;
      }
      const v = lastSeen[s.slug];
      if (v !== null) row[s.slug] = v;
    }
    return row;
  });

  if (series.length === 0 || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground"
        style={{ height }}
      >
        Add two or more agents to see overlaid score history.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full rounded-md border border-border bg-card p-2">
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
            width={40}
            domain={[0, 100]}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 4,
              fontSize: 12,
            }}
            labelFormatter={(t) => new Date(t).toLocaleString()}
            formatter={(v: number) => v.toFixed(2)}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map((s, i) => (
            <Line
              key={s.slug}
              type="monotone"
              dataKey={s.slug}
              name={s.name}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={1.75}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
