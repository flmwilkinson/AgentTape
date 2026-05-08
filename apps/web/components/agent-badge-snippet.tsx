"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

// Author-facing snippet: copy-paste markdown / HTML to put a live
// AgentTape badge on a project README. The endpoint at
// /api/badge/<slug>.svg renders the actual SVG and is cacheable for
// an hour so embedding doesn't pound our API.
//
// The badge is the simplest possible distribution loop: every
// embedded badge is a backlink, a free piece of social proof for
// AgentTape, and a live "this is where we are" indicator the author
// gets without thinking.

interface Props {
  slug: string;
}

export function AgentBadgeSnippet({ slug }: Props) {
  const [copied, setCopied] = useState<"md" | "html" | null>(null);
  const origin =
    typeof window === "undefined"
      ? process.env.NEXT_PUBLIC_SITE_URL ?? "https://agenttape.com"
      : window.location.origin;
  const badgeUrl = `${origin}/api/badge/${slug}.svg`;
  const pageUrl = `${origin}/agents/${slug}`;
  const md = `[![AgentTape](${badgeUrl})](${pageUrl})`;
  const html = `<a href="${pageUrl}"><img src="${badgeUrl}" alt="AgentTape" /></a>`;

  async function copy(form: "md" | "html", text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(form);
      setTimeout(() => setCopied(null), 1800);
    } catch {
      // browsers without clipboard API — silent fail
    }
  }

  return (
    <details className="rounded-md border border-border bg-card">
      <summary className="cursor-pointer px-4 py-2.5 text-sm">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Embed badge
        </span>
        <span className="ml-2 text-foreground/80">
          Show your AgentTape rank on your project README
        </span>
      </summary>
      <div className="space-y-3 border-t border-border px-4 py-3">
        <div>
          {/* Live preview of the actual badge endpoint. */}
          <img
            src={badgeUrl}
            alt={`AgentTape badge for ${slug}`}
            className="rounded-md border border-border bg-background"
          />
        </div>
        <CopyBlock
          label="Markdown"
          text={md}
          copied={copied === "md"}
          onCopy={() => copy("md", md)}
        />
        <CopyBlock
          label="HTML"
          text={html}
          copied={copied === "html"}
          onCopy={() => copy("html", html)}
        />
      </div>
    </details>
  );
}

function CopyBlock({
  label,
  text,
  copied,
  onCopy,
}: {
  label: string;
  text: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <button
          type="button"
          onClick={onCopy}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 text-xs",
            copied
              ? "text-gain"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-3 py-2 font-mono text-[11px] leading-relaxed">
        {text}
      </pre>
    </div>
  );
}
