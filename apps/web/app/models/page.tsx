"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api, type AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// Foundation-model board.
//
// Pulls every admitted agent whose entity_kind is foundation_model
// (~370 today) and lets the reader narrow with three filters that
// match the questions a buyer actually asks: who makes it, am I
// paying, can it reason?
//
// Filters are client-side because the data already fits in one
// request and slicing is faster than a server round-trip per change.

const FAMILIES = [
  { v: "", label: "Any" },
  { v: "openai", label: "OpenAI" },
  { v: "anthropic", label: "Anthropic" },
  { v: "google", label: "Google" },
  { v: "meta-llama", label: "Meta" },
  { v: "mistralai", label: "Mistral" },
  { v: "qwen", label: "Qwen" },
  { v: "deepseek", label: "DeepSeek" },
  { v: "x-ai", label: "xAI" },
  { v: "nvidia", label: "NVIDIA" },
  { v: "other", label: "Other" },
] as const;

const TIERS = [
  { v: "", label: "Any" },
  { v: "free", label: "Free" },
  { v: "paid", label: "Paid" },
] as const;

const REASONING = [
  { v: "", label: "All" },
  { v: "reasoning", label: "Reasoning" },
  { v: "non-reasoning", label: "Standard" },
] as const;

const REASONING_TOKENS = [
  "reasoning",
  "thinking",
  "o1",
  "o3",
  "o4",
  "o5",
  "deepseek-r1",
  "deepseek-v3-reasoner",
];

function familyOf(slug: string): string {
  // Slugs derive from openrouter ids — "openai/gpt-4.1-nano" becomes
  // "openai-gpt-4-1-nano". Match multi-word providers (x-ai,
  // meta-llama) first so the simple split-by-dash doesn't truncate
  // them to "x" or "meta".
  const lower = slug.toLowerCase();
  for (const f of FAMILIES) {
    if (f.v && f.v !== "other" && lower.startsWith(f.v + "-")) return f.v;
  }
  return "other";
}

function isFree(name: string, slug: string): boolean {
  return /\(free\)/i.test(name) || /-free$/.test(slug) || /:free/.test(slug);
}

function isReasoning(name: string, slug: string): boolean {
  const blob = `${name} ${slug}`.toLowerCase();
  return REASONING_TOKENS.some((tok) => blob.includes(tok));
}

export default function ModelsPage() {
  const [family, setFamily] = useState<string>("");
  const [tier, setTier] = useState<string>("");
  const [reasoning, setReasoning] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["fm-list"],
    queryFn: () =>
      api.listAgents({
        entity_kind: "foundation_model",
        sort: "score",
        limit: 500,
      }),
  });

  const all = data?.items ?? [];
  const filtered = useMemo(() => {
    let out: AgentSummary[] = all;
    if (family) {
      out = out.filter((m) => familyOf(m.slug) === family);
    }
    if (tier === "free") out = out.filter((m) => isFree(m.name, m.slug));
    if (tier === "paid") out = out.filter((m) => !isFree(m.name, m.slug));
    if (reasoning === "reasoning") {
      out = out.filter((m) => isReasoning(m.name, m.slug));
    } else if (reasoning === "non-reasoning") {
      out = out.filter((m) => !isReasoning(m.name, m.slug));
    }
    return out;
  }, [all, family, tier, reasoning]);

  return (
    <div className="container py-8 md:py-12 space-y-8">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Foundation models
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          The model board.
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
          Every foundation model AgentTape tracks — sourced from the
          OpenRouter catalogue, scored by context, pricing, provider
          tier and modality. The flagship index is{" "}
          <Link href="/indexes/fm-50" className="text-primary hover:underline">
            FM-50
          </Link>
          .
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <Toggle
          label="Family"
          value={family}
          onChange={setFamily}
          options={FAMILIES.map((f) => ({ v: f.v, label: f.label }))}
        />
        <Toggle
          label="Pricing"
          value={tier}
          onChange={setTier}
          options={TIERS.map((t) => ({ v: t.v, label: t.label }))}
        />
        <Toggle
          label="Mode"
          value={reasoning}
          onChange={setReasoning}
          options={REASONING.map((r) => ({ v: r.v, label: r.label }))}
        />
        <span className="ml-auto text-xs text-muted-foreground">
          {filtered.length} of {all.length} models
        </span>
      </div>

      {isLoading ? (
        <section className="rounded-md border border-border bg-card px-4 py-12 text-center text-sm text-muted-foreground">
          Loading models…
        </section>
      ) : filtered.length === 0 ? (
        <section className="rounded-md border border-dashed border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No models match these filters. Try clearing one.
          </p>
        </section>
      ) : (
        <section className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full min-w-[640px] text-sm">
            <thead className="text-xs uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-right">Rank</th>
                <th className="px-3 py-2 text-left">Model</th>
                <th className="px-3 py-2 text-right">24h</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Δ24h</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Adoption</th>
                <th className="px-3 py-2 text-right hidden md:table-cell">Quality</th>
                <th className="px-3 py-2 text-right hidden lg:table-cell">Momentum</th>
                <th className="px-3 py-2 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((m, i) => (
                <tr key={m.id} className="border-b border-border last:border-b-0">
                  <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                    #{m.score?.rank_now ?? i + 1}
                  </td>
                  <td className="px-3 py-2">
                    <Link
                      href={`/agents/${m.slug}`}
                      className="font-sans font-medium hover:text-primary"
                    >
                      {m.name}
                    </Link>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {familyOf(m.slug)}
                      {isFree(m.name, m.slug) && " · free"}
                      {isReasoning(m.name, m.slug) && " · reasoning"}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <RankArrow
                      delta={m.score?.rank_delta_24h ?? null}
                      rankNow={m.score?.rank_now ?? null}
                    />
                  </td>
                  <td className="px-3 py-2 text-right font-semibold">
                    {formatScore(m.score?.agent_score ?? null)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {m.score?.delta_24h != null ? (
                      <MoverChip
                        delta={m.score.delta_24h}
                        unit="score"
                        variant="outline"
                      />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell">
                    {m.score?.adoption?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground hidden md:table-cell">
                    {m.score?.quality === null
                      ? "Unrated"
                      : m.score?.quality?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right hidden lg:table-cell">
                    {m.score?.momentum?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <WatchToggle slug={m.slug} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
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
      <span className="inline-flex flex-wrap rounded-md border border-border bg-card p-0.5">
        {options.map((o) => (
          <button
            key={o.v || "any"}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              "rounded-sm px-2.5 py-1.5 text-[11px] font-mono uppercase tracking-wider transition-colors",
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
