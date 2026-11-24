import type { Metadata } from "next";
import type { ReactNode } from "react";

// trending/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "Trending AI Agents: Biggest Gainers Today",
  description:
    "The AI agents and models gaining fastest right now, ranked by AgentScore change over 24 hours, 7 days or 30 days. Filter by capability, deployment or kind.",
  alternates: { canonical: "/trending" },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
