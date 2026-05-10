"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type AgentSummary } from "@/lib/api-client";
import { useWebSocket, type WsFrame } from "@/lib/ws";
import { formatScore, relativeTime } from "@/lib/format";
import { WatchToggle } from "@/components/watch-toggle";

// /new — the autonomous-discovery brag.
// Server-rendered initial paint via TanStack Query, plus a WS feed
// that prepends new admissions as they happen. We don't surface a
// "Live / Reconnecting" pill on this page anymore — the WebSocket
// reconnects on every navigation and the pill flashed in and out
// constantly, which read as broken rather than alive. Page freshness
// is communicated by the relative-time stamp on each row instead.

type Kind = "all" | "application" | "foundation_model";

const KINDS: { v: Kind; label: string }[] = [
  { v: "all", label: "All" },
  { v: "application", label: "Applications" },
  { v: "foundation_model", label: "Foundation models" },
];

export default function DiscoveryPage() {
  const [kind, setKind] = useState<Kind>("all");
  const { data: initial } = useQuery({
    queryKey: ["recent-discoveries", kind],
    queryFn: () =>
      api.recentDiscoveries(
        30,
        kind === "all" ? undefined : kind,
      ),
  });
  const [stream, setStream] = useState<AgentSummary[]>([]);

  // Subscribe but ignore connection state: we only react to event
  // frames. If the WS drops, the next visit will pull fresh data via
  // useQuery and refresh on its own, no UI affordance needed.
  useWebSocket({
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

  // Merge: live first (newest), then initial. De-dupe by slug. Apply
  // the Kind filter to the merged stream too — the WS feed produces
  // both kinds, so without this the filter would only catch the
  // server-rendered slice.
  const seen = new Set<string>();
  const merged = [...stream, ...(initial ?? [])].filter((a) => {
    if (seen.has(a.slug)) return false;
    seen.add(a.slug);
    if (kind !== "all" && a.entity_kind !== kind) return false;
    return true;
  });

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-8">
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

      <div className="mb-4 inline-flex rounded-md border border-border bg-card p-0.5">
        {KINDS.map((k) => (
          <button
            key={k.v}
            type="button"
            onClick={() => setKind(k.v)}
            className={`rounded-sm px-3 py-1 text-xs font-mono uppercase tracking-wider transition-colors ${
              kind === k.v
                ? "bg-subtle text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {k.label}
          </button>
        ))}
      </div>

      <ol className="space-y-2">
        {merged.length === 0 && (
          <li className="rounded-md border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
            Waiting for the first admission…
          </li>
        )}
        {merged.map((a) => (
          <li
            key={`${a.slug}-${a.id}`}
            className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 rounded-md border border-border bg-card px-3 py-3 md:gap-4 md:px-4"
          >
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground hidden sm:inline">
              {a.discovered_via.replace(/_/g, " ")}
            </span>
            <Link
              href={`/agents/${a.slug}`}
              className="min-w-0 col-start-1 row-start-1 sm:col-start-auto"
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
            <WatchToggle slug={a.slug} size="sm" />
          </li>
        ))}
      </ol>
    </div>
  );
}
