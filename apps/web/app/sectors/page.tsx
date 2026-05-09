"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { api } from "@/lib/api-client";
import { TableSkeleton } from "@/components/skeleton";
import { ToggleGroup } from "@/components/toggle-group";

// /sectors — index of indexes. Rolls every capability/deployment/
// maturity tag into a single row showing the cohort's average
// AgentScore plus a tiny up/down arrow indicating whether it's
// trending over the selected window.
//
// Why three slicers? Because "is coding hot right now?" and "is
// CLI-deployed agents hot right now?" are different questions and a
// reader cares about both. Maturity is the third axis since stable
// vs experimental moves in different rhythms.

const KINDS = [
  { v: "capability", label: "Capability" },
  { v: "deployment", label: "Deployment" },
  { v: "maturity", label: "Maturity" },
] as const;

const WINDOWS = [
  { v: "1d", label: "1d" },
  { v: "7d", label: "7d" },
  { v: "30d", label: "30d" },
] as const;

type Kind = (typeof KINDS)[number]["v"];
type Window = (typeof WINDOWS)[number]["v"];

export default function SectorsPage() {
  const [kind, setKind] = useState<Kind>("capability");
  const [window, setWindow] = useState<Window>("7d");

  const { data, isLoading } = useQuery({
    queryKey: ["sectors", kind, window],
    queryFn: () => api.sectors(kind, window),
  });

  const rows = data ?? [];

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-6">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Sectors
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Where the heat is.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Average AgentScore for every cohort. Compare capabilities,
          deployment shapes, and maturity tiers side by side — the
          arrow next to each score shows the move over the window.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ToggleGroup
          label="Slice"
          value={kind}
          onChange={(v) => setKind(v as Kind)}
          options={KINDS.map((k) => ({ v: k.v, label: k.label }))}
        />
        <ToggleGroup
          label="Window"
          value={window}
          onChange={(v) => setWindow(v as Window)}
          options={WINDOWS.map((w) => ({ v: w.v, label: w.label }))}
        />
      </div>

      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left">Sector</th>
              <th className="px-3 py-2 text-right">Members</th>
              <th className="px-3 py-2 text-right">Avg score</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <TableSkeleton rows={6} cols={4} />}
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                  No sectors yet — agents need tags before this page can
                  populate. The discovery service will fill them in.
                </td>
              </tr>
            )}
            {rows.map((r) => {
              // Tiny inline arrow encodes direction over the selected
              // window. Threshold of |0.5| filters out flat noise so a
              // sector reading "0.04 vs last week" doesn't look like a
              // gainer. No arrow when there's no history yet.
              const dir =
                r.delta == null || Math.abs(r.delta) < 0.5
                  ? null
                  : r.delta > 0
                    ? "up"
                    : "down";
              return (
                <tr
                  key={r.value}
                  className="border-b border-border last:border-b-0"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium">{r.display_name}</div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {kind} · {r.value}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground">
                    {r.members}
                  </td>
                  <td className="px-3 py-2 text-right font-semibold">
                    <span className="inline-flex items-center justify-end gap-1.5">
                      <span>{r.avg_now == null ? "—" : r.avg_now.toFixed(1)}</span>
                      {dir === "up" && (
                        <ArrowUp className="h-3.5 w-3.5 text-gain" />
                      )}
                      {dir === "down" && (
                        <ArrowDown className="h-3.5 w-3.5 text-loss" />
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/sectors/${kind}/${r.value}`}
                      className="text-[11px] font-mono uppercase tracking-wider text-primary hover:underline"
                    >
                      Drill in →
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

