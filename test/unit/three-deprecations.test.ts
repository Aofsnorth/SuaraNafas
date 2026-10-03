import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { installThreeDeprecationFilter } from "@/lib/three-deprecations";

const CLOCK_DEPRECATION =
  "THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.";

describe("installThreeDeprecationFilter", () => {
  const originalWarn = console.warn;

  beforeEach(() => {
    console.warn = vi.fn();
  });

  afterEach(() => {
    console.warn = originalWarn;
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("drops the upstream Clock deprecation and nothing else", () => {
    const spy = vi.fn();
    console.warn = spy;

    installThreeDeprecationFilter();

    console.warn(CLOCK_DEPRECATION);
    console.warn("WebGL context lost");

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith("WebGL context lost");
  });

  it("only matches the whole first argument", () => {
    const spy = vi.fn();
    console.warn = spy;

    installThreeDeprecationFilter();

    console.warn(`scene: ${CLOCK_DEPRECATION}`);
    console.warn(undefined, CLOCK_DEPRECATION);

    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("does not wrap console.warn twice", () => {
    installThreeDeprecationFilter();
    const afterFirstInstall = console.warn;

    installThreeDeprecationFilter();

    expect(console.warn).toBe(afterFirstInstall);
  });

  it("leaves the console untouched in production", () => {
    vi.stubEnv("NODE_ENV", "production");

    installThreeDeprecationFilter();

    console.warn(CLOCK_DEPRECATION);

    expect(console.warn).toHaveBeenCalledWith(CLOCK_DEPRECATION);
  });
});