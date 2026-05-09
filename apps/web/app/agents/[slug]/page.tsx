import Link from "next/link";
import { notFound } from "next/navigation";
import { Download, ExternalLink, Github } from "lucide-react";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore, relativeTime } from "@/lib/format";
import { AgentBadgeSnippet } from "@/components/agent-badge-snippet";
import { AgentLiveHeader } from "@/components/agent-live-header";
import { BackLink } from "@/components/back-link";
import { FmFactsPanel } from "@/components/fm-facts-panel";
import { ScoreBreakdownPanel } from "@/components/score-breakdown-panel";
import { TickerCard } from "@/components/ticker-card";

// 5-minute ISR. Cached HTML keeps serving when the backend is slow or
// unreachable; only first-time renders for an uncached slug actually
// hit the API. Trade-off: a 5-minute lag on score moves vs a hard
// outage when Hetzner blips.
export const revalidate = 300;

export async function generateMetadata(
  { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
  const { slug } = await params;
  try {
    const a = await api.getAgent(slug);
    return {
      title: a.name,
      description: a.description ?? `${a.name} on AgentTape`,
      openGraph: {
        title: `${a.name} — AgentTape`,
        description: a.description ?? `${a.name} on AgentTape`,
        images: [{ url: `/api/og/agent/${a.slug}` }],
      },
    };
  } catch {
    return { title: slug };
  }
}

export default async function AgentPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let agent;
  try {
    agent = await api.getAgent(slug);
  } catch {
    notFound();
  }
  const [signals, similar, benchmarks] = await Promise.all([
    api.agentSignals(slug, { window: "30d" }).catch(() => []),
    api.agentSimilar(slug, 6).catch(() => []),
    api.agentBenchmarks(slug).catch(() => []),
  ]);

  // JSON-LD structured data — schema.org/Dataset is the closest fit
  // since each agent is a thing-described-by-stats here.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: agent.name,
    description: agent.description ?? undefined,
    identifier: agent.slug,
    url: `/agents/${agent.slug}`,
    keywords: agent.tags.map((t) => t.value).join(", "),
    distribution: agent.github_repo
      ? [
          {
            "@type": "DataDownload",
            contentUrl: `https://github.com/${agent.github_repo}`,
          },
        ]
      : undefined,
  };

  return (
    <article>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="container pt-4">
        <BackLink
          href={agent.entity_kind === "foundation_model" ? "/models" : "/"}
          label={agent.entity_kind === "foundation_model" ? "Models" : "Floor"}
        />
      </div>

      <AgentLiveHeader agent={agent} />

      <div className="container py-8 md:py-12 space-y-12">
        {/* External + meta */}
        <section className="flex flex-wrap items-center gap-4 text-sm">
          {agent.github_repo && (
            <a
              href={`https://github.com/${agent.github_repo}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <Github className="h-4 w-4" /> {agent.github_repo}
            </a>
          )}
          {agent.homepage_url && (
            <a
              href={agent.homepage_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" /> Homepage
            </a>
          )}
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"}/agents/${slug}/signals.csv?window=30d`}
            className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground"
            aria-label="Download raw signals (CSV, last 30 days)"
          >
            <Download className="h-4 w-4" /> Signals CSV
          </a>
          <span className="ml-auto text-xs text-muted-foreground">
            Discovered {relativeTime(agent.discovered_at)}
          </span>
        </section>

        {/* Unified score breakdown: time-series chart at the top,
            collapsible per-pillar contributions below. Each pillar
            row shows its current score, 24h delta, and (when
            expanded) every signal feeding it with raw + scaled
            values. Replaces the previous trio of "How computed",
            "Breakdown chart" and "What moved" panels — same data,
            one place. */}
        <ScoreBreakdownPanel slug={slug} agent={agent} signals={signals} />

        {/* Foundation-model facts (only renders for FMs). The panel
            surfaces the OpenRouter metadata that's *not* used for
            scoring — context length, pricing, modality — so readers
            can still sanity-check what the model is. */}
        {agent.entity_kind === "foundation_model" && (
          <FmFactsPanel facts={agent.facts ?? {}} />
        )}

        {/* Embeddable badge for the agent's author. */}
        <AgentBadgeSnippet slug={slug} />

        {/* Benchmarks */}
        {benchmarks.length > 0 && (
          <section>
            <SectionHead label="Benchmarks" />
            <div className="overflow-hidden rounded-md border border-border bg-card">
              <table className="num w-full text-sm">
                <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="px-4 py-2 text-left">Benchmark</th>
                    <th className="px-4 py-2 text-right">Score</th>
                    <th className="px-4 py-2 text-right">Max</th>
                    <th className="px-4 py-2 text-right">Captured</th>
                  </tr>
                </thead>
                <tbody>
                  {benchmarks.map((b) => (
                    <tr key={b.benchmark_id} className="border-b border-border last:border-b-0">
                      <td className="px-4 py-2 font-mono">{b.benchmark_name}</td>
                      <td className="px-4 py-2 text-right font-semibold">
                        {b.score.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 text-right text-muted-foreground">
                        {b.max_score?.toFixed(2) ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-right text-muted-foreground">
                        {relativeTime(b.captured_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Similar */}
        {similar.length > 0 && (
          <section>
            <SectionHead
              label="Similar"
              hint="Vibe-search via embedding cosine"
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {similar.map((s) => (
                <TickerCard key={s.agent.id} agent={s.agent} />
              ))}
            </div>
          </section>
        )}

        {/* Manipulation flags — only render if any are present. Quietly. */}
        {agent.manipulation_flags &&
          Object.keys(agent.manipulation_flags).length > 0 && (
            <section className="rounded-md border border-loss/40 bg-loss-subtle p-4">
              <div className="font-mono text-[10px] uppercase tracking-wider text-loss">
                Integrity flags
              </div>
              <ul className="mt-2 space-y-1 text-sm">
                {Object.entries(agent.manipulation_flags).map(([rule, body]) => (
                  <li key={rule} className="text-foreground/85">
                    <span className="font-mono text-xs">{rule}</span>{" "}
                    <span className="text-muted-foreground">
                      —{" "}
                      {(body as { reason?: string })?.reason ?? "flagged"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

        <div className="hairline pt-6 text-xs text-muted-foreground">
          Score envelope last computed{" "}
          {relativeTime(agent.score?.computed_at ?? null)}.{" "}
          {agent.score?.quality === null
            ? "Quality is Unrated — agent has no benchmark results yet."
            : null}
        </div>
      </div>
    </article>
  );
}

function SectionHead({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="mb-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
