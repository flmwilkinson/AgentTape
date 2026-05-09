export default function Loading() {
  return (
    <article className="animate-pulse">
      <div className="border-b border-border bg-card">
        <div className="container py-10 space-y-4">
          <div className="h-3 w-16 rounded bg-muted/40" />
          <div className="h-12 w-2/3 max-w-md rounded bg-muted/40 md:h-16" />
          <div className="h-4 w-1/2 max-w-sm rounded bg-muted/30" />
        </div>
      </div>
      <div className="container py-8 md:py-12 space-y-8">
        <div className="h-48 rounded-md border border-border bg-card" />
        <div className="rounded-md border border-border bg-card divide-y divide-border">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3">
              <div className="h-4 w-8 rounded bg-muted/30" />
              <div className="h-4 flex-1 max-w-[16rem] rounded bg-muted/30" />
              <div className="h-4 w-12 rounded bg-muted/30" />
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
