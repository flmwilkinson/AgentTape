import type { Metadata } from "next";
import type { ReactNode } from "react";

// search/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "Search AI Agents and Models",
  description:
    "Search every AI agent, MCP server and foundation model AgentTape tracks. Filter by capability, license, deployment or model dependency, sorted by AgentScore.",
  alternates: { canonical: "/search" },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
