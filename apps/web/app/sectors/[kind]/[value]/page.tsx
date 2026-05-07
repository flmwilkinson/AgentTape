import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { BackLink } from "@/components/back-link";
import { MoverChip } from "@/components/mover-chip";
import { SectorChart } from "@/components/sector-chart";
import { SectorMembersPanel } from "@/components/sector-members-panel";

// Sector detail — like an index page but rolled up by tag.
//
// Shows:
//   - cohort headline (avg AgentScore, member count, verdict)
//   - 30d composite chart (avg score over time)
//   - members table, ranked by score, with watch toggles
// The same shape as /indexes/[slug] so the mental model stays
// consistent: "another index, just one rolled up by capability".

const VALID_KINDS = ["capability", "deployment", "maturity", "domain", "license"];

export const dynamic = "force-dynamic";

interface PageParams {
  params: Promise<{ kind: string; value: string }>;
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { kind, value } = await params;
  return {
    title: `${pretty(value)} agents — ${kind} sector`,
    description: `Live ranking of agents tagged ${kind}:${value}. Composite chart, member list, AgentScore.`,
    alternates: { canonical: `/sectors/${kind}/${value}` },
  };
}

export default async function SectorDetailPage({ params }: PageParams) {
  const { kind, value } = await params;
  if (!VALID_KINDS.includes(kind)) notFound();

  // Members are server-loaded; the chart is now a client component
  // that fetches history per chosen window. We still pull a quick
  // 7d slice here just to compute the headline composite + delta.
  const [history, members] = await Promise.all([
    api.sectorHistory(kind, value, "7d").catch(() => []),
    api.listAgents({
      tag_kind: kind,
      tag_value: value,
      sort: "score",
      limit: 100,
    }).catch(() => null),
  ]);

  // Empty sector — no admitted agents carry this tag yet. Render an
  // explainer + a route back to /sectors instead of a hard 404. Bad
  // 404s look like a broken site to users who clicked from a chip.
  if (!members || members.items.length === 0) {
    return (
      <article>
        <div className="border-b border-border bg-card">
          <div className="container py-10">
            <BackLink href="/sectors" label="All sectors" className="mb-4" />
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Sector · {kind}
            </div>
            <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
              {pretty(value)}
            </h1>
            <p className="mt-2 max-w-prose text-sm text-muted-foreground">
              No admitted agents are tagged{" "}
              <span className="font-mono">{kind}:{value}</span> yet. The
              discovery service tags agents as it admits them — check
              back, or browse the sectors that already have members.
            </p>
            <div className="mt-6">
              <Link
                href="/sectors"
                className="text-sm font-medium text-primary hover:underline"
              >
                Browse sectors with members →
              </Link>
            </div>
          </div>
        </div>
      </article>
    );
  }

  const composite =
    history.length > 0 ? history.at(-1)?.avg_score ?? null : null;
  const first = history.length > 0 ? history[0]?.avg_score ?? null : null;
  const delta =
    composite != null && first != null ? composite - first : null;

  return (
    <article>
      <div className="border-b border-border bg-card">
        <div className="container py-10">
          <BackLink href="/sectors" label="All sectors" className="mb-4" />
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Sector · {kind}
          </div>
          <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-5xl">
            {pretty(value)}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Cohort of {members.total} admitted agents tagged{" "}
            <span className="font-mono">{kind}:{value}</span>. Composite
            below is the cohort's average AgentScore.
          </p>

          <div className="mt-6 grid gap-6 md:grid-cols-[auto_1fr]">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Avg AgentScore
              </div>
              <div className="mt-1 text-stat-xl font-semibold num">
                {formatScore(composite)}
              </div>
              {delta !== null && (
                <div className="mt-1">
                  <MoverChip delta={delta} unit="score" />
                  <span className="ml-2 text-xs text-muted-foreground">
                    vs 30d ago
                  </span>
                </div>
              )}
            </div>
            <div className="min-w-0">
              <SectorChart kind={kind} value={value} />
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8 md:py-12 space-y-8 pb-24 md:pb-12">
        <SectorMembersPanel members={members.items} />

        <p className="hairline pt-6 text-xs text-muted-foreground">
          Browse all sectors at{" "}
          <Link href="/sectors" className="text-primary hover:underline">
            /sectors
          </Link>
          .
        </p>
      </div>
    </article>
  );
}

function pretty(value: string): string {
  return value
    .split("-")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}
