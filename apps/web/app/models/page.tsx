"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api, type AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { CompareTrayToggle } from "@/components/compare-tray";
import { Dropdown } from "@/components/dropdown";
import { MobileRankList, type MobileRankItem } from "@/components/mobile-rank-list";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { TableSkeleton } from "@/components/skeleton";
import { ToggleGroup } from "@/components/toggle-group";
import { WatchToggle } from "@/components/watch-toggle";

// Foundation-model board.
//
// Pulls every admitted foundation_model (~370) and lets the reader
// narrow on the questions a buyer actually asks: who makes it, can
// it think, can it see, am I paying. Slug prefixes are derived from
// the OpenRouter provider id (e.g. mistral/ministral-3-8b →
// "mistral-ministral-3-8b") so family detection is straight prefix
// match against the real data, not the OpenRouter URL form.

const FAMILIES: { v: string; label: string }[] = [
  { v: "", label: "Any" },
  { v: "openai", label: "OpenAI" },
  { v: "anthropic", label: "Anthropic" },
  { v: "google", label: "Google" },
  { v: "meta", label: "Meta" },
  { v: "mistral", label: "Mistral" },
  { v: "qwen", label: "Qwen" },
  { v: "deepseek", label: "DeepSeek" },
  { v: "xai", label: "xAI" },
  { v: "nvidia", label: "NVIDIA" },
  { v: "amazon", label: "Amazon" },
  { v: "perplexity", label: "Perplexity" },
  { v: "minimax", label: "MiniMax" },
  { v: "moonshotai", label: "Moonshot" },
  { v: "z", label: "Z.ai" },
  { v: "nous", label: "Nous" },
  { v: "other", label: "Other" },
];

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

const MODALITIES = [
  { v: "", label: "All" },
  { v: "text", label: "Text-only" },
  { v: "image", label: "Vision" },
  { v: "audio", label: "Audio" },
  { v: "video", label: "Video" },
  { v: "multimodal", label: "Multimodal" },
] as const;

const OPENNESS = [
  { v: "", label: "All" },
  { v: "open", label: "Open weights" },
  { v: "closed", label: "Closed" },
] as const;

// Open-weights families. Conservative — vendors who actually publish
// model weights / accept self-hosting. Closed providers (OpenAI,
// Anthropic, Google) sit in the complement.
const OPEN_FAMILIES = new Set([
  "meta",
  "mistral",
  "qwen",
  "deepseek",
  "nvidia",
  "moonshotai",
  "minimax",
  "nous",
  "z",
  "sao10k",
]);

const REASONING_TOKENS = [
  "reasoning",
  "thinking",
  "-r1",
  "-o1",
  "-o3",
  "-o4",
  "-o5",
  "deep-research",
];

function familyOf(slug: string): string {
  const head = slug.split("-", 1)[0].toLowerCase();
  if (FAMILIES.some((f) => f.v === head)) return head;
  return "other";
}

function isFree(name: string, slug: string): boolean {
  return /\(free\)/i.test(name) || /-free$/.test(slug) || /:free/.test(slug);
}

function isReasoning(name: string, slug: string): boolean {
  const blob = `${name} ${slug}`.toLowerCase();
  return REASONING_TOKENS.some((tok) => blob.includes(tok));
}

function modalityOf(facts: Record<string, unknown>): string {
  return ((facts.modality as string | undefined) ?? "text->text").toLowerCase();
}

function isMultimodal(modality: string): boolean {
  // Anything with 2+ input types (text + image / audio / video / file).
  const inputs = modality.split("->")[0];
  return /\+/.test(inputs);
}

export default function ModelsPage() {
  const [family, setFamily] = useState<string>("");
  const [tier, setTier] = useState<string>("");
  const [reasoning, setReasoning] = useState<string>("");
  const [modality, setModality] = useState<string>("");
  const [openness, setOpenness] = useState<string>("");

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
    if (family) out = out.filter((m) => familyOf(m.slug) === family);
    if (tier === "free") out = out.filter((m) => isFree(m.name, m.slug));
    if (tier === "paid") out = out.filter((m) => !isFree(m.name, m.slug));
    if (reasoning === "reasoning") {
      out = out.filter((m) => isReasoning(m.name, m.slug));
    } else if (reasoning === "non-reasoning") {
      out = out.filter((m) => !isReasoning(m.name, m.slug));
    }
    if (modality) {
      out = out.filter((m) => {
        const mod = modalityOf(m.facts);
        if (modality === "multimodal") return isMultimodal(mod);
        if (modality === "text") return !isMultimodal(mod);
        // image / audio / video — substring match on input side.
        const inputs = mod.split("->")[0];
        return inputs.includes(modality);
      });
    }
    if (openness === "open") {
      out = out.filter((m) => OPEN_FAMILIES.has(familyOf(m.slug)));
    } else if (openness === "closed") {
      out = out.filter((m) => !OPEN_FAMILIES.has(familyOf(m.slug)));
    }
    // Sort by rank_now so the displayed rank column is monotonic.
    // The API returns rows ordered by agent_score (full precision)
    // but rank_now is computed at a slightly different snapshot
    // moment, so when scores tie at e.g. 36.4 the display order
    // and the rank number can disagree (#4, #6, #5 ...). Sorting
    // by rank_now keeps them aligned. Rows with no rank fall
    // through to the bottom by score.
    out = [...out].sort((a, b) => {
      const ra = a.score?.rank_now;
      const rb = b.score?.rank_now;
      if (ra != null && rb != null) return ra - rb;
      if (ra != null) return -1;
      if (rb != null) return 1;
      return (b.score?.agent_score ?? 0) - (a.score?.agent_score ?? 0);
    });
    return out;
  }, [all, family, tier, reasoning, modality, openness]);

  const totalCount = all.length;

  function clearAll() {
    setFamily("");
    setTier("");
    setReasoning("");
    setModality("");
    setOpenness("");
  }

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
          Every foundation model AgentTape tracks ({totalCount} today),
          sourced from OpenRouter. The flagship index is{" "}
          <Link href="/indexes/fm-50" className="text-primary hover:underline">
            FM-50
          </Link>
          .
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        {/* Family / Modality have many options → Dropdown. The
            three-option filters use ToggleGroup so the active choice
            is always visible without a click. */}
        <Dropdown label="Family" value={family} onChange={setFamily} options={FAMILIES.map((f) => ({ value: f.v, label: f.label }))} triggerWidth="min-w-[140px]" />
        <Dropdown label="Modality" value={modality} onChange={setModality} options={MODALITIES.map((m) => ({ value: m.v, label: m.label }))} />
        <ToggleGroup label="Openness" value={openness} onChange={setOpenness} options={OPENNESS.map((o) => ({ v: o.v, label: o.label }))} />
        <ToggleGroup label="Pricing" value={tier} onChange={setTier} options={TIERS.map((t) => ({ v: t.v, label: t.label }))} />
        <ToggleGroup label="Mode" value={reasoning} onChange={setReasoning} options={REASONING.map((r) => ({ v: r.v, label: r.label }))} />
        {(family || tier || reasoning || modality || openness) && (
          <button
            type="button"
            onClick={clearAll}
            className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
          >
            Clear
          </button>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {filtered.length} of {totalCount} models
        </span>
      </div>

      {isLoading ? (
        <section className="overflow-x-auto rounded-md border border-border bg-card">
          <table className="num w-full min-w-[640px] text-sm">
            <tbody>
              <TableSkeleton rows={8} cols={6} />
            </tbody>
          </table>
        </section>
      ) : filtered.length === 0 ? (
        <section className="rounded-md border border-dashed border-border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">
            No models match these filters. Try clearing one.
          </p>
        </section>
      ) : (
        <>
        <MobileRankList
          items={filtered.map<MobileRankItem>((m, i) => {
            const fam = familyOf(m.slug);
            const mod = modalityOf(m.facts);
            const labelBits: string[] = [fam];
            if (OPEN_FAMILIES.has(fam)) labelBits.push("open");
            if (isFree(m.name, m.slug)) labelBits.push("free");
            if (isReasoning(m.name, m.slug)) labelBits.push("reasoning");
            if (isMultimodal(mod)) labelBits.push("multimodal");
            return {
              slug: m.slug,
              name: m.name,
              label: labelBits.join(" · "),
              rank: m.score?.rank_now ?? i + 1,
              score: m.score?.agent_score ?? null,
              delta24h: m.score?.delta_24h ?? null,
              rankDelta24h: m.score?.rank_delta_24h ?? null,
            };
          })}
        />
        <section className="hidden overflow-x-auto rounded-md border border-border bg-card md:block">
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
                <th className="px-3 py-2 text-center w-12">Cmp</th>
                <th className="px-3 py-2 text-center w-12">Watch</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((m, i) => {
                const fam = familyOf(m.slug);
                const mod = modalityOf(m.facts);
                const labelBits: string[] = [fam];
                if (OPEN_FAMILIES.has(fam)) labelBits.push("open");
                if (isFree(m.name, m.slug)) labelBits.push("free");
                if (isReasoning(m.name, m.slug)) labelBits.push("reasoning");
                if (isMultimodal(mod)) labelBits.push("multimodal");
                return (
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
                        {labelBits.join(" · ")}
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
                    <td className="px-3 py-2 text-center">
                      <CompareTrayToggle slug={m.slug} />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <WatchToggle slug={m.slug} size="sm" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
        </>
      )}
    </div>
  );
}
