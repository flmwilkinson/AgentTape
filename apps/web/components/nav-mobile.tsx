"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  BookOpen,
  Compass,
  Cpu,
  GitCompare,
  Hash,
  Home,
  Layers,
  Menu,
  Star,
  TrendingUp,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCompareTray } from "@/lib/compare-tray";

// Mobile-only bottom tab bar.
//
// The five tabs are picked to cover the *entry points* a mobile user
// actually starts from: the Floor, the buyer flow (Sectors), what's
// moving (Trending), the active compare list (Compare), and a More
// sheet that opens a slide-up surface containing everything else
// (Models, Indexes, Search, Watchlist, Articles, Methodology, About,
// Developers). Without that More sheet, mobile users had no way to
// reach half the app.

type Tab = {
  href: string;
  label: string;
  icon: typeof Home;
  match?: (pathname: string) => boolean;
};

const TABS: Tab[] = [
  { href: "/", label: "Floor", icon: Home, match: (p) => p === "/" },
  { href: "/sectors", label: "Sectors", icon: Hash },
  { href: "/trending", label: "Trending", icon: TrendingUp },
  { href: "/compare", label: "Compare", icon: GitCompare },
];

// Items in the More sheet — everything not on the bar. Order is rough
// importance / use-frequency, with "destinations" first and "context"
// pages (methodology, about, developers) last.
const MORE: { href: string; label: string; icon: typeof Home }[] = [
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/indexes", label: "Indexes", icon: Layers },
  { href: "/search", label: "Search", icon: Compass },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/articles", label: "Articles", icon: BookOpen },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
  { href: "/about", label: "About", icon: BookOpen },
];

export function NavMobile() {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  const compareCount = useCompareTray().length;

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur md:hidden">
        <ul className="grid grid-cols-5">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = t.match
              ? t.match(pathname)
              : pathname.startsWith(t.href);
            const showBadge = t.href === "/compare" && compareCount > 0;
            return (
              <li key={t.href}>
                <Link
                  href={t.href}
                  className={cn(
                    "relative flex h-16 flex-col items-center justify-center gap-1 text-[11px] text-muted-foreground transition-colors",
                    active && "text-primary",
                  )}
                  aria-label={t.label}
                >
                  <Icon
                    className="h-5 w-5"
                    strokeWidth={active ? 2.5 : 1.75}
                  />
                  <span className="font-mono uppercase tracking-wider">
                    {t.label}
                  </span>
                  {showBadge && (
                    <span className="absolute right-3 top-2 rounded-full bg-primary px-1.5 py-0.5 font-mono text-[9px] leading-none text-primary-foreground">
                      {compareCount}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setMoreOpen(true)}
              aria-label="More"
              className="flex h-16 w-full flex-col items-center justify-center gap-1 text-[11px] text-muted-foreground"
            >
              <Menu className="h-5 w-5" strokeWidth={1.75} />
              <span className="font-mono uppercase tracking-wider">
                More
              </span>
            </button>
          </li>
        </ul>
      </nav>

      {/* More sheet — slides up over the bottom of the screen. Lives
          on the mobile bar so users can reach Models / Indexes /
          Search / Watchlist / Articles / Methodology / About /
          Developers without digging. */}
      {moreOpen && (
        <>
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setMoreOpen(false)}
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm md:hidden"
          />
          <div className="fixed inset-x-0 bottom-0 z-50 max-h-[80vh] overflow-y-auto rounded-t-xl border-t border-border bg-card shadow-2xl md:hidden">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                More
              </div>
              <button
                type="button"
                onClick={() => setMoreOpen(false)}
                aria-label="Close"
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <ul className="divide-y divide-border">
              {MORE.map((m) => {
                const Icon = m.icon;
                const active = pathname.startsWith(m.href);
                return (
                  <li key={m.href}>
                    <Link
                      href={m.href}
                      onClick={() => setMoreOpen(false)}
                      className={cn(
                        "flex items-center gap-3 px-4 py-3 text-sm",
                        active ? "text-primary" : "text-foreground/85",
                      )}
                    >
                      <Icon
                        className="h-4 w-4 text-muted-foreground"
                        strokeWidth={1.75}
                      />
                      {m.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
    </>
  );
}
