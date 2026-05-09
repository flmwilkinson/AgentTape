// Root-level loading skeleton. Streams instantly while the server
// component tree is still resolving, so the browser never sits on a
// blank page during SSR or page-to-page navigation. Next.js wraps
// the page in a Suspense boundary using this file as the fallback,
// which means a 5–9 second cold render now paints a usable
// placeholder in <100 ms.

export default function Loading() {
  return (
    <div className="animate-pulse">
      {/* Ticker tape placeholder */}
      <div className="border-b border-border bg-card">
        <div className="container flex gap-4 py-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-6 w-32 shrink-0 rounded bg-muted/40"
            />
          ))}
        </div>
      </div>

      <div className="container py-8 md:py-12 space-y-12">
        {/* Headline placeholder */}
        <section>
          <div className="h-3 w-16 rounded bg-muted/40" />
          <div className="mt-4 h-10 w-3/4 max-w-xl rounded bg-muted/40 md:h-14" />
          <div className="mt-3 h-4 w-2/3 max-w-md rounded bg-muted/30" />
        </section>

        {/* Two-column movers placeholder */}
        <section>
          <div className="grid gap-3 md:grid-cols-2">
            {[0, 1].map((i) => (
              <div
                key={i}
                className="rounded-md border border-border bg-card p-4 space-y-3"
              >
                <div className="h-3 w-24 rounded bg-muted/40" />
                {[0, 1, 2].map((j) => (
                  <div key={j} className="h-4 w-full rounded bg-muted/30" />
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* Capability rail placeholder */}
        <section>
          <div className="h-3 w-32 rounded bg-muted/40" />
          <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="rounded-md border border-border bg-card p-4 space-y-3"
              >
                <div className="h-3 w-20 rounded bg-muted/40" />
                <div className="h-4 w-full rounded bg-muted/30" />
                <div className="h-4 w-5/6 rounded bg-muted/30" />
                <div className="h-4 w-4/6 rounded bg-muted/30" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
