import type { MetadataRoute } from "next";
import { api } from "@/lib/api-client";
import { ARTICLES } from "@/lib/articles";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.io";

// next.js sitemap. Includes every static surface plus every admitted
// agent + every index. Capped at 50K URLs by spec; we're nowhere near
// that.

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
    "/report/inaugural",
    "/top/coding-agents",
    "/top/browser-agents",
    "/top/foundation-models",
    "/top/open-source-ai-agents",
    "/top/mcp-servers",
    "/articles",
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

  // Agents — every admitted agent gets its own URL. We pull a wide page
  // because the API caps at 100; for >100 agents we'd want to paginate.
  let agentUrls: MetadataRoute.Sitemap = [];
  try {
    const agents = await api.listAgents({ limit: 100, sort: "score" });
    agentUrls = agents.items.map((a) => ({
      url: `${SITE}/agents/${a.slug}`,
      lastModified: a.score?.computed_at
        ? new Date(a.score.computed_at)
        : now,
      changeFrequency: "daily",
      priority: 0.6,
    }));
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

  return [...staticPaths, ...indexUrls, ...agentUrls, ...articleUrls];
}
