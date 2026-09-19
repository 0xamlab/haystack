#!/usr/bin/env node
// A stand-in for the compiled Algenta native worker binary that MISBEHAVES at the startup
// handshake, for `native_worker_client_startup_failure.test.ts`. The regular fixture
// (`_native_worker_test_fixture.mjs`) always completes the `{"status":"ready"}` handshake and
// takes its scenario from the first request; a startup failure happens BEFORE any request is
// sent, so this fixture is driven by the environment the spawning test sets instead:
//
//   ALGENTA_TEST_STARTUP_HANDSHAKE
//     "not-ready"       -- the first frame is a well-formed JSON object whose status is not
//                          "ready" (a worker still booting), then the socket stays open
//     "invalid-output"  -- the first frame's body is not valid JSON
//
//   ALGENTA_TEST_STARTUP_RECORD
//     a file this process APPENDS one JSON line to -- {"pid", "socketPath"} -- before it
//     starts listening, so the test can prove afterwards that every worker the client spawned
//     (it retries startup once) is gone and that the temp dir the client created for it (the
//     socket's parent directory) was removed. Written by the fixture, not guessed by the test:
//     the record is the only durable trace of a worker whose temp dir is meant to vanish.
import { appendFileSync } from "node:fs";
import net from "node:net";
import { argv, env, exit, pid } from "node:process";

const serverIndex = argv.indexOf("--server");
const socketPath = argv[serverIndex + 1];
const handshake = env.ALGENTA_TEST_STARTUP_HANDSHAKE;
const recordPath = env.ALGENTA_TEST_STARTUP_RECORD;

if (!socketPath || !recordPath || !handshake) {
  exit(2);
}

function sendRawFrame(socket, bodyBuffer) {
  const header = Buffer.alloc(4);
  header.writeUInt32BE(bodyBuffer.length, 0);
  socket.write(Buffer.concat([header, bodyBuffer]));
}

const server = net.createServer((socket) => {
  if (handshake === "invalid-output") {
    sendRawFrame(socket, Buffer.from("{not json", "utf-8"));
  } else {
    sendRawFrame(socket, Buffer.from(JSON.stringify({ status: "booting" }), "utf-8"));
  }
  // Never answer anything else: the client must decide on the handshake alone.
});

appendFileSync(recordPath, `${JSON.stringify({ pid, socketPath })}\n`);
server.listen(socketPath);
