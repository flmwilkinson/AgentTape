"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";

const WINDOWS = ["1h", "1d", "7d", "30d"] as const;

export default function MoversPage() {
  const [window, setWindow] = useState<(typeof WINDOWS)[number]>("1d");
  const { data: rows, isLoading } = useQuery({
    queryKey: ["movers", window],
    queryFn: () => api.movers(window, 50),
  });

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Movers
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Biggest score moves.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Sorted by absolute change in AgentScore over the window.
        </p>
      </div>

      <div className="mb-4 inline-flex rounded-md border border-border bg-card p-0.5">
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

      <div className="overflow-hidden rounded-md border border-border bg-card">
        <table className="num w-full text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-4 py-2 text-left">Agent</th>
              <th className="px-4 py-2 text-right">Score</th>
              <th className="px-4 py-2 text-right">Δ</th>
              <th className="px-4 py-2 text-right">Window start</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && rows?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  No movers in this window.
                </td>
              </tr>
            )}
            {rows?.map((m) => (
              <tr
                key={m.agent.slug}
                className="border-b border-border last:border-b-0"
              >
                <td className="px-4 py-2">
                  <Link
                    href={`/agents/${m.agent.slug}`}
                    className="font-sans font-medium hover:text-primary"
                  >
                    {m.agent.name}
                  </Link>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {m.agent.discovered_via.replace(/_/g, " ")}
                  </div>
                </td>
                <td className="px-4 py-2 text-right font-semibold">
                  {formatScore(m.score_now)}
                </td>
                <td className="px-4 py-2 text-right">
                  <MoverChip delta={m.delta} unit="score" />
                </td>
                <td className="px-4 py-2 text-right text-muted-foreground">
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
