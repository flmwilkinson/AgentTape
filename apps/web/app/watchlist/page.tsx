"use client";

import Link from "next/link";
import { Star } from "lucide-react";
import { useQueries } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { useWatchlist } from "@/lib/watchlist";
import { MobileRankList, type MobileRankItem } from "@/components/mobile-rank-list";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// /watchlist — pinned agents, rendered as a personal floor.
//
// Cookie-based, no auth. The list lives in `agenttape_watch`; star
// toggles update it in place across tabs that share the cookie. The
// data fetches a /agents/{slug} per pinned entry — small N so the
// individual fetch overhead is fine.

export default function WatchlistPage() {
  const slugs = useWatchlist();
  const queries = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ["agent", slug],
      queryFn: () => api.getAgent(slug),
    })),
  });

  return (
    <div className="container py-8 md:py-12 space-y-8">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Watchlist
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Your pinned stocks.
        </h1>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Stored in a cookie on this device. Nothing leaves your browser
          — no account required. Use the star button on any agent's
          ticker page to add it here.
        </p>
      </header>

      {slugs.length === 0 ? (
        <section className="rounded-md border border-dashed border-border bg-card p-8 text-center">
          <Star
            className="mx-auto h-6 w-6 text-muted-foreground/50"
            strokeWidth={1.75}
          />
          <p className="mt-3 text-sm text-muted-foreground">
            Your watchlist is empty.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Tap the star in the{" "}
            <Link href="/" className="text-primary hover:underline">
              Watch
            </Link>{" "}
            column on any agent table, or in the header of an{" "}
            <Link href="/" className="text-primary hover:underline">
              agent's
            </Link>{" "}
            page.
          </p>
        </section>
      ) : (
        <>
        <MobileRankList
          items={queries
            .map<MobileRankItem | null>((q, i) => {
              const a = q.data;
              if (!a) return null;
              return {
                slug: a.slug,
                name: a.name,
                label:
                  a.entity_kind === "foundation_model" ? "model" : "agent",
                rank: a.score?.rank_now ?? null,
                score: a.score?.agent_score ?? null,
                delta24h: a.score?.delta_24h ?? null,
                rankDelta24h: a.score?.rank_delta_24h ?? null,
                showCompare: false,
              };
            })
            .filter((x): x is MobileRankItem => x !== null)}
        />
        <section className="hidden overflow-x-auto rounded-md border border-border bg-card md:block">
          <table className="num w-full min-w-[640px] text-sm">
            <thead className="text-xs uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-3 py-2 text-left">Agent</th>
                <th className="px-3 py-2 text-right">Rank</th>
                <th className="px-3 py-2 text-right">24h</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Δ24h</th>
                <th className="px-3 py-2 text-center w-12">Unpin</th>
              </tr>
            </thead>
            <tbody>
              {queries.map((q, i) => {
                const slug = slugs[i];
                const a = q.data;
                if (!a) {
                  return (
                    <tr key={slug} className="border-b border-border last:border-b-0">
                      <td colSpan={6} className="px-4 py-3 text-xs text-muted-foreground">
                        Loading {slug}…
                      </td>
                    </tr>
                  );
                }
                return (
                  <tr key={`${a.slug}-${a.id}`} className="border-b border-border last:border-b-0">
                    <td className="px-3 py-2">
                      <Link
                        href={`/agents/${a.slug}`}
                        className="font-sans font-medium hover:text-primary"
                      >
                        {a.name}
                      </Link>
                      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {a.entity_kind === "foundation_model" ? "model" : "agent"}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right text-muted-foreground">
                      {a.score?.rank_now ?? "—"}
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
                    <td className="px-3 py-2 text-center">
                      <WatchToggle slug={a.slug} size="sm" />
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
