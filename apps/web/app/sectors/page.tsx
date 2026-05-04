"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";

// /sectors — index of indexes. Rolls every capability/deployment/
// maturity tag into a single row showing how the cohort's average
// AgentScore moved over the window. Verdict (booming / steady /
// declining) is the headline number a reader takes away.
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

type Verdict =
  | "booming"
  | "growing"
  | "steady"
  | "cooling"
  | "declining"
  | "no_history";

const VERDICT_TONE: Record<Verdict, { tone: string; label: string }> = {
  booming: { tone: "text-gain", label: "Booming" },
  growing: { tone: "text-gain", label: "Growing" },
  steady: { tone: "text-muted-foreground", label: "Steady" },
  cooling: { tone: "text-loss", label: "Cooling" },
  declining: { tone: "text-loss", label: "Declining" },
  no_history: { tone: "text-muted-foreground", label: "—" },
};

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
          Average AgentScore for every cohort, plus how it's moved.
          Compare capabilities, deployment shapes, and maturity tiers
          side by side — the row verdict is the headline answer.
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Toggle
          label="Slice"
          value={kind}
          onChange={(v) => setKind(v as Kind)}
          options={KINDS.map((k) => ({ v: k.v, label: k.label }))}
        />
        <Toggle
          label="Window"
          value={window}
          onChange={(v) => setWindow(v as Window)}
          options={WINDOWS.map((w) => ({ v: w.v, label: w.label }))}
        />
      </div>

      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full min-w-[640px] text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-left">Sector</th>
              <th className="px-3 py-2 text-right">Members</th>
              <th className="px-3 py-2 text-right">Avg score</th>
              <th className="px-3 py-2 text-right">Δ {window}</th>
              <th className="px-3 py-2 text-right">Verdict</th>
              <th className="px-3 py-2"></th>
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
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  No sectors yet — agents need tags before this page can
                  populate. The discovery service will fill them in.
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const tone = VERDICT_TONE[r.verdict];
              const Arrow =
                r.delta == null
                  ? Minus
                  : r.delta >= 0.5
                    ? ArrowUpRight
                    : r.delta <= -0.5
                      ? ArrowDownRight
                      : Minus;
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
                    {r.avg_now == null ? "—" : r.avg_now.toFixed(1)}
                  </td>
                  <td className={cn("px-3 py-2 text-right font-mono", tone.tone)}>
                    {r.delta == null
                      ? "—"
                      : `${r.delta >= 0 ? "+" : ""}${r.delta.toFixed(2)}`}
                  </td>
                  <td className={cn("px-3 py-2 text-right", tone.tone)}>
                    <span className="inline-flex items-center gap-1.5">
                      <Arrow className="h-3.5 w-3.5" />
                      <span className="font-mono text-xs uppercase tracking-wider">
                        {tone.label}
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/search?kind=${kind}&value=${r.value}`}
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

function Toggle({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { v: string; label: string }[];
}) {
  return (
    <label className="inline-flex items-center gap-2">
      <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="inline-flex rounded-md border border-border bg-card p-0.5">
        {options.map((o) => (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              "rounded-sm px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors",
              value === o.v
                ? "bg-subtle text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        ))}
      </span>
    </label>
  );
}
