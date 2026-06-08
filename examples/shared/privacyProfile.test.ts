import assert from "node:assert/strict";
import test from "node:test";

import { resolveExampleApiKey, resolveExampleBaseUrl } from "./privacyProfile.ts";

test("resolveExampleBaseUrl defaults to the cloud-managed base URL", () => {
  assert.equal(
    resolveExampleBaseUrl({
      component: "TypeScript example test",
      env: {},
    }),
    "https://api.algenta.ai",
  );
});

test("resolveExampleBaseUrl rejects Algenta cloud in private profiles", () => {
  try {
    resolveExampleBaseUrl({
      component: "TypeScript example test",
      env: {
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
        ALGENTA_DISABLE_CLOUD: "1",
      },
    });
    assert.fail("expected private-profile base URL resolution to fail closed");
  } catch (error) {
    assert.match(String(error), /cannot target Algenta-owned cloud URLs/);
    assert.match(String(error), /ALGENTA_BASE_URL \/ DE_BASE_URL \/ ALGENTA_API_URL/);
  }
});

test("resolveExampleBaseUrl allows self-hosted targets in private profiles", () => {
  assert.equal(
    resolveExampleBaseUrl({
      component: "TypeScript example test",
      env: {
        ALGENTA_DEPLOYMENT_MODE: "air_gapped",
        ALGENTA_DISABLE_CLOUD: "1",
        ALGENTA_BASE_URL: "http://localhost:8000",
      },
    }),
    "http://localhost:8000",
  );
});

test("resolveExampleBaseUrl accepts DE_BASE_URL in private profiles", () => {
  assert.equal(
    resolveExampleBaseUrl({
      component: "TypeScript example test",
      env: {
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
        ALGENTA_DISABLE_CLOUD: "1",
        DE_BASE_URL: "http://localhost:8001",
      },
    }),
    "http://localhost:8001",
  );
});

test("resolveExampleBaseUrl accepts ALGENTA_API_URL in private profiles", () => {
  assert.equal(
    resolveExampleBaseUrl({
      component: "TypeScript example test",
      env: {
        ALGENTA_DEPLOYMENT_MODE: "self_hosted",
        ALGENTA_DISABLE_CLOUD: "1",
        ALGENTA_API_URL: "http://localhost:8002",
      },
    }),
    "http://localhost:8002",
  );
});

test("resolveExampleApiKey prefers ALGENTA_API_KEY over DE_API_KEY", () => {
  assert.equal(
    resolveExampleApiKey({
      component: "TypeScript example test",
      env: {
        ALGENTA_API_KEY: "algenta-key",
        DE_API_KEY: "legacy-key",
      },
    }),
    "algenta-key",
  );
});

test("resolveExampleApiKey accepts DE_API_KEY when ALGENTA_API_KEY is absent", () => {
  assert.equal(
    resolveExampleApiKey({
      component: "TypeScript example test",
      env: {
        DE_API_KEY: "legacy-key",
      },
    }),
    "legacy-key",
  );
});

test("resolveExampleApiKey fails closed when no API key is configured", () => {
  assert.throws(
    () =>
      resolveExampleApiKey({
        component: "TypeScript example test",
        env: {},
      }),
    /ALGENTA_API_KEY or DE_API_KEY/,
  );
});
