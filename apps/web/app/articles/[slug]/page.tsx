import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { ARTICLES, ARTICLE_BY_SLUG } from "@/lib/articles";

export function generateStaticParams() {
  return ARTICLES.map((a) => ({ slug: a.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const a = ARTICLE_BY_SLUG[slug];
  if (!a) return { title: "Not found" };
  return {
    title: `${a.title} — AgentTape`,
    description: a.description,
    keywords: a.keywords,
    alternates: { canonical: `/articles/${a.slug}` },
    openGraph: {
      title: a.title,
      description: a.description,
      type: "article",
      publishedTime: a.published_at,
      authors: a.author ? [a.author] : undefined,
    },
  };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const a = ARTICLE_BY_SLUG[slug];
  if (!a) notFound();

  // schema.org Article structured data — gives Google the right
  // signal that this is editorial content, not a product page.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: a.title,
    description: a.description,
    datePublished: a.published_at,
    author: a.author
      ? { "@type": "Person", name: a.author }
      : { "@type": "Organization", name: "AgentTape" },
    publisher: { "@type": "Organization", name: "AgentTape" },
    keywords: a.keywords.join(", "),
  };

  return (
    <article className="container py-10 md:py-14 max-w-5xl">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <header className="mb-10 border-b border-border pb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Article ·{" "}
          {new Date(a.published_at).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
          })}
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          {a.title}
        </h1>
        <p className="editorial mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground md:text-xl">
          {a.description}
        </p>
      </header>

      <div>{a.body}</div>

      <div className="hairline mt-12 pt-6 text-xs text-muted-foreground">
        Read more in{" "}
        <Link href="/articles" className="text-primary hover:underline">
          all articles
        </Link>{" "}
        or open the live{" "}
        <Link href="/indexes" className="text-primary hover:underline">
          indexes
        </Link>
        .
      </div>
    </article>
  );
}
