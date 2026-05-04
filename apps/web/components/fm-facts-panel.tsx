import { ExternalLink } from "lucide-react";

// Foundation-model facts panel.
//
// Foundation models don't accumulate the kind of time-series signals
// (stars, downloads, mentions) that drive the application-agent
// pillar bars. What they DO have is rich source-of-truth metadata
// from OpenRouter: context window, pricing, modality, provider tier.
// This panel surfaces that so an FM agent page isn't just a flat
// chart with nothing under it.

interface Facts {
  openrouter_id?: string;
  context_length?: number;
  max_completion_tokens?: number;
  modality?: string;
  tokenizer?: string;
  instruct_type?: string;
  input_price_per_million?: number;
  output_price_per_million?: number;
  is_moderated?: boolean;
  html_url?: string;
}

interface Props {
  facts: Record<string, unknown>;
}

export function FmFactsPanel({ facts }: Props) {
  const f = facts as Facts;
  if (!f.openrouter_id && !f.context_length) return null;

  const provider = (f.openrouter_id ?? "").split("/", 1)[0] || "—";
  const isFree = (f.openrouter_id ?? "").includes("free");

  const items: { label: string; value: React.ReactNode }[] = [
    { label: "Provider", value: provider },
    {
      label: "Context",
      value:
        f.context_length != null ? formatTokens(f.context_length) : "—",
    },
    {
      label: "Max output",
      value:
        f.max_completion_tokens != null
          ? formatTokens(f.max_completion_tokens)
          : "—",
    },
    { label: "Modality", value: f.modality ?? "text" },
    {
      label: "Input price",
      value:
        f.input_price_per_million != null
          ? `$${f.input_price_per_million.toFixed(2)}/M`
          : isFree
            ? "free"
            : "—",
    },
    {
      label: "Output price",
      value:
        f.output_price_per_million != null
          ? `$${f.output_price_per_million.toFixed(2)}/M`
          : isFree
            ? "free"
            : "—",
    },
    { label: "Tokenizer", value: f.tokenizer ?? "—" },
    {
      label: "Moderated",
      value: f.is_moderated == null ? "—" : f.is_moderated ? "Yes" : "No",
    },
  ];

  return (
    <section className="rounded-md border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Model facts
          </div>
          <div className="text-[11px] text-muted-foreground">
            Sourced from OpenRouter. Refreshes daily.
          </div>
        </div>
        {f.html_url && (
          <a
            href={f.html_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            OpenRouter <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 px-4 py-4 sm:grid-cols-4">
        {items.map((it) => (
          <div key={it.label}>
            <dt className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              {it.label}
            </dt>
            <dd className="mt-0.5 text-sm">{it.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}
