import type { ReactNode } from "react";

// Articles registry.
//
// Every editorial article lives in its own file under
// apps/web/content/articles/*.mdx. Each .mdx file exports a `meta`
// object (frontmatter-style) and a default React component for the
// body. We auto-discover them via webpack's require.context — drop a
// new .mdx into content/articles/ and it shows up everywhere ARTICLES
// is consumed (listing page, [slug] route, sitemap) without touching
// this file.
//
// One pseudo-article is kept defined here because its body is
// rendered by a dedicated route rather than a static body:
//   - the auto-generated weekly recap at /articles/this-week
// It carries `external_href` so the listing page links there rather
// than to the default /articles/{slug} route.

export type ArticleKind = "weekly" | "report" | "guide" | "comparison";

export interface ArticleMeta {
  slug: string;
  title: string;
  description: string;
  published_at: string;
  author?: string;
  keywords: string[];
  // Visual classification — drives chip colour in the listing and
  // featured-card eligibility ("weekly" is the only kind that ever
  // gets the top featured slot).
  kind: ArticleKind;
  // Set when the article lives at a non-/articles/{slug} URL.
  external_href?: string;
  // Render a "Live" pill on the listing — used for any article that
  // recomputes itself from current data each week.
  live?: boolean;
}

export interface Article extends ArticleMeta {
  body: ReactNode;
}

// Tag colours per article kind. Kept in lock-step with the listing
// page; if a new kind is added, add a row here too.
export const ARTICLE_KIND_TAG: Record<
  ArticleKind,
  { label: string; tone: string }
> = {
  weekly: {
    label: "Weekly report",
    tone: "border-primary/40 bg-primary/10 text-primary",
  },
  report: {
    label: "Special report",
    tone: "border-gain/40 bg-gain-subtle text-gain",
  },
  guide: {
    label: "Guide",
    tone: "border-border bg-subtle text-foreground/85",
  },
  comparison: {
    label: "Comparison",
    tone: "border-border bg-subtle text-foreground/85",
  },
};

// ----------------------------------------------------------- live entries

// Date helper for "most recent Monday in UTC" — used as the
// published_at for the auto weekly recap so the listing reads "this
// week" rather than the deploy date.
function lastMondayISO(): string {
  const now = new Date();
  const day = now.getUTCDay(); // 0 = Sun, 1 = Mon, …
  const diff = (day + 6) % 7;
  const monday = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate() - diff,
    ),
  );
  return monday.toISOString().slice(0, 10);
}

const weeklyRecap: Article = {
  slug: "this-week",
  title: "This week on AgentTape",
  description:
    "The seven-day recap, recomputed every visit: biggest movers, new admissions, hot sectors. Auto-generated from the live index.",
  published_at: lastMondayISO(),
  author: "AgentTape",
  kind: "weekly",
  keywords: ["weekly recap", "agenttape", "trending", "movers"],
  external_href: "/articles/this-week",
  live: true,
  body: null,
};

// ----------------------------------------------------------- mdx entries

// webpack scans content/articles/ at build time, eagerly imports every
// .mdx, and gives us a synchronous lookup keyed by relative path. The
// effect: a new .mdx file is picked up by a rebuild with no edit here.
type MdxModule = {
  default: (props: Record<string, unknown>) => ReactNode;
  meta: ArticleMeta;
};
const ctx = require.context("../content/articles", false, /\.mdx$/);
// Dedupe by slug. Next's MDX page-extension wiring (pageExtensions
// includes "mdx") sometimes makes webpack surface the same file under
// two keys — e.g. "./foo.mdx" and "./foo" — and that doubled the
// listing once we had >4 articles. Slug is the stable identity; keep
// the first hit and drop later collisions.
const bySlug = new Map<string, Article>();
for (const key of ctx.keys()) {
  const { default: Body, meta } = ctx(key) as MdxModule;
  if (bySlug.has(meta.slug)) continue;
  bySlug.set(meta.slug, { ...meta, body: <Body /> });
}
// Newest first; tie-break by slug so build output is deterministic.
const mdxArticles: Article[] = [...bySlug.values()].sort((a, b) => {
  if (a.published_at !== b.published_at) {
    return b.published_at.localeCompare(a.published_at);
  }
  return a.slug.localeCompare(b.slug);
});

// ----------------------------------------------------------- registry

export const ARTICLES: Article[] = [weeklyRecap, ...mdxArticles];

export const ARTICLE_BY_SLUG: Record<string, Article> = Object.fromEntries(
  ARTICLES.map((a) => [a.slug, a]),
);
