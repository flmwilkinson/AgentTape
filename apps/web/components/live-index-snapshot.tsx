import { api } from "@/lib/api-client";
import { IndexSnapshot, type IndexSnapshotRow } from "@/components/article-blocks";

// Server-side live snapshot of an AgentTape index.
//
// Articles use this instead of a hardcoded IndexSnapshot so the
// numbers shown in editorial content always match what's live on
// /indexes/[slug]. Falls back to the static `fallback` rows if the
// API is unreachable at render time, so an article still renders
// during a backend outage.

interface Props {
  index_slug: string;
  caption: string;
  limit?: number;
  fallback?: {
    composite: number;
    delta_label?: string;
    rows: IndexSnapshotRow[];
  };
}

export async function LiveIndexSnapshot({
  index_slug,
  caption,
  limit = 6,
  fallback,
}: Props) {
  const detail = await api.getIndex(index_slug).catch(() => null);
  if (!detail) {
    if (fallback) {
      return (
        <IndexSnapshot
          index_slug={index_slug}
          caption={caption}
          composite={fallback.composite}
          delta_label={fallback.delta_label}
          rows={fallback.rows}
        />
      );
    }
    return null;
  }

  // Pull a 30-day history slice so we can show a real composite delta
  // rather than a hand-typed "▲ vs 30d" decoration.
  const history = await api
    .indexHistory(index_slug, "30d")
    .catch(() => [] as { captured_at: string; composite_value: number }[]);
  const composite = detail.composite_value ?? 0;
  const earliest = history[0]?.composite_value ?? null;
  const delta = earliest != null ? composite - earliest : null;
  const delta_label =
    delta == null
      ? undefined
      : delta >= 0
        ? `▲ ${delta.toFixed(1)} vs 30d`
        : `▼ ${Math.abs(delta).toFixed(1)} vs 30d`;

  // Sort constituents by score (the index ordering in the detail
  // payload isn't guaranteed) and take the top N.
  const ranked = [...detail.constituents]
    .filter((c) => c.agent.score?.agent_score != null)
    .sort(
      (a, b) =>
        (b.agent.score?.agent_score ?? 0) - (a.agent.score?.agent_score ?? 0),
    )
    .slice(0, limit);

  const rows: IndexSnapshotRow[] = ranked.map((c, i) => ({
    rank: i + 1,
    name: c.agent.name,
    score: c.agent.score?.agent_score ?? 0,
    delta: c.agent.score?.delta_24h ?? undefined,
  }));

  return (
    <IndexSnapshot
      index_slug={index_slug}
      caption={caption}
      composite={composite}
      delta_label={delta_label}
      rows={rows}
    />
  );
}
