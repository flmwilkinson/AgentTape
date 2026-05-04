"use client";

import { Search as SearchIcon, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { AgentSearchHit } from "@/components/agent-search-hit";

// URL-as-state: ?q=...&mode=text|vibe&kind=...&value=...
// Filter URLs are shareable.

export default function SearchPage() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const mode = (params.get("mode") as "text" | "vibe" | null) ?? "text";
  const kind = params.get("kind");
  const value = params.get("value");

  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);

  function setQuery(next: Partial<{ q: string; mode: "text" | "vibe"; kind: string | null; value: string | null }>) {
    const cur = new URLSearchParams(params.toString());
    if (next.q !== undefined) {
      next.q ? cur.set("q", next.q) : cur.delete("q");
    }
    if (next.mode !== undefined) cur.set("mode", next.mode);
    if (next.kind !== undefined) {
      next.kind ? cur.set("kind", next.kind) : cur.delete("kind");
    }
    if (next.value !== undefined) {
      next.value ? cur.set("value", next.value) : cur.delete("value");
    }
    router.replace(`/search?${cur.toString()}`);
  }

  const { data: searchData, isLoading: searching } = useQuery({
    queryKey: ["search", q, mode],
    queryFn: () => api.search(q, mode, 30),
    enabled: q.length > 0,
  });
  const { data: filterData } = useQuery({
    queryKey: ["agents-filter", kind, value],
    queryFn: () =>
      api.listAgents({
        sort: "score",
        limit: 30,
        tag_kind: kind ?? undefined,
        tag_value: value ?? undefined,
      }),
    enabled: !q && (!!kind || !!value),
  });
  const { data: tags } = useQuery({
    queryKey: ["tags"],
    queryFn: api.tags,
  });

  const hits = searchData?.hits ?? [];
  const facets = searchData?.facets ?? {};

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Search
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          {kind && value ? (
            <>
              All <span className="font-mono text-2xl">{value}</span> agents.
            </>
          ) : (
            <>Find an agent.</>
          )}
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          {kind && value ? (
            <>
              Filtered by <span className="font-mono">{kind}:{value}</span>.{" "}
              Sorted by AgentScore. Use the input below to narrow further, or
              clear the filter from the sidebar.
            </>
          ) : (
            <>
              Type starts-of-name first (Gemini → Gemini matches first). Switch
              to <span className="font-medium">vibe</span> to search by
              embedding similarity (when configured).
            </>
          )}
        </p>
      </div>

      <form
        className="mb-6 flex flex-col gap-3 md:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery({ q: draft });
        }}
      >
        <div className="flex flex-1 items-center gap-2 rounded-md border border-border bg-card px-3">
          <SearchIcon className="h-4 w-4 text-muted-foreground" />
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="autonomous browser agent…"
            className="flex-1 bg-transparent py-2.5 text-sm outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {(["text", "vibe"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setQuery({ mode: m })}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-sm px-3 py-2 text-xs font-mono uppercase tracking-wider transition-colors",
                mode === m
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m === "vibe" && <Sparkles className="h-3 w-3" />} {m}
            </button>
          ))}
        </div>
      </form>

      <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
        {/* Facet sidebar */}
        <aside className="space-y-4 text-sm">
          <FacetSection title="Filter by tag" />
          {(tags ?? [])
            .reduce<Record<string, typeof tags>>((acc, t) => {
              if (!t) return acc;
              (acc[t.kind] ??= [] as never).push(t);
              return acc;
            }, {})
            && Object.entries(
              (tags ?? []).reduce<Record<string, typeof tags>>((acc, t) => {
                (acc[t.kind] ??= [] as never).push(t);
                return acc;
              }, {}),
            ).map(([k, ts]) => (
              <div key={k}>
                <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {k}
                </div>
                <ul className="space-y-0.5">
                  {(ts ?? []).slice(0, 8).map((t) => {
                    const active = kind === t.kind && value === t.value;
                    return (
                      <li key={`${t.kind}:${t.value}`}>
                        <button
                          type="button"
                          onClick={() =>
                            setQuery(
                              active
                                ? { kind: null, value: null }
                                : { kind: t.kind, value: t.value },
                            )
                          }
                          className={cn(
                            "flex w-full items-center justify-between rounded-sm px-1.5 py-1 text-left text-xs hover:bg-subtle",
                            active && "bg-subtle text-foreground",
                          )}
                        >
                          <span className="truncate">{t.display_name}</span>
                          <span className="num text-muted-foreground">{t.count}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
        </aside>

        {/* Results */}
        <section className="rounded-md border border-border bg-card divide-y divide-border">
          {q && searching && (
            <div className="px-4 py-6 text-sm text-muted-foreground">Searching…</div>
          )}
          {q && !searching && hits.length === 0 && (
            <div className="px-4 py-6 text-sm text-muted-foreground">
              No matches.
            </div>
          )}
          {q &&
            hits.map((h) => (
              <AgentSearchHit
                key={h.agent.id}
                agent={h.agent}
                similarity={h.similarity}
              />
            ))}
          {!q && filterData?.items.map((a) => (
            <AgentSearchHit key={a.id} agent={a} />
          ))}
          {!q && !filterData && (
            <div className="px-4 py-6 text-sm text-muted-foreground">
              Type to search, or pick a tag from the left.
            </div>
          )}
        </section>
      </div>

      {q && Object.keys(facets).length > 0 && (
        <section className="mt-10">
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Facets in this result set
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {Object.entries(facets).flatMap(([kind, vs]) =>
              (vs ?? []).slice(0, 6).map((v) => (
                <Link
                  key={`${kind}:${v.value}`}
                  href={`/search?kind=${kind}&value=${v.value}`}
                  className="rounded-full border border-border bg-subtle px-2.5 py-0.5 text-muted-foreground hover:text-foreground"
                >
                  <span className="font-mono uppercase tracking-wider mr-1.5 text-muted-foreground/70">
                    {kind}
                  </span>
                  {v.value}{" "}
                  <span className="num text-muted-foreground/60">{v.count}</span>
                </Link>
              )),
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function FacetSection({ title }: { title: string }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
      {title}
    </div>
  );
}
