// Algenta Repositories agent-core — REAL NDJSON /run sidecar (vendored Cline SDK).
//
// Run headless from the vendored-SDK dir so @cline/* resolve:
//   ANTHROPIC_API_KEY=... bun algenta/run-server.ts [port]
//
// Contract matches the Python loopback client (repository_intelligence_agent_core_client):
//   POST /run { working_dir, task_spec, injected_context, provider?, model?,
//               suppress_exploration?, limits? }
//   -> NDJSON; final frame { type:"final", status, agent_run_id, files_changed,
//      telemetry, working_tree_diff:null (advisory — Python recomputes), text }
import http from "node:http";
import { runAgent } from "./adapter";

const HOST = "127.0.0.1";
const PORT = Number(process.env.AGENT_CORE_PORT || process.argv[2] || 0);

function asString(v: unknown): string {
	if (v == null) return "";
	return typeof v === "string" ? v : JSON.stringify(v);
}

function buildPrompt(payload: Record<string, unknown>): string {
	if (typeof payload.prompt === "string" && payload.prompt.trim())
		return payload.prompt;
	const task = (payload.task_spec ?? {}) as Record<string, unknown>;
	const ctx = (payload.injected_context ?? {}) as Record<string, unknown>;
	const issue = asString(task.issue_text) || "(see the evidence bundle)";
	const suspects = Array.isArray(ctx.suspect_files)
		? (ctx.suspect_files as string[])
		: [];
	const suspectLine = suspects.length
		? ` Likely files: ${suspects.join(", ")}.`
		: "";
	return `Fix this repository issue: ${issue}.${suspectLine} Make the minimal correct change with your file-editing tools, then stop.`;
}

const server = http.createServer((req, res) => {
	if (req.method === "GET" && req.url === "/health") {
		res.writeHead(200, { "content-type": "application/json" });
		res.end(JSON.stringify({ status: "ok", engine: "cline_fork" }));
		return;
	}
	if (req.method === "POST" && req.url === "/run") {
		let body = "";
		req.on("data", (c) => (body += c));
		req.on("end", async () => {
			res.writeHead(200, { "content-type": "application/x-ndjson" });
			let payload: Record<string, unknown>;
			try {
				payload = JSON.parse(body || "{}");
			} catch {
				res.end(
					`${JSON.stringify({
						type: "final",
						status: "failed",
						error: "invalid json body",
					})}\n`,
				);
				return;
			}
			try {
				const taskSpec = (payload.task_spec ?? {}) as Record<string, unknown>;
				const toolProfile =
					typeof payload.tool_profile === "string"
						? (payload.tool_profile as string)
						: typeof taskSpec.tool_profile === "string"
							? (taskSpec.tool_profile as string)
							: undefined;
				// Engine-behind: when task_spec.engine is present, export the loopback engine
				// config so the Algenta-tools plugin can reach the LOCAL engine for THIS run.
				// (Sequential single-run sidecar; per-run env is acceptable here.)
				const engine = (taskSpec.engine ?? {}) as Record<string, unknown>;
				if (typeof engine.url === "string" && engine.url) {
					process.env.ALGENTA_ENGINE_URL = String(engine.url);
					process.env.ALGENTA_REPOSITORY_ID = String(
						engine.repository_id ?? "",
					);
					process.env.ALGENTA_SNAPSHOT_ID = String(engine.snapshot_id ?? "");
					process.env.ALGENTA_WORKING_DIR = String(payload.working_dir ?? "");
					if (engine.api_key)
						process.env.ALGENTA_API_KEY = String(engine.api_key);
				}
				const result = await runAgent({
					working_dir: String(payload.working_dir ?? ""),
					prompt: buildPrompt(payload),
					injected_context: asString(payload.injected_context),
					// LLM provider/model = any (BYOM): payload, then task_spec.engine, else adapter default.
					provider: payload.provider
						? String(payload.provider)
						: engine.provider
							? String(engine.provider)
							: undefined,
					model: payload.model
						? String(payload.model)
						: engine.model
							? String(engine.model)
							: undefined,
					suppress_exploration: Boolean(payload.suppress_exploration),
					tool_profile: toolProfile,
					limits: payload.limits as
						| { maxIterations?: number; timeoutMs?: number }
						| undefined,
				});
				res.write(
					`${JSON.stringify({
						type: "final",
						status: result.status === "completed" ? "completed" : result.status,
						agent_run_id: result.agent_run_id,
						transcript_ref: null,
						working_tree_diff: null, // advisory only — Python recomputes the authoritative diff
						telemetry: {
							turns: result.iterations,
							tokens_in_uncached: result.usage?.inputTokens ?? 0,
							tokens_out: result.usage?.outputTokens ?? 0,
							cache_read_tokens: result.usage?.cacheReadTokens ?? 0,
							cache_write_tokens: result.usage?.cacheWriteTokens ?? 0,
							total_cost: result.usage?.totalCost ?? 0,
							provider: result.provider,
							model: result.model,
						},
						files_changed: result.files_changed,
						text: result.text,
					})}\n`,
				);
			} catch (err) {
				res.write(
					`${JSON.stringify({
						type: "final",
						status: "aborted",
						error: String(err),
					})}\n`,
				);
			}
			res.end();
		});
		return;
	}
	res.writeHead(404);
	res.end();
});

server.listen(PORT, HOST, () => {
	const addr = server.address() as { port: number };
	console.log(`AGENT_CORE_LISTENING ${addr.port}`);
});
