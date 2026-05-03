// Number / date formatters used across the app.
//
// Score formatting is deliberately simple: 0-100, one decimal place,
// bumped to "—" when null (the "Unrated" state for quality).

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (Math.abs(value) < 1000) return value.toLocaleString("en-US");
  if (Math.abs(value) < 1_000_000)
    return (value / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  if (Math.abs(value) < 1_000_000_000)
    return (value / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  return (value / 1_000_000_000).toFixed(1).replace(/\.0$/, "") + "B";
}

export function formatDelta(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "" : "±";
  return `${sign}${value.toFixed(2)}`;
}

export function formatDeltaPct(
  now: number,
  prior: number | null | undefined,
): string {
  if (prior === null || prior === undefined || prior === 0) return "—";
  const pct = ((now - prior) / prior) * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

export function relativeTime(iso: string | Date | null | undefined): string {
  if (!iso) return "—";
  const t = typeof iso === "string" ? new Date(iso).getTime() : iso.getTime();
  const diff = Date.now() - t;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(t).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function deltaSign(now: number, prior?: number | null): "up" | "down" | "flat" {
  if (prior === null || prior === undefined) return "flat";
  if (now > prior) return "up";
  if (now < prior) return "down";
  return "flat";
}
