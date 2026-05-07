import Link from "next/link";

// Root not-found page. Hit whenever a route returns 404 from
// `notFound()` or matches no route at all. Pairs with error.tsx so
// Next's dev server has every required boundary on hand.

export default function NotFound() {
  return (
    <div className="container py-16 text-center">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        404
      </div>
      <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
        Nothing here.
      </h1>
      <p className="mt-3 max-w-prose mx-auto text-sm text-muted-foreground">
        The agent, index, or article you're looking for either moved or never
        existed. Try the floor, or search for a name.
      </p>
      <div className="mt-6 flex justify-center gap-3">
        <Link
          href="/"
          className="rounded-md border border-primary bg-primary text-primary-foreground px-4 py-2 text-sm hover:bg-primary/90"
        >
          Back to floor
        </Link>
        <Link
          href="/search"
          className="rounded-md border border-border bg-card px-4 py-2 text-sm hover:bg-subtle"
        >
          Search
        </Link>
      </div>
    </div>
  );
}
