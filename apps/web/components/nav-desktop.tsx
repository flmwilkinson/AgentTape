"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { Search, Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

// Top nav. The product is a directory + index of AI-agent stocks; the
// labels intentionally use the stock-exchange vocabulary the user
// already understands. Search lives in the header as an always-visible
// box (not a tab) — same pattern as Bloomberg / Yahoo Finance.
const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Floor" },
  { href: "/indexes", label: "Indexes" },
  { href: "/models", label: "Models" },
  { href: "/sectors", label: "Sectors" },
  { href: "/trending", label: "Trending" },
  { href: "/articles", label: "Articles" },
];

export function NavDesktop() {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");
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
        <form
          className="ml-auto flex items-center"
          onSubmit={(e) => {
            e.preventDefault();
            const v = q.trim();
            router.push(v ? `/search?q=${encodeURIComponent(v)}` : "/search");
          }}
        >
          <label className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search agents, models…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-8 w-56 rounded-md border border-border bg-card pl-8 pr-3 text-xs placeholder:text-muted-foreground/70 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
        </form>
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
