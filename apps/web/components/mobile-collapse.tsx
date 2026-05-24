"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

interface Props {
  // Header content rendered inside the toggle button on mobile.
  header: ReactNode;
  // Optional trailing element rendered as a sibling of the toggle
  // (not part of the tap target) — use for navigation links like
  // "All →" that should keep working when the user taps them.
  trailing?: ReactNode;
  children: ReactNode;
  // Defaults to closed on mobile so a list of N collapsibles doesn't
  // dominate the page. On md+ the toggle is suppressed and content
  // is always rendered via the `md:block` class, so this only
  // affects the mobile breakpoint.
  defaultOpen?: boolean;
}

// Mobile-only collapsible. Renders its children inline on md+ screens
// (toggle UI hidden, body always visible) and as a click-to-expand
// disclosure on mobile. Used by the Floor's capability rail so the
// "What do you need an agent for?" section doesn't force users to
// scroll past ten full agent lists before reaching the next section.
export function MobileCollapse({
  header,
  trailing,
  children,
  defaultOpen = false,
}: Props) {
  const [openOnMobile, setOpenOnMobile] = useState(defaultOpen);

  return (
    <>
      <div className="flex items-baseline justify-between border-b border-border px-4 py-2.5">
        <button
          type="button"
          onClick={() => setOpenOnMobile((v) => !v)}
          aria-expanded={openOnMobile}
          // ``pointer-events-none`` on md+ neutralises the toggle so
          // the header reads as a static label, matching the original
          // desktop layout. ``text-left`` because button defaults to
          // center-alignment.
          className="flex min-w-0 flex-1 items-start gap-2 text-left md:pointer-events-none md:cursor-default"
        >
          <span className="min-w-0 flex-1">{header}</span>
          <ChevronDown
            aria-hidden
            className={`h-4 w-4 shrink-0 self-center text-muted-foreground transition-transform md:hidden ${
              openOnMobile ? "rotate-180" : ""
            }`}
          />
        </button>
        {trailing && <div className="ml-3 shrink-0">{trailing}</div>}
      </div>
      <div className={openOnMobile ? "block" : "hidden md:block"}>
        {children}
      </div>
    </>
  );
}
