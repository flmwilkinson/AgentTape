"use client";

import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { toggleWatched, useWatchlist } from "@/lib/watchlist";

// Star toggle for adding an agent to the cookie-based watchlist. Drop
// it onto any ticker page or row — it's small, hydration-safe, and
// keeps every instance in sync via the watchlist store.

interface Props {
  slug: string;
  size?: "sm" | "md";
  className?: string;
  showLabel?: boolean;
}

export function WatchToggle({
  slug,
  size = "md",
  className,
  showLabel = false,
}: Props) {
  // Subscribing pulls the latest list each tick.
  const list = useWatchlist();
  const watched = list.includes(slug);

  const iconCls = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";

  return (
    <button
      type="button"
      aria-label={watched ? "Remove from watchlist" : "Add to watchlist"}
      onClick={() => toggleWatched(slug)}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
        watched
          ? "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15"
          : "border-border bg-card text-muted-foreground hover:bg-subtle hover:text-foreground",
        className,
      )}
    >
      <Star
        className={iconCls}
        strokeWidth={2}
        fill={watched ? "currentColor" : "none"}
      />
      {showLabel && (
        <span className="font-mono uppercase tracking-wider">
          {watched ? "Watching" : "Watch"}
        </span>
      )}
    </button>
  );
}
