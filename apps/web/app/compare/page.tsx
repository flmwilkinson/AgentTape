"use client";

import { Plus, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { PillarBar } from "@/components/pillar-bar";
import { Sparkline } from "@/components/sparkline";

// Up to 4 agents, side-by-side. URL is the canonical state:
// /compare?slugs=foo,bar,baz

const MAX = 4;

export default function ComparePage() {
  const router = useRouter();
  const params = useSearchParams();
  const raw = params.get("slugs") ?? "";
  const slugs = raw ? raw.split(",").filter(Boolean).slice(0, MAX) : [];
  const [draft, setDraft] = useState("");

  const { data: agents } = useQuery({
    queryKey: ["compare", slugs.join(",")],
    queryFn: async () => {
      if (slugs.length === 0) return [];
      const out = await Promise.all(
        slugs.map((s) => api.getAgent(s).catch(() => null)),
      );
      return out.filter((a): a is NonNullable<typeof a> => Boolean(a));
    },
    enabled: slugs.length > 0,
  });

  function setSlugs(next: string[]) {
    const cur = new URLSearchParams(params.toString());
    next.length ? cur.set("slugs", next.join(",")) : cur.delete("slugs");
    router.replace(`/compare?${cur.toString()}`);
  }

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Compare
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Up to four, side by side.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Add agents by slug. The URL is shareable.
        </p>
      </div>

      <form
        className="mb-6 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!draft) return;
          if (slugs.includes(draft)) return;
          if (slugs.length >= MAX) return;
          setSlugs([...slugs, draft]);
          setDraft("");
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="agent-slug"
          className="flex-1 rounded-md border border-border bg-card px-3 py-2 text-sm outline-none placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" /> Add
        </button>
      </form>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {(agents ?? []).map((a) => (
          <div
            key={a.slug}
            className="rounded-md border border-border bg-card p-4"
          >
            <div className="flex items-start justify-between">
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {a.discovered_via.replace(/_/g, " ")}
                </div>
                <div className="truncate text-sm font-medium">{a.name}</div>
              </div>
              <button
                type="button"
                aria-label="Remove"
                onClick={() => setSlugs(slugs.filter((s) => s !== a.slug))}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 text-stat-md font-semibold num">
              {formatScore(a.score?.agent_score ?? null)}
            </div>
            <div className="mt-3">
              <PillarBar
                score={{
                  adoption: a.score?.adoption ?? null,
                  quality: a.score?.quality ?? null,
                  momentum: a.score?.momentum ?? null,
                  community: a.score?.community ?? null,
                }}
                variant="compact"
              />
            </div>
          </div>
        ))}
        {Array.from({ length: Math.max(0, MAX - (agents?.length ?? 0)) }).map(
          (_, i) => (
            <div
              key={`empty-${i}`}
              className="flex min-h-[200px] items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground"
            >
              add an agent
            </div>
          ),
        )}
      </div>
    </div>
  );
}
