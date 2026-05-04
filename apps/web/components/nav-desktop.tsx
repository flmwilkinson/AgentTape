"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { SearchCombobox } from "@/components/search-combobox";
import { ThemeToggle } from "@/components/theme-toggle";

// Top nav. The product is a directory + index of AI-agent stocks; the
// labels intentionally use the stock-exchange vocabulary the user
// already understands. The search box autocompletes via /search/suggest
// so a user typing "gemini" gets Gemini matches first, not unrelated
// description hits.
const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Floor" },
  { href: "/indexes", label: "Indexes" },
  { href: "/models", label: "Models" },
  { href: "/sectors", label: "Sectors" },
  { href: "/trending", label: "Trending" },
  { href: "/search", label: "Search" },
  { href: "/articles", label: "Articles" },
];

export function NavDesktop() {
  const pathname = usePathname();
  return (
    <header className="hidden md:block sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center gap-6">
        <Link
          href="/"
          className="font-mono text-sm font-semibold tracking-[0.18em] uppercase"
        >
          AgentTape
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {NAV.map((n) => {
            const active =
              n.href === "/"
                ? pathname === "/"
                : pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
                  active && "text-foreground",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <SearchCombobox className="ml-auto w-64" />
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <Link
            href="/watchlist"
            className={cn(
              "inline-flex items-center gap-1 hover:text-foreground",
              pathname.startsWith("/watchlist") && "text-foreground",
            )}
            aria-label="Watchlist"
          >
            <Star className="h-3.5 w-3.5" />
            <span>Watchlist</span>
          </Link>
          <Link href="/methodology" className="hover:text-foreground">
            Methodology
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
