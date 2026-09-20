import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      // Source files only: dist/** is the tsc build output and is exercised by
      // the dist-artifact tests, but tracking it would double-count every line.
      include: ["src/**/*.ts"],
      reporter: ["text", "lcov"],
      // Floors sit 2 points below the values measured by `npm run test:coverage`
      // when they were last raised (99.4% statements, 97.9% branches, 99.2%
      // functions, 99.5% lines). Raise them as coverage improves; never lower them.
      thresholds: {
        statements: 97,
        branches: 95,
        functions: 97,
        lines: 97,
      },
    },
  },
});
