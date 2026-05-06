"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { GitCompare, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { Dropdown } from "@/components/dropdown";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

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

const MAX_COMPARE = 5;

interface Props {
  members: AgentSummary[];
}

export function SectorMembersPanel({ members }: Props) {
  const router = useRouter();
  const params = useSearchParams();

  const license = params.get("license") ?? "";
  const deployment = params.get("deployment") ?? "";
  const maturity = params.get("maturity") ?? "";
  const compareCsv = params.get("compare") ?? "";
  const selected = useMemo(
    () => new Set(compareCsv.split(",").filter(Boolean)),
    [compareCsv],
  );

  const setParam = (key: string, value: string) => {
    const cur = new URLSearchParams(params.toString());
    if (value) cur.set(key, value);
    else cur.delete(key);
    router.replace(`?${cur.toString()}`, { scroll: false });
  };

  function toggleSelect(slug: string) {
    const next = new Set(selected);
    if (next.has(slug)) {
      next.delete(slug);
    } else {
      if (next.size >= MAX_COMPARE) return; // cap silently
      next.add(slug);
    }
    setParam("compare", Array.from(next).join(","));
  }

  function clearSelection() {
    setParam("compare", "");
  }

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
              const checked = selected.has(a.slug);
              const license = (a.tags ?? []).find((t) => t.kind === "license")?.value;
              const deployment = (a.tags ?? []).find((t) => t.kind === "deployment")?.value;
              return (
                <tr key={a.id} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2 text-center">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSelect(a.slug)}
                      disabled={!checked && selected.size >= MAX_COMPARE}
                      aria-label={checked ? `Remove ${a.name} from compare` : `Add ${a.name} to compare`}
                      className="h-3.5 w-3.5 rounded-sm accent-primary"
                    />
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

      {selected.size >= 1 && (
        <CompareBar
          slugs={Array.from(selected)}
          onClear={clearSelection}
          onRemove={(slug) => toggleSelect(slug)}
        />
      )}
    </section>
  );
}

function CompareBar({
  slugs,
  onClear,
  onRemove,
}: {
  slugs: string[];
  onClear: () => void;
  onRemove: (slug: string) => void;
}) {
  const canCompare = slugs.length >= 2;
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 backdrop-blur md:bottom-4 md:inset-x-auto md:left-1/2 md:right-auto md:-translate-x-1/2 md:rounded-md md:border md:shadow-lg">
      <div className="container flex items-center gap-3 py-3 md:max-w-2xl">
        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          {slugs.length}/{MAX_COMPARE} selected
        </span>
        <ul className="flex flex-1 flex-wrap gap-1.5 overflow-hidden">
          {slugs.map((s) => (
            <li
              key={s}
              className="inline-flex items-center gap-1 rounded-sm border border-border bg-subtle px-2 py-0.5 text-xs"
            >
              <span className="truncate max-w-[140px]">{s}</span>
              <button
                type="button"
                onClick={() => onRemove(s)}
                aria-label={`Remove ${s}`}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={onClear}
          className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
        >
          Clear
        </button>
        <Link
          href={canCompare ? `/compare?slugs=${slugs.join(",")}` : "#"}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
            canCompare
              ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
              : "pointer-events-none border-border text-muted-foreground",
          )}
          aria-disabled={!canCompare}
        >
          <GitCompare className="h-3.5 w-3.5" />
          {canCompare ? "Compare selected" : "Pick 2+ to compare"}
        </Link>
      </div>
    </div>
  );
}
