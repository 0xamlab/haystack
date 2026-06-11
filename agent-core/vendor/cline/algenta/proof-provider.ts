import { Llms } from "@cline/core";
import type {
	ApiHandler,
	ApiStreamChunk,
	HandlerModelInfo,
	Message,
	ToolDefinition,
} from "@cline/llms";

export const ALGENTA_PROOF_PROVIDER_ID = "algenta-proof";
export const ALGENTA_PROOF_MODEL_ID = "algenta/gpt-proof-model";
export const ALGENTA_PROOF_API_KEY_ENV = "ALGENTA_PROOF_API_KEY";

const DEFAULT_TARGET_FILE = "proof-target.txt";
const TARGET_FILE_PATTERN = /(?:^|\n)\s*TARGET_FILE\s*=\s*([^\n\r]+)/i;

const MODEL_INFO = {
	id: ALGENTA_PROOF_MODEL_ID,
	name: "Algenta Deterministic Proof Model",
	contextWindow: 16_384,
	maxInputTokens: 16_384,
	maxTokens: 2_048,
	capabilities: ["tools", "streaming", "prompt-cache"] as const,
	apiFormat: "default" as const,
	systemRole: "system" as const,
	status: "active" as const,
	family: "algenta-proof",
};

type ProofStep =
	| {
			toolName: "localize";
			arguments: { issue: string; changed_files: string[]; failing_tests: string[] };
			usage: { inputTokens: number; outputTokens: number; cacheWriteTokens?: number };
	  }
	| {
			toolName: "graph_query";
			arguments: { file_path: string; direction: "both" };
			usage: { inputTokens: number; outputTokens: number; cacheReadTokens: number };
	  }
	| {
			toolName: "apply_patch";
			arguments: { input: string };
			usage: { inputTokens: number; outputTokens: number; cacheReadTokens: number };
	  }
	| {
			toolName: "simulate_patch";
			arguments: { confidence: number };
			usage: { inputTokens: number; outputTokens: number; cacheReadTokens: number };
	  }
	| {
			finalText: string;
			usage: { inputTokens: number; outputTokens: number; cacheReadTokens: number };
	  };

let providerRegistered = false;
let streamSequence = 0;

function nextStreamId(): string {
	streamSequence += 1;
	return `algenta_proof_${streamSequence}`;
}

function collectCompletedToolResults(messages: Message[]): Set<string> {
	const completed = new Set<string>();
	for (const message of messages) {
		for (const part of message.content ?? []) {
			if (
				part &&
				typeof part === "object" &&
				"type" in part &&
				part.type === "tool_result" &&
				"name" in part &&
				typeof part.name === "string"
			) {
				completed.add(part.name);
			}
		}
	}
	return completed;
}

function latestUserText(messages: Message[]): string {
	for (let index = messages.length - 1; index >= 0; index -= 1) {
		const message = messages[index];
		if (message.role !== "user") {
			continue;
		}
		const text = message.content
			.map((part) =>
				part && typeof part === "object" && "type" in part && part.type === "text"
					? ("text" in part && typeof part.text === "string" ? part.text : "")
					: "",
			)
			.join("\n")
			.trim();
		if (text) {
			return text;
		}
	}
	return "";
}

function ensureToolAvailable(tools: ToolDefinition[] | undefined, toolName: string): void {
	if (!tools?.some((tool) => tool.name === toolName)) {
		const available = tools?.map((tool) => tool.name).sort().join(", ") || "none";
		throw new Error(
			`Algenta proof provider requires tool '${toolName}', but it is not available in the runtime (available: ${available}).`,
		);
	}
}

function resolveTargetFile(messages: Message[]): string {
	const latestPrompt = latestUserText(messages);
	const match = latestPrompt.match(TARGET_FILE_PATTERN);
	const candidate = match?.[1]?.trim();
	return candidate || DEFAULT_TARGET_FILE;
}

function proofPatchInput(targetFile: string): string {
	return [
		"*** Begin Patch",
		`*** Update File: ${targetFile}`,
		"@@",
		" alpha",
		"+beta",
		"*** End Patch",
	].join("\n");
}

function resolveProofStep(messages: Message[], tools: ToolDefinition[] | undefined): ProofStep {
	const latestPrompt = latestUserText(messages).toLowerCase();
	const targetFile = resolveTargetFile(messages);
	if (latestPrompt.includes("prime runtime extensions")) {
		return {
			finalText: "Algenta proof runtime primed. Continue to execute the tool sequence.",
			usage: {
				inputTokens: 48,
				outputTokens: 12,
				cacheWriteTokens: 8,
			},
		};
	}
	const completed = collectCompletedToolResults(messages);
	if (!completed.has("localize")) {
		ensureToolAvailable(tools, "localize");
		return {
			toolName: "localize",
			arguments: {
				issue: "Prove the live Algenta engine-backed plugin plane for parity.",
				changed_files: [targetFile],
				failing_tests: ["tests/test_cline_live_run_proof.py"],
			},
			usage: {
				inputTokens: 120,
				outputTokens: 24,
				cacheWriteTokens: 64,
			},
		};
	}
	if (!completed.has("graph_query")) {
		ensureToolAvailable(tools, "graph_query");
		return {
			toolName: "graph_query",
			arguments: { file_path: targetFile, direction: "both" },
			usage: {
				inputTokens: 128,
				outputTokens: 20,
				cacheReadTokens: 18,
			},
		};
	}
	if (!completed.has("apply_patch")) {
		ensureToolAvailable(tools, "apply_patch");
		return {
			toolName: "apply_patch",
			arguments: { input: proofPatchInput(targetFile) },
			usage: {
				inputTokens: 140,
				outputTokens: 26,
				cacheReadTokens: 24,
			},
		};
	}
	if (!completed.has("simulate_patch")) {
		ensureToolAvailable(tools, "simulate_patch");
		return {
			toolName: "simulate_patch",
			arguments: { confidence: 0.99 },
			usage: {
				inputTokens: 152,
				outputTokens: 22,
				cacheReadTokens: 32,
			},
		};
	}
	return {
		finalText: "Algenta live proof run completed.",
		usage: {
			inputTokens: 160,
			outputTokens: 14,
			cacheReadTokens: 40,
		},
	};
}

class AlgentaProofHandler implements ApiHandler {
	readonly #modelInfo: HandlerModelInfo;

	constructor(modelId: string) {
		this.#modelInfo = {
			id: modelId,
			info: { ...MODEL_INFO, id: modelId },
		};
	}

	getMessages(systemPrompt: string, messages: Message[]): unknown {
		return { systemPrompt, messages };
	}

	getModel(): HandlerModelInfo {
		return this.#modelInfo;
	}

	async *createMessage(
		_systemPrompt: string,
		messages: Message[],
		tools?: ToolDefinition[],
	): AsyncGenerator<ApiStreamChunk> {
		const streamId = nextStreamId();
		const step = resolveProofStep(messages, tools);
		yield {
			type: "usage",
			id: streamId,
			inputTokens: step.usage.inputTokens,
			outputTokens: step.usage.outputTokens,
			cacheReadTokens: step.usage.cacheReadTokens,
			cacheWriteTokens: step.usage.cacheWriteTokens,
			totalCost: 0,
		};

		if ("toolName" in step) {
			yield {
				type: "tool_calls",
				id: streamId,
				tool_call: {
					call_id: `${streamId}_${step.toolName}`,
					function: {
						id: `${streamId}_${step.toolName}`,
						name: step.toolName,
						arguments: step.arguments,
					},
				},
			};
			return;
		}

		yield {
			type: "text",
			id: streamId,
			text: step.finalText,
		};
		yield {
			type: "done",
			id: streamId,
			success: true,
		};
	}
}

export function ensureAlgentaProofProviderRegistered(): void {
	if (providerRegistered) {
		return;
	}
	Llms.registerProvider({
		provider: {
			id: ALGENTA_PROOF_PROVIDER_ID,
			name: "Algenta Proof Provider",
			description:
				"Deterministic proof-only provider that drives the vendored Cline runtime through a fixed tool sequence.",
			defaultModelId: ALGENTA_PROOF_MODEL_ID,
			env: [ALGENTA_PROOF_API_KEY_ENV],
			client: "custom",
			source: "system",
		},
		models: {},
	});
	Llms.registerModel(
		ALGENTA_PROOF_PROVIDER_ID,
		ALGENTA_PROOF_MODEL_ID,
		MODEL_INFO,
	);
	Llms.registerHandler(ALGENTA_PROOF_PROVIDER_ID, (config) => {
		const modelId =
			typeof config.modelId === "string" && config.modelId.trim()
				? config.modelId
				: ALGENTA_PROOF_MODEL_ID;
		return new AlgentaProofHandler(modelId);
	});
	providerRegistered = true;
}
