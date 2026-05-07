"use client";

import { useEffect } from "react";

// Last-resort boundary — catches errors that escape the root layout
// itself (e.g. a hot-reload fault before <html> finishes rendering).
// Must own its own <html> + <body> because the root layout is part of
// the failed tree it's replacing. Plain styles only — no Tailwind, no
// design tokens — since the stylesheet may be the thing that failed.

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("Global error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
          background: "#0b0d10",
          color: "#e5e7eb",
          minHeight: "100vh",
          margin: 0,
          padding: "4rem 1.5rem",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
        }}
      >
        <div style={{ maxWidth: 480 }}>
          <div
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 10,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "#9ca3af",
            }}
          >
            Application crashed
          </div>
          <h1
            style={{
              marginTop: 8,
              fontSize: 28,
              fontWeight: 600,
              lineHeight: 1.2,
            }}
          >
            Something broke at the root.
          </h1>
          <p style={{ marginTop: 12, color: "#9ca3af", fontSize: 14 }}>
            The page can't recover on its own. Click retry — if it keeps
            looping, refresh the tab.
          </p>
          {error.digest && (
            <p
              style={{
                marginTop: 8,
                fontFamily: "ui-monospace, monospace",
                fontSize: 11,
                color: "#6b7280",
              }}
            >
              ref: {error.digest}
            </p>
          )}
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 24,
              padding: "8px 16px",
              fontSize: 14,
              borderRadius: 6,
              border: "1px solid #2563eb",
              background: "#2563eb",
              color: "white",
              cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      </body>
    </html>
  );
}
