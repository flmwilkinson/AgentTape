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

// Each signal is colour-coded by the pillar it primarily feeds, so
// reading the chart you immediately see which lines roll up to which
// pillar. Same hue families as the breakdown chart (Adoption=blue,
// Quality=green, Momentum=red, Community=slate). Within a pillar,
// lightness varies by index so multiple signals in the same family
// stay distinguishable.

type Pillar = "adoption" | "quality" | "momentum" | "community";

const SIGNAL_PILLAR: Record<string, Pillar> = {
  // adoption — raw "how many people use this" counts
  github_stars: "adoption",
  hf_downloads_30d: "adoption",
  npm_weekly: "adoption",
  pypi_monthly: "adoption",
  mcp_registry_listed: "adoption",
  stackoverflow_questions_7d: "adoption",
  producthunt_upvotes: "adoption",

  // quality — anything benchmark / citation shaped
  benchmark_score: "quality",
  arxiv_citations: "quality",

  // momentum — mention velocity and recent activity
  hn_mentions_7d: "momentum",
  reddit_mentions_7d: "momentum",
  bluesky_mentions_7d: "momentum",
  github_mentions_7d: "momentum",
  github_commits_7d: "momentum",

  // community — relationships and discussion depth
  github_contributors: "community",
  github_forks: "community",
  hn_points_7d: "community",
  reddit_points_7d: "community",
  hf_likes: "community",
  hf_trending_rank: "community",
};

const PILLAR_HSL: Record<
  Pillar,
  { hue: number; saturation: number; lightnesses: number[] }
> = {
  adoption: { hue: 217, saturation: 80, lightnesses: [42, 55, 65, 75] },
  quality: { hue: 142, saturation: 65, lightnesses: [38, 48, 58, 68] },
  momentum: { hue: 358, saturation: 70, lightnesses: [50, 60, 70, 80] },
  community: { hue: 215, saturation: 22, lightnesses: [45, 55, 65, 72] },
};

// Series colour is bound to the source name — not the array index —
// so toggling visibility doesn't reshuffle which line is which colour.
// Within a pillar, peers are ordered by their source name so the
// shade is stable across reloads.
function colorFor(source: string, allSources: string[]): string {
  const pillar = SIGNAL_PILLAR[source] ?? "adoption";
  const peers = allSources
    .filter((s) => (SIGNAL_PILLAR[s] ?? "adoption") === pillar)
    .sort();
  const idx = Math.max(0, peers.indexOf(source));
  const { hue, saturation, lightnesses } = PILLAR_HSL[pillar];
  const lightness = lightnesses[idx % lightnesses.length];
  return `hsl(${hue} ${saturation}% ${lightness}%)`;
}

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

  const allSources = series.map((s) => s.source);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap gap-2 text-xs">
        {series.map((s) => {
          const on = active.includes(s.source);
          const color = colorFor(s.source, allSources);
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
              cursor={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1, strokeDasharray: "3 3" }}
              isAnimationActive={false}
            />
            {series.map((s) =>
              active.includes(s.source) ? (
                <Line
                  key={s.source}
                  type="monotone"
                  dataKey={s.source}
                  name={s.source.replace(/_/g, " ")}
                  stroke={colorFor(s.source, allSources)}
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
