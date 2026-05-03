import { api } from "@/lib/api-client";
import { IndexCard } from "@/components/index-card";

export const dynamic = "force-dynamic";
export const metadata = { title: "Indexes" };

export default async function IndexesPage() {
  const indexes = await api.listIndexes();
  const histories = await Promise.all(
    indexes.map((i) =>
      api
        .indexHistory(i.slug, "30d")
        .then((rows) => ({ slug: i.slug, values: rows.map((r) => r.composite_value) }))
        .catch(() => ({ slug: i.slug, values: [] as number[] })),
    ),
  );
  const histBySlug = Object.fromEntries(histories.map((h) => [h.slug, h.values]));

  return (
    <div className="container py-8 md:py-12">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Indexes
        </div>
        <h1 className="editorial mt-2 text-3xl font-semibold leading-tight md:text-4xl">
          Five indexes at launch.
        </h1>
        <p className="mt-3 max-w-prose text-sm text-muted-foreground md:text-base">
          Equal-weight v1, weekly rebalance Mondays 03:00 UTC. Every index has
          a published methodology and a transparent rebalance log.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {indexes.map((i) => (
          <IndexCard key={i.id} index={i} history={histBySlug[i.slug] ?? []} />
        ))}
      </div>
    </div>
  );
}
