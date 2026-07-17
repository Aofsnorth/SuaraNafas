"use client";

import { useSyncExternalStore } from "react";

function getMediaQueryList() {
  if (typeof window === "undefined") return null;
  return window.matchMedia("(prefers-reduced-motion: reduce)");
}

function subscribe(callback: () => void) {
  const mql = getMediaQueryList();
  if (!mql) return () => {};
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}

function getSnapshot() {
  const mql = getMediaQueryList();
  return mql?.matches ?? false;
}

function getServerSnapshot() {
  return false;
}

export function useReducedMotion() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
