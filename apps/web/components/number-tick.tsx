"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

// A number that animates between values + pulses the cell background
// in gain or loss color when it changes. Mounted once at the cell
// where the number appears; use a stable ``id`` if you want pulses
// only when this *specific* metric changes (rather than on remount).

interface Props {
  value: number | null | undefined;
  format: (v: number | null | undefined) => string;
  className?: string;
  // Suppress animation on first mount so a freshly-loaded page doesn't
  // pulse every cell at once.
  animateOnMount?: boolean;
}

export function NumberTick({
  value,
  format,
  className,
  animateOnMount = false,
}: Props) {
  const prevRef = useRef<number | null | undefined>(undefined);
  const [pulse, setPulse] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    const cur = value;
    const isFirst = prev === undefined;
    prevRef.current = cur;

    if (cur === null || cur === undefined) return;
    if (isFirst && !animateOnMount) return;

    if (typeof prev === "number" && prev !== cur) {
      setPulse(cur > prev ? "up" : "down");
      const t = setTimeout(() => setPulse(null), 700);
      return () => clearTimeout(t);
    }
  }, [value, animateOnMount]);

  return (
    <span
      data-pulse={pulse ?? undefined}
      className={cn("num inline-block transition-colors", className)}
    >
      {format(value)}
    </span>
  );
}
