import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      // Source files only: dist/** is the tsc build output and is exercised by
      // the dist-artifact tests, but tracking it would double-count every line.
      include: ["src/**/*.ts"],
      reporter: ["text", "lcov"],
      // Floors sit 2 points below the values measured when this config was
      // introduced (78.4% statements, 63.7% branches, 84.7% functions, 79.3%
      // lines). Raise them as coverage improves; never lower them.
      thresholds: {
        statements: 76,
        branches: 61,
        functions: 82,
        lines: 77,
      },
    },
  },
});
