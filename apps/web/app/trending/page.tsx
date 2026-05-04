"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";

// /trending — biggest movers over a window, with rank-movement arrows
// alongside score deltas. Two filters: time window (1h/1d/7d/30d) and
// kind (application / foundation_model / all). The combination is the
// canonical query for "what's heating up in this category right now".

const WINDOWS = ["1h", "1d", "7d", "30d"] as const;
const KINDS = [
  { v: "all", label: "All" },
  { v: "application", label: "Apps" },
  { v: "foundation_model", label: "Models" },
] as const;

export default function TrendingPage() {
  const [window, setWindow] = useState<(typeof WINDOWS)[number]>("1d");
  const [kind, setKind] = useState<(typeof KINDS)[number]["v"]>("all");
  const { data: rows, isLoading } = useQuery({
    queryKey: ["movers", window],
    queryFn: () => api.movers(window, 100),
  });

  const filtered = useMemo(() => {
    if (!rows) return [];
    if (kind === "all") return rows;
    return rows.filter((m) => m.agent.entity_kind === kind);
  }, [rows, kind]);

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Trending
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Biggest moves.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Sorted by absolute AgentScore change over the window. The arrow
          column shows rank-movement in the last 24 hours within the kind
          (apps vs foundation models compete in their own ladders).
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setWindow(w)}
              className={cn(
                "rounded-sm px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors",
                window === w
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {w}
            </button>
          ))}
        </div>
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {KINDS.map((k) => (
            <button
              key={k.v}
              type="button"
              onClick={() => setKind(k.v)}
              className={cn(
                "rounded-sm px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors",
                kind === k.v
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border bg-card">
        <table className="num w-full text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-right">#</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-right">24h</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Δ {window}</th>
              <th className="px-3 py-2 text-right hidden md:table-cell">Window start</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No movers in this window.
                </td>
              </tr>
            )}
            {filtered.map((m) => (
              <tr
                key={m.agent.slug}
                className="border-b border-border last:border-b-0"
              >
                <td className="px-3 py-2 text-right text-muted-foreground">
                  {m.agent.score?.rank_now ?? "—"}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/agents/${m.agent.slug}`}
                    className="font-sans font-medium hover:text-primary"
                  >
                    {m.agent.name}
                  </Link>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {m.agent.entity_kind === "foundation_model" ? "model" : "app"}
                    {" · "}
                    {m.agent.discovered_via.replace(/_/g, " ")}
                  </div>
                </td>
                <td className="px-3 py-2 text-right">
                  <RankArrow
                    delta={m.agent.score?.rank_delta_24h ?? null}
                    rankNow={m.agent.score?.rank_now ?? null}
                  />
                </td>
                <td className="px-3 py-2 text-right font-semibold">
                  {formatScore(m.score_now)}
                </td>
                <td className="px-3 py-2 text-right">
                  <MoverChip delta={m.delta} unit="score" />
                </td>
                <td className="px-3 py-2 text-right text-muted-foreground hidden md:table-cell">
                  {m.score_at_window_start === null
                    ? "—"
                    : formatScore(m.score_at_window_start)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
