"use client";

import { useState } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDeltaPct, formatScore } from "@/lib/format";
import type { AgentDetail } from "@/lib/api-client";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { PillarBar } from "@/components/pillar-bar";
import { useWebSocket, type WsFrame } from "@/lib/ws";

// The big-name + score + pillars block at the top of an agent ticker
// page. Wires /ws/agent/<slug> so numbers tick when scoring publishes
// a new score_changed event.

interface Props {
  agent: AgentDetail;
}

export function AgentLiveHeader({ agent }: Props) {
  const [score, setScore] = useState(agent.score);
  const { connected } = useWebSocket({
    path: `/ws/agent/${agent.slug}`,
    onFrame: (frame: WsFrame) => {
      if (frame.type !== "event") return;
      const ev = frame.event as Partial<typeof agent.score> & {
        kind?: string;
      };
      if (ev.kind !== "score_changed") return;
      setScore({
        agent_score: ev.agent_score ?? null,
        adoption: ev.adoption ?? null,
        quality: ev.quality ?? null,
        momentum: ev.momentum ?? null,
        community: ev.community ?? null,
        manipulation_resistance: ev.manipulation_resistance ?? null,
        computed_at: new Date().toISOString(),
      });
    },
  });

  const prior = agent.score?.agent_score ?? null;
  const now = score?.agent_score ?? null;
  const deltaPct = prior != null && now != null ? formatDeltaPct(now, prior) : "—";

  return (
    <div className="border-b border-border bg-card">
      <div className="container py-8 md:py-12">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {agent.discovered_via.replace(/_/g, " ")}
          </span>
          <span className="text-muted-foreground/50">·</span>
          <span className="text-[11px] text-muted-foreground">
            {agent.slug}
          </span>
          <span className="ml-auto inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
            {connected ? (
              <Wifi className="h-3 w-3 text-gain" />
            ) : (
              <WifiOff className="h-3 w-3 text-loss" />
            )}
            Live
          </span>
        </div>

        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          {agent.name}
        </h1>
        {agent.description && (
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
            {agent.description}
          </p>
        )}

        <div className="mt-8 grid gap-8 md:grid-cols-[auto_1fr]">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              AgentScore
            </div>
            <div className="mt-1 flex items-end gap-3">
              <NumberTick
                value={now}
                format={formatScore}
                className="text-stat-xl font-semibold"
                animateOnMount={false}
              />
              {prior != null && now != null && (
                <MoverChip delta={now - prior} unit="score" className="mb-1" />
              )}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              {deltaPct}{" "}
              <span className="text-muted-foreground/60">vs last recompute</span>
            </div>
          </div>
          <PillarBar
            score={{
              adoption: score?.adoption ?? null,
              quality: score?.quality ?? null,
              momentum: score?.momentum ?? null,
              community: score?.community ?? null,
            }}
            className="self-end"
          />
        </div>

        {agent.tags?.length > 0 && (
          <div className="mt-6 flex flex-wrap gap-1.5">
            {agent.tags.map((t) => (
              <span
                key={`${t.kind}:${t.value}`}
                className={cn(
                  "rounded-full border border-border bg-subtle px-2.5 py-0.5 text-[11px] text-muted-foreground",
                )}
                title={t.kind}
              >
                <span className="font-mono uppercase tracking-wider mr-1.5 text-muted-foreground/70">
                  {t.kind}
                </span>
                {t.display_name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
