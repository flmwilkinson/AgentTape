"use client";

import { useEffect } from "react";

// Power-user shortcuts. Bound at the document level so they work on
// any page. Currently:
//
//   /         focus the nav search input
//   Esc       blur the active input (rely on browser default)
//
// We intentionally don't shadow common browser shortcuts (Ctrl/Cmd-K
// is a candidate but more invasive). The "/" convention follows
// GitHub, Linear, Vercel, etc. — users with the muscle memory will
// just try it.

export function GlobalKeyboardShortcuts() {
  useEffect(() => {
    function isTypingTarget(t: EventTarget | null): boolean {
      if (!(t instanceof HTMLElement)) return false;
      if (t.isContentEditable) return true;
      const tag = t.tagName.toLowerCase();
      return tag === "input" || tag === "textarea" || tag === "select";
    }

    function focusSearch(): boolean {
      // Prefer the visible search input — pick whichever exists. The
      // nav-bar combobox uses input[type=search], so target by type
      // first; fall back to a class hook if needed.
      const el = document.querySelector<HTMLInputElement>(
        'header input[type="search"]',
      );
      if (!el) return false;
      el.focus();
      el.select();
      return true;
    }

    function onKey(e: KeyboardEvent) {
      // "/" focuses search unless the user is already typing in a
      // form control — otherwise typing a slash mid-message would
      // yank focus, which would be infuriating.
      if (e.key === "/" && !isTypingTarget(e.target)) {
        if (focusSearch()) {
          e.preventDefault();
        }
      }
    }

    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return null;
}
