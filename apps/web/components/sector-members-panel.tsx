"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CompareTrayToggle } from "@/components/compare-tray";
import { Dropdown } from "@/components/dropdown";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// Note: Link is used for the agent name links inside the table rows.

// Filterable + multi-selectable member list for the sector detail
// page. Filter state and selection state both live in the URL so
// they survive sharing, refresh, and the browser back button.
//
// URL params used:
//   ?license=mit&deployment=cli&maturity=stable
//   ?compare=slug1,slug2,slug3   (up to 5)
//
// Filter rule: agents missing a tag for a given axis match "Any" but
// are filtered out only when a non-empty value is selected. Missing
// data never silently drops a row.

const LICENSES = [
  { value: "", label: "Any" },
  { value: "mit", label: "MIT" },
  { value: "apache-2.0", label: "Apache 2.0" },
  { value: "bsd", label: "BSD" },
  { value: "agpl", label: "AGPL" },
  { value: "gpl", label: "GPL" },
  { value: "mpl", label: "MPL" },
  { value: "proprietary", label: "Proprietary" },
];

const DEPLOYMENTS = [
  { value: "", label: "Any" },
  { value: "cli", label: "CLI" },
  { value: "library", label: "Library" },
  { value: "saas", label: "SaaS" },
  { value: "ide-plugin", label: "IDE plugin" },
  { value: "browser-extension", label: "Browser ext" },
  { value: "mcp-server", label: "MCP server" },
  { value: "self-hosted", label: "Self-hosted" },
];

const MATURITIES = [
  { value: "", label: "Any" },
  { value: "stable", label: "Stable" },
  { value: "beta", label: "Beta" },
  { value: "experimental", label: "Experimental" },
];

interface Props {
  members: AgentSummary[];
}

export function SectorMembersPanel({ members }: Props) {
  const router = useRouter();
  const params = useSearchParams();

  const license = params.get("license") ?? "";
  const deployment = params.get("deployment") ?? "";
  const maturity = params.get("maturity") ?? "";

  const setParam = (key: string, value: string) => {
    const cur = new URLSearchParams(params.toString());
    if (value) cur.set(key, value);
    else cur.delete(key);
    router.replace(`?${cur.toString()}`, { scroll: false });
  };

  // Filtering: an agent matches the filter if (a) the filter is empty
  // (Any) or (b) the agent has at least one tag with the matching
  // kind+value. Agents with no tag of that kind don't get filtered out
  // unless the user picks a non-empty value.
  const filtered = useMemo(() => {
    return members.filter((a) => {
      const has = (kind: string, value: string) =>
        !value ||
        (a.tags ?? []).some((t) => t.kind === kind && t.value === value);
      return (
        has("license", license) &&
        has("deployment", deployment) &&
        has("maturity", maturity)
      );
    });
  }, [members, license, deployment, maturity]);

  const anyFilter = Boolean(license || deployment || maturity);

  return (
    <section>
      <div className="mb-3">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Members
        </div>
        <div className="text-xs text-muted-foreground">
          {filtered.length} of {members.length} shown · ranked by AgentScore
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Dropdown
          label="License"
          value={license}
          onChange={(v) => setParam("license", v)}
          options={LICENSES}
        />
        <Dropdown
          label="Deployment"
          value={deployment}
          onChange={(v) => setParam("deployment", v)}
          options={DEPLOYMENTS}
        />
        <Dropdown
          label="Maturity"
          value={maturity}
          onChange={(v) => setParam("maturity", v)}
          options={MATURITIES}
        />
        {anyFilter && (
          <button
            type="button"
            onClick={() => {
              setParam("license", "");
              setParam("deployment", "");
              setParam("maturity", "");
            }}
            className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            Clear filters
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="num w-full min-w-[680px] text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 w-9"></th>
              <th className="px-3 py-2 text-right">Rank</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-right">24h</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Δ24h</th>
              <th className="px-3 py-2 w-8"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-xs text-muted-foreground">
                  No agents match these filters. Try clearing one.
                </td>
              </tr>
            )}
            {filtered.map((a, i) => {
              const license = (a.tags ?? []).find((t) => t.kind === "license")?.value;
              const deployment = (a.tags ?? []).find((t) => t.kind === "deployment")?.value;
              return (
                <tr key={a.id} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2 text-center">
                    <CompareTrayToggle slug={a.slug} />
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                    #{a.score?.rank_now ?? i + 1}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/agents/${a.slug}`}
                      className="font-sans font-medium hover:text-primary"
                    >
                      {a.name}
                    </Link>
                    <div className="mt-0.5 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
                      {license && (
                        <span className="rounded-sm border border-border bg-subtle px-1.5 py-0.5 font-mono">
                          {license}
                        </span>
                      )}
                      {deployment && (
                        <span className="rounded-sm border border-border bg-subtle px-1.5 py-0.5 font-mono">
                          {deployment}
                        </span>
                      )}
                      {a.description && (
                        <span className="line-clamp-1 normal-case">
                          {a.description}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <RankArrow
                      delta={a.score?.rank_delta_24h ?? null}
                      rankNow={a.score?.rank_now ?? null}
                    />
                  </td>
                  <td className="px-3 py-2 text-right font-semibold">
                    {formatScore(a.score?.agent_score ?? null)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {a.score?.delta_24h != null ? (
                      <MoverChip
                        delta={a.score.delta_24h}
                        unit="score"
                        variant="outline"
                      />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <WatchToggle slug={a.slug} size="sm" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </section>
  );
}
