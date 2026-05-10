"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

// First-visit explainer for the floor page.
//
// Reading "AgentTape" + a scrolling tape of three-letter codes tells a
// returning trader exactly what they're looking at. It tells everyone
// else nothing. This card answers "what is this thing?" once, then
// disappears for the lifetime of the localStorage entry — so it never
// nags returning users.

const STORAGE_KEY = "agenttape_welcome_dismissed_v1";

export function WelcomeBanner() {
  // Default to false so SSR doesn't flash the banner on every server
  // render before client read happens. The effect only flips it on
  // when the localStorage flag is absent.
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      const dismissed = window.localStorage.getItem(STORAGE_KEY);
      if (!dismissed) setShow(true);
    } catch {
      // Storage blocked (private mode, embedded iframe) — show the
      // banner this session, no harm.
      setShow(true);
    }
  }, []);

  function dismiss() {
    setShow(false);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      // Same — fine if storage is unavailable.
    }
  }

  if (!show) return null;

  return (
    <div className="border-b border-primary/30 bg-primary/5">
      <div className="container flex items-start gap-4 py-3 text-sm md:py-3.5">
        <div className="flex-1">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">
            New here?
          </span>{" "}
          <span className="text-foreground/85">
            AgentTape is a live ranking of AI agents and foundation
            models, updated hourly from public signals like GitHub
            stars and benchmark results. No curated list. Every
            input{" "}
            <a href="/methodology" className="text-primary underline-offset-2 hover:underline">
              published
            </a>
            . Higher AgentScore = more public activity and quality
            across four pillars; click any name for the signals
            behind it.
          </span>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss welcome banner"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
