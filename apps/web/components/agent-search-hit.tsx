"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import type { AgentSummary } from "@/lib/api-client";
import { Sparkline } from "@/components/sparkline";

// One row in the search-results list. Dense + scannable — sparkline
// on every row is the rule, even when we don't yet have the data
// (the empty Sparkline preserves row height so the list doesn't
// jitter while sparklines load in).

interface AgentSearchHitProps {
  agent: AgentSummary;
  similarity?: number | null;
  history?: number[];
  className?: string;
}

export function AgentSearchHit({
  agent,
  similarity,
  history,
  className,
}: AgentSearchHitProps) {
  return (
    <Link
      href={`/agents/${agent.slug}`}
      className={cn(
        "group grid grid-cols-[1fr_auto_120px_64px] items-center gap-4 px-3 py-3 transition-colors hover:bg-subtle",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="truncate text-sm font-medium text-foreground group-hover:text-primary">
            {agent.name}
          </div>
          <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {agent.description ?? agent.github_repo ?? agent.slug}
        </div>
      </div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {agent.discovered_via.replace(/_/g, " ")}
      </div>
      <Sparkline values={history ?? []} width={120} height={24} />
      <div className="text-right num text-sm font-semibold">
        {formatScore(agent.score?.agent_score ?? null)}
        {similarity !== null && similarity !== undefined && (
          <div className="num text-[10px] text-muted-foreground">
            {(similarity * 100).toFixed(0)}% match
          </div>
        )}
      </div>
    </Link>
  );
}
