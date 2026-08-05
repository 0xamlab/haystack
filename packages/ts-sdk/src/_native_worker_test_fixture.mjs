#!/usr/bin/env node
// A minimal stand-in for the compiled Algenta native worker binary, speaking the exact
// same wire protocol `native_worker_client.ts` expects: a Unix socket at the path given
// via `--server <path>`, a `{"status":"ready"}` handshake frame on connect, then one
// framed JSON response per framed JSON request. Spawned directly by the tests below via
// `ALGENTA_NATIVE_WORKER` pointed at this file (its shebang makes it directly
// executable) -- no real Mojo binary needed for CI.
//
// Behavior is driven by the FIRST request's own "scenario" field, so one fixture script
// covers every test case:
//   "echo"        -- responds with {"echo": <the request>}
//   "slow"        -- waits SLOW_SCENARIO_DELAY_MS before responding, for timeout tests
//   "malformed"   -- writes a frame whose body is not valid JSON
//   "crash"       -- exits immediately after the ready handshake, before any request
//   "big"         -- responds with a payload of `rows` copies of a fixed row (size tests)
import net from "node:net";
import { argv, exit } from "node:process";

const serverIndex = argv.indexOf("--server");
const socketPath = argv[serverIndex + 1];
// Longer than any test's own `timeoutMs` argument to `callNativeWorker`, so the
// "slow" scenario reliably triggers a timeout rather than racing it.
const SLOW_SCENARIO_DELAY_MS = 2000;

function sendFrame(socket, obj) {
  const payload = Buffer.from(JSON.stringify(obj), "utf-8");
  const header = Buffer.alloc(4);
  header.writeUInt32BE(payload.length, 0);
  socket.write(Buffer.concat([header, payload]));
}

function sendRawFrame(socket, bodyBuffer) {
  const header = Buffer.alloc(4);
  header.writeUInt32BE(bodyBuffer.length, 0);
  socket.write(Buffer.concat([header, bodyBuffer]));
}

const server = net.createServer(socket => {
  let buffer = Buffer.alloc(0);
  sendFrame(socket, { status: "ready" });

  socket.on("data", chunk => {
    buffer = Buffer.concat([buffer, chunk]);
    if (buffer.length < 4) return;
    const size = buffer.readUInt32BE(0);
    if (buffer.length < 4 + size) return;
    const body = buffer.subarray(4, 4 + size);
    buffer = buffer.subarray(4 + size);
    const request = JSON.parse(body.toString("utf-8"));
    const scenario = request.scenario ?? "echo";

    if (scenario === "crash") {
      exit(1);
    } else if (scenario === "slow") {
      // A fixed constant, not `request.delayMs`: no test needs a configurable delay
      // (every "slow" test just wants "longer than the timeout it passes"), and a
      // request-controlled value flowing into setTimeout is a resource-exhaustion
      // pattern CodeQL flags regardless of actual reachability -- clamping it with
      // Math.min/Math.max still counts as "user-controlled" to CodeQL's taint
      // tracking, so removing the input from the timer entirely, not bounding it, is
      // what actually clears the finding.
      setTimeout(() => sendFrame(socket, { echo: request }), SLOW_SCENARIO_DELAY_MS);
    } else if (scenario === "malformed") {
      sendRawFrame(socket, Buffer.from("{not json", "utf-8"));
    } else if (scenario === "big") {
      const row = [1, 2, 3, 4, 5];
      const rows = Array.from({ length: request.rows ?? 10 }, () => row);
      sendFrame(socket, { result: { columns: ["a", "b", "c", "d", "e"], rows } });
    } else {
      sendFrame(socket, { echo: request });
    }
  });
});

server.listen(socketPath);
