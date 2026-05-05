"use client";

import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api, type SignalSeries } from "@/lib/api-client";
import { SignalChart } from "@/components/signal-chart";

// Time-series chart + "Show Your Work" CSV download. Every signal we
// have data for becomes a visible series on first paint — the user
// asked why some weren't showing up; the answer was that the panel
// hid them behind toggles. Toggle-off remains available for noise
// reduction; default-on is the right answer.

interface Props {
  slug: string;
  initial: SignalSeries[];
  entityKind?: string;
}

export function AgentSignalPanel({ slug, initial, entityKind }: Props) {
  const [window, setWindow] = useState<"7d" | "30d" | "90d" | "all">("30d");
  const { data: series } = useQuery({
    queryKey: ["agent-signals", slug, window],
    queryFn: () => api.agentSignals(slug, { window }),
    initialData: initial,
    staleTime: 15_000,
  });

  const sources = useMemo(() => series.map((s) => s.source), [series]);
  // Every available signal lights up by default. Users toggle off for
  // noise reduction; nothing should be hidden on first paint.
  const [active, setActive] = useState<string[]>(() =>
    initial.map((s) => s.source),
  );

  // Foundation models score from OpenRouter metadata (context, price,
  // modality, provider tier), not GitHub/HF/Reddit time-series signals.
  // The empty signal panel for FMs misleads readers into thinking the
  // ingestion pipeline is broken — render a clear handoff to the
  // facts panel instead.
  const isFM = entityKind === "foundation_model";
  if (isFM && sources.length === 0) {
    return (
      <div className="rounded-md border border-border bg-card p-4">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Signals
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Foundation models don't accumulate the same time-series signals as
          application agents (stars, downloads, mentions). The score is
          derived from OpenRouter metadata — see <strong>Model facts</strong>{" "}
          above for the inputs and <strong>How this score was computed</strong>{" "}
          for the formula.
        </p>
      </div>
    );
  }

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
