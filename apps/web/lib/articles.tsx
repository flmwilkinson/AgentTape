import type { ReactNode } from "react";
import CodingAgents2026, {
  meta as codingAgents2026Meta,
} from "@/content/articles/best-ai-coding-agents-2026.mdx";
import FmRanking, {
  meta as fmRankingMeta,
} from "@/content/articles/best-foundation-models-for-ai-agents-2026.mdx";
import OssAlternatives, {
  meta as ossAlternativesMeta,
} from "@/content/articles/open-source-alternatives-devin-cursor-claude-code.mdx";
import BuyersGuide, {
  meta as buyersGuideMeta,
} from "@/content/articles/how-to-choose-ai-agent-2026.mdx";

// Articles registry.
//
// As of the MDX migration every editorial article lives in its own
// file under apps/web/content/articles/. This module is the
// assembly point: it imports each .mdx as a React component (default
// export) plus its frontmatter-style `meta` (named export), and
// exposes the merged registry the rest of the app already consumed.
//
// Two pseudo-articles are kept defined here because their bodies are
// rendered by dedicated routes rather than from a static body:
//   - the inaugural launch report (custom JSON-driven page at
//     /report/inaugural)
//   - the auto-generated weekly recap at /articles/this-week
// Both carry `external_href` so the listing page links there rather
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

const inauguralReport: Article = {
  slug: "inaugural-report",
  title: "TAPE-100: the inaugural AgentTape report",
  description:
    "The first published edition of the AgentTape index. Every constituent was admitted by software, without a curated seed list.",
  published_at: "2026-04-22",
  author: "AgentTape",
  kind: "report",
  keywords: [
    "agenttape",
    "tape-100",
    "inaugural report",
    "ai agent index launch",
  ],
  external_href: "/report/inaugural",
  body: null,
};

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

// Each .mdx exports `meta` (structurally an ArticleMeta) and a
// default React component for the body. Pair them up here so the
// rest of the app keeps consuming the existing `Article` shape.
type MdxBody = (props: Record<string, unknown>) => ReactNode;

function fromMdx(meta: unknown, Body: MdxBody): Article {
  return { ...(meta as ArticleMeta), body: <Body /> };
}

const codingAgents2026 = fromMdx(
  codingAgents2026Meta,
  CodingAgents2026 as MdxBody,
);
const fmRanking = fromMdx(fmRankingMeta, FmRanking as MdxBody);
const ossAlternatives = fromMdx(
  ossAlternativesMeta,
  OssAlternatives as MdxBody,
);
const buyersGuide = fromMdx(buyersGuideMeta, BuyersGuide as MdxBody);

// ----------------------------------------------------------- registry

export const ARTICLES: Article[] = [
  weeklyRecap,
  inauguralReport,
  codingAgents2026,
  fmRanking,
  ossAlternatives,
  buyersGuide,
];

export const ARTICLE_BY_SLUG: Record<string, Article> = Object.fromEntries(
  ARTICLES.map((a) => [a.slug, a]),
);
