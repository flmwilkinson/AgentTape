export default function Loading() {
  return (
    <article className="animate-pulse">
      <div className="border-b border-border bg-card">
        <div className="container py-10 space-y-4">
          <div className="h-3 w-16 rounded bg-muted/40" />
          <div className="h-12 w-3/4 max-w-xl rounded bg-muted/40 md:h-16" />
          <div className="h-4 w-2/3 max-w-lg rounded bg-muted/30" />
        </div>
      </div>
      <div className="container py-8 md:py-12 space-y-10">
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="rounded-md border border-border bg-card p-6 space-y-3"
            >
              <div className="h-3 w-20 rounded bg-muted/40" />
              <div className="h-8 w-24 rounded bg-muted/40" />
              <div className="h-3 w-16 rounded bg-muted/30" />
            </div>
          ))}
        </div>
        <div className="h-64 rounded-md border border-border bg-card" />
      </div>
    </article>
  );
}
