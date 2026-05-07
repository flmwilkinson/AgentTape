"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ARTICLE_KIND_TAG,
  type ArticleKind,
  type ArticleMeta,
} from "@/lib/articles";

// Client filter UI for the articles index. Lives in its own file so
// the server page can pass *only* the metadata across the boundary —
// keeping every article's heavy `body` JSX out of the client bundle.
//
// Layout:
//   1. Featured "live" cards. Today the only live article is the
//      auto-generated weekly recap; pinned at the top so the always-
//      fresh report is the first thing visitors see.
//   2. Filter row: search input + kind chips + month dropdown.
//      Search matches title / description / keywords case-insensitively.
//   3. Card grid of remaining articles, each with a kind-coloured chip.

const ALL_KINDS: ArticleKind[] = ["weekly", "report", "guide", "comparison"];

interface Props {
  articles: ArticleMeta[];
}

export function ArticlesIndex({ articles }: Props) {
  const [query, setQuery] = useState("");
  const [kindFilter, setKindFilter] = useState<ArticleKind | "all">("all");
  const [month, setMonth] = useState<string>("all"); // YYYY-MM or "all"

  const featured = articles.filter((a) => a.live);
  const restPool = articles.filter((a) => !a.live);

  // Build the unique YYYY-MM list once from non-live articles. The
  // weekly recap's published_at is "this Monday", which would
  // otherwise show up as a phantom month here.
  const months = useMemo(() => {
    const set = new Set<string>();
    for (const a of restPool) {
      const d = new Date(a.published_at);
      set.add(
        `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`,
      );
    }
    return [...set].sort().reverse();
  }, [restPool]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return restPool.filter((a) => {
      if (kindFilter !== "all" && a.kind !== kindFilter) return false;
      if (month !== "all") {
        const d = new Date(a.published_at);
        const ym = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
        if (ym !== month) return false;
      }
      if (q.length > 0) {
        const hay = (
          a.title +
          " " +
          a.description +
          " " +
          (a.keywords ?? []).join(" ")
        ).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [restPool, query, kindFilter, month]);

  const anyFilter =
    query.trim().length > 0 || kindFilter !== "all" || month !== "all";

  return (
    <article className="container py-10 md:py-14 max-w-5xl space-y-10">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Articles
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          Field notes from the floor.
        </h1>
        <p className="editorial mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
          A weekly recap that recomputes itself, plus deeper guides and
          comparisons against the same live data that drives the indexes.
        </p>
      </header>

      {featured.length > 0 && (
        <section>
          <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            This week — auto-generated
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {featured.map((a) => (
              <FeaturedCard key={a.slug} article={a} />
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative flex-1 md:max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search articles…"
              className="h-9 w-full rounded-md border border-border bg-card pl-9 pr-9 text-sm placeholder:text-muted-foreground/70 focus:outline-none focus:ring-1 focus:ring-primary"
              autoComplete="off"
              data-1p-ignore
              data-lpignore="true"
              suppressHydrationWarning
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-0.5 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          <div className="inline-flex flex-wrap gap-1.5">
            <KindChip
              active={kindFilter === "all"}
              onClick={() => setKindFilter("all")}
              label="All"
            />
            {ALL_KINDS.map((k) => (
              <KindChip
                key={k}
                active={kindFilter === k}
                onClick={() => setKindFilter(k)}
                label={ARTICLE_KIND_TAG[k].label}
                tone={ARTICLE_KIND_TAG[k].tone}
              />
            ))}
          </div>

          {months.length > 1 && (
            <select
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-2 text-xs"
              aria-label="Filter by month"
            >
              <option value="all">All months</option>
              {months.map((m) => (
                <option key={m} value={m}>
                  {new Date(m + "-01T00:00:00Z").toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "long",
                    timeZone: "UTC",
                  })}
                </option>
              ))}
            </select>
          )}

          {anyFilter && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setKindFilter("all");
                setMonth("all");
              }}
              className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          )}

          <span className="ml-auto text-xs text-muted-foreground">
            {filtered.length} of {restPool.length}
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-card px-6 py-10 text-center text-sm text-muted-foreground">
            No articles match these filters.
          </div>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {filtered.map((a) => (
              <li key={a.slug}>
                <ArticleCard article={a} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}

// ----------------------------------------------------------- atoms

function FeaturedCard({ article: a }: { article: ArticleMeta }) {
  const tag = ARTICLE_KIND_TAG[a.kind];
  const href = a.external_href ?? `/articles/${a.slug}`;
  return (
    <Link
      href={href}
      className="group relative block rounded-md border-2 border-primary/30 bg-primary/[0.03] p-5 transition-colors hover:bg-primary/[0.06] md:p-6"
    >
      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
        {a.live && (
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[9px] text-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            Live
          </span>
        )}
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[9px]",
            tag.tone,
          )}
        >
          {tag.label}
        </span>
        <span className="text-muted-foreground">
          {new Date(a.published_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>
      <h2 className="editorial mt-2 text-2xl font-semibold leading-tight md:text-3xl group-hover:text-primary">
        {a.title}
      </h2>
      <p className="mt-2 text-sm text-muted-foreground md:text-base">
        {a.description}
      </p>
    </Link>
  );
}

function ArticleCard({ article: a }: { article: ArticleMeta }) {
  const tag = ARTICLE_KIND_TAG[a.kind];
  const href = a.external_href ?? `/articles/${a.slug}`;
  return (
    <Link
      href={href}
      className="block h-full rounded-md border border-border bg-card p-5 transition-colors hover:border-foreground/20 hover:bg-subtle"
    >
      <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
        <span
          className={cn("rounded-full border px-2 py-0.5 text-[9px]", tag.tone)}
        >
          {tag.label}
        </span>
        <span className="text-muted-foreground">
          {new Date(a.published_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}
        </span>
        {a.author && (
          <>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-muted-foreground">{a.author}</span>
          </>
        )}
      </div>
      <div className="mt-2 text-base font-medium leading-snug">{a.title}</div>
      <p className="mt-1 text-sm text-muted-foreground">{a.description}</p>
    </Link>
  );
}

function KindChip({
  active,
  onClick,
  label,
  tone,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  tone?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider transition-colors",
        active
          ? tone ?? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-subtle hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}
