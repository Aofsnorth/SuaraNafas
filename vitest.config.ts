import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const projectRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(projectRoot, "src"),
    },
  },
  test: {
    // Tests live under the project's tests/ directory, mirroring the rule that
    // test files never sit beside the source they cover.
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});