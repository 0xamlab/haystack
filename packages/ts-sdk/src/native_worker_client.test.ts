// SPDX-License-Identifier: Apache-2.0
import { fileURLToPath } from "node:url";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FIXTURE_PATH = fileURLToPath(
  new URL("./_native_worker_test_fixture.mjs", import.meta.url),
);

const ORIGINAL_ENV = { ...process.env };

function resetEnv() {
  for (const key of ["ALGENTA_NATIVE_WORKER", "ALGENTA_RUNTIME_WORKER", "ALGENTA_MOJO_BINARY"]) {
    delete process.env[key];
  }
}

describe("native worker client", () => {
  beforeEach(() => {
    resetEnv();
    vi.resetModules();
  });

  afterEach(async () => {
    const mod = await import("./native_worker_client.js");
    mod.closeNativeWorker();
    process.env = { ...ORIGINAL_ENV };
    resetEnv();
  });

  it("nativeWorkerAvailable is false with no override set", async () => {
    const mod = await import("./native_worker_client.js");
    expect(mod.nativeWorkerAvailable()).toBe(false);
  });

  it("nativeWorkerAvailable is true once ALGENTA_NATIVE_WORKER is set", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    expect(mod.nativeWorkerAvailable()).toBe(true);
  });

  it("falls back through the legacy override names in order", async () => {
    process.env.ALGENTA_MOJO_BINARY = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    expect(mod.nativeWorkerAvailable()).toBe(true);
    const response = await mod.callNativeWorker({ scenario: "echo", probe: 1 });
    expect(response).toEqual({ echo: { scenario: "echo", probe: 1 } });
  });

  it("spawns the worker, completes the ready handshake, and round-trips a request", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    const response = await mod.callNativeWorker({
      scenario: "echo",
      type: "query_execute",
      columns: ["a"],
    });
    expect(response).toEqual({
      echo: { scenario: "echo", type: "query_execute", columns: ["a"] },
    });
  });

  it("reuses one spawned session across multiple calls", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    const first = await mod.callNativeWorker({ scenario: "echo", n: 1 });
    const second = await mod.callNativeWorker({ scenario: "echo", n: 2 });
    expect(first).toEqual({ echo: { scenario: "echo", n: 1 } });
    expect(second).toEqual({ echo: { scenario: "echo", n: 2 } });
  });

  it("throws when the worker returns a malformed frame", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    await expect(mod.callNativeWorker({ scenario: "malformed" })).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
    });
  });

  it("retries once on timeout, then throws wrapping the original timeout message", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    // Both attempts hit the same slow fixture, so this exercises the retry-once
    // path end to end, not just a single failure -- matching the Python SDK worker's
    // own `execute`, which never surfaces attempt 1's raw error directly.
    await expect(
      mod.callNativeWorker({ scenario: "slow" }, 200),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime could not execute.",
      details: { error: expect.stringContaining("did not respond in time") },
    });
  });

  it("throws when the worker process exits mid-request", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    await expect(mod.callNativeWorker({ scenario: "crash" })).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
    });
  });

  it("throws a clear error when no override is configured at all", async () => {
    const mod = await import("./native_worker_client.js");
    await expect(mod.callNativeWorker({ scenario: "echo" })).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: expect.stringContaining("ALGENTA_NATIVE_WORKER"),
    });
  });

  it("handles a response spanning multiple socket data events (a large row set)", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const mod = await import("./native_worker_client.js");
    const response = await mod.callNativeWorker({ scenario: "big", rows: 50_000 });
    const result = response.result as { columns: string[]; rows: number[][] };
    expect(result.columns).toEqual(["a", "b", "c", "d", "e"]);
    expect(result.rows).toHaveLength(50_000);
    expect(result.rows[0]).toEqual([1, 2, 3, 4, 5]);
  });
});
