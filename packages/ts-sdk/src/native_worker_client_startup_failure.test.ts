// SPDX-License-Identifier: Apache-2.0
// Startup-failure cleanup for the bundled native worker client.
//
// `startSession` closes the parent's copy of the worker's log descriptor once the socket has
// connected, and then, if the ready handshake is not a `{"status":"ready"}` frame, calls
// `cleanupOnFailure()`. That helper used to begin with a second, unconditional close of the
// same descriptor, which threw `EBADF` -- so the worker was never killed, the
// `algenta-runtime-*` temp dir was never removed, and the caller saw a bare `Error: EBADF`
// instead of the typed `MojoRuntimeConfigurationError`. These tests drive both startup-failure
// paths through a fixture that misbehaves at the handshake and assert, from the fixture's own
// record of what was spawned, that every worker is gone and every temp dir is removed.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const FIXTURE_PATH = fileURLToPath(
  new URL("./_native_worker_startup_failure_fixture.mjs", import.meta.url),
);

// `os.tmpdir()` reads the REAL process environment, not the `process.env` object, so the
// override below must be written through the env-backed `process.env` -- which is why this
// file restores TMPDIR in place in `afterEach` instead of reassigning `process.env` wholesale
// (a reassignment swaps in a plain object whose later writes never reach the real environment).
const ORIGINAL_TMPDIR = process.env.TMPDIR;
const HOST_TMPDIR = os.tmpdir();
const PROCESS_GONE_TIMEOUT_MS = 2_000;
const PROCESS_GONE_POLL_MS = 20;
const RUNTIME_DIR_PREFIX = "algenta-runtime-";

interface SpawnRecord {
  pid: number;
  socketPath: string;
}

// A private tmp root per test: `startSession` builds its temp dir under `os.tmpdir()`, which
// honours TMPDIR, so pointing TMPDIR here makes "no algenta-runtime-* dir remains in the tmp
// root the client used" checkable without other test files' concurrent workers interfering.
let tmpRoot: string;
let recordPath: string;

function resetEnv() {
  for (const key of [
    "ALGENTA_NATIVE_WORKER",
    "ALGENTA_RUNTIME_WORKER",
    "ALGENTA_MOJO_BINARY",
    "ALGENTA_TEST_STARTUP_HANDSHAKE",
    "ALGENTA_TEST_STARTUP_RECORD",
  ]) {
    delete process.env[key];
  }
}

function readSpawnRecords(): SpawnRecord[] {
  if (!fs.existsSync(recordPath)) return [];
  return fs
    .readFileSync(recordPath, "utf-8")
    .split("\n")
    .filter(line => line.length > 0)
    .map(line => JSON.parse(line) as SpawnRecord);
}

function processAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code !== "ESRCH";
  }
}

async function waitForProcessGone(pid: number): Promise<boolean> {
  const deadline = Date.now() + PROCESS_GONE_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (!processAlive(pid)) return true;
    await new Promise(resolve => setTimeout(resolve, PROCESS_GONE_POLL_MS));
  }
  return !processAlive(pid);
}

function runtimeDirsIn(root: string): string[] {
  return fs.readdirSync(root).filter(name => name.startsWith(RUNTIME_DIR_PREFIX));
}

async function expectEveryWorkerCleanedUp(): Promise<void> {
  const records = readSpawnRecords();
  // The fixture records each process the client spawned; the client retries startup once,
  // so there is at least one, and every one of them must have been cleaned up.
  expect(records.length).toBeGreaterThan(0);
  for (const record of records) {
    expect(await waitForProcessGone(record.pid)).toBe(true);
    const tempDir = path.dirname(record.socketPath);
    expect(path.basename(tempDir).startsWith(RUNTIME_DIR_PREFIX)).toBe(true);
    expect(path.dirname(tempDir)).toBe(tmpRoot);
    expect(fs.existsSync(tempDir)).toBe(false);
  }
  expect(runtimeDirsIn(tmpRoot)).toEqual([]);
}

async function startupFailure(handshake: string): Promise<unknown> {
  process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
  process.env.ALGENTA_TEST_STARTUP_HANDSHAKE = handshake;
  process.env.ALGENTA_TEST_STARTUP_RECORD = recordPath;
  const mod = await import("./native_worker_client.js");
  try {
    await mod.callNativeWorker({}, 1000);
  } catch (error) {
    return error;
  }
  throw new Error("callNativeWorker resolved against a worker that never became ready");
}

describe("native worker client startup failures", () => {
  beforeEach(() => {
    resetEnv();
    vi.resetModules();
    // A SHORT prefix on purpose: the worker's Unix socket lives at
    // <tmpRoot>/algenta-runtime-XXXXXX/worker.sock, and a Unix socket path is capped at 104
    // bytes on macOS (108 on Linux). macOS's per-user TMPDIR is already ~50 bytes, so a long
    // prefix here pushes the path over the cap, `listen()` fails inside the fixture, and the
    // client reports "exited during startup" instead of exercising the handshake path.
    tmpRoot = fs.mkdtempSync(path.join(HOST_TMPDIR, "nwc-"));
    recordPath = path.join(tmpRoot, "spawned.jsonl");
    process.env.TMPDIR = tmpRoot;
    expect(os.tmpdir()).toBe(tmpRoot);
  });

  afterEach(async () => {
    const mod = await import("./native_worker_client.js");
    mod.closeNativeWorker();
    // Belt and braces: never leave a fixture process behind if an assertion above failed.
    for (const record of readSpawnRecords()) {
      try {
        process.kill(record.pid, "SIGKILL");
      } catch {
        // already gone -- the expected case
      }
    }
    fs.rmSync(tmpRoot, { recursive: true, force: true });
    if (ORIGINAL_TMPDIR === undefined) {
      delete process.env.TMPDIR;
    } else {
      process.env.TMPDIR = ORIGINAL_TMPDIR;
    }
    resetEnv();
  });

  it("a non-ready handshake surfaces the typed startup error and cleans up the worker", async () => {
    const errors = await import("./mojo_errors.js");
    const failure = await startupFailure("not-ready");
    expect(failure).toBeInstanceOf(errors.MojoRuntimeConfigurationError);
    expect(failure).toMatchObject({
      name: "MojoRuntimeConfigurationError",
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime returned an invalid startup response.",
    });
    expect(String((failure as Error).message)).not.toContain("EBADF");
    await expectEveryWorkerCleanedUp();
  });

  it("an invalid first frame surfaces the typed decode error and cleans up the worker", async () => {
    const errors = await import("./mojo_errors.js");
    const failure = await startupFailure("invalid-output");
    expect(failure).toBeInstanceOf(errors.MojoRuntimeConfigurationError);
    expect(failure).toMatchObject({
      name: "MojoRuntimeConfigurationError",
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime returned invalid output.",
    });
    expect(String((failure as Error).message)).not.toContain("EBADF");
    await expectEveryWorkerCleanedUp();
  });
});
