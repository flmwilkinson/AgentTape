"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ActivitySquare,
  Cpu,
  Home,
  Search,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Mobile-only bottom tab bar. Five tabs max — Methodology lives in
// the footer / desktop top nav so we don't burn a slot on it here.
//
// Labels mirror the desktop nav so the mental model is the same on
// either device:
//   Floor    — overview
//   Indexes  — sector + foundation-model baskets
//   Models   — foundation-model board
//   Trending — biggest movers
//   Search
const TABS = [
  { href: "/", label: "Floor", icon: Home },
  { href: "/indexes", label: "Indexes", icon: ActivitySquare },
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/trending", label: "Trending", icon: TrendingUp },
  { href: "/search", label: "Search", icon: Search },
];

export function NavMobile() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur md:hidden">
      <ul className="grid grid-cols-5">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active =
            t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                className={cn(
                  "flex h-16 flex-col items-center justify-center gap-1 text-[11px] text-muted-foreground transition-colors",
                  active && "text-primary",
                )}
                aria-label={t.label}
              >
                <Icon className="h-5 w-5" strokeWidth={active ? 2.5 : 1.75} />
                <span className="font-mono uppercase tracking-wider">
                  {t.label}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
