// Algenta Repositories — real agent-core adapter over the vendored Cline SDK.
//
// The helper exports below are shared by the sidecar session server and the
// single-shot runAgent() wrapper. They resolve provider/model credentials,
// build a deterministic local ClineCore config, and derive proof-friendly file
// and tool metadata from the SDK result surface.
import { ClineCore, Llms } from "@cline/core";
import { mojoGateAfterTool } from "./mojo-gate";
import {
	ALGENTA_PROOF_API_KEY_ENV,
	ALGENTA_PROOF_MODEL_ID,
	ALGENTA_PROOF_PROVIDER_ID,
	ensureAlgentaProofProviderRegistered,
} from "./proof-provider";
import { algentaTools } from "./tools";

export interface RunAgentArgs {
	working_dir: string;
	prompt: string; // the task
	injected_context?: string; // token-compressed evidence bundle (repo intelligence)
	provider?: string; // default "anthropic"
	model?: string; // default = provider's defaultModelId
	base_url?: string;
	headers?: Record<string, string>;
	suppress_exploration?: boolean; // legacy token-reduction flag: block read/search/fetch tools
	tool_profile?: string; // AR-OPT-4 tool profile (takes precedence over suppress_exploration)
	limits?: { maxIterations?: number; timeoutMs?: number };
	enable_spawn_agent?: boolean;
	enable_agent_teams?: boolean;
}

export interface RunAgentResult {
	status: string; // AgentFinishReason: completed | max_iterations | aborted | mistake_limit | error
	agent_run_id: string;
	text: string;
	iterations: number;
	files_changed: string[];
	usage?: {
		inputTokens: number;
		outputTokens: number;
		cacheReadTokens?: number;
		cacheWriteTokens?: number;
		totalCost?: number;
	};
	provider: string;
	model: string;
}

const EXPLORATION_TOOLS = [
	"read_files",
	"search_codebase",
	"fetch_web_content",
	"ask_question",
];
const SHELL_TOOLS = ["run_commands"];
const WRITE_TOOLS = new Set(["editor", "apply_patch"]);

// AR-OPT-4 tool profiles — trim the agent's tool surface to cut exploration tokens.
//   no_exploration_no_shell         -> block exploration AND the shell (most token-frugal;
//                                       the agent edits purely from the injected bundle).
//   no_exploration_local_validation -> block exploration; keep the shell so the agent may
//                                       validate its patch in-sandbox after editing.
// Falls back to the legacy suppress_exploration flag when no profile is given.
function suppressedTools(args: RunAgentArgs): string[] {
	switch (args.tool_profile) {
		case "no_exploration_no_shell":
			return [...EXPLORATION_TOOLS, ...SHELL_TOOLS];
		case "no_exploration_local_validation":
			return [...EXPLORATION_TOOLS];
		default:
			return args.suppress_exploration ? [...EXPLORATION_TOOLS] : [];
	}
}

export interface ResolvedProviderConfig {
	providerId: string;
	modelId: string;
	apiKey: string;
	baseUrl?: string;
	headers?: Record<string, string>;
}

export async function resolveProviderConfig(
	args: RunAgentArgs,
): Promise<ResolvedProviderConfig> {
	// Resolve provider/model/apiKey from .env via the SDK catalog — any provider.
	const requested = args.provider || "anthropic";
	const providerId =
		(
			Llms as { normalizeProviderId?: (p: string) => string }
		).normalizeProviderId?.(requested) ?? requested;
	if (
		providerId === ALGENTA_PROOF_PROVIDER_ID ||
		args.model === ALGENTA_PROOF_MODEL_ID
	) {
		ensureAlgentaProofProviderRegistered();
	}
	const collection = await Llms.getProviderCollection(providerId);
	const envNames: string[] = collection?.provider?.env ?? [];
	const apiKey = envNames.map((k) => process.env[k]?.trim()).find(Boolean);
	const modelId = args.model || collection?.provider?.defaultModelId;
	if (!modelId) throw new Error(`no model id for provider '${providerId}'`);
	if (!apiKey) {
		const proofHint =
			modelId === ALGENTA_PROOF_MODEL_ID
				? ` (proof model requires ${ALGENTA_PROOF_API_KEY_ENV})`
				: "";
		throw new Error(
			`no API key in env for '${providerId}' (tried: ${envNames.join(", ") || "none"})${proofHint}`,
		);
	}
	return {
		providerId,
		modelId,
		apiKey,
		baseUrl: args.base_url?.trim() || undefined,
		headers:
			args.headers && Object.keys(args.headers).length > 0
				? { ...args.headers }
				: undefined,
	};
}

export function buildToolPolicies(
	args: RunAgentArgs,
	options?: { autoApproveAll?: boolean },
): Record<string, { enabled?: boolean; autoApprove?: boolean }> {
	// Auto-approve everything (headless); optionally hard-suppress exploration tools.
	const autoApproveAll = options?.autoApproveAll !== false;
	const toolPolicies: Record<
		string,
		{ enabled?: boolean; autoApprove?: boolean }
	> = {
		"*": { enabled: true, autoApprove: autoApproveAll },
	};
	for (const t of suppressedTools(args)) toolPolicies[t] = { enabled: false };
	return toolPolicies;
}

export function buildSystemPrompt(args: RunAgentArgs): string {
	const disabledTools = suppressedTools(args);
	const guidance = [
		"You are Algenta's automated repository-fixing agent.",
		"Apply the requested change using your file-editing tools, then stop.",
		"Do not ask questions.",
		"The repository root is the current working directory.",
	];
	if (disabledTools.length > 0 || args.injected_context) {
		guidance.push(
			"When editing files, use repository-relative paths only (for example: src/app.ts). Never use absolute paths like /src/app.ts.",
		);
		guidance.push(
			"Prefer apply_patch for minimal textual edits. Use editor only when apply_patch is impractical.",
		);
	}
	if (disabledTools.length > 0) {
		guidance.push(
			`Do not call policy-disabled tools: ${disabledTools.join(", ")}.`,
		);
	}
	if (args.injected_context) {
		guidance.push(
			"Treat the injected repository evidence bundle as authoritative. If it names the target file, edit that file directly instead of exploring the repository.",
		);
	}
	return (
		guidance.join(" ") +
		(args.injected_context
			? `\n\n[REPOSITORY EVIDENCE BUNDLE — authoritative; prefer it over exploring the repo]\n${args.injected_context}`
			: "")
	);
}

export function buildStartConfig(
	args: RunAgentArgs,
	provider: ResolvedProviderConfig,
): Parameters<typeof ClineCore.prototype.start>[0] {
	const engineEnabled = Boolean(process.env.ALGENTA_ENGINE_URL);
	return {
		config: {
			providerId: provider.providerId,
			modelId: provider.modelId,
			apiKey: provider.apiKey,
			...(provider.baseUrl ? { baseUrl: provider.baseUrl } : {}),
			...(provider.headers ? { headers: { ...provider.headers } } : {}),
			cwd: args.working_dir,
			workspaceRoot: args.working_dir,
			systemPrompt: buildSystemPrompt(args),
			enableTools: true,
			enableSpawnAgent: Boolean(args.enable_spawn_agent),
			enableAgentTeams: Boolean(args.enable_agent_teams),
			// Engine-behind seam: load the Algenta tools plugin (localize/graph_query/
			// simulate_patch) AND the govern hook ONLY when an engine URL is configured.
			// Additive — without ALGENTA_ENGINE_URL the run is exactly as before.
			// The govern hook is wired via `config.hooks` (not the plugin's top-level
			// hooks): in backendMode "local" the runtime merges config.hooks into the
			// loop, but a pluginPaths plugin only contributes its setup()/tools — its
			// hooks are not wired. Tools come from the plugin; the hook comes from here.
			...(engineEnabled
				? {
						pluginPaths: [
							new URL("./algenta-plugin.ts", import.meta.url).pathname,
						],
						extraTools: algentaTools,
						hooks: { afterTool: mojoGateAfterTool },
					}
				: {}),
			// Always bound iterations: a non-converging suppressed run otherwise loops
			// and (uncached) re-bills the whole context per turn — the 466k-token blowup
			// the G0 run caught. Default cap 12; callers may tighten via limits.maxIterations.
			execution: { maxIterations: args.limits?.maxIterations ?? 12 },
		},
		...(engineEnabled
			? {
					localRuntime: {
						configExtensions: ["plugins", "skills"] as const,
					},
				}
			: {}),
		source: "api",
		interactive: false,
	} as Parameters<typeof ClineCore.prototype.start>[0];
}

export function collectFilesChangedFromToolCalls(
	toolCalls:
		| {
				name: string;
				input?: unknown;
				error?: string;
		  }[]
		| undefined,
): string[] {
	const filesChanged = new Set<string>();
	for (const call of toolCalls ?? []) {
		if (!WRITE_TOOLS.has(call.name) || call.error) continue;
		const input = call.input as
			| { path?: string; file?: string; files?: unknown }
			| undefined;
		const filesField = input?.files;
		const candidates = [
			input?.path,
			input?.file,
			...(Array.isArray(filesField) ? filesField : []),
		];
		for (const p of candidates) if (typeof p === "string") filesChanged.add(p);
	}
	return [...filesChanged];
}

export async function runAgent(args: RunAgentArgs): Promise<RunAgentResult> {
	const provider = await resolveProviderConfig(args);
	const toolPolicies = buildToolPolicies(args);

	const cline = await ClineCore.create({
		clientName: "algenta-agent-core",
		backendMode: "local",
		toolPolicies,
	} as Parameters<typeof ClineCore.create>[0]);

	let agentRunId = "";
	try {
		const started = await cline.start(buildStartConfig(args, provider));
		agentRunId = started.sessionId;

		const result = await (
			cline as unknown as {
				send: (i: unknown) => Promise<
					| {
							finishReason?: string;
							text?: string;
							iterations?: number;
							usage?: {
								inputTokens?: number;
								outputTokens?: number;
								totalCost?: number;
							};
							toolCalls?: { name: string; input?: unknown; error?: string }[];
					  }
					| undefined
				>;
			}
		).send({
			sessionId: agentRunId,
			prompt: args.prompt,
			mode: "act",
			timeoutMs: args.limits?.timeoutMs ?? 150000,
		});

		// Authoritative usage incl. prompt-cache read/write. Research: getAccumulatedUsage's
		// aggregateUsage is the real breakdown (and includes subagents); send().usage omits
		// cache fields, which is why earlier G0 runs reported cache_w=0 even though the
		// anthropic provider declares the prompt-cache capability. Prefer accumulated usage.
		let usage = result?.usage as
			| {
					inputTokens?: number;
					outputTokens?: number;
					cacheReadTokens?: number;
					cacheWriteTokens?: number;
					totalCost?: number;
			  }
			| undefined;
		try {
			const acc = await (
				cline as unknown as {
					getAccumulatedUsage?: (id: string) => Promise<
						| {
								aggregateUsage?: Record<string, number>;
								usage?: Record<string, number>;
						  }
						| undefined
					>;
				}
			).getAccumulatedUsage?.(agentRunId);
			const agg = acc?.aggregateUsage ?? acc?.usage;
			if (agg) usage = { ...usage, ...agg };
		} catch {
			/* fall back to send().usage */
		}
		return {
			status: result?.finishReason ?? "unknown",
			agent_run_id: agentRunId,
			text: result?.text ?? "",
			iterations: result?.iterations ?? 0,
			files_changed: collectFilesChangedFromToolCalls(result?.toolCalls),
			usage: usage
				? {
						inputTokens: usage.inputTokens ?? 0,
						outputTokens: usage.outputTokens ?? 0,
						cacheReadTokens: usage.cacheReadTokens ?? 0,
						cacheWriteTokens: usage.cacheWriteTokens ?? 0,
						totalCost: usage.totalCost,
					}
				: undefined,
			provider: provider.providerId,
			model: provider.modelId,
		};
	} finally {
		const anyCline = cline as unknown as {
			dispose?: (r?: string) => Promise<void>;
		};
		if (typeof anyCline.dispose === "function") {
			await anyCline.dispose("run_complete").catch(() => {});
		}
	}
}
