import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

// Styled article-block primitives.
//
// Articles import these instead of dropping inline HTML so every
// long-form post lands in the same design system: bg-card, text-
// muted-foreground, hsl(var(--primary)), font-mono labels, etc.
// If the brand palette ever changes, every article inherits the
// new tokens without a content rewrite.

// ---------------------------------------------------------------- prose

/** Wrap an article in this; gives it the magazine-typography styling. */
export function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="editorial space-y-5 text-base leading-relaxed text-foreground/90 md:text-lg">
      {children}
    </div>
  );
}

export function H2({ children }: { children: ReactNode }) {
  return (
    <h2 className="editorial mt-12 text-2xl font-semibold leading-tight md:text-3xl">
      {children}
    </h2>
  );
}

export function H3({ children }: { children: ReactNode }) {
  return (
    <h3 className="editorial mt-8 text-xl font-semibold leading-snug md:text-2xl">
      {children}
    </h3>
  );
}

// ------------------------------------------------------------- stat grid

export interface Stat {
  label: string;
  name: string;
  detail: string;
}

/** 4-up stat row, used as an article opener. */
export function StatGrid({ items }: { items: Stat[] }) {
  return (
    <div className="my-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((s) => (
        <div
          key={s.label + s.name}
          className="rounded-md border border-border bg-card p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {s.label}
          </div>
          <div className="mt-1 text-base font-semibold leading-tight">
            {s.name}
          </div>
          <div className="num mt-0.5 text-xs text-muted-foreground">
            {s.detail}
          </div>
        </div>
      ))}
    </div>
  );
}

// --------------------------------------------------------------- badges

export type Badge = string | { label: string; tone?: "default" | "gain" | "loss" | "primary" };

/** Inline tag chips — used under product H2s. */
export function Badges({ items }: { items: Badge[] }) {
  return (
    <div className="my-3 flex flex-wrap gap-1.5 font-mono text-[11px]">
      {items.map((b, i) => {
        const item = typeof b === "string" ? { label: b, tone: "default" as const } : b;
        return (
          <span
            key={i}
            className={cn(
              "rounded-md border px-2 py-0.5",
              item.tone === "gain" && "border-gain/40 text-gain",
              item.tone === "loss" && "border-loss/40 text-loss",
              item.tone === "primary" && "border-primary/40 text-primary",
              (!item.tone || item.tone === "default") &&
                "border-border bg-subtle text-muted-foreground",
            )}
          >
            {item.label}
          </span>
        );
      })}
    </div>
  );
}

// ----------------------------------------------------------- score bars

export interface ScoreRow {
  label: string;
  value: number;
  max?: number;
}

/** Horizontal score-bar list — used for benchmark leaderboards. */
export function ScoreBars({
  caption,
  rows,
  source,
}: {
  caption: string;
  rows: ScoreRow[];
  source?: string;
}) {
  const max = Math.max(...rows.map((r) => r.value), 100);
  return (
    <div className="my-8 rounded-md border border-border bg-card p-4 md:p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
        {caption}
      </div>
      <div className="mt-3 space-y-1.5 font-mono text-xs">
        {rows.map((r) => {
          const pct = ((r.value / (r.max ?? max)) * 100).toFixed(1);
          return (
            <div key={r.label} className="flex items-center gap-3">
              <span className="w-44 shrink-0 truncate text-foreground/85">
                {r.label}
              </span>
              <div className="relative h-3.5 flex-1 overflow-hidden rounded-sm bg-gain/10">
                <div
                  className="absolute inset-y-0 left-0 bg-gain"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="num w-14 text-right tabular-nums text-foreground/85">
                {r.value.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>
      {source && (
        <div className="mt-3 text-[11px] text-muted-foreground">{source}</div>
      )}
    </div>
  );
}

// ------------------------------------------------------- tradeoff table

export interface TradeoffRow {
  job: string;
  pick: ReactNode;
  why: string;
}

/** "Trade-offs by job" comparison table. */
export function TradeoffTable({ rows }: { rows: TradeoffRow[] }) {
  return (
    <div className="my-6 overflow-x-auto rounded-md border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="text-left font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          <tr className="border-b border-border">
            <th className="px-4 py-2 font-medium">Job</th>
            <th className="px-4 py-2 font-medium">Default pick</th>
            <th className="px-4 py-2 font-medium">Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className="border-b border-border last:border-b-0"
            >
              <td className="px-4 py-2.5 align-top">{r.job}</td>
              <td className="px-4 py-2.5 align-top font-medium">{r.pick}</td>
              <td className="px-4 py-2.5 align-top text-muted-foreground">
                {r.why}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -------------------------------------------------------- persona cards

export interface PersonaCard {
  audience: string;
  pick: string;
  body: string;
}

/** 3-up "what to default to, by persona" grid. */
export function PersonaCards({ items }: { items: PersonaCard[] }) {
  return (
    <div className="my-6 grid gap-3 md:grid-cols-3">
      {items.map((p) => (
        <div
          key={p.audience}
          className="rounded-md border border-border bg-card p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            {p.audience}
          </div>
          <div className="mt-1.5 text-base font-semibold leading-snug">
            {p.pick}
          </div>
          <p className="mt-2 text-sm text-foreground/85">{p.body}</p>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------- index snapshot

export interface IndexSnapshotRow {
  rank: number;
  name: string;
  score: number;
  delta?: number;
}

/** Live-tape callout — shows a slice of an AgentTape index. */
export function IndexSnapshot({
  index_slug,
  caption,
  composite,
  delta_label,
  rows,
}: {
  index_slug: string;
  caption: string;
  composite: number;
  delta_label?: string;
  rows: IndexSnapshotRow[];
}) {
  return (
    <Link
      href={`/indexes/${index_slug}`}
      className="group my-8 block overflow-hidden rounded-md border border-border bg-card font-mono text-sm transition-colors hover:border-foreground/20"
    >
      <div className="flex items-center justify-between border-b border-border bg-subtle/50 px-4 py-2.5">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {caption}
        </span>
        <span className="num font-semibold">
          {composite.toFixed(1)}
          {delta_label && (
            <span className="ml-2 font-mono text-xs text-gain">{delta_label}</span>
          )}
        </span>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((r) => (
          <li
            key={r.rank}
            className="flex items-center justify-between gap-3 px-4 py-2.5 group-hover:bg-subtle/40"
          >
            <span className="flex min-w-0 items-center gap-3">
              <span className="num w-5 text-muted-foreground">{r.rank}</span>
              <span className="truncate text-foreground/90">{r.name}</span>
            </span>
            <span className="num shrink-0 tabular-nums">
              {r.score.toFixed(1)}
              {r.delta != null && r.delta !== 0 && (
                <span
                  className={cn(
                    "ml-2 text-xs",
                    r.delta > 0 ? "text-gain" : "text-loss",
                  )}
                >
                  {r.delta > 0 ? "+" : ""}
                  {r.delta.toFixed(2)}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
      <div className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
        Open the live tape →
      </div>
    </Link>
  );
}

// ----------------------------------------------------------- product H2

/** Numbered H2 used to introduce a product entry; pairs with Badges. */
export function ProductHeading({
  rank,
  name,
}: {
  rank: number;
  name: string;
}) {
  return (
    <h2 className="editorial mt-14 text-2xl font-semibold leading-tight md:text-3xl">
      <span className="num mr-3 text-muted-foreground">{rank}.</span>
      {name}
    </h2>
  );
}

// ---------------------------------------------------------------- lede

/** Opening paragraph with drop-cap and editorial scale. */
export function Lede({ children }: { children: ReactNode }) {
  return (
    <p className="editorial my-6 text-xl leading-relaxed text-foreground/90 md:text-2xl first-letter:editorial first-letter:float-left first-letter:mr-2 first-letter:text-6xl first-letter:font-semibold first-letter:leading-none first-letter:text-primary md:first-letter:text-7xl">
      {children}
    </p>
  );
}

// ---------------------------------------------------------- section grid

/** Section divider — full-width rule + section number kicker. */
export function SectionDivider({ number, label }: { number: string; label: string }) {
  return (
    <div className="mt-16 border-t border-border pt-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary">
        § {number} / {label}
      </div>
    </div>
  );
}

/** Two-column section: prose on the left, spec card pinned right. */
export function Section({ children }: { children: ReactNode }) {
  return (
    <div className="mt-6 grid gap-6 md:grid-cols-[1fr_280px] md:gap-10 md:items-start">
      {children}
    </div>
  );
}

/** Left-column prose. Enforces max-width so lines don't sprawl. */
export function SectionContent({ children }: { children: ReactNode }) {
  return (
    <div className="editorial space-y-4 text-base leading-relaxed text-foreground/90 md:text-lg">
      {children}
    </div>
  );
}

// ----------------------------------------------------------- spec card

export interface SpecRow {
  key: string;
  value: ReactNode;
  big?: boolean;
}

/** Sticky spec card — fixed-width sidebar inside Section. */
export function SpecCard({
  title,
  badge,
  rows,
}: {
  title: string;
  badge?: string;
  rows: SpecRow[];
}) {
  return (
    <aside className="rounded-md border border-border bg-card font-mono text-xs md:sticky md:top-20">
      <div className="flex items-center justify-between border-b border-border bg-foreground px-3 py-2 text-background">
        <span className="text-[10px] uppercase tracking-[0.18em]">{title}</span>
        {badge && (
          <span className="text-[10px] uppercase tracking-[0.16em] opacity-80">
            {badge}
          </span>
        )}
      </div>
      <div className="divide-y divide-dashed divide-border">
        {rows.map((r) => (
          <div key={r.key} className="flex items-baseline justify-between gap-3 px-3 py-2.5">
            <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              {r.key}
            </span>
            <span
              className={cn(
                "text-right",
                r.big ? "text-base font-semibold text-primary" : "text-foreground/90",
              )}
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------- ticker table

export interface TickerRow {
  symbol: string;
  stars: ReactNode;
  license: string;
  default_model: string;
  replaces?: string;
  trend?: "up" | "down" | "flat";
}

/** "Live · OSS coding agents" at-a-glance table with pulse indicator. */
export function TickerTable({
  caption,
  asof,
  rows,
}: {
  caption: string;
  asof: string;
  rows: TickerRow[];
}) {
  return (
    <div className="my-8 overflow-hidden rounded-md border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border bg-foreground px-4 py-2 text-background">
        <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em]">
          <span className="relative inline-block h-1.5 w-1.5 rounded-full bg-gain">
            <span className="absolute inset-0 animate-ping rounded-full bg-gain opacity-60" />
          </span>
          {caption}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] opacity-80">
          {asof}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] font-mono text-xs">
          <thead className="bg-subtle/50 text-muted-foreground">
            <tr className="border-b border-border">
              <th className="px-4 py-2 text-left text-[10px] uppercase tracking-[0.16em] font-medium">Project</th>
              <th className="px-4 py-2 text-left text-[10px] uppercase tracking-[0.16em] font-medium">Stars</th>
              <th className="px-4 py-2 text-left text-[10px] uppercase tracking-[0.16em] font-medium">License</th>
              <th className="px-4 py-2 text-left text-[10px] uppercase tracking-[0.16em] font-medium">Default model</th>
              <th className="hidden px-4 py-2 text-left text-[10px] uppercase tracking-[0.16em] font-medium md:table-cell">
                Most replaces
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.symbol} className="border-b border-border last:border-b-0 hover:bg-subtle/40">
                <td className="px-4 py-2.5 font-semibold tracking-wider">{r.symbol}</td>
                <td className="px-4 py-2.5 font-semibold text-primary">
                  {r.stars}
                  {r.trend === "up" && <span className="ml-1 text-gain">▲</span>}
                  {r.trend === "down" && <span className="ml-1 text-loss">▼</span>}
                </td>
                <td className="px-4 py-2.5">
                  <span className="rounded-sm border border-border bg-subtle px-1.5 py-0.5 text-[10px]">
                    {r.license}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-foreground/90">{r.default_model}</td>
                <td className="hidden px-4 py-2.5 italic text-muted-foreground md:table-cell">
                  {r.replaces ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------- quad grid

export interface QuadItem {
  number: string;
  name: string;
  who: string;
  body: ReactNode;
}

/** 2x2 grid of "reasons" — used for the why-OSS section. */
export function QuadGrid({
  title,
  deck,
  items,
}: {
  title: ReactNode;
  deck: ReactNode;
  items: QuadItem[];
}) {
  return (
    <section className="my-12 rounded-md border border-border bg-card p-6 md:p-10">
      <h2 className="editorial text-2xl font-semibold leading-tight md:text-3xl">
        {title}
      </h2>
      <p className="editorial mt-3 max-w-prose text-base leading-relaxed text-muted-foreground md:text-lg">
        {deck}
      </p>
      <div className="mt-8 grid gap-px overflow-hidden rounded-md bg-border sm:grid-cols-2">
        {items.map((q) => (
          <div key={q.number} className="bg-card p-5">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
              ▲ Reason {q.number}
            </div>
            <div className="editorial mt-2 text-xl font-semibold leading-snug md:text-2xl">
              {q.name}
            </div>
            <div className="mt-1 text-xs italic text-muted-foreground">{q.who}</div>
            <p className="mt-3 text-sm leading-relaxed text-foreground/85">
              {q.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------- pull quote

/** Italic pull-quote with primary left rule. */
export function PullQuote({ children }: { children: ReactNode }) {
  return (
    <blockquote className="editorial my-10 max-w-xl border-l-2 border-primary pl-6 text-2xl italic leading-snug text-foreground/90 md:text-3xl">
      {children}
    </blockquote>
  );
}

// ---------------------------------------------------------- CTA panel

// ----------------------------------------------------------- axes grid

export interface Axis {
  label: string;
  body: ReactNode;
}

/** 3-up axes/criteria row. Used to set up "we score on X, Y, Z" intros. */
export function AxesGrid({ items }: { items: Axis[] }) {
  return (
    <div className="my-8 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((a) => (
        <div
          key={a.label}
          className="rounded-md border border-border bg-card p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
            {a.label}
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground/90">
            {a.body}
          </p>
        </div>
      ))}
    </div>
  );
}

// ----------------------------------------------------------- step header

/** Big numbered step heading — used in the buyer's-guide article. */
export function StepHeader({
  number,
  eyebrow,
  title,
}: {
  number: string;
  eyebrow: string;
  title: ReactNode;
}) {
  return (
    <div className="mt-16 grid grid-cols-[60px_1fr] items-start gap-4 border-t border-border pt-8 md:grid-cols-[88px_1fr] md:gap-6">
      <div className="editorial text-5xl font-semibold leading-none text-primary md:text-7xl">
        {number}
      </div>
      <div>
        <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {eyebrow}
        </div>
        <h2 className="editorial mt-1 text-2xl font-semibold leading-tight md:text-3xl">
          {title}
        </h2>
      </div>
    </div>
  );
}

// ----------------------------------------------------------- checklist

/** "Tear out" checklist box — distinct enough to feel like a snippet. */
export function ChecklistBox({
  tearout_label,
  title,
  items,
}: {
  tearout_label: string;
  title: ReactNode;
  items: ReactNode[];
}) {
  return (
    <section className="relative my-12 rounded-md border border-border bg-card p-6 md:p-10">
      <span className="absolute left-6 top-0 -translate-y-1/2 bg-background px-2 font-mono text-[10px] uppercase tracking-[0.18em] text-primary">
        {tearout_label}
      </span>
      <h2 className="editorial mt-2 text-2xl font-semibold leading-tight md:text-3xl">
        {title}
      </h2>
      <ol className="mt-5 list-none space-y-0">
        {items.map((it, i) => (
          <li
            key={i}
            className="grid grid-cols-[42px_24px_1fr] items-start gap-2 border-t border-border py-3.5 first:border-t-0 md:grid-cols-[56px_24px_1fr]"
          >
            <span className="font-mono text-xs tracking-wider text-primary">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span
              aria-hidden
              className="mt-1 inline-block h-3.5 w-3.5 rounded-sm border border-foreground bg-background"
            />
            <span className="text-sm leading-relaxed text-foreground/90 md:text-base">
              {it}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ------------------------------------------------------------- model card

export interface ModelCardSplit {
  label: string;
  body: ReactNode;
}

export interface ModelCardStat {
  label: string;
  value: ReactNode;
}

/** Numbered FM-ranking card — for foundation-model leaderboard articles. */
export function ModelCard({
  rank,
  name,
  maker,
  badge,
  tag,
  splits,
  stat,
}: {
  rank: number;
  name: string;
  maker: string;
  badge?: string;
  tag: ReactNode;
  splits: [ModelCardSplit, ModelCardSplit];
  stat: ModelCardStat;
}) {
  const isTop = rank === 1;
  return (
    <div
      className={cn(
        "my-3 grid grid-cols-[44px_1fr] gap-3 rounded-md border bg-card p-4 sm:grid-cols-[56px_1fr] sm:gap-4 md:p-6",
        isTop ? "border-primary border-2" : "border-border",
      )}
    >
      <div
        className={cn(
          "editorial text-3xl font-semibold leading-none tabular-nums md:text-4xl",
          isTop ? "text-primary" : "text-muted-foreground",
        )}
      >
        {String(rank).padStart(2, "0")}
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-2">
          <h3 className="text-base font-semibold md:text-lg">{name}</h3>
          <span className="text-xs text-muted-foreground">{maker}</span>
          {badge && (
            <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-2.5 text-sm leading-relaxed text-foreground/90 md:text-base">
          {tag}
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {splits.map((s) => (
            <div key={s.label}>
              <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {s.label}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground md:text-sm">
                {s.body}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between rounded-md bg-subtle px-3 py-2 text-sm">
          <span className="text-muted-foreground">{stat.label}</span>
          <span className="num font-semibold text-foreground">{stat.value}</span>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------- choose grid

export interface ChooseItem {
  heading: string;
  body: ReactNode;
}

/** 2x2 small "how to choose" recommendation cards. */
export function ChooseGrid({ items }: { items: ChooseItem[] }) {
  return (
    <div className="my-6 grid gap-2.5 sm:grid-cols-2">
      {items.map((c) => (
        <div
          key={c.heading}
          className="rounded-md border border-border bg-card p-4"
        >
          <div className="text-sm font-medium">{c.heading}</div>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
        </div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------ CTA buttons

export interface CTAButton {
  label: string;
  href: string;
}

/** Twin link buttons under an article — "compare" + "see live index". */
export function CTAButtonRow({ items }: { items: CTAButton[] }) {
  return (
    <nav className="my-10 grid gap-2 border-t border-border pt-8 sm:grid-cols-2">
      {items.map((b) => (
        <Link
          key={b.href}
          href={b.href}
          className="group flex items-center justify-between rounded-md border border-border bg-card px-5 py-4 text-sm font-medium transition-colors hover:bg-subtle"
        >
          <span>{b.label}</span>
          <span aria-hidden className="text-muted-foreground transition-transform group-hover:translate-x-0.5">
            →
          </span>
        </Link>
      ))}
    </nav>
  );
}

// ------------------------------------------------------- closer paragraph

/** Editorial closing-line — italic, slightly bigger than body. */
export function Closer({ children }: { children: ReactNode }) {
  return (
    <p className="editorial mt-8 text-xl leading-snug text-foreground/90 md:text-2xl">
      {children}
    </p>
  );
}

/** Inverted dark callout — links to a live AgentTape index. */
export function CTAPanel({
  tag,
  title,
  body,
  href,
  cta_label,
}: {
  tag: string;
  title: ReactNode;
  body: ReactNode;
  href: string;
  cta_label: string;
}) {
  return (
    <section className="relative my-12 overflow-hidden rounded-md bg-foreground p-8 text-background md:p-12">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
        ▲ {tag}
      </div>
      <h3 className="editorial mt-3 max-w-prose text-3xl font-semibold leading-tight md:text-4xl">
        {title}
      </h3>
      <p className="mt-4 max-w-prose text-base leading-relaxed text-background/70">
        {body}
      </p>
      <Link
        href={href}
        className="mt-7 inline-flex items-center gap-3 rounded-sm border border-background bg-background px-5 py-3 font-mono text-xs font-semibold uppercase tracking-[0.14em] text-foreground transition-colors hover:bg-primary hover:text-background hover:border-primary"
      >
        {cta_label} <span aria-hidden>→</span>
      </Link>
    </section>
  );
}
