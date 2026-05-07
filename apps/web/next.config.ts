import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const withMDX = createMDX({
  // remark/rehype plugins go here when we want them; for now the
  // article surface is custom-component-heavy and pure markdown
  // syntax is enough for the prose blocks.
});

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@agenttape/shared"],
  // Tell Next that .mdx files are routable / importable as pages and
  // components. We don't actually route any /pages/*.mdx — the only
  // role MDX plays here is "import an .mdx article body as a React
  // component" — but the extension still has to be allowed.
  pageExtensions: ["ts", "tsx", "mdx"],
};

export default withMDX(nextConfig);
