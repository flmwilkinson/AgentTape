"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CompareTrayToggle } from "@/components/compare-tray";
import { Dropdown } from "@/components/dropdown";
import { MobileRankList, type MobileRankItem } from "@/components/mobile-rank-list";
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

// Pretty labels for known tag values. Anything not in this map falls
// back to a Title-Cased rendition of the slug-style value.
const PRETTY: Record<string, string> = {
  "mit": "MIT",
  "apache-2.0": "Apache 2.0",
  "agpl": "AGPL",
  "gpl": "GPL",
  "bsd": "BSD",
  "mpl": "MPL",
  "proprietary": "Proprietary",
  "cli": "CLI",
  "library": "Library",
  "saas": "SaaS",
  "ide-plugin": "IDE plugin",
  "browser-extension": "Browser ext",
  "mcp-server": "MCP server",
  "self-hosted": "Self-hosted",
  "stable": "Stable",
  "beta": "Beta",
  "experimental": "Experimental",
};

function prettyLabel(value: string): string {
  return (
    PRETTY[value] ??
    value
      .split("-")
      .map((s) => (s.length ? s[0].toUpperCase() + s.slice(1) : s))
      .join(" ")
  );
}

// Build the filter options actually present in this sector's agents,
// each with the count of matching agents. An option only appears if
// at least one agent has it; that way users never select a filter
// that empties the table.
function deriveOptions(
  members: AgentSummary[],
  kind: string,
): { value: string; label: string }[] {
  const counts = new Map<string, number>();
  for (const a of members) {
    for (const t of a.tags ?? []) {
      if (t.kind !== kind) continue;
      counts.set(t.value, (counts.get(t.value) ?? 0) + 1);
    }
  }
  if (counts.size === 0) return [];
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return [
    { value: "", label: "Any" },
    ...sorted.map(([value, n]) => ({
      value,
      label: `${prettyLabel(value)} · ${n}`,
    })),
  ];
}

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

  // Build dropdown options from the actual tag distribution in this
  // sector. A dropdown only renders if there are at least two options
  // (Any + one real value) — otherwise filtering by it would either
  // be a no-op or empty the table on first click.
  const licenseOpts = useMemo(() => deriveOptions(members, "license"), [members]);
  const deploymentOpts = useMemo(() => deriveOptions(members, "deployment"), [members]);
  const maturityOpts = useMemo(() => deriveOptions(members, "maturity"), [members]);

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
        {licenseOpts.length >= 2 && (
          <Dropdown
            label="License"
            value={license}
            onChange={(v) => setParam("license", v)}
            options={licenseOpts}
          />
        )}
        {deploymentOpts.length >= 2 && (
          <Dropdown
            label="Deployment"
            value={deployment}
            onChange={(v) => setParam("deployment", v)}
            options={deploymentOpts}
          />
        )}
        {maturityOpts.length >= 2 && (
          <Dropdown
            label="Maturity"
            value={maturity}
            onChange={(v) => setParam("maturity", v)}
            options={maturityOpts}
          />
        )}
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
        <span className="ml-auto text-[10px] text-muted-foreground">
          Tick <span className="font-mono">+</span> on any row to add it to your compare tray (up to 5).
        </span>
      </div>

      <MobileRankList
        items={filtered.map<MobileRankItem>((a, i) => {
          const license = (a.tags ?? []).find((t) => t.kind === "license")?.value;
          const deployment = (a.tags ?? []).find((t) => t.kind === "deployment")?.value;
          return {
            slug: a.slug,
            name: a.name,
            label: [license, deployment].filter(Boolean).join(" · ") || undefined,
            rank: a.score?.rank_now ?? i + 1,
            score: a.score?.agent_score ?? null,
            delta24h: a.score?.delta_24h ?? null,
            rankDelta24h: a.score?.rank_delta_24h ?? null,
          };
        })}
      />

      <div className="hidden overflow-x-auto rounded-md border border-border bg-card md:block">
        <table className="num w-full min-w-[680px] text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-3 py-2 text-center w-12">Cmp</th>
              <th className="px-3 py-2 text-right">Rank</th>
              <th className="px-3 py-2 text-left">Agent</th>
              <th className="px-3 py-2 text-right">24h</th>
              <th className="px-3 py-2 text-right">Score</th>
              <th className="px-3 py-2 text-right">Δ24h</th>
              <th className="px-3 py-2 text-center w-12">Watch</th>
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
