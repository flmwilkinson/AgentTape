"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

// Custom dropdown.
//
// We deliberately avoid the native <select> here: native selects pop
// an OS-rendered list that ignores our color-scheme tokens on some
// browsers (Chromium on Windows specifically) and flashes light on
// dark mode. This component renders a fully-styled menu in our own
// theme, so the flash can't happen.

export interface Option {
  value: string;
  label: string;
}

interface Props {
  label?: string;
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  placeholder?: string;
  className?: string;
  // Width of the trigger; menu inherits the same min-width.
  triggerWidth?: string;
}

export function Dropdown({
  label,
  value,
  onChange,
  options,
  placeholder = "Any",
  className,
  triggerWidth = "min-w-[120px]",
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const current = options.find((o) => o.value === value);

  return (
    <label className={cn("inline-flex items-center gap-2", className)}>
      {label && (
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      )}
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            "inline-flex h-8 items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 text-xs",
            triggerWidth,
          )}
        >
          <span className="truncate">{current?.label ?? placeholder}</span>
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
        {open && (
          <ul
            role="listbox"
            className={cn(
              "absolute left-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-md border border-border bg-card py-1 shadow-lg",
              triggerWidth,
            )}
          >
            {options.map((o) => {
              const active = o.value === value;
              return (
                <li key={o.value || "any"} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(o.value);
                      setOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between gap-3 px-2.5 py-1.5 text-left text-xs transition-colors",
                      active ? "bg-subtle text-foreground" : "hover:bg-subtle/60 text-muted-foreground",
                    )}
                  >
                    <span className="truncate">{o.label}</span>
                    {active && <Check className="h-3 w-3 shrink-0 text-primary" />}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </label>
  );
}
