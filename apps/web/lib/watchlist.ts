"use client";

// Cookie-based watchlist — no auth, no server state. Stored as a single
// cookie (`agenttape_watch`) holding a comma-separated list of slugs.
// Cap at 50 to keep the cookie under typical 4 KB limits.
//
// Why cookies and not localStorage:
//   - Sent with every request, so SSR routes (e.g. /watchlist) can read
//     it server-side without a client roundtrip.
//   - Survives privacy-tracker blockers that nuke localStorage.

import { useEffect, useSyncExternalStore } from "react";

const COOKIE = "agenttape_watch";
const MAX = 50;

function readCookie(): string[] {
  if (typeof document === "undefined") return [];
  const m = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=([^;]*)`));
  if (!m) return [];
  try {
    return decodeURIComponent(m[1])
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

function writeCookie(slugs: string[]) {
  if (typeof document === "undefined") return;
  const value = encodeURIComponent(slugs.slice(0, MAX).join(","));
  // 1 year, lax samesite — works for SSR reads + GET-style nav.
  document.cookie = `${COOKIE}=${value}; max-age=${60 * 60 * 24 * 365}; path=/; samesite=lax`;
}

// useSyncExternalStore-friendly broadcast so multiple components stay
// in sync within a tab. Cross-tab sync (storage events) isn't needed
// for a watchlist that updates rarely.
type Listener = () => void;
const listeners = new Set<Listener>();
let cache: string[] | null = null;

function notify() {
  cache = null;
  for (const l of listeners) l();
}

export function getWatchlist(): string[] {
  if (cache === null) cache = readCookie();
  return cache;
}

export function setWatchlist(slugs: string[]): void {
  writeCookie(slugs);
  notify();
}

export function isWatched(slug: string): boolean {
  return getWatchlist().includes(slug);
}

export function toggleWatched(slug: string): boolean {
  const cur = getWatchlist();
  const next = cur.includes(slug)
    ? cur.filter((s) => s !== slug)
    : [slug, ...cur];
  setWatchlist(next);
  return !cur.includes(slug);
}

function subscribe(l: Listener) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useWatchlist(): string[] {
  // SSR snapshot returns empty — the value populates on hydration.
  return useSyncExternalStore(subscribe, getWatchlist, () => []);
}

// Track the last visit timestamp so we can show a "since you were last
// here" callout. Not a watchlist concern strictly, but the cookie
// machinery is the same.
const LAST_VISIT_COOKIE = "agenttape_last_visit";

export function useMarkVisited(): void {
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.cookie = `${LAST_VISIT_COOKIE}=${Math.floor(Date.now() / 1000)}; max-age=${60 * 60 * 24 * 365}; path=/; samesite=lax`;
  }, []);
}

export function getLastVisit(): Date | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(
    new RegExp(`(?:^|; )${LAST_VISIT_COOKIE}=([^;]*)`),
  );
  if (!m) return null;
  const ts = parseInt(m[1], 10);
  if (!Number.isFinite(ts)) return null;
  return new Date(ts * 1000);
}
