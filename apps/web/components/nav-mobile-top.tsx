"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SearchCombobox } from "@/components/search-combobox";

// Slim top bar shown only on mobile. The desktop NavDesktop is
// hidden below md, leaving mobile users with just the bottom tab
// bar; this gives them the brand and the autocomplete combobox.
// On /search the page's own search input is bigger and fully
// featured, so we collapse this one to just the brand mark to
// avoid duplicate inputs.

export function NavMobileTop() {
  const pathname = usePathname();
  const onSearchPage = pathname.startsWith("/search");
  return (
    <header className="md:hidden sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-12 items-center gap-3 px-3">
        <Link
          href="/"
          className="font-mono text-xs font-semibold tracking-[0.18em] uppercase"
        >
          AgentTape
        </Link>
        {!onSearchPage && (
          <SearchCombobox
            className="flex-1"
            placeholder="Search…"
          />
        )}
      </div>
    </header>
  );
}
