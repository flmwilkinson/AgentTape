"use client";

import { useMemo } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SignalSeries } from "@/lib/api-client";

// "What moved this score in the last 24 hours" — a transparent,
// rules-based attribution view. We don't try to back-fit pillar
// arithmetic; we just surface which underlying signals changed and
// by how much, so a reader can see the *why* behind a score move.
//
// Mapping each source → pillar follows the scoring service:
//   adoption  : stars / downloads / package installs / mcp listed
//   quality   : benchmark scores
//   momentum  : commits / hn / reddit / arxiv citations
//   community : forks / contributors / hf likes / hf trending rank

type Pillar = "adoption" | "quality" | "momentum" | "community";

const SOURCE_META: Record<
  string,
  { label: string; pillar: Pillar; inverse?: boolean }
> = {
  github_stars: { label: "GitHub stars", pillar: "adoption" },
  github_forks: { label: "GitHub forks", pillar: "community" },
  github_commits_7d: { label: "Commits (7d)", pillar: "momentum" },
  github_contributors: { label: "Contributors", pillar: "community" },
  github_mentions_7d: { label: "GitHub mentions (7d)", pillar: "adoption" },
  hf_downloads_30d: { label: "HF downloads (30d)", pillar: "adoption" },
  hf_likes: { label: "HF likes", pillar: "community" },
  // hf_trending_rank: 1 is best, so a *fall* in rank value = improvement.
  hf_trending_rank: { label: "HF trending rank", pillar: "community", inverse: true },
  npm_weekly: { label: "npm weekly installs", pillar: "adoption" },
  pypi_monthly: { label: "PyPI monthly installs", pillar: "adoption" },
  mcp_registry_listed: { label: "MCP registry listings", pillar: "adoption" },
  hn_points_7d: { label: "Hacker News points (7d)", pillar: "momentum" },
  hn_mentions_7d: { label: "Hacker News mentions (7d)", pillar: "momentum" },
  reddit_points_7d: { label: "Reddit points (7d)", pillar: "momentum" },
  reddit_mentions_7d: { label: "Reddit mentions (7d)", pillar: "momentum" },
  benchmark_score: { label: "Benchmark score", pillar: "quality" },
  arxiv_citations: { label: "arXiv citations", pillar: "momentum" },
};

interface Contribution {
  source: string;
  label: string;
  pillar: Pillar;
  delta: number;
  pctDelta: number | null;
  valueNow: number;
  valuePrior: number;
}

function computeContributions(series: SignalSeries[]): Contribution[] {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  const out: Contribution[] = [];

  for (const s of series) {
    if (s.points.length === 0) continue;
    const meta = SOURCE_META[s.source];
    if (!meta) continue;

    // Sort ascending so .at(-1) is latest.
    const sorted = [...s.points].sort(
      (a, b) =>
        new Date(a.captured_at).getTime() - new Date(b.captured_at).getTime(),
    );
    const latest = sorted.at(-1)!;

    // Pick the anchor for "what was this 24h ago":
    //   1. The latest reading older than 24h, if any → real comparison.
    //   2. Otherwise, the signal first appeared inside the 24h window;
    //      treat the prior as 0 so a freshly-arrived signal shows up
    //      ("0 → 47, +47").
    const olderPts = sorted.filter(
      (p) => new Date(p.captured_at).getTime() <= cutoff,
    );
    const anchorValue =
      olderPts.length > 0 ? olderPts.at(-1)!.value : 0;

    const rawDelta = latest.value - anchorValue;
    // Inverse sources (rank: lower is better) flip the sign so positive
    // delta always means "good for the score".
    const delta = meta.inverse ? -rawDelta : rawDelta;
    const pctDelta =
      anchorValue !== 0
        ? (delta / Math.abs(anchorValue)) * 100
        : null;

    if (delta === 0) continue;
    out.push({
      source: s.source,
      label: meta.label,
      pillar: meta.pillar,
      delta,
      pctDelta,
      valueNow: latest.value,
      valuePrior: anchorValue,
    });
  }

  // Rank by magnitude — % change when available, absolute delta otherwise.
  out.sort((a, b) => {
    const am = a.pctDelta != null ? Math.abs(a.pctDelta) : Math.abs(a.delta);
    const bm = b.pctDelta != null ? Math.abs(b.pctDelta) : Math.abs(b.delta);
    return bm - am;
  });

  return out;
}

// Pillar swatch colours mirror PillarBar so the user can visually link
// "what moved" rows back to the bar above.
const PILLAR_SWATCH: Record<Pillar, string> = {
  adoption: "hsl(var(--primary))",
  quality: "hsl(var(--gain))",
  momentum: "hsl(var(--loss))",
  community: "hsl(var(--neutral))",
};

function fmtCount(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  if (Number.isInteger(n)) return String(n);
  return n.toFixed(2);
}

interface Props {
  signals: SignalSeries[];
  className?: string;
}

export function ScoreContributors({ signals, className }: Props) {
  const rows = useMemo(() => computeContributions(signals).slice(0, 6), [
    signals,
  ]);

  if (rows.length === 0) {
    return (
      <div className={cn("rounded-md border border-border bg-card p-4", className)}>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          What moved (24h)
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          No signal changes in the last 24 hours.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("rounded-md border border-border bg-card", className)}>
      <div className="border-b border-border px-4 py-2.5">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          What moved (24h)
        </div>
        <div className="text-[11px] text-muted-foreground">
          Underlying signals ranked by 24-hour change.
        </div>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => {
          const positive = r.delta > 0;
          const Icon = positive ? ArrowUpRight : r.delta < 0 ? ArrowDownRight : Minus;
          const tone = positive ? "text-gain" : "text-loss";
          return (
            <li
              key={r.source}
              className="flex items-center gap-3 px-4 py-2.5 text-sm"
            >
              <span
                className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground"
                title={`${r.pillar} pillar`}
              >
                <span
                  className="block h-2 w-2 rounded-sm"
                  style={{ backgroundColor: PILLAR_SWATCH[r.pillar] }}
                />
                {r.pillar}
              </span>
              <span className="flex-1 truncate">{r.label}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {fmtCount(r.valuePrior)} → {fmtCount(r.valueNow)}
              </span>
              <span className={cn("inline-flex items-center gap-1 font-mono text-xs", tone)}>
                <Icon className="h-3.5 w-3.5" />
                {r.pctDelta != null
                  ? `${positive ? "+" : ""}${r.pctDelta.toFixed(1)}%`
                  : `${positive ? "+" : ""}${fmtCount(r.delta)}`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
