"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { Dropdown } from "@/components/dropdown";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// /trending — biggest movers over a window with three orthogonal
// filters (window / kind / capability or deployment). Tag filters
// are pushed to the API so the limit is applied AFTER the filter
// (otherwise the slice gets truncated to whatever happens to land
// in the top-N before tag matching).

const WINDOWS = ["1h", "1d", "7d", "30d"] as const;
const KINDS = [
  { v: "all", label: "All" },
  { v: "application", label: "Agents" },
  { v: "foundation_model", label: "Models" },
] as const;

const CAPABILITIES = [
  { v: "", label: "Any" },
  { v: "code-generation", label: "Code" },
  { v: "browsing", label: "Browser" },
  { v: "research", label: "Research" },
  { v: "rag", label: "RAG" },
  { v: "multi-agent", label: "Multi-agent" },
  { v: "automation", label: "Automation" },
  { v: "tool-use", label: "Tool use" },
  { v: "memory", label: "Memory" },
  { v: "vision", label: "Vision" },
  { v: "voice", label: "Voice" },
] as const;

const DEPLOYMENTS = [
  { v: "", label: "Any" },
  { v: "library", label: "Library" },
  { v: "cli", label: "CLI" },
  { v: "saas", label: "SaaS" },
  { v: "ide-plugin", label: "IDE plugin" },
  { v: "browser-extension", label: "Browser ext" },
  { v: "mcp-server", label: "MCP" },
] as const;

export default function TrendingPage() {
  const [window, setWindow] = useState<(typeof WINDOWS)[number]>("1d");
  const [kind, setKind] = useState<(typeof KINDS)[number]["v"]>("all");
  const [capability, setCapability] = useState<string>("");
  const [deployment, setDeployment] = useState<string>("");

  const { data: rows, isLoading } = useQuery({
    queryKey: ["movers", window, kind, capability, deployment],
    queryFn: () =>
      api.movers(window, 100, {
        capability: capability || undefined,
        deployment: deployment || undefined,
        entity_kind:
          kind === "application"
            ? "application"
            : kind === "foundation_model"
              ? "foundation_model"
              : undefined,
      }),
  });

  const list = rows ?? [];

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
          Ranked by absolute AgentScore change over the window. Filter by kind,
          capability, or deployment to slice the moves you actually care about.
          The arrow column is rank-movement in the last 24 hours within the
          kind (agents vs foundation models keep separate ladders).
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Toggle
          label="Window"
          value={window}
          onChange={(v) => setWindow(v as (typeof WINDOWS)[number])}
          options={WINDOWS.map((w) => ({ v: w, label: w }))}
        />
        <Toggle
          label="Kind"
          value={kind}
          onChange={(v) => setKind(v as (typeof KINDS)[number]["v"])}
          options={KINDS.map((k) => ({ v: k.v, label: k.label }))}
        />
        <Dropdown
          label="Capability"
          value={capability}
          onChange={setCapability}
          options={CAPABILITIES.map((c) => ({ value: c.v, label: c.label }))}
        />
        <Dropdown
          label="Deployment"
          value={deployment}
          onChange={setDeployment}
          options={DEPLOYMENTS.map((d) => ({ value: d.v, label: d.label }))}
        />
        {(capability || deployment || kind !== "all") && (
          <button
            type="button"
            onClick={() => {
              setCapability("");
              setDeployment("");
              setKind("all");
            }}
            className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full min-w-[640px] text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-right">Rank</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-right">24h</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Δ {window}</th>
              <th className="px-3 py-2 text-right hidden md:table-cell">Window start</th>
              <th className="px-3 py-2 w-8"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                  Loading…
                </td>
              </tr>
            )}
            {!isLoading && list.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                  No movers match these filters in this window.
                </td>
              </tr>
            )}
            {list.map((m) => (
              <tr
                key={`${m.agent.slug}-${m.agent.id}`}
                className="border-b border-border last:border-b-0"
              >
                <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                  {m.agent.score?.rank_now != null
                    ? `#${m.agent.score.rank_now}`
                    : "—"}
                </td>
                <td className="px-3 py-2">
                  <Link
                    href={`/agents/${m.agent.slug}`}
                    className="font-sans font-medium hover:text-primary"
                  >
                    {m.agent.name}
                  </Link>
                  <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {m.agent.entity_kind === "foundation_model" ? "model" : "agent"}
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
                <td className="px-3 py-2 text-right">
                  <WatchToggle slug={m.agent.slug} size="sm" />
                </td>
              </tr>
            ))}
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

