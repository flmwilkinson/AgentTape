import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { RankArrow } from "@/components/rank-arrow";
import { WatchToggle } from "@/components/watch-toggle";

// Foundation-model board.
//
// Pulls every admitted agent whose `entity_kind = 'foundation_model'`.
// (The filter happens server-side via the FM-50 index when populated;
// we additionally show the full set here, sorted by score.)

export const dynamic = "force-dynamic";
export const metadata = { title: "Models" };

export default async function ModelsPage() {
  // FM-50 already publishes the curated, ranked top-50 foundation
  // models. We render straight from the index constituents so the
  // ordering matches /indexes/fm-50 exactly — no need to refilter
  // /agents (which is capped at the application-agent population).
  const fmIndex = await api.getIndex("fm-50").catch(() => null);
  const models = (fmIndex?.constituents ?? [])
    .map((c) => c.agent)
    .sort(
      (a, b) => (b.score?.agent_score ?? 0) - (a.score?.agent_score ?? 0),
    );

  return (
    <div className="container py-8 md:py-12 space-y-10">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Foundation models
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          The model board.
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-muted-foreground md:text-base">
          Foundation models tracked as their own stocks — distinct from
          application agents because the inputs that matter (benchmark
          performance, context length, openness, pricing) differ from
          adoption-driven application metrics. The flagship index here is{" "}
          <Link href="/indexes/fm-50" className="text-primary hover:underline">FM-50</Link>.
        </p>
      </header>

      {models.length === 0 ? (
        <section className="rounded-md border border-dashed border-border bg-card p-8 text-center">
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            No models yet
          </div>
          <p className="editorial mt-3 max-w-prose mx-auto text-base leading-relaxed text-muted-foreground">
            The foundation-model board is warming up. Models stream in from
            the OpenRouter catalogue on a daily schedule — check back shortly.
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
              {models.map((m, i) => (
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
                      {m.discovered_via.replace(/_/g, " ")}
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
                      <MoverChip delta={m.score.delta_24h} unit="score" variant="outline" />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right hidden md:table-cell">
                    {m.score?.adoption?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right text-muted-foreground hidden md:table-cell">
                    {m.score?.quality === null ? "Unrated" : m.score?.quality?.toFixed(1) ?? "—"}
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
