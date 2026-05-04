// Thin REST client over the apps/api endpoints.
//
// We consume the OpenAPI types from @agenttape/shared but keep the
// fetcher itself untyped at the wire — the response shapes are
// re-typed at the call site so a schema drift surfaces as a TS error
// in the page that uses the response, not a generic API helper.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { searchParams?: Record<string, string | number | boolean | string[] | undefined> } = {},
): Promise<T> {
  const { searchParams, ...rest } = init;
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

  const res = await fetch(url, {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(rest.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${path}${detail ? ` — ${detail.slice(0, 200)}` : ""}`);
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

  search: (q: string, mode: "text" | "vibe" = "text", limit = 20) =>
    apiFetch<SearchResult>("/search", {
      searchParams: { q, mode, limit },
      cache: "no-store",
    }),

  searchSuggest: (q: string, limit = 8) =>
    apiFetch<
      {
        kind: "agent";
        slug: string;
        name: string;
        entity_kind: string;
        description: string | null;
        agent_score: number | null;
      }[]
    >("/search/suggest", {
      searchParams: { q, limit },
      cache: "no-store",
    }),

  tags: () => apiFetch<Tag[]>("/tags"),

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

  events: (params: { kind?: string; limit?: number; offset?: number } = {}) =>
    apiFetch<Page<EventOut>>("/events", { searchParams: params, cache: "no-store" }),

  recentDiscoveries: (limit = 12) =>
    apiFetch<AgentSummary[]>("/discovery/recent", {
      searchParams: { limit },
      cache: "no-store",
    }),
};
