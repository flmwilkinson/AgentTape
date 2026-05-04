import Link from "next/link";
import type { Metadata } from "next";
import { ARTICLES } from "@/lib/articles";

export const metadata: Metadata = {
  title: "Articles — AgentTape",
  description:
    "Long-form analysis of the AI agent and foundation-model landscape. Deep dives, comparisons, and ranked guides.",
  alternates: { canonical: "/articles" },
};

export default function ArticlesIndexPage() {
  return (
    <article className="container py-10 md:py-14 max-w-4xl space-y-10">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Articles
        </div>
        <h1 className="editorial mt-2 text-4xl font-semibold leading-tight md:text-5xl md:leading-[1.05]">
          Field notes from the floor.
        </h1>
        <p className="editorial mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg">
          Deep dives and ranked guides written against the same live data
          that drives the indexes. Use them to choose well and stay current.
        </p>
      </header>

      {ARTICLES.length === 0 ? (
        <section className="rounded-md border border-dashed border-border bg-card px-6 py-10 text-center">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            No articles yet
          </div>
          <p className="editorial mt-3 max-w-prose mx-auto text-base leading-relaxed text-muted-foreground">
            Articles ship as they're written.
          </p>
        </section>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-card">
          {ARTICLES.map((a) => (
            <li key={a.slug}>
              <Link
                href={`/articles/${a.slug}`}
                className="block px-5 py-5 hover:bg-subtle"
              >
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  {new Date(a.published_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                  {a.author && (
                    <>
                      <span className="mx-2 text-muted-foreground/40">·</span>
                      {a.author}
                    </>
                  )}
                </div>
                <div className="mt-1 text-lg font-medium leading-snug">
                  {a.title}
                </div>
                <p className="mt-1 max-w-prose text-sm text-muted-foreground">
                  {a.description}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
