"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";

// Sector composite chart with window picker.
//
// 1d  → 5-min buckets (server-side).
// 7d  → hour buckets.
// 30d / 90d / all → day buckets.
// Tooltip always shows full date+time so you can tell which 5-min
// tick a hover lands on, not just the day.

const WINDOWS = [
  { v: "1d", label: "1d" },
  { v: "7d", label: "7d" },
  { v: "30d", label: "30d" },
  { v: "90d", label: "90d" },
  { v: "all", label: "All" },
] as const;

type Window = (typeof WINDOWS)[number]["v"];

interface Props {
  kind: string;
  value: string;
  height?: number;
  initialWindow?: Window;
}

export function SectorChart({
  kind,
  value,
  height = 200,
  initialWindow = "7d",
}: Props) {
  const [window, setWindow] = useState<Window>(initialWindow);
  const { data: history, isLoading } = useQuery({
    queryKey: ["sector-history", kind, value, window],
    queryFn: () => api.sectorHistory(kind, value, window),
  });

  const data = (history ?? [])
    .filter((p) => p.avg_score != null)
    .map((p) => ({
      t: new Date(p.captured_at).getTime(),
      avg: p.avg_score as number,
      agents: p.agents,
    }));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-end">
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {WINDOWS.map((w) => (
            <button
              key={w.v}
              type="button"
              onClick={() => setWindow(w.v)}
              className={cn(
                "rounded-sm px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider transition-colors",
                window === w.v
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-md border border-dashed border-border bg-card p-6 text-center text-xs text-muted-foreground">
          Loading…
        </div>
      ) : data.length < 2 ? (
        <div className="rounded-md border border-dashed border-border bg-card p-6 text-center text-xs text-muted-foreground">
          Not enough history in this window yet — try a wider one, or come
          back as the 5-minute heartbeat accumulates readings.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t) => formatTick(t as number, window)}
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
                new Date(t as number).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
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
      )}
    </div>
  );
}

function formatTick(t: number, window: Window): string {
  const d = new Date(t);
  if (window === "1d") {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
