// SPDX-License-Identifier: Apache-2.0
/**
 * A direct, in-process-spawned connection to the bundled Algenta native runtime worker --
 * the same binary and the same wire protocol the Python SDK already uses, so a TypeScript
 * caller with that binary available needs no separately started daemon and no gRPC hop.
 *
 * Wire protocol (byte-for-byte the engine's native worker protocol):
 *   - a Unix domain socket, one connection per worker process
 *   - on connect, the worker sends one frame: {"status":"ready"}
 *   - request/response: [4-byte big-endian uint32 length][UTF-8 JSON payload]
 *   - 64 MiB frame cap, enforced both directions
 *
 * Binary resolution mirrors the Python SDK's own override chain, using the SAME environment
 * variable names on purpose -- a path that already works for Python on this machine works
 * for TypeScript with zero additional configuration:
 *   ALGENTA_NATIVE_WORKER, then the legacy ALGENTA_RUNTIME_WORKER, then ALGENTA_MOJO_BINARY.
 *
 * What this deliberately does NOT do yet: locate a binary with no environment variable set
 * at all. Until such packaging exists, `MojoRuntime` falls back to the gRPC daemon
 * transport whenever no override is set, so nothing about existing behavior changes.
 */
import { spawn, type ChildProcess } from "node:child_process";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs";

import { MojoRuntimeConfigurationError } from "./mojo_errors.js";

const MAX_FRAME_BYTES = 64 * 1024 * 1024;
const STARTUP_TIMEOUT_MS = 30_000;
const CONNECT_POLL_INTERVAL_MS = 10;

function resolveNativeWorkerPath(): string | null {
  const override =
    process.env.ALGENTA_NATIVE_WORKER ||
    process.env.ALGENTA_RUNTIME_WORKER ||
    process.env.ALGENTA_MOJO_BINARY;
  if (!override) {
    return null;
  }
  return override;
}

/** True the moment a caller could plausibly reach the native worker -- i.e. one of the
 * override environment variables is set. Cheap and synchronous, so `MojoRuntime` can
 * decide which transport to use without an async probe on every call. */
export function nativeWorkerAvailable(): boolean {
  return resolveNativeWorkerPath() !== null;
}

function sendFrame(socket: net.Socket, request: Record<string, unknown>): void {
  const payload = Buffer.from(JSON.stringify(request), "utf-8");
  if (payload.length === 0 || payload.length > MAX_FRAME_BYTES) {
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "The bundled Algenta runtime request is too large.",
    );
  }
  const header = Buffer.alloc(4);
  header.writeUInt32BE(payload.length, 0);
  socket.write(Buffer.concat([header, payload]));
}

/** Reads exactly one frame off `socket`, buffering across as many `data` events as it
 * takes. Node delivers TCP/Unix-socket bytes as they arrive, not message-aligned, so a
 * single frame can span multiple `data` events and a single `data` event can contain
 * more than one frame's worth of bytes -- this drains only what the current frame
 * needs and leaves the remainder for the next call via `leftover`. */
function recvFrame(
  socket: net.Socket,
  leftover: Buffer,
  timeoutMs: number,
): Promise<{ frame: Record<string, unknown>; rest: Buffer }> {
  return new Promise((resolve, reject) => {
    let buffer = leftover;
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      socket.removeListener("data", onData);
      socket.removeListener("error", onError);
      socket.removeListener("close", onClose);
      clearTimeout(timer);
      fn();
    };

    const tryParse = () => {
      if (buffer.length < 4) return false;
      const frameSize = buffer.readUInt32BE(0);
      if (frameSize <= 0 || frameSize > MAX_FRAME_BYTES) {
        finish(() =>
          reject(
            new MojoRuntimeConfigurationError(
              "compute_runtime_unavailable",
              "The bundled Algenta runtime returned an invalid response size.",
            ),
          ),
        );
        return true;
      }
      if (buffer.length < 4 + frameSize) return false;
      const body = buffer.subarray(4, 4 + frameSize);
      const rest = buffer.subarray(4 + frameSize);
      let parsed: unknown;
      try {
        parsed = JSON.parse(body.toString("utf-8"));
      } catch (error) {
        finish(() =>
          reject(
            new MojoRuntimeConfigurationError(
              "compute_runtime_unavailable",
              "The bundled Algenta runtime returned invalid output.",
              { error: error instanceof Error ? error.message : String(error) },
            ),
          ),
        );
        return true;
      }
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        finish(() =>
          reject(
            new MojoRuntimeConfigurationError(
              "compute_runtime_unavailable",
              "The bundled Algenta runtime returned a non-object response.",
            ),
          ),
        );
        return true;
      }
      finish(() => resolve({ frame: parsed as Record<string, unknown>, rest }));
      return true;
    };

    const onData = (chunk: Buffer) => {
      buffer = Buffer.concat([buffer, chunk]);
      tryParse();
    };
    const onError = (error: Error) => {
      finish(() =>
        reject(
          new MojoRuntimeConfigurationError("compute_runtime_unavailable", error.message),
        ),
      );
    };
    const onClose = () => {
      finish(() =>
        reject(
          new MojoRuntimeConfigurationError(
            "compute_runtime_unavailable",
            "The bundled Algenta runtime closed its connection unexpectedly.",
          ),
        ),
      );
    };

    const timer = setTimeout(() => {
      finish(() =>
        reject(
          new MojoRuntimeConfigurationError(
            "compute_runtime_unavailable",
            "The bundled Algenta runtime did not respond in time.",
          ),
        ),
      );
    }, timeoutMs);

    socket.on("data", onData);
    socket.on("error", onError);
    socket.on("close", onClose);
    if (!tryParse()) {
      // Nothing buffered yet; wait for `data`.
    }
  });
}

interface WorkerSession {
  proc: ChildProcess;
  socket: net.Socket;
  socketPath: string;
  tempDir: string;
  leftover: Buffer;
}

let sessionPromise: Promise<WorkerSession> | null = null;

async function startSession(workerPath: string): Promise<WorkerSession> {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-runtime-"));
  const socketPath = path.join(tempDir, "worker.sock");
  const logPath = path.join(tempDir, "worker.log");
  const logFd = fs.openSync(logPath, "w");

  const proc = spawn(workerPath, ["--server", socketPath], {
    stdio: ["ignore", logFd, logFd],
    detached: false,
  });

  // The parent's copy of the worker's log descriptor: the child holds its own duplicate, so
  // this one is needed only until `spawn` returns, and it must be closed exactly once. The
  // connect step below closes it as soon as the socket is up, and `cleanupOnFailure` used to
  // close it AGAIN unconditionally -- so every failed handshake threw EBADF out of the cleanup
  // itself, the worker was never killed, the temp dir was never removed, and the caller saw
  // `EBADF` instead of the typed error (or, had the descriptor number been reused meanwhile,
  // an unrelated descriptor would have been closed). One guarded close serves every path.
  let logFdOpen = true;
  const closeLogFd = () => {
    if (!logFdOpen) return;
    logFdOpen = false;
    fs.closeSync(logFd);
  };

  const cleanupOnFailure = () => {
    closeLogFd();
    try {
      if (proc.exitCode === null) proc.kill();
    } catch {
      // already gone
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  };

  let exited = false;
  proc.once("exit", () => {
    exited = true;
  });

  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let socket: net.Socket | null = null;
  while (Date.now() < deadline) {
    if (exited) {
      cleanupOnFailure();
      throw new MojoRuntimeConfigurationError(
        "compute_runtime_unavailable",
        "The bundled Algenta runtime exited during startup.",
      );
    }
    if (fs.existsSync(socketPath)) {
      try {
        socket = await new Promise<net.Socket>((resolve, reject) => {
          const candidate = net.createConnection({ path: socketPath });
          candidate.once("connect", () => resolve(candidate));
          candidate.once("error", reject);
        });
        break;
      } catch {
        // Not accepting connections yet; keep polling.
      }
    }
    await new Promise(r => setTimeout(r, CONNECT_POLL_INTERVAL_MS));
  }
  if (socket === null) {
    cleanupOnFailure();
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "The bundled Algenta runtime did not become ready.",
    );
  }

  closeLogFd();
  const remaining = Math.max(100, deadline - Date.now());
  let ready: { frame: Record<string, unknown>; rest: Buffer };
  try {
    ready = await recvFrame(socket, Buffer.alloc(0), remaining);
  } catch (error) {
    socket.destroy();
    cleanupOnFailure();
    throw error;
  }
  if (ready.frame.status !== "ready") {
    socket.destroy();
    cleanupOnFailure();
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "The bundled Algenta runtime returned an invalid startup response.",
    );
  }

  return { proc, socket, socketPath, tempDir, leftover: ready.rest };
}

function closeSession(session: WorkerSession): void {
  try {
    session.socket.destroy();
  } catch {
    // already closed
  }
  try {
    if (session.proc.exitCode === null) session.proc.kill();
  } catch {
    // already gone
  }
  fs.rmSync(session.tempDir, { recursive: true, force: true });
}

/** Send one request to the bundled native worker and return its response, spawning and
 * caching the worker process (one per Node process, reused across calls) the same way
 * Python's `_WorkerSession` does. Retries once on a transport failure, closing and
 * discarding the stale session first -- the same discipline the Python SDK's own worker
 * `execute` uses, since a worker that died between calls must not be trusted a second
 * time under the same connection. */
export async function callNativeWorker(
  request: Record<string, unknown>,
  timeoutMs: number = 30_000,
): Promise<Record<string, unknown>> {
  const workerPath = resolveNativeWorkerPath();
  if (workerPath === null) {
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "No bundled Algenta runtime worker is configured (set ALGENTA_NATIVE_WORKER).",
    );
  }

  for (let attempt = 0; attempt < 2; attempt++) {
    if (sessionPromise === null) {
      sessionPromise = startSession(workerPath);
    }
    let session: WorkerSession;
    try {
      session = await sessionPromise;
    } catch (error) {
      sessionPromise = null;
      if (attempt === 1) throw error;
      continue;
    }
    try {
      sendFrame(session.socket, request);
      const { frame, rest } = await recvFrame(session.socket, session.leftover, timeoutMs);
      session.leftover = rest;
      return frame;
    } catch (error) {
      closeSession(session);
      sessionPromise = null;
      if (attempt === 1) {
        throw new MojoRuntimeConfigurationError(
          "compute_runtime_unavailable",
          "The bundled Algenta runtime could not execute.",
          { error: error instanceof Error ? error.message : String(error) },
        );
      }
    }
  }
  throw new Error("unreachable");
}

/** Close and discard the cached worker session, if any. Exposed for tests and for a
 * caller that wants a clean process exit without an orphaned child. */
export function closeNativeWorker(): void {
  if (sessionPromise === null) return;
  sessionPromise
    .then(session => closeSession(session))
    .catch(() => {
      // Session never started; nothing to close.
    });
  sessionPromise = null;
}
