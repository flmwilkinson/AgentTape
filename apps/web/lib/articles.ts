// Articles registry — long-form SEO content. Each entry is rendered
// at /articles/<slug>. Body is plain text with a minimal markdown
// dialect: blank-line paragraphs, `## ` for h2, `### ` for h3,
// `- ` for bullet items, `> ` for pull-quotes, and `[label](url)`
// for links. Bold inline is `**text**`. That's enough to write
// quality SEO copy without pulling in a Markdown library.
//
// Workflow for adding an article:
//   1. Use Claude.ai with one of the prompts shipped in /articles
//      to draft the body.
//   2. Drop the result into a new entry below — the page renders
//      automatically on next deploy. No content backend needed.

export interface Article {
  slug: string;
  title: string;
  // Used as <meta description> + the social-card preview. Aim ~155 chars.
  description: string;
  // ISO date string. Sets <article:published_time> + sitemap lastmod.
  published_at: string;
  // Optional human author byline.
  author?: string;
  // Body text in the lightweight markdown dialect described above.
  body: string;
  // Search-engine keyword phrases this article is targeting. Surfaces
  // in the article's structured data and helps you keep editorial
  // discipline while writing — the keywords are not auto-stuffed.
  keywords: string[];
}

export const ARTICLES: Article[] = [
  {
    slug: "best-ai-coding-agents-2026",
    title: "The best AI coding agents in 2026 — ranked, live",
    description:
      "A live comparison of the top AI coding agents — Cursor, Claude Code, Aider, Devin, Cline and more — ranked by the AgentScore composite of adoption, quality and momentum.",
    published_at: "2026-05-04",
    keywords: [
      "best ai coding agents",
      "ai code generation tools",
      "claude code vs cursor",
      "best ai for coding",
    ],
    body: `# placeholder
This article hasn't been written yet. Use the prompt at
/articles#prompts to draft it, then paste the body here.`,
  },
];

export const ARTICLE_BY_SLUG: Record<string, Article> = Object.fromEntries(
  ARTICLES.map((a) => [a.slug, a]),
);
