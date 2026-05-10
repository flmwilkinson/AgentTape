// Thin REST client over the apps/api endpoints.
//
// We consume the OpenAPI types from @agenttape/shared but keep the
// fetcher itself untyped at the wire — the response shapes are
// re-typed at the call site so a schema drift surfaces as a TS error
// in the page that uses the response, not a generic API helper.
//
// Server-side timeout is critical: when the backend is unreachable
// (Hetzner outage, network blip, DNS hiccup), Node's default fetch
// hangs ~10-30s before failing. That manifests as a 10-second blank
// page on Vercel before any error UI renders. Capping at 3s means a
// failed call surfaces in user-visible time.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

// Adaptive timeout. Two contexts have different requirements:
//
// - **SSR / ISR** (server component on Vercel): the user is already
//   waiting on first byte. Bailing at 2s means a slow-API moment
//   produces an empty cached page that gets served for the next
//   5 minutes — worse than waiting an extra 6 seconds. Vercel's
//   default function timeout is 10s, so 8s leaves headroom.
// - **Client interaction** (refetches, react-query, search): the
//   user wants quick "loading vs broken" feedback. 2s is the
//   perception threshold for "broken".
//
// Detected by `typeof window === 'undefined'` at call time. Server
// components see undefined, client components see the global.
const SSR_TIMEOUT_MS = 8000;
const CLIENT_TIMEOUT_MS = 2000;
function defaultTimeout(): number {
  return typeof window === "undefined" ? SSR_TIMEOUT_MS : CLIENT_TIMEOUT_MS;
}

// Typed error so callers can distinguish a real 404 (resource gone)
// from a transient failure (timeout, 5xx, network blip). The
// per-page handlers used to call notFound() on ANY exception, which
// caused Next.js ISR to cache transient timeout failures as 404
// pages for 5 minutes — that's the "go to /indexes/fm-50 → 404 →
// refresh → page renders" bug. Now they can branch on .status.
export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string, path: string) {
    super(`${status}: ${path}${body ? ` — ${body.slice(0, 200)}` : ""}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & {
    searchParams?: Record<string, string | number | boolean | string[] | undefined>;
    timeoutMs?: number;
  } = {},
): Promise<T> {
  const { searchParams, timeoutMs = defaultTimeout(), ...rest } = init;
  let url = `${API_BASE}${path}`;
  if (searchParams) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(searchParams)) {
      if (v === undefined) continue;
      if (Array.isArray(v)) v.forEach((x) => qs.append(k, String(x)));
      else qs.set(k, String(v));
    }
    const s = qs.toString();
    if (s) url += `?${s}`;
  }

  // Respect a caller-supplied AbortSignal (e.g. React Query) but
  // also bound the call ourselves so a hung backend can't blank the
  // page for 30s. AbortSignal.timeout produces a one-shot signal we
  // merge with whatever the caller already passed.
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const signal = rest.signal
    ? AbortSignal.any([rest.signal, timeoutSignal])
    : timeoutSignal;

  const res = await fetch(url, {
    ...rest,
    signal,
    headers: {
      Accept: "application/json",
      ...(rest.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail, path);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------- shared shapes

export type ScoreEnvelope = {
  agent_score: number | null;
  adoption: number | null;
  quality: number | null;
  momentum: number | null;
  community: number | null;
  manipulation_resistance: number | null;
  computed_at: string | null;
  // 24-hour delta. null = no history old enough; 0 = computed and flat.
  score_24h_ago: number | null;
  delta_24h: number | null;
  // Rank within entity_kind (global). 1 = top.
  // rank_delta_24h: positive = climbed, negative = dropped.
  rank_now: number | null;
  rank_24h_ago: number | null;
  rank_delta_24h: number | null;
};

export type AgentSummary = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  discovered_via: string;
  discovered_at: string;
  homepage_url: string | null;
  github_repo: string | null;
  entity_kind: string;
  // Source-of-truth facts surfaced for foundation models (modality,
  // openrouter_id, context_length, pricing). {} for application agents.
  facts: Record<string, unknown>;
  // Lightweight tag list. Always present on summaries (kind+value);
  // detail responses additionally fill in display_name.
  tags: { kind: string; value: string; display_name?: string }[];
  score: ScoreEnvelope;
};

export type AgentDetail = AgentSummary & {
  hf_org: string | null;
  hf_model_ids: string[] | null;
  package_names: Record<string, unknown> | null;
  arxiv_ids: string[] | null;
  eligibility_status: string;
  eligibility_score: number | null;
  eligibility_reasons: Record<string, unknown> | null;
  manipulation_flags: Record<string, unknown> | null;
  tags: { kind: string; value: string; display_name: string }[];
  facts: Record<string, unknown>;
  // Derived badges — null when not enough data yet.
  retention: {
    ratio: number;
    status: "growing" | "holding" | "fading" | "decaying";
    score_now: number;
    score_at_30d: number;
    days_since_admission: number;
  } | null;
  openrouter_rank: {
    rank: number;
    total: number;
    tokens_30d: number;
  } | null;
};

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type IndexSummary = {
  id: string;
  slug: string;
  name: string;
  methodology_md: string | null;
  rebalance_frequency: string;
  members_count: number;
  composite_value: number | null;
};

export type IndexConstituent = { agent: AgentSummary; weight: number; added_at: string };
export type IndexDetail = IndexSummary & {
  constituents: IndexConstituent[];
  last_rebalance_at: string | null;
};
export type IndexSnapshot = { captured_at: string; composite_value: number };
export type RebalanceLog = {
  id: string;
  run_at: string;
  additions: unknown[] | null;
  removals: unknown[] | null;
  weight_changes: unknown[] | null;
  narrative_md: string | null;
};

export type SignalSeries = {
  source: string;
  points: { captured_at: string; value: number }[];
};

export type Mover = {
  agent: AgentSummary;
  delta: number;
  score_at_window_start: number | null;
  score_now: number;
};

export type EventOut = {
  id: string;
  kind: string;
  agent_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type SearchResult = {
  hits: { agent: AgentSummary; similarity: number | null }[];
  facets: Record<string, { value: string; count: number }[]>;
};

export type Tag = {
  kind: string;
  value: string;
  display_name: string;
  count: number;
};

// ---------------------------------------------------------- endpoints

export const api = {
  listAgents: (params: {
    q?: string;
    tag_kind?: string;
    tag_value?: string;
    entity_kind?: "application" | "foundation_model" | "framework" | "mcp_server";
    sort?: "score" | "discovered" | "name";
    limit?: number;
    offset?: number;
  } = {}) => apiFetch<Page<AgentSummary>>("/agents", { searchParams: params, cache: "no-store" }),

  getAgent: (slug: string) =>
    apiFetch<AgentDetail>(`/agents/${slug}`, { cache: "no-store" }),

  agentSignals: (slug: string, params: { sources?: string[]; window?: string } = {}) =>
    apiFetch<SignalSeries[]>(`/agents/${slug}/signals`, {
      searchParams: params,
      cache: "no-store",
    }),

  agentBenchmarks: (slug: string) =>
    apiFetch<
      {
        benchmark_id: string;
        benchmark_name: string;
        captured_at: string;
        score: number;
        max_score: number | null;
      }[]
    >(`/agents/${slug}/benchmarks`),

  agentSimilar: (slug: string, limit = 10) =>
    apiFetch<{ agent: AgentSummary; similarity: number }[]>(
      `/agents/${slug}/similar`,
      { searchParams: { limit } },
    ),

  agentScoreHistory: (slug: string, window = "30d") =>
    apiFetch<
      {
        captured_at: string;
        agent_score: number;
        adoption: number | null;
        quality: number | null;
        momentum: number | null;
        community: number | null;
      }[]
    >(`/agents/${slug}/score-history`, {
      searchParams: { window },
      cache: "no-store",
    }),

  listIndexes: () => apiFetch<IndexSummary[]>("/indexes", { cache: "no-store" }),

  getIndex: (slug: string) =>
    apiFetch<IndexDetail>(`/indexes/${slug}`, { cache: "no-store" }),

  indexHistory: (slug: string, window = "30d") =>
    apiFetch<IndexSnapshot[]>(`/indexes/${slug}/history`, {
      searchParams: { window },
      cache: "no-store",
    }),

  indexRebalances: (slug: string, limit = 10) =>
    apiFetch<RebalanceLog[]>(`/indexes/${slug}/rebalances`, {
      searchParams: { limit },
    }),

  movers: (
    window: "1h" | "1d" | "7d" | "30d" = "1d",
    limit = 10,
    filters: {
      capability?: string;
      deployment?: string;
      entity_kind?: "application" | "foundation_model";
    } = {},
  ) =>
    apiFetch<Mover[]>("/movers", {
      searchParams: { window, limit, ...filters },
      cache: "no-store",
    }),

  search: (
    q: string,
    mode: "text" | "vibe" = "text",
    limit = 20,
    tag?: { kind: string | null; value: string | null } | null,
  ) =>
    apiFetch<SearchResult>("/search", {
      searchParams: {
        q,
        mode,
        limit,
        tag_kind: tag?.kind ?? undefined,
        tag_value: tag?.value ?? undefined,
      },
      cache: "no-store",
    }),

  searchSuggest: (q: string, limit = 8) =>
    apiFetch<
      (
        | {
            kind: "agent";
            slug: string;
            name: string;
            entity_kind: string;
            description: string | null;
            agent_score: number | null;
          }
        | {
            kind: "tag";
            tag_kind: string;
            tag_value: string;
            count: number;
          }
      )[]
    >("/search/suggest", {
      searchParams: { q, limit },
      cache: "no-store",
    }),

  tags: () => apiFetch<Tag[]>("/tags"),

  sectorHistory: (
    kind: string,
    value: string,
    window: "1d" | "7d" | "30d" | "90d" | "all" = "7d",
  ) =>
    apiFetch<
      { captured_at: string; avg_score: number | null; agents: number }[]
    >(`/sectors/${kind}/${value}/history`, {
      searchParams: { window },
      cache: "no-store",
    }),

  sectors: (
    kind: "capability" | "deployment" | "maturity" = "capability",
    window: "1d" | "7d" | "30d" = "7d",
  ) =>
    apiFetch<
      {
        value: string;
        display_name: string;
        members: number;
        avg_now: number | null;
        avg_then: number | null;
        delta: number | null;
        verdict:
          | "booming"
          | "growing"
          | "steady"
          | "cooling"
          | "declining"
          | "no_history";
      }[]
    >("/sectors", {
      searchParams: { kind, window },
      cache: "no-store",
    }),

  // Top-N agents per tag value in a single response. Used by the
  // Floor's capability rail — replaces a fan-out of N parallel
  // /agents calls that ran into client-side timeouts in production.
  sectorsTop: (
    kind: "capability" | "deployment" | "maturity" = "capability",
    top = 3,
  ) =>
    apiFetch<
      {
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
            adoption: number | null;
            quality: number | null;
            momentum: number | null;
            community: number | null;
            score_24h_ago: number | null;
            delta_24h: number | null;
          };
        }[];
      }[]
    >("/sectors/top", {
      searchParams: { kind, top },
      cache: "no-store",
    }),

  events: (params: { kind?: string; limit?: number; offset?: number } = {}) =>
    apiFetch<Page<EventOut>>("/events", { searchParams: params, cache: "no-store" }),

  recentDiscoveries: (limit = 12) =>
    apiFetch<AgentSummary[]>("/discovery/recent", {
      searchParams: { limit },
      cache: "no-store",
    }),
};
