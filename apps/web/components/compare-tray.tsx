"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GitCompare, Plus, X, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import {
  COMPARE_TRAY_MAX,
  toggleCompareTray,
  clearCompareTray,
  removeFromCompareTray,
  useCompareTray,
} from "@/lib/compare-tray";

// Compare tray — a floating, persistent shortlist anchor in the
// bottom-right corner. Click any agent's "+" button anywhere on the
// site, the drawer pops up showing what's selected. The shortlist
// survives navigation and reload via localStorage.

export function CompareTrayLauncher() {
  const slugs = useCompareTray();
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // Close the drawer whenever the user navigates. Without this, tapping
  // an agent in the drawer leaves it open and covering the next page —
  // particularly bad on mobile where the drawer eats the bottom of the
  // viewport.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  if (slugs.length === 0) return null;

  const canCompare = slugs.length >= 2;

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open compare tray"
          className="fixed bottom-20 right-4 z-40 inline-flex items-center gap-2 rounded-full border border-border bg-foreground px-4 py-2.5 text-sm font-medium text-background shadow-lg hover:bg-primary md:bottom-6"
        >
          <GitCompare className="h-4 w-4" />
          Compare
          <span className="ml-1 rounded-full bg-background/20 px-2 py-0.5 text-xs">
            {slugs.length}
          </span>
        </button>
      )}

      {open && (
        <div
          className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-card shadow-2xl md:bottom-6 md:right-6 md:left-auto md:inset-x-auto md:max-w-md md:rounded-md md:border"
          role="dialog"
          aria-label="Compare tray"
        >
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Compare tray
              </div>
              <div className="text-sm font-medium">
                {slugs.length} of {COMPARE_TRAY_MAX} selected
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close"
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-border">
            {slugs.map((slug) => (
              <li
                key={slug}
                className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm"
              >
                <Link
                  href={`/agents/${slug}`}
                  className="min-w-0 flex-1 truncate hover:text-primary"
                >
                  {slug}
                </Link>
                <button
                  type="button"
                  onClick={() => removeFromCompareTray(slug)}
                  aria-label={`Remove ${slug}`}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2 border-t border-border px-4 py-3">
            <button
              type="button"
              onClick={clearCompareTray}
              className="text-xs font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
            <Link
              href={canCompare ? `/compare?slugs=${slugs.join(",")}` : "#"}
              onClick={() => canCompare && setOpen(false)}
              className={cn(
                "ml-auto inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
                canCompare
                  ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                  : "pointer-events-none border-border text-muted-foreground",
              )}
              aria-disabled={!canCompare}
            >
              <GitCompare className="h-3.5 w-3.5" />
              {canCompare
                ? `Compare ${slugs.length}`
                : "Pick another to compare"}
            </Link>
          </div>
        </div>
      )}
    </>
  );
}

// Top-bar Compare link. Always navigates to /compare; shows a small
// badge with the current tray count so the user can see at a glance
// how many slugs are queued. Used in both desktop and mobile nav so
// the compare flow has a permanent home, not just the floating tray.
export function CompareNavLink({ className }: { className?: string }) {
  const slugs = useCompareTray();
  const pathname = usePathname();
  const active = pathname.startsWith("/compare");
  const href = slugs.length >= 2
    ? `/compare?slugs=${slugs.join(",")}`
    : "/compare";
  return (
    <Link
      href={href}
      aria-label="Compare"
      className={cn(
        "inline-flex items-center gap-1 hover:text-foreground",
        active && "text-foreground",
        className,
      )}
    >
      <GitCompare className="h-3.5 w-3.5" />
      <span>Compare</span>
      {slugs.length > 0 && (
        <span className="ml-1 rounded-full bg-primary/15 px-1.5 py-0.5 font-mono text-[10px] leading-none text-primary">
          {slugs.length}
        </span>
      )}
    </Link>
  );
}

// "+" button to drop on any agent row or card. Auto-shows the
// in/out state from localStorage; clicking toggles. Pass
// ``showLabel`` to render a chip-shaped button with text — used on
// the agent detail header where the feature deserves visibility,
// vs the icon-only form used in dense table rows.
export function CompareTrayToggle({
  slug,
  size = "sm",
  showLabel = false,
  className,
}: {
  slug: string;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}) {
  const slugs = useCompareTray();
  const inTray = slugs.includes(slug);
  const full = slugs.length >= COMPARE_TRAY_MAX && !inTray;
  const iconCls = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";

  if (showLabel) {
    return (
      <button
        type="button"
        onClick={() => toggleCompareTray(slug)}
        disabled={full}
        aria-label={inTray ? "Remove from compare tray" : "Add to compare tray"}
        title={
          full ? "Compare tray is full (5 max)" : "Compare with up to 4 others"
        }
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
          inTray
            ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/15"
            : full
              ? "border-border text-muted-foreground/50 cursor-not-allowed"
              : "border-border bg-card text-foreground/85 hover:bg-subtle",
          className,
        )}
      >
        {inTray ? (
          <Check className={iconCls} strokeWidth={2.5} />
        ) : (
          <Plus className={iconCls} strokeWidth={2.25} />
        )}
        {inTray
          ? `In tray (${slugs.length}/${COMPARE_TRAY_MAX})`
          : full
            ? "Tray full"
            : "Compare"}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => toggleCompareTray(slug)}
      disabled={full}
      aria-label={inTray ? "Remove from compare tray" : "Add to compare tray"}
      title={
        inTray
          ? "In compare tray — click to remove"
          : full
            ? "Compare tray is full (5 max)"
            : "Add to compare tray"
      }
      className={cn(
        "inline-flex items-center justify-center rounded-md border transition-colors",
        size === "sm" ? "h-6 w-6" : "h-7 w-7",
        inTray
          ? "border-primary/40 bg-primary/10 text-primary hover:bg-primary/15"
          : full
            ? "border-border text-muted-foreground/50 cursor-not-allowed"
            : "border-border bg-card text-muted-foreground hover:bg-subtle hover:text-foreground",
        className,
      )}
    >
      {inTray ? (
        <Check className={iconCls} strokeWidth={2.5} />
      ) : (
        <Plus className={iconCls} strokeWidth={2.25} />
      )}
    </button>
  );
}
