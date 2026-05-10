import Link from "next/link";
import { ArrowUpRight, Github, Globe } from "lucide-react";
import { formatScore } from "@/lib/format";
import { MoverChip } from "@/components/mover-chip";
import { CAPABILITIES } from "@/lib/taxonomy";

// "Top 3 per capability" rail for the floor page. Pure presentation —
// the Floor page fetches /sectors/top server-side and passes the
// groups in. Render contract:
//
//   • groups === null  → upstream errored; render an actionable
//                        "couldn't load" panel with a fallback link
//                        per capability so the user is never staring
//                        at silent empty boxes.
//   • groups === []    → upstream returned, but no capability has any
//                        admitted-and-tagged agents yet. Same panel
//                        but with a different copy ("no listings yet").
//   • groups[].agents.length === 0 for some entries  → silently drop
//                        those capabilities; show the rest normally.
//
// Why this is a SERVER component (with data passed in):
//   The previous version did 10 parallel /agents calls from the
//   browser, which worked locally but timed out in production for
//   half the capabilities under the 2s client budget — so the rail
//   came back empty for real users. Routing the rail through one
//   server-side /sectors/top fetch (cached by Next ISR) means the
//   rail is now as reliable as /sectors and /search, which already
//   work, and adds zero JS to the client bundle.

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

const RAIL_ORDER = new Map(CAPABILITIES.map((c, i) => [c.slug, i]));

export type CapabilityGroup = {
  value: string;
  display_name: string;
  agents: {
    id: string;
    slug: string;
    name: string;
    entity_kind: string;
    homepage_url: string | null;
    github_repo: string | null;
    score: {
      agent_score: number | null;
      delta_24h: number | null;
    };
  }[];
};

interface Props {
  // Pass null when the upstream fetch errored, [] when it succeeded
  // with no data. Lets us render a different empty-state copy for
  // each so the user can act on what's actually wrong.
  groups: CapabilityGroup[] | null;
}

export function CapabilityRail({ groups }: Props) {
  // Upstream failed — give the user a working alternative instead
  // of pretending nothing happened. The capability links below /are/
  // a useful fallback because they hit /sectors/{kind}/{value},
  // which is on a different code path than /sectors/top.
  if (groups === null) {
    return (
      <FallbackPanel
        kicker="Top-agents rail unavailable"
        body={
          <>
            We couldn&apos;t load the live top-3 per capability — the
            server returned an error. The capability cards below still
            link through to the full sector pages (filters, compare,
            scorecards) so you can browse without it.
          </>
        }
      />
    );
  }

  const filtered = groups
    .filter((g) => g.agents.length > 0 && BLURBS[g.value] !== undefined)
    .sort(
      (a, b) =>
        (RAIL_ORDER.get(a.value) ?? 999) - (RAIL_ORDER.get(b.value) ?? 999),
    );

  if (filtered.length === 0) {
    return (
      <FallbackPanel
        kicker="No listings yet"
        body={
          <>
            No agents have been tagged + admitted into a capability yet.
            New listings appear here automatically once the discovery
            service tags and the scoring service rates them.
          </>
        }
      />
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {filtered.map((g) => (
        <div
          key={g.value}
          className="rounded-md border border-border bg-card"
        >
          <div className="flex items-baseline justify-between border-b border-border px-4 py-2.5">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                {g.display_name}
              </div>
              <div className="text-xs text-muted-foreground">
                {BLURBS[g.value]}
              </div>
            </div>
            <Link
              href={`/sectors/capability/${g.value}`}
              className="text-[10px] font-mono uppercase tracking-wider text-primary hover:underline"
            >
              All →
            </Link>
          </div>
          <ul>
            {g.agents.map((a, i) => (
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
                  <MoverChip
                    delta={a.score.delta_24h}
                    unit="score"
                    variant="outline"
                  />
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

// Skeleton for Suspense-style boundaries while the fetch is in
// flight. Imported by the Floor page directly.
export function CapabilityRailSkeleton() {
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

function FallbackPanel({
  kicker,
  body,
}: {
  kicker: string;
  body: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-dashed border-border bg-card/40 p-4 text-sm text-muted-foreground">
      <div className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/70">
        {kicker}
      </div>
      <p className="max-w-2xl">{body}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {CAPABILITIES.map((c) => (
          <Link
            key={c.slug}
            href={`/sectors/capability/${c.slug}`}
            className="rounded-md border border-border bg-background px-2.5 py-1 text-xs hover:border-primary/40 hover:bg-subtle"
          >
            {c.label} →
          </Link>
        ))}
      </div>
    </div>
  );
}

function ExternalLinks({ agent }: { agent: CapabilityGroup["agents"][number] }) {
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
