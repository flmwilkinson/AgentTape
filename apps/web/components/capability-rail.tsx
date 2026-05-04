import Link from "next/link";
import { ArrowUpRight, Github, Globe } from "lucide-react";
import { api, type AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";

// "Top 3 per capability" rail for the floor page. Each row links into
// the agent's ticker page; the icons jump straight to the external
// source — GitHub / homepage / HF model page — so a reader can go
// from the home page to the actual codebase in one click.

type Capability = {
  slug: string;
  label: string;
  blurb: string;
};

// The capabilities surfaced here. Order is by perceived user-intent
// (coding agents are the most-searched category by a wide margin) —
// we don't want to bury what most readers came for.
const RAILS: Capability[] = [
  { slug: "code-generation", label: "Coding", blurb: "Write code, review PRs, ship features." },
  { slug: "browsing", label: "Browser", blurb: "Drive a real browser to do tasks for you." },
  { slug: "rag", label: "RAG", blurb: "Retrieve from your data, then answer." },
  { slug: "multi-agent", label: "Multi-agent", blurb: "Orchestrate teams of agents." },
  { slug: "research", label: "Research", blurb: "Read, summarise, cite the literature." },
  { slug: "automation", label: "Automation", blurb: "Run repeated workflows on autopilot." },
];

export async function CapabilityRail() {
  // Six small tag-filtered queries in parallel — total round-trip is
  // dominated by the slowest, ~50–100 ms in dev.
  const groups = await Promise.all(
    RAILS.map(async (cap) => {
      const page = await api
        .listAgents({
          tag_kind: "capability",
          tag_value: cap.slug,
          sort: "score",
          limit: 3,
        })
        .catch(() => ({ items: [] as AgentSummary[], total: 0, limit: 3, offset: 0 }));
      return { cap, items: page.items };
    }),
  );

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
              href={`/search?kind=capability&value=${cap.slug}`}
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
