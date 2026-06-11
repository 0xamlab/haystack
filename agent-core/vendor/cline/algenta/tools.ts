// Algenta engine tools, exposed to the Cline agent via createTool (the "engine behind"
// seam). Each tool calls the Algenta FastAPI engine over LOOPBACK HTTP (the self-hosted
// boundary — no cloud). The agent calls these instead of blind repository exploration:
//   localize       -> 180-language triage -> bounded evidence bundle
//   graph_query    -> dependency / blast-radius graph
//   simulate_patch -> the Mojo decision engine; completesRun gates submission (Q2: a
//                     "do not apply" verdict ENDS the run without a bad edit)
//
// inputSchema is plain JSON Schema (createTool's first overload) to avoid a zod runtime
// dependency from this vendored path. Config comes from env so the plugin stays stateless:
//   ALGENTA_ENGINE_URL     (e.g. http://127.0.0.1:8000)  — required; absent => plugin not loaded
//   ALGENTA_REPOSITORY_ID  — the connector/repository id the run targets
//   ALGENTA_SNAPSHOT_ID    — the immutable snapshot to triage/simulate against
//   ALGENTA_API_KEY        — bearer token for the engine

import { AsyncLocalStorage } from "node:async_hooks";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { AgentTool } from "@cline/core";
import { createTool } from "@cline/sdk";

const pexec = promisify(execFile);

// B3 (PR8): per-run engine config is threaded through AsyncLocalStorage, NOT process-global
// env. Each run executes inside engineContext.run(ctx, ...), so concurrent sessions can never
// read each other's engine URL / API key — the cross-tenant secret bleed + serialization the
// old global-env + activeEngineSessionId mutex caused. Outside a run the store is undefined and
// the engine seam is inert (ENGINE() === "").
export interface EngineContext {
	url: string;
	repositoryId: string;
	snapshotId: string;
	apiKey: string;
	workingDir: string;
}

export const engineContext = new AsyncLocalStorage<EngineContext>();

const _ctx = (): Partial<EngineContext> => engineContext.getStore() ?? {};

// Exported so the govern hook (mojo-gate.ts) shares ONE engine seam — same loopback
// config, same diff capture, same authenticated POST — instead of duplicating it.
export const ENGINE = () => (_ctx().url ?? "").replace(/\/$/, "");
export const REPO = () => _ctx().repositoryId ?? "";
export const SNAPSHOT = () => _ctx().snapshotId ?? "";
const KEY = () => _ctx().apiKey ?? "";
export const WORKING_DIR = () => _ctx().workingDir ?? "";

/** Capture the agent's in-flight edits (mods + new + deletes) as a unified diff. */
export async function workingTreeDiff(dir: string): Promise<string> {
	if (!dir) return "";
	try {
		await pexec("git", ["-C", dir, "add", "-A"]);
		const { stdout } = await pexec("git", ["-C", dir, "diff", "--cached"], {
			maxBuffer: 16 * 1024 * 1024,
		});
		return stdout;
	} catch {
		return "";
	}
}

export async function enginePost(
	path: string,
	body: unknown,
): Promise<Record<string, unknown>> {
	const res = await fetch(`${ENGINE()}${path}`, {
		method: "POST",
		headers: {
			"content-type": "application/json",
			...(KEY() ? { authorization: `Bearer ${KEY()}` } : {}),
		},
		body: JSON.stringify(body),
	});
	if (!res.ok) {
		throw new Error(
			`engine ${path} -> ${res.status} ${await res.text().catch(() => "")}`,
		);
	}
	return (await res.json()) as Record<string, unknown>;
}

export const localize = createTool({
	name: "localize",
	description:
		"Triage the repository for this issue and return a bounded evidence bundle " +
		"(suspect files/symbols + snippets). Call this FIRST instead of exploring the repo.",
	inputSchema: {
		type: "object",
		properties: {
			issue: { type: "string", description: "the bug/issue text" },
			changed_files: { type: "array", items: { type: "string" } },
			failing_tests: { type: "array", items: { type: "string" } },
		},
		required: ["issue"],
	},
	execute: async (input: {
		issue: string;
		changed_files?: string[];
		failing_tests?: string[];
	}) => {
		const out = await enginePost(`/v1/repositories/${REPO()}/triage`, {
			snapshot_id: SNAPSHOT(),
			signals: {
				issue_text: input.issue,
				changed_files: input.changed_files ?? [],
				failing_tests: input.failing_tests ?? [],
			},
			max_evidence_items: 12,
		});
		return {
			suspect_files: out.suspect_files ?? [],
			suspect_symbols: out.suspect_symbols ?? [],
			reduction_ratio: out.reduction_ratio,
			evidence: out.evidence_items ?? [],
		};
	},
});

export const graphQuery = createTool({
	name: "graph_query",
	description:
		"Query the dependency / blast-radius graph for a file or symbol.",
	inputSchema: {
		type: "object",
		properties: {
			file_path: { type: "string" },
			symbol_name: { type: "string" },
			direction: { type: "string", enum: ["inbound", "outbound", "both"] },
		},
	},
	execute: async (input: {
		file_path?: string;
		symbol_name?: string;
		direction?: string;
	}) => {
		return enginePost(`/v1/repositories/${REPO()}/graph-query`, {
			snapshot_id: SNAPSHOT(),
			file_path: input.file_path,
			symbol_name: input.symbol_name,
			direction: input.direction ?? "both",
			max_depth: 2,
			max_nodes: 64,
		});
	},
});

export const simulatePatch = createTool({
	name: "simulate_patch",
	description:
		"Verify your CURRENT edits with the Algenta Mojo decision engine — no decision-plan " +
		"id needed; it simulates your in-flight working-tree patch. Returns the gate " +
		"(recommended_action/confidence). Call this before finishing; only finalize when " +
		"recommended_action is 'apply_patch'.",
	inputSchema: {
		type: "object",
		properties: {
			confidence: {
				type: "number",
				description:
					"your self-assessed confidence in the fix (0..1), optional",
			},
		},
	},
	// Q2: completion gate — the verdict ends the run; a non-apply result means do NOT submit.
	lifecycle: { completesRun: true },
	execute: async (input: { confidence?: number }) => {
		const patch_diff = await workingTreeDiff(WORKING_DIR());
		if (!patch_diff.trim()) {
			return {
				recommended_action: "no_change",
				apply: false,
				note: "no working-tree changes to simulate",
			};
		}
		const env = await enginePost(`/v1/repositories/${REPO()}/simulate-patch`, {
			snapshot_id: SNAPSHOT(),
			patch_diff,
			confidence: input.confidence,
		});
		return {
			recommended_action: env.recommended_action,
			confidence: env.confidence,
			engine_version: env.engine_version,
			execution_ms: env.execution_ms,
			apply: env.recommended_action === "apply_patch",
		};
	},
});

// biome-ignore lint/suspicious/noExplicitAny: tool input/output types vary per tool
export const algentaTools: AgentTool<any, any>[] = [
	localize,
	graphQuery,
	simulatePatch,
];
