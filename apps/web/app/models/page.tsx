import Link from "next/link";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { Sparkline } from "@/components/sparkline";

// Foundation-model board.
//
// Pulls every admitted agent whose `entity_kind = 'foundation_model'`.
// (The filter happens server-side via the FM-50 index when populated;
// we additionally show the full set here, sorted by score.)

export const dynamic = "force-dynamic";
export const metadata = { title: "Models" };

export default async function ModelsPage() {
  // For now we filter via the existing /agents endpoint plus a tag-style
  // query. Once the entity_kind column ships through to the API, this
  // becomes a single ?entity_kind=foundation_model filter.
  const [fmIndex, allAgents] = await Promise.all([
    api.getIndex("fm-50").catch(() => null),
    api.listAgents({ sort: "score", limit: 100 }),
  ]);

  // Treat anything in FM-50 as a foundation model. Until the scout runs,
  // FM-50 is empty and this page renders an empty-state explainer.
  const fmSlugs = new Set(fmIndex?.constituents.map((c) => c.agent.slug) ?? []);
  const models = allAgents.items.filter((a) => fmSlugs.has(a.slug));

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
        <section className="rounded-md border border-dashed border-border bg-card p-8">
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            FM-50 — empty
          </div>
          <p className="editorial mt-3 max-w-prose text-base leading-relaxed text-foreground/85">
            The foundation-model scout pulls from{" "}
            <a
              href="https://openrouter.ai/api/v1/models"
              target="_blank"
              rel="noreferrer"
              className="text-primary hover:underline"
            >
              openrouter.ai/api/v1/models
            </a>
            {" "}on its own schedule. If you're seeing this page empty, the
            scout hasn't run yet — kick it off from the discovery service:
          </p>
          <pre className="mt-4 overflow-x-auto rounded bg-muted px-3 py-2 font-mono text-xs">
            python -m discovery.run openrouter_models
          </pre>
        </section>
      ) : (
        <section className="overflow-hidden rounded-md border border-border bg-card">
          <table className="num w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-muted-foreground">
              <tr className="border-b border-border">
                <th className="px-4 py-2 text-right">#</th>
                <th className="px-4 py-2 text-left">Model</th>
                <th className="px-4 py-2 text-left">Source</th>
                <th className="px-4 py-2 text-right">Score</th>
                <th className="px-4 py-2 text-right">Adoption</th>
                <th className="px-4 py-2 text-right">Quality</th>
                <th className="px-4 py-2 text-right">Momentum</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => (
                <tr key={m.id} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2 text-right text-muted-foreground">{i + 1}</td>
                  <td className="px-4 py-2">
                    <Link
                      href={`/agents/${m.slug}`}
                      className="font-sans font-medium hover:text-primary"
                    >
                      {m.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    {m.discovered_via.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-2 text-right font-semibold">
                    {formatScore(m.score?.agent_score ?? null)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {m.score?.adoption?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-muted-foreground">
                    {m.score?.quality === null ? "Unrated" : m.score?.quality?.toFixed(1) ?? "—"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {m.score?.momentum?.toFixed(1) ?? "—"}
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
