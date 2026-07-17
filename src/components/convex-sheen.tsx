"use client";

import { useEffect, useRef, type PointerEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ConvexSheenProps {
  children: ReactNode;
  className?: string;
}

export function ConvexSheen({ children, className }: ConvexSheenProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);

  const resetPosition = () => {
    const root = rootRef.current;

    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }

    if (!root) return;
    root.dataset.active = "false";
  };

  const updatePosition = (event: PointerEvent<HTMLDivElement>) => {
    const root = rootRef.current;
    if (
      !root ||
      !window.matchMedia("(hover: hover) and (pointer: fine)").matches ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      resetPosition();
      return;
    }

    const rect = root.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;

    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current);
    }

    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;

      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        root.dataset.active = "false";
        return;
      }

      root.style.setProperty("--sheen-x", `${x}%`);
      root.style.setProperty("--sheen-y", `${y}%`);
      root.dataset.active = "true";
    });
  };

  useEffect(() => {
    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className={cn("convex-sheen", className)}
      onPointerMove={updatePosition}
      onPointerLeave={resetPosition}
      onPointerCancel={resetPosition}
    >
      {children}
    </div>
  );
}
