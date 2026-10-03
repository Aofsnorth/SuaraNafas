/**
 * Dev-only filter for a single upstream deprecation we cannot fix here.
 *
 * three.js r183 deprecated `THREE.Clock` in favour of `THREE.Timer`, but
 * @react-three/fiber still builds one internally when it creates a store
 * (`clock: new THREE.Clock()`). This app never constructs a Clock itself, and
 * upgrading does not remove it — r3f 9.8.1, the newest 9.x, has the same line —
 * so there is no application-level call site to change.
 *
 * The notice is cosmetic: the class still works, and three.js prints it once per
 * session. Only that exact string is dropped; every other warning still reaches
 * the console. Delete this file and its single call site once @react-three/fiber
 * moves to THREE.Timer.
 */

const SILENCED = [
  "THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.",
] as const;

export function installThreeDeprecationFilter(): void {
  if (process.env.NODE_ENV === "production") return;
  if (typeof console === "undefined" || typeof console.warn !== "function") return;

  const currentWarn = console.warn as { __threeDeprecationFilter?: boolean };
  if (currentWarn.__threeDeprecationFilter) return;

  const originalWarn = console.warn.bind(console);

  const filteredWarn = (...args: unknown[]) => {
    const first = typeof args[0] === "string" ? args[0] : "";
    if ((SILENCED as readonly string[]).includes(first)) return;
    originalWarn(...args);
  };
  (filteredWarn as { __threeDeprecationFilter?: boolean }).__threeDeprecationFilter = true;

  console.warn = filteredWarn;
}