// Algenta govern hook — the calibrated-risk gate INSIDE the Cline agent loop.
//
// Cline's built-in tools let the agent EDIT files; this AgentExtension `afterTool` hook
// makes every edit pass through the Algenta decision engine before the loop continues.
// After each `apply_patch` / `editor` tool call it captures the cumulative working-tree
// patch and asks the LOCAL engine (loopback HTTP — the self-hosted boundary, no cloud)
// to simulate it with the Mojo Monte-Carlo engine and return the calibrated-risk verdict.
// The verdict is fed back into the loop so the agent reacts to risk automatically —
// without having to remember to call the `simulate_patch` tool itself.
//
// This complements the `simulate_patch` tool (a voluntary, run-completing check): the
// hook is the involuntary governor that fires on EVERY edit.
//
// Mode (env ALGENTA_GATE_MODE):
//   advisory (default) — append the verdict to the edit result the model sees; never
//                        errors or stops. An in-loop signal with no behavior coercion
//                        (shadow-first, the same discipline as AR-OPT-5 routing).
//   enforce            — on a failed gate, mark the edit result `isError` so the agent
//                        treats the edit as rejected and revises within the loop.
//   block              — on a failed gate, stop the run (hard veto: a "do not apply"
//                        verdict ends the run without leaving a bad edit).
//
// Fails OPEN: any engine/infra error leaves the edit untouched — governance must never
// break the agent run. The plugin is only loaded when ALGENTA_ENGINE_URL is set
// (see adapter.ts); the hook re-checks the engine config defensively.
import type { AgentPlugin } from "@cline/core";
import {
	ENGINE,
	enginePost,
	REPO,
	SNAPSHOT,
	WORKING_DIR,
	workingTreeDiff,
} from "./tools";

type AfterToolHook = NonNullable<
	NonNullable<AgentPlugin["hooks"]>["afterTool"]
>;
type GateMode = "advisory" | "enforce" | "block";

// Cline's two file-editing tools (constants.ts: APPLY_PATCH / EDITOR).
const EDIT_TOOLS = new Set(["apply_patch", "editor"]);

function gateMode(): GateMode {
	const m = (process.env.ALGENTA_GATE_MODE ?? "advisory").toLowerCase();
	return m === "enforce" || m === "block" ? m : "advisory";
}

/** Render a tool result's output the way the runtime presents it to the model. */
function renderOutput(o: unknown): string {
	if (o === undefined || o === null) return "";
	if (typeof o === "string") return o;
	if (o instanceof Error) return o.message;
	try {
		return JSON.stringify(o);
	} catch {
		return String(o);
	}
}

// Sequential single-run sidecar: skip re-simulating an unchanged cumulative diff so a
// burst of edits that don't move the patch doesn't re-run the Mojo sim each time.
let lastDiff = "";
let lastVerdict: {
	action: string;
	confidence: unknown;
	engine: unknown;
} | null = null;

export const mojoGateAfterTool: AfterToolHook = async (ctx) => {
	// Govern only successful edits, and only when the local engine is configured.
	if (!ENGINE() || !REPO()) return undefined;
	const toolName = ctx.toolCall?.toolName ?? ctx.tool?.name;
	if (!toolName || !EDIT_TOOLS.has(toolName)) return undefined;
	if (ctx.result?.isError) return undefined;

	try {
		const patchDiff = await workingTreeDiff(WORKING_DIR());
		if (!patchDiff.trim()) return undefined;

		let verdict = lastVerdict;
		if (patchDiff !== lastDiff || verdict === null) {
			const env = await enginePost(
				`/v1/repositories/${REPO()}/simulate-patch`,
				{
					snapshot_id: SNAPSHOT(),
					patch_diff: patchDiff,
				},
			);
			verdict = {
				action: String(env.recommended_action ?? ""),
				confidence: env.confidence,
				engine: env.engine_version,
			};
			lastDiff = patchDiff;
			lastVerdict = verdict;
		}

		const passed = verdict.action === "apply_patch";
		const mode = gateMode();
		const tag =
			`[algenta-risk-gate] recommended_action=${verdict.action} ` +
			`confidence=${verdict.confidence ?? "?"} engine=${verdict.engine ?? "?"} mode=${mode}`;
		const metadata = {
			...(ctx.result?.metadata ?? {}),
			algenta_gate: {
				action: verdict.action,
				confidence: verdict.confidence,
				mode,
				passed,
			},
		};
		const base = renderOutput(ctx.result?.output);

		if (passed) {
			// Gate satisfied — record the verdict; never alter control flow.
			return {
				result: { output: `${base}\n\n${tag} — gate PASSED ✓`, metadata },
			};
		}

		// Gate FAILED.
		const fail =
			`${tag} — gate FAILED: the Algenta calibrated-risk simulation does not approve the ` +
			`current working-tree patch. Reduce blast radius / likely-failing tests and revise ` +
			`before finalizing.`;
		if (mode === "block") {
			// Surface the verdict in output too (not only the stop reason), so the
			// run's evidence records that the gate fired even when it blocks.
			return {
				stop: true,
				reason: fail,
				result: { output: `${base}\n\n${fail}`, metadata },
			};
		}
		return {
			result: {
				output: `${base}\n\n${fail}`,
				isError: mode === "enforce",
				metadata,
			},
		};
	} catch {
		// Governance fails OPEN — never break the agent run on an engine/infra error.
		return undefined;
	}
};
