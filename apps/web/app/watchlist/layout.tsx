import type { Metadata } from "next";
import type { ReactNode } from "react";

// watchlist/page.tsx is a client component, so it can't export metadata
// itself. Without this layout the page inherited the homepage's title
// and description, which Google treats as a duplicate of "/".
export const metadata: Metadata = {
  title: "Your Watchlist",
  // Per-device, cookie-backed list: nothing for search engines to index.
  robots: { index: false, follow: true },
};

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
