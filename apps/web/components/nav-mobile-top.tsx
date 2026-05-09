"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SearchCombobox } from "@/components/search-combobox";
import { ThemeToggle } from "@/components/theme-toggle";

// Slim top bar shown only on mobile. The desktop NavDesktop is
// hidden below md, leaving mobile users with just the bottom tab
// bar; this gives them the brand, a search box, and the
// light/dark toggle. The search no longer flexes all the way to
// the right edge so the toggle has its own slot in the corner.
// On /search the page's own search input is bigger and fully
// featured, so we collapse this one to just the brand mark to
// avoid duplicate inputs.

export function NavMobileTop() {
  const pathname = usePathname();
  const onSearchPage = pathname.startsWith("/search");
  return (
    <header className="md:hidden sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-12 items-center gap-2 px-3">
        <Link
          href="/"
          className="font-mono text-xs font-semibold tracking-[0.18em] uppercase"
        >
          AgentTape
        </Link>
        {!onSearchPage ? (
          <SearchCombobox
            className="min-w-0 flex-1"
            placeholder="Search…"
          />
        ) : (
          <div className="flex-1" />
        )}
        <ThemeToggle />
      </div>
    </header>
  );
}
