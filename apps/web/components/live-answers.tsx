import Link from "next/link";
import type { ReactNode } from "react";
import type { Leaders } from "@/lib/live-answers";

// Shared UI for live ranking answers on /top/* and /sectors/*. See
// lib/live-answers.ts for how the answers are computed.

// One self-contained sentence naming the current leaders, recomputed
// on every ISR refresh. No date: the page is the live source, not a
// snapshot. It's the line search snippets and AI assistants quote.
export function QuickAnswer({
  noun,
  leaders,
  className = "mt-6",
}: {
  noun: string;
  leaders: Leaders;
  className?: string;
}) {
  const [first, second, third] = leaders.top;
  if (!first) return null;
  return (
    <p className={`${className} max-w-2xl text-base leading-relaxed text-foreground md:text-lg`}>
      Right now, the top-ranked {noun} on AgentTape are{" "}
      <strong className="font-semibold">{first.name}</strong> (AgentScore {first.score})
      {second && (
        <>
          {third ? ", " : " and "}
          <strong className="font-semibold">{second.name}</strong> ({second.score})
        </>
      )}
      {third && (
        <>
          {" "}and <strong className="font-semibold">{third.name}</strong> ({third.score})
        </>
      )}
      .
      {leaders.mover && (
        <>
          {" "}Biggest 24-hour gain:{" "}
          <strong className="font-semibold">{leaders.mover.name}</strong>, up{" "}
          {leaders.mover.delta} points.
        </>
      )}
    </p>
  );
}

// FAQ answering the questions people ask search engines and AI
// assistants, mirrored in FAQPage JSON-LD. Collapsed by default (first
// item open) so the ranking stays the focus; search engines still
// index collapsed text.
export function LiveFaq({ faqs }: { faqs: { q: string; a: string }[] }) {
  if (faqs.length === 0) return null;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a },
    })),
  };
  return (
    <section>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <h2 className="editorial text-2xl font-semibold leading-tight md:text-3xl">
        Common questions
      </h2>
      <div className="mt-4 divide-y divide-border rounded-md border border-border bg-card">
        {faqs.map((f, i) => (
          <details key={i} className="group px-4 py-3" open={i === 0}>
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-foreground [&::-webkit-details-marker]:hidden">
              {f.q}
              <span
                aria-hidden
                className="shrink-0 text-muted-foreground transition-transform group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-2 max-w-prose text-sm leading-relaxed text-muted-foreground md:text-base">
              {linkify(f.a)}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}

// Turn on-site paths mentioned in FAQ copy ("/top/coding-agents",
// "the Compare page") into links. The JSON-LD keeps the plain text.
function linkify(text: string): ReactNode[] {
  return text
    .split(/(\/(?:top|articles|compare|methodology|indexes|trending)(?:\/[\w-]+)?|the Compare page|the search page)/)
    .map((part, i) => {
      if (i % 2 === 0) return part;
      const href =
        part === "the Compare page" ? "/compare" : part === "the search page" ? "/search" : part;
      return (
        <Link key={i} href={href} className="text-primary hover:underline">
          {part}
        </Link>
      );
    });
}

