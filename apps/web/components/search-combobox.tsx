"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Tag as TagIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api-client";

// Debounced autocomplete combobox.
//
// On every keystroke (after 120 ms quiet), we hit /search/suggest
// which returns up to 8 mixed matches: agents whose name/slug or tags
// contain the query, plus tag suggestions themselves. Arrow keys move
// between suggestions; Enter on a highlighted row jumps to the agent
// (or sector page for a tag), Enter on the input runs the full
// /search with the current query.
//
// Two flavours are exported: SearchCombobox (full width, used in
// the desktop nav header) and SearchComboboxMobile (slim, fits the
// mobile top bar). They share the same internals.

type AgentSuggestion = {
  kind: "agent";
  slug: string;
  name: string;
  entity_kind: string;
  description: string | null;
  agent_score: number | null;
};

type TagSuggestion = {
  kind: "tag";
  tag_kind: string;
  tag_value: string;
  count: number;
};

type Suggestion = AgentSuggestion | TagSuggestion;

interface Props {
  className?: string;
  inputClassName?: string;
  placeholder?: string;
  // Initial query — used by /search to pre-populate from the URL.
  initialQuery?: string;
  // Override the default Enter behavior. Called with the current
  // query when the user submits without a highlighted suggestion;
  // /search uses this to run the search inline (preserving mode).
  // Selecting a suggestion still navigates to that agent.
  onEnter?: (q: string) => void;
  // Override the default agent-suggestion behavior. The /search and
  // header consumers want a navigation, but /compare wants to add
  // the slug to the comparison list and clear the box. When set, the
  // combobox calls this and skips routing; the input is cleared and
  // the panel closes after the call.
  onSelectAgent?: (slug: string) => void;
  // When onSelectAgent is set, /compare also wants to suppress tag
  // suggestions (they don't make sense in a "pick one agent"
  // context). This flag does that without coupling the combobox to
  // /compare specifically.
  agentsOnly?: boolean;
  // /compare needs to filter out already-selected agents from the
  // dropdown. Pass a Set of slugs to hide.
  excludeSlugs?: Set<string>;
}

export function SearchCombobox({
  className,
  inputClassName,
  placeholder = "Search agents, models…",
  initialQuery = "",
  onEnter,
  onSelectAgent,
  agentsOnly = false,
  excludeSlugs,
}: Props) {
  const router = useRouter();
  const [q, setQ] = useState(initialQuery);
  const [open, setOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Debounce the suggest call. 120ms is short enough to feel instant
  // while collapsing per-keystroke calls when someone types fast.
  useEffect(() => {
    const trimmed = q.trim();
    if (!trimmed) {
      setSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const list = await api.searchSuggest(trimmed, 8);
        let filtered: Suggestion[] = list;
        if (agentsOnly) filtered = filtered.filter((s) => s.kind === "agent");
        if (excludeSlugs && excludeSlugs.size > 0) {
          filtered = filtered.filter(
            (s) => s.kind !== "agent" || !excludeSlugs.has(s.slug),
          );
        }
        setSuggestions(filtered);
        setActive(0);
      } catch {
        setSuggestions([]);
      }
    }, 120);
    return () => clearTimeout(t);
  }, [q, agentsOnly, excludeSlugs]);

  // Click-outside closes the panel.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function go(slug: string) {
    setOpen(false);
    if (!onEnter) setQ("");
    router.push(`/agents/${slug}`);
  }

  function goSuggestion(s: Suggestion) {
    if (s.kind === "agent") {
      // /compare and any other "pick a slug" caller can intercept
      // selection — we hand them the slug and let them decide what
      // to do (typically: add it to a list, clear the box, refocus).
      if (onSelectAgent) {
        setQ("");
        setOpen(false);
        onSelectAgent(s.slug);
        return;
      }
      go(s.slug);
      return;
    }
    // Tag suggestion → sector landing page for that capability/tag,
    // which already shows members + filters + compare entry points.
    setOpen(false);
    if (!onEnter) setQ("");
    router.push(`/sectors/${s.tag_kind}/${encodeURIComponent(s.tag_value)}`);
  }

  function runFullSearch() {
    setOpen(false);
    const v = q.trim();
    if (onEnter) {
      // Caller wants to handle the submit themselves (e.g. /search
      // updating URL params while preserving mode).
      onEnter(v);
      return;
    }
    router.push(v ? `/search?q=${encodeURIComponent(v)}` : "/search");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const s = suggestions[active];
      if (open && s) {
        goSuggestion(s);
      } else {
        runFullSearch();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showPanel = open && q.trim().length > 0 && suggestions.length > 0;

  return (
    <div
      ref={containerRef}
      className={cn("relative inline-block", className)}
    >
      <label className="relative block">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={q}
          placeholder={placeholder}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => q.trim() && setOpen(true)}
          onKeyDown={onKeyDown}
          // Password manager / form-fill extensions (LastPass, 1Password,
          // Bitwarden, Roboform) inject fdprocessedid attributes on
          // inputs between SSR and hydration. suppressHydrationWarning
          // keeps React quiet about that injected attribute on this
          // exact element. The data-* attributes politely ask the major
          // managers not to bother in the first place.
          suppressHydrationWarning
          autoComplete="off"
          data-1p-ignore
          data-lpignore="true"
          data-form-type="other"
          className={cn(
            "h-8 w-full rounded-md border border-border bg-card pl-8 pr-3 text-xs placeholder:text-muted-foreground/70 focus:outline-none focus:ring-1 focus:ring-primary",
            inputClassName,
          )}
        />
      </label>

      {showPanel && (
        <div
          role="listbox"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-md border border-border bg-card shadow-lg"
        >
          {suggestions.map((s, i) => {
            const key = s.kind === "agent" ? s.slug : `tag:${s.tag_kind}:${s.tag_value}`;
            return (
              <button
                key={key}
                type="button"
                role="option"
                aria-selected={i === active}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => {
                  // mousedown beats the input's blur, so the click lands.
                  e.preventDefault();
                  goSuggestion(s);
                }}
                className={cn(
                  "block w-full border-b border-border px-3 py-2 text-left last:border-b-0 transition-colors",
                  i === active ? "bg-subtle" : "hover:bg-subtle/60",
                )}
              >
                {s.kind === "agent" ? (
                  <>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-medium">{s.name}</span>
                      <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                        {s.entity_kind === "foundation_model" ? "model" : "agent"}
                      </span>
                      {s.agent_score != null && (
                        <span className="num ml-auto text-xs text-muted-foreground">
                          {s.agent_score.toFixed(1)}
                        </span>
                      )}
                    </div>
                    {s.description && (
                      <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                        {s.description}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="flex items-baseline gap-2">
                    <TagIcon className="h-3 w-3 text-primary" />
                    <span className="text-sm font-medium">{s.tag_value}</span>
                    <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                      {s.tag_kind}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {s.count} {s.count === 1 ? "agent" : "agents"} →
                    </span>
                  </div>
                )}
              </button>
            );
          })}
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              runFullSearch();
            }}
            className="block w-full border-t border-border px-3 py-2 text-left text-xs text-primary hover:bg-subtle/60"
          >
            See all results for &ldquo;{q.trim()}&rdquo; →
          </button>
        </div>
      )}
    </div>
  );
}
