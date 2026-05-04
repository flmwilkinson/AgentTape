"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api, type AgentSummary } from "@/lib/api-client";
import { useWebSocket, type WsFrame } from "@/lib/ws";
import { formatScore, relativeTime } from "@/lib/format";

// /discovery — the autonomous-discovery brag.
// Server-rendered initial paint via TanStack Query, plus a WS feed
// that prepends new admissions as they happen.

export default function DiscoveryPage() {
  const { data: initial } = useQuery({
    queryKey: ["recent-discoveries"],
    queryFn: () => api.recentDiscoveries(30),
  });
  const [stream, setStream] = useState<AgentSummary[]>([]);

  const { connected } = useWebSocket({
    path: "/ws/ticker",
    onFrame: async (frame: WsFrame) => {
      if (frame.type !== "event") return;
      const ev = frame.event as { kind?: string; agent_slug?: string };
      if (ev.kind !== "agent_admitted" || !ev.agent_slug) return;
      // Pull the freshly-admitted agent's summary.
      try {
        const detail = await api.getAgent(ev.agent_slug);
        setStream((cur) => [
          { ...detail },
          ...cur.filter((c) => c.slug !== ev.agent_slug),
        ].slice(0, 30));
      } catch {
        /* swallow */
      }
    },
  });

  // Merge: live first (newest), then initial. De-dupe by slug.
  const seen = new Set<string>();
  const merged = [...stream, ...(initial ?? [])].filter((a) => {
    if (seen.has(a.slug)) return false;
    seen.add(a.slug);
    return true;
  });

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Discovery feed
          </div>
          <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
            Agents are appearing here without us telling them to.
          </h1>
          <p className="mt-2 max-w-prose text-sm text-muted-foreground">
            The discovery service scans GitHub, Hugging Face, MCP registries,
            npm/PyPI, arXiv, and Hacker News on its own schedule.
            Admitted agents land here first.
          </p>
        </div>
        <div className="hidden md:inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
          {connected ? (
            <Wifi className="h-3.5 w-3.5 text-gain" />
          ) : (
            <WifiOff className="h-3.5 w-3.5 text-loss" />
          )}
          {connected ? "Live" : "Reconnecting"}
        </div>
      </div>

      <ol className="space-y-2">
        {merged.length === 0 && (
          <li className="rounded-md border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
            Waiting for the first admission…
          </li>
        )}
        {merged.map((a) => (
          <li
            key={a.slug}
            className="grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-md border border-border bg-card px-4 py-3"
          >
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {a.discovered_via.replace(/_/g, " ")}
            </span>
            <Link
              href={`/agents/${a.slug}`}
              className="min-w-0"
            >
              <div className="truncate text-sm font-medium hover:text-primary">
                {a.name}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                {a.description ?? a.github_repo ?? a.slug}
              </div>
            </Link>
            <div className="flex flex-col items-end gap-0.5">
              <span className="num text-sm font-semibold">
                {formatScore(a.score?.agent_score ?? null)}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {relativeTime(a.discovered_at)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
