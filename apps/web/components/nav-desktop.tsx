"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV: { href: string; label: string }[] = [
  { href: "/", label: "Tape" },
  { href: "/indexes", label: "Indexes" },
  { href: "/movers", label: "Movers" },
  { href: "/discovery", label: "Discovery" },
  { href: "/search", label: "Search" },
  { href: "/methodology", label: "Methodology" },
];

export function NavDesktop() {
  const pathname = usePathname();
  return (
    <header className="hidden md:block sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur">
      <div className="container flex h-14 items-center gap-8">
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
        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
