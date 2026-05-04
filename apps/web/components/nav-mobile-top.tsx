"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search } from "lucide-react";

// Slim top bar shown only on mobile. The desktop NavDesktop is
// hidden below md, leaving mobile users with just the bottom tab
// bar; this gives them the brand and a search affordance up top.

export function NavMobileTop() {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <header className="md:hidden sticky top-0 z-30 border-b border-border bg-background/95 backdrop-blur">
      <div className="flex h-12 items-center gap-3 px-3">
        <Link
          href="/"
          className="font-mono text-xs font-semibold tracking-[0.18em] uppercase"
        >
          AgentTape
        </Link>
        <form
          className="flex flex-1 items-center"
          onSubmit={(e) => {
            e.preventDefault();
            const v = q.trim();
            router.push(v ? `/search?q=${encodeURIComponent(v)}` : "/search");
          }}
        >
          <label className="relative flex-1">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              placeholder="Search…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-8 w-full rounded-md border border-border bg-card pl-7 pr-2 text-xs placeholder:text-muted-foreground/70 focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </label>
        </form>
      </div>
    </header>
  );
}
