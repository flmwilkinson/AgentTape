"use client";

import { useState } from "react";
import Link from "next/link";
import { Wifi, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDeltaPct, formatScore } from "@/lib/format";
import type { AgentDetail } from "@/lib/api-client";
import { MoverChip } from "@/components/mover-chip";
import { NumberTick } from "@/components/number-tick";
import { PillarBar } from "@/components/pillar-bar";
import { WatchToggle } from "@/components/watch-toggle";
import { useWebSocket, type WsFrame } from "@/lib/ws";

// The big-name + score + pillars block at the top of an agent ticker
// page. Wires /ws/agent/<slug> so numbers tick when scoring publishes
// a new score_changed event.

interface Props {
  agent: AgentDetail;
}

export function AgentLiveHeader({ agent }: Props) {
  const [score, setScore] = useState(agent.score);
  const { connected } = useWebSocket({
    path: `/ws/agent/${agent.slug}`,
    onFrame: (frame: WsFrame) => {
      if (frame.type !== "event") return;
      const ev = frame.event as Partial<typeof agent.score> & {
        kind?: string;
      };
      if (ev.kind !== "score_changed") return;
      // Live frame doesn't carry 24h history fields — keep whatever we
      // had at SSR time so deltas still render until the next page nav.
      setScore((prev) => ({
        agent_score: ev.agent_score ?? null,
        adoption: ev.adoption ?? null,
        quality: ev.quality ?? null,
        momentum: ev.momentum ?? null,
        community: ev.community ?? null,
        manipulation_resistance: ev.manipulation_resistance ?? null,
        computed_at: new Date().toISOString(),
        score_24h_ago: prev?.score_24h_ago ?? null,
        delta_24h: prev?.delta_24h ?? null,
        rank_now: prev?.rank_now ?? null,
        rank_24h_ago: prev?.rank_24h_ago ?? null,
        rank_delta_24h: prev?.rank_delta_24h ?? null,
      }));
    },
  });

  const prior = agent.score?.agent_score ?? null;
  const now = score?.agent_score ?? null;
  const deltaPct = prior != null && now != null ? formatDeltaPct(now, prior) : "—";

  return (
    <div className="border-b border-border bg-card">
      <div className="container py-8 md:py-12">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {agent.discovered_via.replace(/_/g, " ")}
          </span>
          <span className="text-muted-foreground/50">·</span>
          <span className="text-[11px] text-muted-foreground">
            {agent.slug}
          </span>
          {/* Live / Not-Live indicator is desktop-only. On mobile the
              icon flashed every time the WebSocket reconnected during
              page navigation, which read as visual noise more than
              useful state. The watch toggle still shows. */}
          <span className="ml-auto hidden items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground md:inline-flex">
            {connected ? (
              <Wifi className="h-3 w-3 text-gain" />
            ) : (
              <WifiOff className="h-3 w-3 text-loss" />
            )}
            Live
          </span>
          <span className="ml-auto md:ml-0">
            <WatchToggle slug={agent.slug} showLabel />
          </span>
        </div>

        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          {agent.name}
        </h1>
        {agent.description && (
          <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
            {agent.description}
          </p>
        )}

        <div className="mt-8 grid gap-8 md:grid-cols-[auto_1fr]">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              AgentScore
            </div>
            <div className="mt-1 flex items-end gap-3">
              <NumberTick
                value={now}
                format={formatScore}
                className="text-stat-xl font-semibold"
                animateOnMount={false}
              />
              {/* 24h delta is the prominent change signal — not the
                  inter-recompute delta. Distinguishing null (no
                  history) from 0 (compared, unchanged) matters. */}
              {agent.score?.delta_24h != null ? (
                <MoverChip
                  delta={agent.score.delta_24h}
                  unit="score"
                  className="mb-1"
                />
              ) : prior != null && now != null && now !== prior ? (
                <MoverChip delta={now - prior} unit="score" className="mb-1" />
              ) : null}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              {agent.score?.delta_24h != null
                ? `${agent.score.delta_24h >= 0 ? "+" : ""}${agent.score.delta_24h.toFixed(2)} vs 24h ago`
                : deltaPct !== "—"
                  ? `${deltaPct} vs last recompute`
                  : "No 24h history yet"}
            </div>
          </div>
          <PillarBar
            score={{
              adoption: score?.adoption ?? null,
              quality: score?.quality ?? null,
              momentum: score?.momentum ?? null,
              community: score?.community ?? null,
            }}
            className="self-end"
          />
        </div>

        {(agent.retention || agent.openrouter_rank) && (
          <DerivedBadges
            retention={agent.retention}
            openrouterRank={agent.openrouter_rank}
          />
        )}

        {agent.tags?.length > 0 && (
          <TagGroups tags={agent.tags} />
        )}
      </div>
    </div>
  );
}

// Derived-badge row. Sits above the tag chips. Carries the two
// computed-at-request-time signals — month-2 retention proxy and
// OpenRouter usage rank — neither of which is a stored signal value
// but both are useful at-a-glance reads ("still growing 60d post-
// launch" / "OpenRouter top 8 of 47") that benchmarks alone don't
// surface.

const RETENTION_TONE: Record<
  "growing" | "holding" | "fading" | "decaying",
  { tone: string; label: string; hint: string }
> = {
  growing: {
    tone: "border-gain/40 bg-gain-subtle text-gain",
    label: "Growing past launch",
    hint: "Score now is at least 10% above the 30-day post-admission baseline.",
  },
  holding: {
    tone: "border-border bg-subtle text-foreground/85",
    label: "Holding",
    hint: "Score now is within ±10% of the 30-day post-admission baseline.",
  },
  fading: {
    tone: "border-border bg-subtle text-muted-foreground",
    label: "Fading since launch",
    hint: "Score now is 10–50% below the 30-day post-admission baseline.",
  },
  decaying: {
    tone: "border-loss/40 bg-loss-subtle text-loss",
    label: "Decaying since launch",
    hint: "Score now is more than 50% below the 30-day post-admission baseline.",
  },
};

function fmtTokens(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toString();
}

function DerivedBadges({
  retention,
  openrouterRank,
}: {
  retention: AgentDetail["retention"];
  openrouterRank: AgentDetail["openrouter_rank"];
}) {
  return (
    <div className="mt-6 flex flex-wrap gap-2">
      {retention && (
        <span
          title={`${RETENTION_TONE[retention.status].hint} Score now ${retention.score_now.toFixed(1)} vs ${retention.score_at_30d.toFixed(1)} at +30d (admitted ${retention.days_since_admission}d ago).`}
          className={cn(
            "rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
            RETENTION_TONE[retention.status].tone,
          )}
        >
          {RETENTION_TONE[retention.status].label} ·{" "}
          <span className="num">{retention.ratio.toFixed(2)}×</span>
        </span>
      )}
      {openrouterRank && (
        <span
          title={`OpenRouter token volume (30d): ${fmtTokens(openrouterRank.tokens_30d)} tokens. Ranked among ${openrouterRank.total} foundation models with recent OpenRouter readings.`}
          className="rounded-full border border-primary/40 bg-primary/5 px-2.5 py-0.5 text-[11px] font-medium text-primary"
        >
          OpenRouter <span className="num">#{openrouterRank.rank}</span>{" "}
          <span className="text-muted-foreground">
            of {openrouterRank.total}
          </span>
        </span>
      )}
    </div>
  );
}

// Tag chips grouped by kind. The previous version stamped every chip
// with its kind ("LICENSE mit", "DEPLOYMENT cli") which was visually
// dense and made similar chips harder to scan. Grouping puts the
// kind label once per group and lets the values themselves carry the
// chip — much closer to how a reader expects metadata to render.
const KIND_ORDER = [
  "capability",
  "deployment",
  "model_dep",
  "license",
  "maturity",
  "domain",
];
const KIND_LABEL: Record<string, string> = {
  capability: "Capabilities",
  deployment: "Deployment",
  model_dep: "Built on",
  license: "License",
  maturity: "Maturity",
  domain: "Domain",
};

function TagGroups({
  tags,
}: {
  tags: { kind: string; value: string; display_name: string }[];
}) {
  const grouped = new Map<
    string,
    { kind: string; value: string; display_name: string }[]
  >();
  for (const t of tags) {
    if (!grouped.has(t.kind)) grouped.set(t.kind, []);
    grouped.get(t.kind)!.push(t);
  }
  // Stable order: well-known kinds first, anything else after.
  const orderedKinds = [
    ...KIND_ORDER.filter((k) => grouped.has(k)),
    ...[...grouped.keys()].filter((k) => !KIND_ORDER.includes(k)),
  ];

  return (
    <div className="mt-6 space-y-2">
      {orderedKinds.map((kind) => (
        <div
          key={kind}
          className="flex flex-wrap items-center gap-1.5"
        >
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/70 mr-1">
            {KIND_LABEL[kind] ?? kind}
          </span>
          {grouped.get(kind)!.map((t) => {
            // model_dep chips link to the family's sector page —
            // /sectors/model_dep/<family> lists every app tagged with
            // that family, which is what a reader who clicked "Built
            // on Claude" actually wants ("show me other Claude
            // apps"). The tag value is a family slug ('claude',
            // 'gpt', ...), never a specific FM slug.
            if (t.kind === "model_dep") {
              return (
                <Link
                  key={`${t.kind}:${t.value}`}
                  href={`/sectors/model_dep/${t.value}`}
                  className="rounded-full border border-primary/30 bg-primary/5 px-2.5 py-0.5 text-[11px] text-primary hover:bg-primary/10"
                >
                  {t.display_name}
                </Link>
              );
            }
            return (
              <span
                key={`${t.kind}:${t.value}`}
                className={cn(
                  "rounded-full border border-border bg-subtle px-2.5 py-0.5 text-[11px] text-foreground/85",
                )}
              >
                {t.display_name}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}
