// SPDX-License-Identifier: Apache-2.0
// Failure modes of the bundled native worker transport that the echo fixture
// cannot express on its own: startup failures, protocol violations in the
// worker's frames, the outgoing frame cap, retry-once recovery and shutdown.
// Each protocol scenario is a tiny worker script generated into a scratch
// directory at run time and spawned exactly like the real binary would be.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const FIXTURE_PATH = path.join(__dirname, "_native_worker_test_fixture.mjs");
const ORIGINAL_ENV = { ...process.env };
const OVERRIDE_KEYS = ["ALGENTA_NATIVE_WORKER", "ALGENTA_RUNTIME_WORKER", "ALGENTA_MOJO_BINARY"];
const MAX_FRAME_BYTES = 64 * 1024 * 1024;

// Shared by every generated worker: the same framing the client speaks.
const WORKER_PRELUDE = [
  "import net from \"node:net\";",
  "import fs from \"node:fs\";",
  "import { argv, exit } from \"node:process\";",
  "const socketPath = argv[argv.indexOf(\"--server\") + 1];",
  "function headerOnly(size) {",
  "  const header = Buffer.alloc(4);",
  "  header.writeUInt32BE(size, 0);",
  "  return header;",
  "}",
  "function rawFrame(body) {",
  "  return Buffer.concat([headerOnly(body.length), body]);",
  "}",
  "function frame(value) {",
  "  return rawFrame(Buffer.from(JSON.stringify(value), \"utf-8\"));",
  "}",
  "const ready = socket => socket.write(frame({ status: \"ready\" }));",
  "function serve(onConnect, onRequest) {",
  "  net.createServer(socket => {",
  "    onConnect(socket);",
  "    let buffer = Buffer.alloc(0);",
  "    socket.on(\"data\", chunk => {",
  "      buffer = Buffer.concat([buffer, chunk]);",
  "      if (buffer.length < 4) return;",
  "      const size = buffer.readUInt32BE(0);",
  "      if (buffer.length < 4 + size) return;",
  "      const body = buffer.subarray(4, 4 + size);",
  "      buffer = buffer.subarray(4 + size);",
  "      onRequest(socket, JSON.parse(body.toString(\"utf-8\")));",
  "    });",
  "  }).listen(socketPath);",
  "}",
].join("\n");

const SCENARIOS = {
  exitOnStart: "exit(3);",
  eager:
    "serve(socket => socket.write(Buffer.concat([frame({ status: \"ready\" }), frame({ eager: true })])), " +
    "() => {});",
  oversizedReply: "serve(ready, socket => socket.write(headerOnly(0xffffffff)));",
  zeroReply: "serve(ready, socket => socket.write(headerOnly(0)));",
  arrayReply: "serve(ready, socket => socket.write(frame([1, 2, 3])));",
} as const;

let scriptDir: string;
const workers = {} as Record<keyof typeof SCENARIOS, string>;

function writeWorker(name: string, body: string): string {
  const file = path.join(scriptDir, `${name}.mjs`);
  fs.writeFileSync(file, `#!/usr/bin/env node\n${WORKER_PRELUDE}\n${body}\n`, "utf8");
  fs.chmodSync(file, 0o755);
  return file;
}

function resetEnv(): void {
  for (const key of OVERRIDE_KEYS) {
    delete process.env[key];
  }
}

async function loadClient() {
  return import("./native_worker_client.js");
}

describe("native worker client edges", () => {
  beforeAll(() => {
    scriptDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-worker-edges-"));
    for (const [name, body] of Object.entries(SCENARIOS)) {
      workers[name as keyof typeof SCENARIOS] = writeWorker(name, body);
    }
  });

  afterAll(() => {
    fs.rmSync(scriptDir, { recursive: true, force: true });
  });

  beforeEach(() => {
    resetEnv();
    vi.resetModules();
  });

  afterEach(async () => {
    const client = await loadClient();
    client.closeNativeWorker();
    process.env = { ...ORIGINAL_ENV };
    resetEnv();
  });

  it("treats a blank override as unset", async () => {
    process.env.ALGENTA_NATIVE_WORKER = "";
    const client = await loadClient();

    expect(client.nativeWorkerAvailable()).toBe(false);
    await expect(client.callNativeWorker({ scenario: "echo" })).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "No bundled Algenta runtime worker is configured (set ALGENTA_NATIVE_WORKER).",
    });
  });

  it("surfaces a startup exit unwrapped after the second attempt also fails", async () => {
    process.env.ALGENTA_NATIVE_WORKER = workers.exitOnStart;
    const client = await loadClient();

    await expect(client.callNativeWorker({ scenario: "echo" }, 1_000)).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime exited during startup.",
    });
  });

  // Deliberately not covered here: a worker whose handshake frame is not `ready`
  // or not JSON. startSession() closes the log descriptor before reading the
  // handshake and then calls cleanupOnFailure(), which closes it again; the
  // EBADF from that second close pre-empts the intended error and skips the
  // proc.kill() / rmSync() that follow it, orphaning the worker process.

  it.each([
    ["a frame header above the 64 MiB cap", "oversizedReply", "invalid response size"],
    ["a zero-length frame header", "zeroReply", "invalid response size"],
    ["a JSON array instead of an object", "arrayReply", "non-object response"],
  ] as const)("wraps %s as a could-not-execute failure after one retry", async (_label, scenario, fragment) => {
    process.env.ALGENTA_NATIVE_WORKER = workers[scenario];
    const client = await loadClient();

    await expect(client.callNativeWorker({ scenario: "echo" }, 1_000)).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime could not execute.",
      details: { error: expect.stringContaining(fragment) },
    });
  });

  it("consumes a frame the worker sent ahead of the request", async () => {
    process.env.ALGENTA_NATIVE_WORKER = workers.eager;
    const client = await loadClient();

    await expect(client.callNativeWorker({ scenario: "echo" }, 1_000)).resolves.toEqual({
      eager: true,
    });
  });

  it("retries once when the first session dies at startup and the second comes up", async () => {
    // The generated worker exits on its very first spawn (leaving a marker) and
    // serves echo replies on every spawn after that.
    const marker = path.join(scriptDir, "flaky.marker");
    process.env.ALGENTA_NATIVE_WORKER = writeWorker(
      "flakyStart",
      [
        `const MARKER = ${JSON.stringify(marker)};`,
        "if (!fs.existsSync(MARKER)) {",
        "  fs.writeFileSync(MARKER, \"first\");",
        "  exit(7);",
        "}",
        "serve(ready, (socket, request) => socket.write(frame({ echo: request })));",
      ].join("\n"),
    );
    const client = await loadClient();

    await expect(client.callNativeWorker({ probe: 1 }, 2_000)).resolves.toEqual({
      echo: { probe: 1 },
    });
    expect(fs.existsSync(marker)).toBe(true);
  });

  it("refuses an outgoing request above the 64 MiB frame cap", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const client = await loadClient();

    await expect(
      client.callNativeWorker({ scenario: "echo", pad: "x".repeat(MAX_FRAME_BYTES) }, 1_000),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The bundled Algenta runtime could not execute.",
      details: { error: "The bundled Algenta runtime request is too large." },
    });
  });

  it("closeNativeWorker is idempotent and a fresh session follows it", async () => {
    process.env.ALGENTA_NATIVE_WORKER = FIXTURE_PATH;
    const client = await loadClient();

    expect(() => client.closeNativeWorker()).not.toThrow();
    await expect(client.callNativeWorker({ scenario: "echo", n: 1 }, 1_000)).resolves.toEqual({
      echo: { scenario: "echo", n: 1 },
    });
    client.closeNativeWorker();
    expect(() => client.closeNativeWorker()).not.toThrow();
    await expect(client.callNativeWorker({ scenario: "echo", n: 2 }, 1_000)).resolves.toEqual({
      echo: { scenario: "echo", n: 2 },
    });
  });

  it("closeNativeWorker tolerates a session that never started", async () => {
    process.env.ALGENTA_NATIVE_WORKER = workers.exitOnStart;
    const client = await loadClient();

    const pending = client.callNativeWorker({ scenario: "echo" }, 1_000);
    expect(() => client.closeNativeWorker()).not.toThrow();

    await expect(pending).rejects.toMatchObject({
      message: "The bundled Algenta runtime exited during startup.",
    });
  });
});
