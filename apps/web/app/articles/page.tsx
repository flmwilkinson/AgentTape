import type { Metadata } from "next";
import { ARTICLES, type ArticleMeta } from "@/lib/articles";
import { ArticlesIndex } from "@/components/articles-index";

export const metadata: Metadata = {
  title: "Articles — AgentTape",
  description:
    "Long-form analysis of the AI agent and foundation-model landscape. Deep dives, comparisons, and ranked guides.",
  alternates: { canonical: "/articles" },
};

// Server component shell. Pulls just the metadata off each Article
// (excluding the heavy `body` JSX) so the client filter doesn't ship
// every article's full body in the page bundle. The body is only ever
// hydrated on the article-detail route anyway.
export default function ArticlesIndexPage() {
  const meta: ArticleMeta[] = ARTICLES.map((a) => ({
    slug: a.slug,
    title: a.title,
    description: a.description,
    published_at: a.published_at,
    author: a.author,
    keywords: a.keywords,
    kind: a.kind,
    external_href: a.external_href,
    live: a.live,
  }));
  return <ArticlesIndex articles={meta} />;
}
