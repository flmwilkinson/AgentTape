import type { MDXComponents } from "mdx/types";
import {
  AxesGrid,
  Badges,
  ChecklistBox,
  ChooseGrid,
  Closer,
  CTAButtonRow,
  CTAPanel,
  H2,
  IndexSnapshot,
  Lede,
  ModelCard,
  PersonaCards,
  ProductHeading,
  Prose,
  PullQuote,
  QuadGrid,
  ScoreBars,
  Section,
  SectionContent,
  SectionDivider,
  SpecCard,
  StatGrid,
  StepHeader,
  TickerTable,
  TradeoffTable,
} from "@/components/article-blocks";

// Component map exposed to every .mdx file under content/. Anything
// listed here is usable as a JSX tag without an import statement
// inside the .mdx — Next's MDX integration looks for this exported
// `useMDXComponents` at the workspace root.
//
// We expose every article-block primitive plus the markdown-to-HTML
// overrides we want (so a plain "## Foo" in markdown becomes a
// styled <H2>, etc.).
export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    // Markdown `## …` becomes the styled H2. Plain paragraphs render
    // as bare <p>; if you want editorial styling, wrap them in
    // <Prose>…</Prose> the same way the JSX articles did. (Inheriting
    // Prose's text classes is what gives the inner <p> elements
    // their look — auto-wrapping at the markdown level would
    // double-wrap and break vertical rhythm.)
    h2: ({ children }) => <H2>{children}</H2>,

    // Article-block primitives. Available in MDX as <Lede>, <StatGrid>,
    // etc. without an import line at the top of every file.
    AxesGrid,
    Badges,
    ChecklistBox,
    ChooseGrid,
    Closer,
    CTAButtonRow,
    CTAPanel,
    H2,
    IndexSnapshot,
    Lede,
    ModelCard,
    PersonaCards,
    ProductHeading,
    Prose,
    PullQuote,
    QuadGrid,
    ScoreBars,
    Section,
    SectionContent,
    SectionDivider,
    SpecCard,
    StatGrid,
    StepHeader,
    TickerTable,
    TradeoffTable,

    // Allow callers to layer their own overrides in if ever needed.
    ...components,
  };
}
