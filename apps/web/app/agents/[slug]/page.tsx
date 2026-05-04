import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink, Github } from "lucide-react";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore, relativeTime } from "@/lib/format";
import { AgentBreakdownChart } from "@/components/agent-breakdown-chart";
import { AgentLiveHeader } from "@/components/agent-live-header";
import { AgentSignalPanel } from "@/components/agent-signal-panel";
import { ScoreContributors } from "@/components/score-contributors";
import { TickerCard } from "@/components/ticker-card";

export const dynamic = "force-dynamic";

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
          <span className="ml-auto text-xs text-muted-foreground">
            Discovered {relativeTime(agent.discovered_at)}
          </span>
        </section>

        {/* Score breakdown chart — overall + four pillar lines, since
            this agent first listed. Reading the lines together is how
            you tell which pillar carried (or dragged) the headline. */}
        <AgentBreakdownChart slug={slug} />

        {/* What moved this score in the last 24 hours — rules-based
            attribution surfaced from the same signals the score uses. */}
        <ScoreContributors signals={signals} />

        {/* Signal time-series */}
        <AgentSignalPanel slug={slug} initial={signals} />

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
