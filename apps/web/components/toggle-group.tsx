"use client";

import { cn } from "@/lib/utils";

// Segmented "toggle" filter — used everywhere we have a small set of
// mutually-exclusive options (≤4) and want zero-click visibility on
// the choice. Anything bigger than 4 should use Dropdown instead so
// the row doesn't visually overflow.
//
// Centralising this here means /trending, /sectors, /models, the
// agent-page window selector etc. all render the same control with
// the same affordances. Returning users see one filter pattern.

export interface ToggleOption {
  v: string;
  label: string;
}

interface Props {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: ToggleOption[];
  className?: string;
}

export function ToggleGroup({
  label,
  value,
  onChange,
  options,
  className,
}: Props) {
  return (
    <label className={cn("inline-flex items-center gap-2", className)}>
      {label && (
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      )}
      <span className="inline-flex rounded-md border border-border bg-card p-0.5">
        {options.map((o) => (
          <button
            key={o.v}
            type="button"
            onClick={() => onChange(o.v)}
            className={cn(
              "rounded-sm px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors",
              value === o.v
                ? "bg-subtle text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        ))}
      </span>
    </label>
  );
}
