import type { Metadata } from "next";
import type { ReactNode } from "react";

// sectors/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "AI Agent Sectors: Capabilities Compared",
  description:
    "Average AgentScore for every AI agent cohort: capabilities, deployment shapes and maturity tiers side by side, with the move over each window.",
  alternates: { canonical: "/sectors" },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
