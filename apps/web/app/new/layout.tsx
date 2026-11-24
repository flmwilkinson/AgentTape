import type { Metadata } from "next";
import type { ReactNode } from "react";

// new/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "New AI Agents: Latest Open-Source Agents, MCP Servers and Skills",
  description:
    "Newly discovered AI agents, MCP servers and Claude skills, found automatically on GitHub, Hugging Face, npm, PyPI, arXiv and Hacker News. Updated continuously.",
  alternates: { canonical: "/new" },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
