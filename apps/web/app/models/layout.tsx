import type { Metadata } from "next";
import type { ReactNode } from "react";

// models/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "Foundation Model Leaderboard: Live AgentScore Rankings",
  description:
    "Every foundation model AgentTape tracks, ranked live by AgentScore from public adoption, quality and momentum signals. Pricing, context length and the FM-50 index.",
  alternates: { canonical: "/models" },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
