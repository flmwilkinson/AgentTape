"use client";

import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { subscribeToToasts, type Toast } from "@/lib/toast";

// Bottom-centre transient toast. Mounts once at the root, pulls every
// dispatched toast off the bus, shows the latest. We keep this simple
// — single slot, fade in / fade out — because the app uses toasts
// only for feedback on user-initiated actions, not background
// notifications.

export function ToastHost() {
  const [active, setActive] = useState<Toast | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsub = subscribeToToasts((t) => {
      setActive(t);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setActive(null), t.durationMs ?? 3000);
    });
    return () => {
      unsub();
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!active) return null;

  return (
    <div
      className={cn(
        // Lift above the floating compare button (bottom-20 on mobile)
        // and the bottom tab bar (h-16) — sits comfortably above both.
        "pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex justify-center px-4 md:bottom-10",
      )}
      role="status"
      aria-live="polite"
    >
      <div
        className={cn(
          "pointer-events-auto flex max-w-sm items-start gap-3 rounded-md border bg-card px-4 py-3 shadow-lg",
          active.tone === 1
            ? "border-gain/40"
            : active.tone === -1
              ? "border-loss/40"
              : "border-border",
        )}
      >
        {active.tone === 1 && (
          <Check className="mt-0.5 h-4 w-4 text-gain" strokeWidth={2.5} />
        )}
        {active.tone === -1 && (
          <X className="mt-0.5 h-4 w-4 text-loss" strokeWidth={2.5} />
        )}
        <div className="flex-1 text-sm">
          <div className="font-medium text-foreground">{active.title}</div>
          {active.body && (
            <div className="mt-0.5 text-xs text-muted-foreground">
              {active.body}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
