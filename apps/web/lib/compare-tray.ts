"use client";

import { useEffect, useSyncExternalStore } from "react";

// Compare tray — a persistent shortlist of agent slugs the user is
// building toward a comparison. Lives in localStorage so it survives
// navigation and reload, broadcasts via storage events so multiple
// open tabs stay in sync, and uses useSyncExternalStore so React
// components re-render whenever the list changes.
//
// Why not URL state: building a comparison is a multi-page activity
// (browse coding agents, look at the score breakdown, check the FM-50
// for engines, then assemble the shortlist). URL state would need
// to thread through every page; a tiny client store is simpler.

const STORAGE_KEY = "agenttape_compare_tray";
const STORAGE_EVENT = "agenttape:compare-changed";
const MAX = 5;

const SSR_EMPTY: readonly string[] = Object.freeze([]);

let cache: string[] | null = null;

function read(): string[] {
  if (typeof window === "undefined") return [];
  if (cache !== null) return cache;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return (cache = []);
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return (cache = []);
    cache = parsed.filter((s): s is string => typeof s === "string");
    return cache;
  } catch {
    return (cache = []);
  }
}

function write(slugs: string[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(slugs));
  } catch {
    // localStorage full or blocked — silent fail; tray just won't
    // persist this round.
  }
  cache = slugs;
  window.dispatchEvent(new Event(STORAGE_EVENT));
}

export function getCompareTray(): string[] {
  return read();
}

export function addToCompareTray(slug: string): void {
  const cur = read();
  if (cur.includes(slug)) return;
  if (cur.length >= MAX) return;
  write([...cur, slug]);
}

export function removeFromCompareTray(slug: string): void {
  const cur = read();
  if (!cur.includes(slug)) return;
  write(cur.filter((s) => s !== slug));
}

export function toggleCompareTray(slug: string): boolean {
  const cur = read();
  if (cur.includes(slug)) {
    write(cur.filter((s) => s !== slug));
    return false;
  }
  if (cur.length >= MAX) return false;
  write([...cur, slug]);
  return true;
}

export function clearCompareTray(): void {
  write([]);
}

export function isInCompareTray(slug: string): boolean {
  return read().includes(slug);
}

export const COMPARE_TRAY_MAX = MAX;

// React hook — components rerender whenever the tray changes (in
// any tab on the same origin).
function subscribe(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onSame = () => listener();
  const onCross = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      cache = null;
      listener();
    }
  };
  window.addEventListener(STORAGE_EVENT, onSame);
  window.addEventListener("storage", onCross);
  return () => {
    window.removeEventListener(STORAGE_EVENT, onSame);
    window.removeEventListener("storage", onCross);
  };
}

export function useCompareTray(): string[] {
  return useSyncExternalStore(
    subscribe,
    () => read(),
    () => SSR_EMPTY as string[],
  );
}

// Optional: clear the local cache once on mount so a fresh tab
// reads fresh from localStorage rather than stale module state.
export function useHydrateCompareTray() {
  useEffect(() => {
    cache = null;
  }, []);
}
