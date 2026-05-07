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
