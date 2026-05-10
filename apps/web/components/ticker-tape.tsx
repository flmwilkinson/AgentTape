"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, Wifi, WifiOff } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { formatScore } from "@/lib/format";
import type { AgentSummary } from "@/lib/api-client";
import { useWebSocket, type WsFrame } from "@/lib/ws";

// The horizontal scrolling tape across the top of the dashboard.
// Cards loop infinitely (the row is duplicated and the inner track
// translates -50% so the seam is invisible). Hovering pauses the scroll.
//
// Live updates: the dashboard's /ws/ticker connection feeds back into
// here, and any signal_changed event for an agent in the tape causes
// that cell to re-render with a fresh value. We don't try to remount
// the whole tape — just the cell.

interface TickerTapeProps {
  initial: AgentSummary[];
}

type LiveScores = Record<string, number>;

interface TapeCellProps {
  agent: AgentSummary;
  scores: LiveScores;
  ariaHidden?: boolean;
}

function TapeCell({ agent, scores, ariaHidden = false }: TapeCellProps) {
  const live = scores[agent.slug];
  const initialScore = agent.score?.agent_score ?? 0;
  const delta = live === undefined ? 0 : live - initialScore;
  const sign = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  return (
    <Link
      href={`/agents/${agent.slug}`}
      tabIndex={ariaHidden ? -1 : undefined}
      aria-hidden={ariaHidden ? true : undefined}
      className="flex shrink-0 items-center gap-3 border-r border-border/60 px-4 py-2 hover:bg-subtle"
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        {agent.slug.slice(0, 18)}
      </span>
      <span className="num text-sm font-semibold text-foreground">
        {formatScore(live ?? initialScore)}
      </span>
      <span
        className={cn(
          "inline-flex items-center gap-0.5 text-[11px] num",
          sign === "up" && "text-gain",
          sign === "down" && "text-loss",
          sign === "flat" && "text-muted-foreground",
        )}
      >
        {sign === "up" && <ArrowUp className="h-2.5 w-2.5" strokeWidth={3} />}
        {sign === "down" && <ArrowDown className="h-2.5 w-2.5" strokeWidth={3} />}
        {Math.abs(delta).toFixed(2)}
      </span>
    </Link>
  );
}

export function TickerTape({ initial }: TickerTapeProps) {
  // Latest score per slug, seeded from server data and updated by WS.
  const [scores, setScores] = useState<LiveScores>(() =>
    Object.fromEntries(
      initial.map((a) => [a.slug, a.score?.agent_score ?? 0]),
    ),
  );

  const { connected } = useWebSocket({
    path: "/ws/ticker",
    onFrame: (frame: WsFrame) => {
      if (frame.type !== "event") return;
      const ev = frame.event as { agent_slug?: string; agent_score?: number };
      if (!ev.agent_slug || ev.agent_score == null) return;
      setScores((prev) =>
        prev[ev.agent_slug!] === ev.agent_score
          ? prev
          : { ...prev, [ev.agent_slug!]: ev.agent_score! },
      );
    },
  });

  // Render the row twice so the marquee has no visible seam.
  return (
    <div className="relative w-full overflow-hidden border-b border-border bg-card">
      {/* Live/Not-Live indicator is desktop-only. On mobile the icon
          flashed in and out every page navigation as the WebSocket
          re-handshook, which read as broken rather than alive. */}
      <div className="absolute right-3 top-1.5 z-10 hidden items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground md:flex">
        {connected ? (
          <Wifi className="h-3 w-3 text-gain" />
        ) : (
          <WifiOff className="h-3 w-3 text-loss" />
        )}
        Live
      </div>
      <div className="tape-pause">
        <div
          className="tape-track flex w-max items-stretch gap-0 will-change-transform"
          aria-label="Live AgentScore tape"
        >
          {/* Two copies are needed for the seamless marquee loop —
              the CSS animation translates -50%, so the second copy
              has to be there to fill the right side as the first
              scrolls off. We mark the second copy aria-hidden and
              non-focusable so screen readers only read each agent
              once and tab order doesn't go through duplicates twice. */}
          {initial.map((agent, idx) => (
            <TapeCell
              key={`a-${agent.slug}-${idx}`}
              agent={agent}
              scores={scores}
            />
          ))}
          <div aria-hidden="true" className="contents">
            {initial.map((agent, idx) => (
              <TapeCell
                key={`b-${agent.slug}-${idx}`}
                agent={agent}
                scores={scores}
                ariaHidden
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
