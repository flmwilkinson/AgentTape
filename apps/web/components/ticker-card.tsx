"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import type { AgentSummary } from "@/lib/api-client";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { Sparkline } from "@/components/sparkline";

// Compact agent card used in the ticker tape, the "Just Discovered"
// rail, and watchlists. Vertically the same height across all
// surfaces — a row of these has to align like a tape.

interface TickerCardProps {
  agent: AgentSummary;
  // Optional pre-computed delta + recent history for the sparkline.
  delta?: number | null;
  history?: number[];
  // Tape mode: tighter padding + no border (the tape already has one).
  variant?: "card" | "tape";
  className?: string;
}

export function TickerCard({
  agent,
  delta,
  history,
  variant = "card",
  className,
}: TickerCardProps) {
  const score = agent.score?.agent_score ?? null;
  return (
    <Link
      href={`/agents/${agent.slug}`}
      className={cn(
        "group block min-w-[220px] rounded-md transition-colors",
        variant === "card" &&
          "border border-border bg-card p-3 hover:border-foreground/20 hover:bg-subtle",
        variant === "tape" && "px-4 py-2",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {agent.discovered_via.replace(/_/g, " ")}
          </div>
          <div className="truncate text-sm font-medium text-foreground group-hover:text-primary">
            {agent.name}
          </div>
        </div>
        {delta !== undefined && delta !== null && (
          <MoverChip delta={delta} unit="score" variant="outline" />
        )}
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <NumberTick
          value={score}
          format={formatScore}
          className="text-stat-md font-semibold"
        />
        {history && history.length > 0 && (
          <Sparkline values={history} width={96} height={24} />
        )}
      </div>
    </Link>
  );
}
