import assert from "node:assert/strict";
import test from "node:test";

import { acquireSSESlot, checkRateLimit, sseConnectionLimit } from "../src/ratelimit.js";

test("Algenta plans have no request-rate meter", async () => {
  for (const plan of ["algenta_free", "algenta_pro", "algenta_team", "enterprise"]) {
    assert.deepEqual(await checkRateLimit("org-unmetered", plan), {
      allowed: true,
      remaining: -1,
      limit: 0,
    });
  }
});

test("Enterprise streams have no plan rate or connection meter", async () => {
  assert.deepEqual(await acquireSSESlot("org-enterprise", "enterprise"), {
    allowed: true,
    current: 0,
    limit: 0,
  });
});

test("Algenta stream concurrency matches licensed workers per device", () => {
  assert.equal(sseConnectionLimit("algenta_free"), 1);
  assert.equal(sseConnectionLimit("algenta_pro"), 5);
  assert.equal(sseConnectionLimit("algenta_team"), 20);
  assert.equal(sseConnectionLimit("enterprise"), 0);
});
