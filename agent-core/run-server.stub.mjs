// Algenta Repositories agent-core sidecar.
//
// This offline-contract stub is quarantined behind explicit environment guards in
// `run-server.mjs`. It is retained ONLY for loopback contract tests that need the
// Python<->Node bridge and shared-filesystem mutation path without a live model.

import crypto from "node:crypto";
import { promises as fs } from "node:fs";
import http from "node:http";
import path from "node:path";

const HOST = "127.0.0.1";
const PORT = Number(process.env.AGENT_CORE_PORT || process.argv[2] || 0);

async function runAgent({ working_dir, task_spec, injected_context, limits }) {
	void task_spec;
	void limits;
	const events = [];
	const suspects = (injected_context && injected_context.suspect_files) || [];
	let status = "no_change";

	if (Array.isArray(suspects) && suspects.length > 0) {
		const rel = String(suspects[0]);
		const target = path.join(working_dir, rel);
		try {
			const before = await fs.readFile(target, "utf8");
			await fs.writeFile(target, `${before}\n# agent-core stub edit\n`, "utf8");
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
			working_tree_diff: null,
			telemetry: {
				turns: 1,
				tokens_in_cached: 0,
				tokens_in_uncached: 0,
				tokens_out: 0,
				tool_calls: events.filter((event) => event.type === "tool_call").length,
			},
			agent_run_id: `stub_${crypto.randomUUID()}`,
			session_id: null,
			terminal_state: "offline_contract_only",
			transcript_ref: null,
			artifacts: {
				offline_contract_only: true,
			},
		},
	};
}

function sendNdjson(res, frames) {
	res.writeHead(200, { "content-type": "application/x-ndjson" });
	for (const frame of frames) res.write(`${JSON.stringify(frame)}\n`);
	res.end();
}

const server = http.createServer((req, res) => {
	if (req.method === "GET" && req.url === "/health") {
		res.writeHead(200, { "content-type": "application/json" });
		res.end(
			JSON.stringify({
				status: "ok",
				runtime: { kind: "cline", is_stub: true },
				offline_contract_only: true,
			}),
		);
		return;
	}

	if (req.method === "GET" && req.url === "/manifest") {
		res.writeHead(200, { "content-type": "application/json" });
		res.end(
			JSON.stringify({
				schema_version: "cline-runtime-manifest/v1",
				runtime: {
					kind: "cline",
					is_stub: true,
					entrypoint: "agent-core/run-server.stub.mjs",
				},
				offline_contract_only: true,
			}),
		);
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
				sendNdjson(res, [
					{ type: "final", status: "failed", error: "invalid json body" },
				]);
				return;
			}
			try {
				const { events, final } = await runAgent(payload);
				sendNdjson(res, [...events, final]);
			} catch (err) {
				sendNdjson(res, [
					{ type: "final", status: "aborted", error: String(err) },
				]);
			}
		});
		return;
	}

	res.writeHead(404);
	res.end();
});

server.listen(PORT, HOST, () => {
	const { port } = server.address();
	console.log(`AGENT_CORE_LISTENING ${port}`);
});
