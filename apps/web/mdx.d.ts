// Augment the ambient *.mdx module declaration that ships from
// @types/mdx so we can read each article's frontmatter-style `meta`
// named export. Without this, TS sees only the default export
// (the body component) and rejects `import { meta } from "*.mdx"`.
//
// We type `meta` as the `ArticleMeta` shape so a typo in the .mdx
// frontmatter (kind: "weekly" vs "weeky") fails the type check
// instead of failing at runtime in the listing page.

declare module "*.mdx" {
  import type { ComponentType } from "react";
  import type { ArticleMeta } from "@/lib/articles";

  export const meta: ArticleMeta;
  const MDXComponent: ComponentType<Record<string, unknown>>;
  export default MDXComponent;
}

// Webpack's `require.context` is genuinely available at runtime in
// Next.js bundles, but the @types/node `Require` shape doesn't include
// it. Used by lib/articles.tsx to auto-discover every .mdx under
// content/articles/ — augment globally so the call site stays clean.
declare namespace NodeJS {
  interface RequireContext {
    keys(): string[];
    <T = unknown>(id: string): T;
  }
  interface Require {
    context(
      path: string,
      recursive?: boolean,
      regex?: RegExp,
    ): RequireContext;
  }
}
