import type { MetadataRoute } from "next";
import { api, type AgentSummary } from "@/lib/api-client";
import { ARTICLES } from "@/lib/articles";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.com";

// next.js sitemap. Includes every static surface plus every admitted
// agent + every index. Capped at 50K URLs by spec; we're nowhere near
// that.

// Without this the sitemap would be built once at deploy and never
// pick up newly admitted agents until the next deploy.
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticPaths: MetadataRoute.Sitemap = [
    "/",
    "/about",
    "/indexes",
    "/models",
    "/trending",
    "/new",
    "/search",
    "/compare",
    "/methodology",
    "/top/coding-agents",
    "/top/browser-agents",
    "/top/foundation-models",
    "/top/open-source-ai-agents",
    "/top/mcp-servers",
    "/articles",
    "/articles/this-week",
    "/sectors",
  ].map((path) => ({
    url: `${SITE}${path}`,
    lastModified: now,
    changeFrequency: path === "/" ? "always" : "hourly",
    priority: path === "/" ? 1.0 : path === "/about" ? 0.9 : 0.7,
  }));

  // Indexes — small set (≈6 entries) but each is high-value.
  let indexUrls: MetadataRoute.Sitemap = [];
  try {
    const indexes = await api.listIndexes();
    indexUrls = indexes.map((i) => ({
      url: `${SITE}/indexes/${i.slug}`,
      lastModified: now,
      changeFrequency: "hourly",
      priority: 0.8,
    }));
  } catch {
    // API unavailable at build time — ship the sitemap without index pages.
  }

  // Agents — every admitted agent gets its own URL. The API caps a page
  // at 100, so page through the rest in small batches: Search Console
  // shows agent pages are where nearly all search traffic lands, and
  // agents outside the top 100 were only discoverable via internal
  // links. Batches of 5 keep the burst off the API; a failed page is
  // skipped rather than failing the whole sitemap.
  const PAGE = 100;
  const MAX_PAGES = 50; // 5,000 agents; the sitemap spec allows 50K URLs.
  const toUrl = (a: AgentSummary): MetadataRoute.Sitemap[number] => ({
    url: `${SITE}/agents/${a.slug}`,
    lastModified: a.score?.computed_at ? new Date(a.score.computed_at) : now,
    changeFrequency: "daily",
    priority: 0.6,
  });
  let agentUrls: MetadataRoute.Sitemap = [];
  try {
    const first = await api.listAgents({ limit: PAGE, sort: "score" });
    agentUrls = first.items.map(toUrl);
    const pages = Math.min(Math.ceil(first.total / PAGE), MAX_PAGES);
    for (let start = 1; start < pages; start += 5) {
      const batch = await Promise.all(
        Array.from({ length: Math.min(5, pages - start) }, (_, i) =>
          api
            .listAgents({ limit: PAGE, offset: (start + i) * PAGE, sort: "score" })
            .then((r) => r.items)
            .catch(() => [] as AgentSummary[]),
        ),
      );
      agentUrls.push(...batch.flat().map(toUrl));
    }
  } catch {
    // Same fallback — sitemap stays valid even when API is unreachable.
  }

  // Articles — long-form SEO content. Each gets a dedicated URL with
  // its publish date as lastmod so search engines respect the freshness.
  const articleUrls: MetadataRoute.Sitemap = ARTICLES.map((a) => ({
    url: `${SITE}/articles/${a.slug}`,
    lastModified: new Date(a.published_at),
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  // Scores can move between page fetches, shifting an agent across a
  // page boundary; drop any duplicate URLs that produces.
  const seen = new Set<string>();
  agentUrls = agentUrls.filter((u) => !seen.has(u.url) && !!seen.add(u.url));

  return [...staticPaths, ...indexUrls, ...agentUrls, ...articleUrls];
}
