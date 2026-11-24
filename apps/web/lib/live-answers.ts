import type { AgentSummary } from "@/lib/api-client";
import { formatScore } from "@/lib/format";

// Live answers for ranking pages (/top/*, /sectors/*).
//
// The rankings are live, so answers never carry a date or a hard-coded
// winner: anything the data can answer ("best right now", "which are
// open source", "what's gaining") is computed from the current members
// on each render (5-minute ISR); anything it can't points at the live
// charts and score breakdowns. Facts about scoring must match
// /methodology (pillar weights, hourly/daily refresh, Monday
// rebalance); update both together.

export interface Leaders {
  // Best first, by AgentScore. Empty when the ranking has no members.
  top: { name: string; score: string }[];
  // Biggest positive 24h AgentScore move among members, if any.
  mover: { name: string; delta: string } | null;
  // Members carrying an OSI-approved license tag.
  open: { count: number; total: number; names: string[] };
  // Where the live chart for this ranking lives.
  chartPath: string;
}

export type Faq = { q: string; a: string | ((l: Leaders) => string) };

export const OSI_LICENSES = new Set(["mit", "apache-2.0", "bsd", "mpl", "gpl", "agpl"]);

// Sort by AgentScore so tables, quick answers and structured data
// always agree on who is #1.
export function rankByScore<T extends { score: AgentSummary["score"] }>(rows: T[]): T[] {
  return [...rows].sort(
    (x, y) => (y.score?.agent_score ?? -1) - (x.score?.agent_score ?? -1),
  );
}

export function computeLeaders(ranked: AgentSummary[], chartPath: string): Leaders {
  const mover = ranked
    .filter((a) => (a.score?.delta_24h ?? 0) > 0)
    .sort((x, y) => (y.score?.delta_24h ?? 0) - (x.score?.delta_24h ?? 0))[0];
  const open = ranked.filter((a) =>
    a.tags.some((t) => t.kind === "license" && OSI_LICENSES.has(t.value)),
  );
  return {
    top: ranked.slice(0, 3).map((a) => ({
      name: a.name,
      score: formatScore(a.score?.agent_score ?? null),
    })),
    mover: mover
      ? { name: mover.name, delta: (mover.score?.delta_24h ?? 0).toFixed(1) }
      : null,
    open: { count: open.length, total: ranked.length, names: open.slice(0, 3).map((a) => a.name) },
    chartPath,
  };
}

export function resolveFaqs(faqs: Faq[], leaders: Leaders): { q: string; a: string }[] {
  return faqs.map((f) => ({ q: f.q, a: typeof f.a === "function" ? f.a(leaders) : f.a }));
}

export const APP_SCORING =
  "AgentScore is a 0–100 composite of four pillars: adoption (40%), community (30%), quality (20%, from benchmarks where they exist) and momentum (10%). GitHub stars are one adoption signal among many, alongside package downloads, mentions, contributors and release activity. A pillar with no data counts as zero rather than being re-weighted, so thinly documented projects can't score high by accident.";

export const CADENCE =
  "Most signals (GitHub, package downloads, Hacker News and Bluesky mentions) refresh hourly; benchmarks and slower sources refresh daily. The index membership rebalances every Monday at 03:00 UTC.";

function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export function bestNow(noun: string) {
  return (l: Leaders) => {
    const [a, ...rest] = l.top;
    if (!a) {
      return `This ranking is still filling in. The live chart at ${l.chartPath} shows current members as they're admitted.`;
    }
    const followers = rest.map((x) => `${x.name} (${x.score})`);
    return `Right now it's ${a.name}, with an AgentScore of ${a.score}${
      followers.length ? `, followed by ${listNames(followers)}` : ""
    }. This changes as new signals arrive: the ranking above is live, and each agent's page charts its score over time. The best ${noun} for you depends on your task, so shortlist two or three and put them side by side on the Compare page.`;
  };
}

export function openSourceNow(noun: string) {
  return (l: Leaders) => {
    if (!l.open.total) {
      return "Each agent's page shows its license once the ranking fills in. /top/open-source-ai-agents ranks open-source agents only.";
    }
    const led = l.open.names.length ? `, led by ${listNames(l.open.names)}` : "";
    return `Right now ${l.open.count} of the ${l.open.total} ${noun} in this ranking carry an OSI-approved license (MIT, Apache 2.0, BSD, MPL, GPL or AGPL)${led}. Each agent's page shows its license, and /top/open-source-ai-agents ranks open-source agents only. Open-source agents still need a model, through an API key or a local model.`;
  };
}

export function gainingNow(l: Leaders): string {
  const tail =
    "/trending shows every mover over 24 hours, 7 days or 30 days, and each agent's page breaks the move down by signal.";
  return l.mover
    ? `Right now the biggest 24-hour gain in this ranking is ${l.mover.name}, up ${l.mover.delta} points. ${tail}`
    : `Nothing in this ranking has gained in the last 24 hours. ${tail}`;
}

export const SEE_THE_DATA =
  " Open any agent to see its score chart and a per-pillar breakdown down to each raw signal; /methodology has the full formula.";

export const FM_SCORING =
  "Foundation models use five pillars: quality (35%, from benchmarks), adoption (25%), efficiency (20%, cost and speed), momentum (10%) and community (10%). A pillar with no data counts as zero, so only fully rated models can reach 100.";

export function withYear(text: string): string {
  return text.replace("{year}", String(new Date().getUTCFullYear()));
}

