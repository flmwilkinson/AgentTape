"use client";

import Link from "next/link";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import type { AgentSummary } from "@/lib/api-client";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { Sparkline } from "@/components/sparkline";

// Mobile-first watchlist row — full bleed, big tap target, sparkline
// inline. The drag handle is rendered for visual affordance; actual
// reordering interaction is wired by the parent page when present.

interface WatchlistRowProps {
  agent: AgentSummary;
  delta?: number | null;
  history?: number[];
  draggable?: boolean;
  className?: string;
}

export function WatchlistRow({
  agent,
  delta,
  history,
  draggable = false,
  className,
}: WatchlistRowProps) {
  return (
    <Link
      href={`/agents/${agent.slug}`}
      className={cn(
        "flex items-center gap-3 border-b border-border px-3 py-3 transition-colors hover:bg-subtle md:px-4",
        className,
      )}
    >
      {draggable && (
        <span className="touch-none text-muted-foreground/60">
          <GripVertical className="h-4 w-4" />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{agent.name}</div>
        <div className="truncate font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {agent.discovered_via.replace(/_/g, " ")}
        </div>
      </div>
      <Sparkline values={history ?? []} width={72} height={22} />
      <div className="flex flex-col items-end gap-1">
        <NumberTick
          value={agent.score?.agent_score ?? null}
          format={formatScore}
          className="text-sm font-semibold"
        />
        {delta !== undefined && delta !== null && (
          <MoverChip delta={delta} unit="score" variant="outline" />
        )}
      </div>
    </Link>
  );
}
