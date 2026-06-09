// Algenta Repositories agent-core sidecar.
//
// This is the ONLY net-new deployable process in the Algenta Repositories product
// (the rest is the shared decision-engine consumed in-process). It exists because the
// forked-Cline execution loop is TypeScript and cannot run in-process in Python.
//
// The HTTP/NDJSON `POST /run` contract below is the REAL, stable loopback contract the
// Python planner (`verified_agentic` tier) drives. `runAgent()` is currently a STUB seam:
// it proves the Python<->Node loopback + shared-filesystem file-mutation + the
// Python-authoritative-diff path end-to-end without a model. It will be replaced by the
// vendored Apache-2.0 `@cline/core` headless runtime:
//
//     import { ClineCore } from "@cline/core";
//     const cline = await ClineCore.create({ clientName: "algenta-repositories",
//                                            capabilities: <tool-suppressed + bundle-injected> });
//     const session = await cline.start({ cwd: working_dir, prompt: <task + injected_context> });
//
// SECURITY (production, not this scaffold): one job == one disposable microVM/gVisor
// sandbox, default-deny egress except the loopback model proxy. See plan §6.
//
// Python is the source of truth for the diff: the `working_tree_diff` field below is
// advisory/debug only — Python recomputes the authoritative diff from before/after tree
// state. The sidecar's job is to mutate files under `working_dir` and report status.

import crypto from "node:crypto";
import { promises as fs } from "node:fs";
import http from "node:http";
import path from "node:path";

const HOST = "127.0.0.1";
const PORT = Number(process.env.AGENT_CORE_PORT || process.argv[2] || 0);

/**
 * STUB execution seam. Replace the body with vendored ClineCore.create()/start().
 *
 * Contract (input): { working_dir, task_spec, injected_context, limits }
 *   injected_context carries our token-compressed evidence bundle + suspect files/symbols
 *   + graph blast-radius, so the agent skips repository exploration.
 *
 * Contract (output): { events: Event[], final: FinalFrame }
 *   The agent MUST mutate files under working_dir; Python captures the diff itself.
 */
async function runAgent({ working_dir, task_spec, injected_context, limits }) {
  void task_spec;
  void limits;
  const events = [];
  const suspects = (injected_context && injected_context.suspect_files) || [];
  let status = "no_change";

  // Deterministic stub: append a marker to the first injected suspect file. This
  // exercises injected-context flow -> agent edit -> shared FS, nothing more.
  if (Array.isArray(suspects) && suspects.length > 0) {
    const rel = String(suspects[0]);
    const target = path.join(working_dir, rel);
    try {
      const before = await fs.readFile(target, "utf8");
      await fs.writeFile(target, before + "\n# agent-core stub edit\n", "utf8");
      events.push({ type: "tool_call", tool: "edit_file", path: rel });
      events.push({ type: "tool_result", tool: "edit_file", ok: true });
      status = "completed";
    } catch (err) {
      events.push({ type: "error", message: String(err) });
      status = "failed";
    }
  }

  return {
    events,
    final: {
      type: "final",
      status,
      // Advisory/debug only — Python recomputes the authoritative diff.
      working_tree_diff: null,
      telemetry: {
        turns: 1,
        tokens_in_cached: 0,
        tokens_in_uncached: 0,
        tokens_out: 0,
        tool_calls: events.filter((e) => e.type === "tool_call").length,
      },
      agent_run_id: "stub_" + crypto.randomUUID(),
      transcript_ref: null,
    },
  };
}

function sendNdjson(res, frames) {
  res.writeHead(200, { "content-type": "application/x-ndjson" });
  for (const frame of frames) res.write(JSON.stringify(frame) + "\n");
  res.end();
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ status: "ok", stub: true }));
    return;
  }

  if (req.method === "POST" && req.url === "/run") {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", async () => {
      let payload;
      try {
        payload = JSON.parse(body || "{}");
      } catch {
        sendNdjson(res, [{ type: "final", status: "failed", error: "invalid json body" }]);
        return;
      }
      try {
        const { events, final } = await runAgent(payload);
        sendNdjson(res, [...events, final]);
      } catch (err) {
        sendNdjson(res, [{ type: "final", status: "aborted", error: String(err) }]);
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

server.listen(PORT, HOST, () => {
  const { port } = server.address();
  // Machine-readable readiness line so a parent process can discover the bound port.
  console.log("AGENT_CORE_LISTENING " + port);
});
