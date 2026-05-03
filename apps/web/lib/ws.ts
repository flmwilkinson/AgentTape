"use client";

// Minimal WS hook.
//
// Connects to a single channel, surfaces the snapshot frame separately
// from the event stream, and reconnects with a small backoff. The
// realtime service sends one of four frame types
// (snapshot/event/heartbeat/warning) — we route them all through onFrame
// and let the consumer decide what to do.

import { useEffect, useRef, useState } from "react";

const WS_BASE = process.env.NEXT_PUBLIC_REALTIME_URL ?? "ws://localhost:8002";

export type WsFrame =
  | { type: "snapshot"; scope: string; [k: string]: unknown }
  | { type: "event"; channel: string; event: Record<string, unknown> }
  | { type: "heartbeat" }
  | { type: "warning"; reason: string; detail: string };

export interface UseWsOptions {
  // Path on the realtime service. e.g. "/ws/ticker", "/ws/agent/foo".
  path: string;
  // Called with every frame the server sends.
  onFrame?: (frame: WsFrame) => void;
  // Disable connection (e.g. while a slug is undefined).
  enabled?: boolean;
}

export function useWebSocket({ path, onFrame, enabled = true }: UseWsOptions) {
  const [snapshot, setSnapshot] = useState<WsFrame | null>(null);
  const [connected, setConnected] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  useEffect(() => {
    if (!enabled) return;
    let socket: WebSocket | null = null;
    let attempts = 0;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (stopped) return;
      socket = new WebSocket(`${WS_BASE}${path}`);
      socket.onopen = () => {
        attempts = 0;
        setConnected(true);
      };
      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        // Exponential-ish backoff, cap at 8s.
        const delay = Math.min(8000, 500 * Math.pow(1.6, attempts));
        attempts += 1;
        timer = setTimeout(connect, delay);
      };
      socket.onerror = () => socket?.close();
      socket.onmessage = (ev) => {
        let frame: WsFrame;
        try {
          frame = JSON.parse(ev.data) as WsFrame;
        } catch {
          return;
        }
        if (frame.type === "snapshot") setSnapshot(frame);
        if (frame.type === "warning") setWarning(frame.detail);
        onFrameRef.current?.(frame);
      };
    }

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [path, enabled]);

  return { snapshot, connected, warning };
}
