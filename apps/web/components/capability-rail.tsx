"use client";

import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { ArrowUpRight, Github, Globe } from "lucide-react";
import { api, type AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { CAPABILITIES } from "@/lib/taxonomy";

// "Top 3 per capability" rail for the floor page. Each row links into
// the agent's ticker page; the icons jump straight to the external
// source — GitHub / homepage / HF model page — so a reader can go
// from the home page to the actual codebase in one click.
//
// Why this is a CLIENT component (browser-side fetch) rather than a
// server component:
//   The Floor's other server-side fetches (movers, indexes, top
//   agents) work fine, but ten parallel ``listAgents?tag_kind=...&
//   tag_value=...`` calls from Vercel's edge function to the Hetzner
//   API consistently came back empty in production. Same calls work
//   reliably from the browser — that's how /search renders the same
//   data without issue. The asymmetry is some combination of
//   connection-pool exhaustion, region routing, or per-call cold
//   start. Rather than chase the bug we use the path that's already
//   proven to work, with react-query for the cache + Suspense-style
//   skeleton via initialData/isPending.

const BLURBS: Record<string, string> = {
  "code-generation": "Write code, review PRs, ship features.",
  browsing: "Drive a real browser to do tasks for you.",
  research: "Read, summarise, cite the literature.",
  rag: "Retrieve from your data, then answer.",
  "multi-agent": "Orchestrate teams of agents.",
  automation: "Run repeated workflows on autopilot.",
  "tool-use": "Call APIs, run code, use tools.",
  memory: "Long-term recall across sessions.",
  vision: "See images, charts, screenshots.",
  voice: "Speak and listen in real time.",
};

const RAILS = CAPABILITIES.map((c) => ({
  slug: c.slug,
  label: c.label,
  blurb: BLURBS[c.slug] ?? "",
}));

export function CapabilityRail() {
  // One query per capability, all in parallel via useQueries. Each
  // is independently cached for 5 minutes so flipping back to the
  // Floor doesn't refetch immediately. Failed queries (timeouts,
  // 5xx) gracefully resolve to an empty group rather than blanking
  // the whole rail.
  const queries = useQueries({
    queries: RAILS.map((cap) => ({
      queryKey: ["capability-rail", cap.slug],
      queryFn: () =>
        api.listAgents({
          tag_kind: "capability",
          tag_value: cap.slug,
          sort: "score",
          limit: 3,
        }),
      staleTime: 5 * 60 * 1000,
      retry: 1,
    })),
  });

  const groups = RAILS.map((cap, i) => ({
    cap,
    items: queries[i].data?.items ?? [],
    isLoading: queries[i].isLoading,
  }));

  // While at least one query is still loading, render a skeleton
  // grid so the section keeps its space rather than collapsing to
  // zero height and jumping the page when results arrive.
  const anyLoading = groups.some((g) => g.isLoading);

  if (anyLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="animate-pulse rounded-md border border-border bg-card p-4 space-y-3"
          >
            <div className="h-3 w-20 rounded bg-muted/40" />
            <div className="h-4 w-full rounded bg-muted/30" />
            <div className="h-4 w-5/6 rounded bg-muted/30" />
            <div className="h-4 w-4/6 rounded bg-muted/30" />
          </div>
        ))}
      </div>
    );
  }

  const filled = groups.filter((g) => g.items.length > 0);
  if (filled.length === 0) return null;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {filled.map(({ cap, items }) => (
        <div
          key={cap.slug}
          className="rounded-md border border-border bg-card"
        >
          <div className="flex items-baseline justify-between border-b border-border px-4 py-2.5">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {cap.label}
              </div>
              <div className="text-xs text-muted-foreground">{cap.blurb}</div>
            </div>
            <Link
              href={`/sectors/capability/${cap.slug}`}
              className="text-[10px] font-mono uppercase tracking-wider text-primary hover:underline"
            >
              All →
            </Link>
          </div>
          <ul>
            {items.map((a, i) => (
              <li
                key={a.id}
                className="flex items-center gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
              >
                <span className="font-mono text-xs text-muted-foreground tabular-nums">
                  #{i + 1}
                </span>
                <Link
                  href={`/agents/${a.slug}`}
                  className="min-w-0 flex-1 truncate text-sm hover:text-primary"
                >
                  {a.name}
                </Link>
                <span className="num text-sm font-semibold">
                  {formatScore(a.score?.agent_score ?? null)}
                </span>
                {a.score?.delta_24h != null ? (
                  <MoverChip delta={a.score.delta_24h} unit="score" variant="outline" />
                ) : null}
                <ExternalLinks agent={a} />
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ExternalLinks({ agent }: { agent: AgentSummary }) {
  const links: { href: string; icon: typeof Github; label: string }[] = [];
  if (agent.github_repo) {
    links.push({
      href: `https://github.com/${agent.github_repo}`,
      icon: Github,
      label: "GitHub repo",
    });
  } else if (agent.homepage_url) {
    links.push({
      href: agent.homepage_url,
      icon: Globe,
      label: "Homepage",
    });
  }
  if (links.length === 0) {
    return (
      <Link
        href={`/agents/${agent.slug}`}
        aria-label="Ticker page"
        className="text-muted-foreground hover:text-foreground"
      >
        <ArrowUpRight className="h-3.5 w-3.5" />
      </Link>
    );
  }
  return (
    <div className="inline-flex items-center gap-1.5">
      {links.map((l) => {
        const Icon = l.icon;
        return (
          <a
            key={l.href}
            href={l.href}
            target="_blank"
            rel="noreferrer"
            aria-label={l.label}
            className="text-muted-foreground hover:text-foreground"
          >
            <Icon className="h-3.5 w-3.5" />
          </a>
        );
      })}
    </div>
  );
}
