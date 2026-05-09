import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // /api/* are JSON + OG-image endpoints, no value to crawlers.
        disallow: ["/api/"],
      },
    ],
    // Note: no `host` field. Google ignores it and Yandex / some
    // older bots have been known to mis-parse it. The canonical
    // domain is communicated via per-page <link rel="canonical"> tags
    // and via the 301 from www -> apex on the host (Vercel project
    // settings / Cloudflare DNS), not via robots.txt.
    sitemap: `${SITE}/sitemap.xml`,
  };
}
