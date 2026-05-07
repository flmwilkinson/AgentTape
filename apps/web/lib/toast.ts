"use client";

// Minimal toast bus. Anything in the app can call ``showToast(...)``
// and the <ToastHost> mounted in the root layout renders it. We don't
// need a proper notification queue — the app only uses toasts for
// transient feedback ("Added to compare", "Tray full") so a single
// in-flight slot is enough. A second toast within the window cancels
// the first, which is exactly what users expect when they're clicking
// fast.

export interface Toast {
  id: number;
  title: string;
  body?: string;
  // 0 = neutral (default), 1 = positive, -1 = warning.
  tone?: -1 | 0 | 1;
  durationMs?: number;
}

const EVENT = "agenttape:toast";

export function showToast(t: Omit<Toast, "id">): void {
  if (typeof window === "undefined") return;
  const toast: Toast = { ...t, id: Date.now() + Math.random() };
  window.dispatchEvent(new CustomEvent<Toast>(EVENT, { detail: toast }));
}

// Subscribe — used by ToastHost. Returns a cleanup.
export function subscribeToToasts(
  listener: (t: Toast) => void,
): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = (e: Event) => listener((e as CustomEvent<Toast>).detail);
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
