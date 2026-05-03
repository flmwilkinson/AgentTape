"use client";

import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api, type SignalSeries } from "@/lib/api-client";
import { SignalChart } from "@/components/signal-chart";

// Time-series chart + "Show Your Work" CSV download. We pre-pick a
// sensible default set of overlays from what's available so the chart
// has something on it on first paint.
const DEFAULT_VISIBLE = [
  "github_stars",
  "hf_downloads_30d",
  "hn_mentions_7d",
  "benchmark_score",
];

interface Props {
  slug: string;
  initial: SignalSeries[];
}

export function AgentSignalPanel({ slug, initial }: Props) {
  const [window, setWindow] = useState<"7d" | "30d" | "90d" | "all">("30d");
  const { data: series } = useQuery({
    queryKey: ["agent-signals", slug, window],
    queryFn: () => api.agentSignals(slug, { window }),
    initialData: initial,
    staleTime: 15_000,
  });

  const sources = useMemo(() => series.map((s) => s.source), [series]);
  const [active, setActive] = useState<string[]>(() =>
    initial
      .filter((s) => DEFAULT_VISIBLE.includes(s.source))
      .map((s) => s.source) ||
    initial.slice(0, 2).map((s) => s.source),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Signals
        </div>
        <div className="flex items-center gap-2">
          {(["7d", "30d", "90d", "all"] as const).map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setWindow(w)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-mono uppercase tracking-wider transition-colors",
                window === w
                  ? "border-foreground/30 bg-subtle text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {w}
            </button>
          ))}
          <a
            href={`/api/agents/${slug}/signals.csv?window=${window}`}
            className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <Download className="h-3 w-3" /> CSV
          </a>
        </div>
      </div>
      <SignalChart
        series={series}
        active={active}
        onToggle={(src) =>
          setActive((cur) =>
            cur.includes(src) ? cur.filter((s) => s !== src) : [...cur, src],
          )
        }
      />
      <div className="text-xs text-muted-foreground">
        {sources.length === 0
          ? "No signals recorded yet — ingestion will populate this within a tier interval."
          : `Show Your Work: ${sources.length} sources, ${series
              .reduce((acc, s) => acc + s.points.length, 0)
              .toLocaleString()} points.`}
      </div>
    </div>
  );
}
