"use client";

import { Suspense } from "react";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";
import { AgentSearchHit } from "@/components/agent-search-hit";
import { SearchCombobox } from "@/components/search-combobox";

// URL-as-state: ?q=...&mode=text|vibe&kind=...&value=...
// Filter URLs are shareable.

// Next 15 requires useSearchParams to live below a Suspense boundary
// so the build can statically render the rest of the route. We wrap
// the inner component here; the outer default export is the Suspense
// shell that satisfies the pre-render check.
export default function SearchPage() {
  return (
    <Suspense fallback={<SearchSkeleton />}>
      <SearchPageInner />
    </Suspense>
  );
}

function SearchSkeleton() {
  return (
    <div className="container py-8 md:py-12">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Search
      </div>
      <div className="mt-2 h-10 w-72 animate-pulse rounded-md bg-muted" />
      <div className="mt-6 h-9 w-full max-w-md animate-pulse rounded-md bg-muted" />
    </div>
  );
}

function SearchPageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const mode = (params.get("mode") as "text" | "vibe" | null) ?? "text";
  const kind = params.get("kind");
  const value = params.get("value");
  // Entity-kind tab. Search and tag-listing both return mixed
  // results; users frequently want either "just apps" or "just
  // models" — that's what /trending and /new already expose, so
  // /search gets the same control. Filter is applied client-side
  // post-fetch so the request stays one round-trip.
  const ek = (params.get("ek") as "all" | "application" | "foundation_model" | null) ?? "all";

  function setQuery(
    next: Partial<{
      q: string;
      mode: "text" | "vibe";
      kind: string | null;
      value: string | null;
      ek: "all" | "application" | "foundation_model";
    }>,
  ) {
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
    if (next.ek !== undefined) {
      next.ek === "all" ? cur.delete("ek") : cur.set("ek", next.ek);
    }
    router.replace(`/search?${cur.toString()}`);
  }

  // Unified search query. With a query string, we hit /search and
  // include the tag filter so text + facet combine on one request.
  // Without a query string, we hit /agents with a tag filter so the
  // sidebar still drives a result list — same UI, two backends.
  const { data: searchData, isLoading: searching } = useQuery({
    queryKey: ["search", q, mode, kind, value],
    queryFn: () =>
      api.search(q, mode, 30, kind && value ? { kind, value } : null),
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

  const allHits = searchData?.hits ?? [];
  const allFilter = filterData?.items ?? [];
  // Apply Kind filter post-fetch so the entire UI (results, facets,
  // filter pane) reads consistently with the chosen tab.
  const hits =
    ek === "all"
      ? allHits
      : allHits.filter((h) => h.agent.entity_kind === ek);
  const filteredFilter =
    ek === "all"
      ? allFilter
      : allFilter.filter((a) => a.entity_kind === ek);
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

      {/* Smart search: combobox with prefix-prioritised autocomplete.
          On /search specifically, Enter without a highlighted match
          stays on the page and runs the search using the current
          mode (text or vibe). Selecting a suggestion still jumps to
          its detail page. */}
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:flex-wrap">
        <SearchCombobox
          className="flex-1 min-w-[260px]"
          inputClassName="h-11 text-sm"
          placeholder="autonomous browser agent, claude, gemini…"
          initialQuery={q}
          onEnter={(next) => setQuery({ q: next })}
        />
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
        <div className="inline-flex rounded-md border border-border bg-card p-0.5">
          {(
            [
              { v: "all" as const, label: "All" },
              { v: "application" as const, label: "Apps" },
              { v: "foundation_model" as const, label: "Models" },
            ]
          ).map((k) => (
            <button
              key={k.v}
              type="button"
              onClick={() => setQuery({ ek: k.v })}
              className={cn(
                "rounded-sm px-3 py-2 text-xs font-mono uppercase tracking-wider transition-colors",
                ek === k.v
                  ? "bg-subtle text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {k.label}
            </button>
          ))}
        </div>
      </div>

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
          {!q && filteredFilter.map((a) => (
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
