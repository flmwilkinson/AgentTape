"use client";

import { cn } from "@/lib/utils";

// Tiny shimmering skeleton for loading rows. Use in place of plain
// "Loading…" text in tables — gives the eye something the right shape
// to wait on while the data lands.

export function SkeletonBlock({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-3 animate-pulse rounded-sm bg-muted",
        className,
      )}
    />
  );
}

// A reusable table-shaped skeleton: N rows of M cells each, the first
// column wider so the "name" stub looks right.
export function TableSkeleton({
  rows = 5,
  cols = 5,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} className="border-b border-border last:border-b-0">
          {Array.from({ length: cols }).map((_, c) => (
            <td key={c} className="px-3 py-3">
              <SkeletonBlock
                className={c === 1 ? "w-32" : c === 0 ? "w-8" : "w-12"}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
