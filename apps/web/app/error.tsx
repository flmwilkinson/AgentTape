"use client";

import { useEffect } from "react";
import Link from "next/link";

// Root-level error boundary. Catches any uncaught error from a route
// segment that doesn't have its own error.tsx. Without this file Next's
// dev server emits "missing required error components, refreshing…"
// in a tight loop on first error, which is the symptom we're fixing.

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // In production we'd ship this to Sentry. For now log to the
    // browser console so dev users see the cause inline.
    // eslint-disable-next-line no-console
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="container py-16 text-center">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Something broke
      </div>
      <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
        That page didn't load.
      </h1>
      <p className="mt-3 max-w-prose mx-auto text-sm text-muted-foreground">
        The error has been logged. Try the action again, or head back to the
        floor.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono text-[10px] text-muted-foreground/60">
          ref: {error.digest}
        </p>
      )}
      <div className="mt-6 flex justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-md border border-border bg-card px-4 py-2 text-sm hover:bg-subtle"
        >
          Retry
        </button>
        <Link
          href="/"
          className="rounded-md border border-primary bg-primary text-primary-foreground px-4 py-2 text-sm hover:bg-primary/90"
        >
          Back to floor
        </Link>
      </div>
    </div>
  );
}
