"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";

// Per-pillar score history. Five lines on one chart:
//   - the headline (0–100, bold)
//   - adoption / quality / momentum / community (the four pillars)
// Window default is "all" — the user explicitly asked for "since
// initially listed", so the default range covers the agent's whole
// history. They can shrink it.

const WINDOWS = [
  { v: "7d", label: "7d" },
  { v: "30d", label: "30d" },
  { v: "90d", label: "90d" },
  { v: "all", label: "All" },
] as const;

type Window = (typeof WINDOWS)[number]["v"];

const SERIES = [
  { key: "agent_score", label: "AgentScore", color: "hsl(var(--foreground))", width: 2.5 },
  { key: "adoption", label: "Adoption", color: "hsl(var(--primary))", width: 1.5 },
  { key: "quality", label: "Quality", color: "hsl(var(--gain))", width: 1.5 },
  { key: "momentum", label: "Momentum", color: "hsl(var(--loss))", width: 1.5 },
  { key: "community", label: "Community", color: "hsl(var(--neutral))", width: 1.5 },
] as const;

interface Props {
  slug: string;
  className?: string;
}

export function AgentBreakdownChart({ slug, className }: Props) {
  const [window, setWindow] = useState<Window>("all");
  const { data, isLoading } = useQuery({
    queryKey: ["score-history", slug, window],
    queryFn: () => api.agentScoreHistory(slug, window),
  });

  const points = (data ?? []).map((p) => ({
    t: new Date(p.captured_at).getTime(),
    agent_score: p.agent_score,
    adoption: p.adoption,
    quality: p.quality,
    momentum: p.momentum,
    community: p.community,
  }));

  const noData = !isLoading && points.length < 2;

  return (
    <div className={cn("rounded-md border border-border bg-card", className)}>
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Score breakdown
          </div>
          <div className="text-[11px] text-muted-foreground">
            Headline plus the four pillars over time. Compare which pillar
            is doing the work behind the move.
          </div>
        </div>
        <div className="inline-flex rounded-md border border-border bg-background p-0.5">
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
      <div className="px-2 py-3">
        {noData ? (
          <div className="px-4 py-12 text-center text-xs text-muted-foreground">
            Only one score on file so far — the line shows up after the
            second recompute.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(t) => formatTick(t, window)}
                stroke="hsl(var(--muted-foreground))"
                fontSize={10}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                domain={[0, 100]}
                stroke="hsl(var(--muted-foreground))"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                width={28}
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
                  const num = typeof v === "number" ? v : null;
                  return [num == null ? "—" : num.toFixed(1), name as string];
                }}
              />
              <Legend
                iconType="line"
                wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
              />
              {SERIES.map((s) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label}
                  stroke={s.color}
                  strokeWidth={s.width}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function formatTick(t: number, window: Window): string {
  const d = new Date(t);
  if (window === "7d") {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
