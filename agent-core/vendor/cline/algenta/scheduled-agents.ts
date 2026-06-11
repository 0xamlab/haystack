import crypto from "node:crypto";
import type { ClineCoreAutomationOptions } from "../sdk/packages/core/src/cline-core/types";
import {
	DEFAULT_APPROVAL_PROFILES,
	type ApprovalProfile,
	type SessionChannel,
	type ToolPolicy,
} from "./server/contracts";

const DEFAULT_CONFIG_EXTENSIONS = ["plugins", "skills"] as const;
const DEFAULT_CHANNEL: SessionChannel = "api";
const DEFAULT_APPROVAL_PROFILE: ApprovalProfile =
	"ci_controlled_repo_automation";

export type ScheduledAgentConfigExtension =
	(typeof DEFAULT_CONFIG_EXTENSIONS)[number];

export type ScheduledAgentWriteScope =
	| "patch_artifact"
	| "bot_branch"
	| "working_tree"
	| "pr_comment"
	| "check_summary";

export interface ScheduledAgentLimits {
	maxIterations?: number;
	timeoutMs?: number;
}

export interface ScheduledAgentEngineConfig {
	url?: string;
	repositoryId?: string;
	snapshotId?: string;
	apiKey?: string;
	requiredTools?: readonly string[];
	expectedCalls?: readonly string[];
	failOnZeroCalls?: boolean;
	requireGovernHook?: boolean;
}

export interface ScheduledAgentAuthorizationInput {
	caller?: string;
	workflowIdentity?: string | null;
	repositoryAllowed?: boolean;
	branchAllowed?: boolean;
}

export interface ScheduledAgentSpecInput {
	scheduleId: string;
	repositoryScope: string;
	workingDir: string;
	prompt: string;
	cronSpecsDir: string;
	workspaceRoot?: string;
	owner?: string;
	channel?: SessionChannel;
	approvalProfile?: ApprovalProfile;
	allowedWriteScope?: readonly ScheduledAgentWriteScope[];
	configExtensions?: readonly ScheduledAgentConfigExtension[];
	idempotencyKey?: string;
	replayOfRunId?: string | null;
	provider?: string;
	model?: string;
	baseUrl?: string;
	toolProfile?: string;
	injectedContext?: string;
	limits?: ScheduledAgentLimits;
	toolPolicies?: Readonly<Record<string, ToolPolicy>>;
	enableSpawnAgent?: boolean;
	enableAgentTeams?: boolean;
	engine?: ScheduledAgentEngineConfig;
	authorization?: ScheduledAgentAuthorizationInput;
	pollIntervalMs?: number;
	claimLeaseSeconds?: number;
	globalMaxConcurrency?: number;
	watcherDebounceMs?: number;
	autoStart?: boolean;
	dbPath?: string;
	cronScope?: ClineCoreAutomationOptions["cronScope"];
}

export interface ScheduledAgentManifest {
	schedule_id: string;
	owner: string;
	channel: SessionChannel;
	repository_scope: string;
	approval_profile: ApprovalProfile;
	allowed_write_scope: ScheduledAgentWriteScope[];
	config_extensions: ScheduledAgentConfigExtension[];
	idempotency_key: string;
	replay_of_run_id: string | null;
	enable_spawn_agent: boolean;
	enable_agent_teams: boolean;
}

export interface ScheduledAgentBlueprint {
	manifest: ScheduledAgentManifest;
	requestHeaders: Record<string, string>;
	automationOptions: ClineCoreAutomationOptions;
	sessionCreatePayload: Record<string, unknown>;
	runtimeBootstrap: {
		source: SessionChannel;
		interactive: false;
		localRuntime: {
			configExtensions: ScheduledAgentConfigExtension[];
		};
	};
}

function requiredString(value: string | undefined, field: string): string {
	if (typeof value !== "string" || value.trim().length === 0) {
		throw new Error(`${field} must be a non-empty string.`);
	}
	return value.trim();
}

function optionalString(value: string | null | undefined): string | undefined {
	if (typeof value !== "string") return undefined;
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : undefined;
}

function optionalPositiveInteger(
	value: number | undefined,
	field: string,
): number | undefined {
	if (value === undefined) return undefined;
	if (!Number.isInteger(value) || value <= 0) {
		throw new Error(`${field} must be a positive integer when provided.`);
	}
	return value;
}

function uniqueStrings(values: readonly string[] | undefined): string[] {
	if (!values) return [];
	const normalized = values.map((value) => requiredString(value, "list item"));
	return [...new Set(normalized)];
}

function normalizeConfigExtensions(
	input: readonly ScheduledAgentConfigExtension[] | undefined,
): ScheduledAgentConfigExtension[] {
	if (!input || input.length === 0) {
		return [...DEFAULT_CONFIG_EXTENSIONS];
	}
	const supported = new Set<ScheduledAgentConfigExtension>(
		DEFAULT_CONFIG_EXTENSIONS,
	);
	const deduped = uniqueStrings(input);
	for (const extension of deduped) {
		if (!supported.has(extension as ScheduledAgentConfigExtension)) {
			throw new Error(
				`config_extensions may only contain ${DEFAULT_CONFIG_EXTENSIONS.join(", ")}.`,
			);
		}
	}
	return deduped as ScheduledAgentConfigExtension[];
}

function normalizeWriteScope(
	profile: ApprovalProfile,
	input: readonly ScheduledAgentWriteScope[] | undefined,
): ScheduledAgentWriteScope[] {
	const allowed = DEFAULT_APPROVAL_PROFILES[profile].allowedWriteScope;
	if (!input || input.length === 0) {
		return [...allowed] as ScheduledAgentWriteScope[];
	}
	const deduped = uniqueStrings(input) as ScheduledAgentWriteScope[];
	for (const scope of deduped) {
		if (!allowed.includes(scope)) {
			throw new Error(
				`allowed_write_scope may only reduce profile permissions for ${profile}.`,
			);
		}
	}
	return deduped;
}

function normalizeLimits(
	limits: ScheduledAgentLimits | undefined,
): ScheduledAgentLimits | undefined {
	if (!limits) return undefined;
	const maxIterations = optionalPositiveInteger(
		limits.maxIterations,
		"limits.maxIterations",
	);
	const timeoutMs = optionalPositiveInteger(limits.timeoutMs, "limits.timeoutMs");
	if (maxIterations === undefined && timeoutMs === undefined) {
		return undefined;
	}
	return {
		...(maxIterations !== undefined ? { maxIterations } : {}),
		...(timeoutMs !== undefined ? { timeoutMs } : {}),
	};
}

function normalizeToolPolicies(
	input: Readonly<Record<string, ToolPolicy>> | undefined,
): Record<string, ToolPolicy> | undefined {
	if (!input) return undefined;
	const output: Record<string, ToolPolicy> = {};
	for (const [toolName, policy] of Object.entries(input)) {
		const normalizedName = requiredString(toolName, "tool_policies key");
		const next: ToolPolicy = {};
		if (typeof policy.enabled === "boolean") next.enabled = policy.enabled;
		if (typeof policy.autoApprove === "boolean") {
			next.autoApprove = policy.autoApprove;
		}
		output[normalizedName] = next;
	}
	return Object.keys(output).length > 0 ? output : undefined;
}

function normalizeAutomationOptions(
	input: ScheduledAgentSpecInput,
): ClineCoreAutomationOptions {
	const cronScope = input.cronScope ?? "workspace";
	if (!["global", "user", "workspace"].includes(cronScope)) {
		throw new Error("cronScope must be one of global, user, or workspace.");
	}
	const dbPath = optionalString(input.dbPath);
	const pollIntervalMs = optionalPositiveInteger(
		input.pollIntervalMs,
		"pollIntervalMs",
	);
	const claimLeaseSeconds = optionalPositiveInteger(
		input.claimLeaseSeconds,
		"claimLeaseSeconds",
	);
	const globalMaxConcurrency = optionalPositiveInteger(
		input.globalMaxConcurrency,
		"globalMaxConcurrency",
	);
	const watcherDebounceMs = optionalPositiveInteger(
		input.watcherDebounceMs,
		"watcherDebounceMs",
	);
	return {
		cronSpecsDir: requiredString(input.cronSpecsDir, "cronSpecsDir"),
		cronScope,
		workspaceRoot:
			optionalString(input.workspaceRoot) ||
			requiredString(input.workingDir, "workingDir"),
		...(dbPath ? { dbPath } : {}),
		...(pollIntervalMs !== undefined ? { pollIntervalMs } : {}),
		...(claimLeaseSeconds !== undefined ? { claimLeaseSeconds } : {}),
		...(globalMaxConcurrency !== undefined ? { globalMaxConcurrency } : {}),
		...(watcherDebounceMs !== undefined ? { watcherDebounceMs } : {}),
		autoStart: input.autoStart !== false,
	};
}

function normalizeEngine(
	engine: ScheduledAgentEngineConfig | undefined,
	repositoryScope: string,
): Record<string, unknown> | undefined {
	if (!engine) return undefined;
	const url = optionalString(engine.url);
	const repositoryId = optionalString(engine.repositoryId);
	const snapshotId = optionalString(engine.snapshotId);
	const apiKey = optionalString(engine.apiKey);
	const normalized = {
		...(url ? { url } : {}),
		repository_id:
			repositoryId || requiredString(repositoryScope, "repositoryScope"),
		...(snapshotId ? { snapshot_id: snapshotId } : {}),
		...(apiKey ? { api_key: apiKey } : {}),
		required_tools: uniqueStrings(engine.requiredTools),
		expected_calls: uniqueStrings(engine.expectedCalls),
		...(typeof engine.failOnZeroCalls === "boolean"
			? { fail_on_zero_calls: engine.failOnZeroCalls }
			: {}),
		...(typeof engine.requireGovernHook === "boolean"
			? { require_govern_hook: engine.requireGovernHook }
			: {}),
	};
	return Object.keys(normalized).length > 0 ? normalized : undefined;
}

function deriveIdempotencyKey(
	explicitKey: string | undefined,
	scheduleId: string,
	repositoryScope: string,
	prompt: string,
): string {
	if (explicitKey) return explicitKey;
	const digest = crypto
		.createHash("sha256")
		.update(`${scheduleId}\n${repositoryScope}\n${prompt}`)
		.digest("hex")
		.slice(0, 16);
	return `scheduled-agent:${scheduleId}:${digest}`;
}

function normalizeAuthorization(
	input: ScheduledAgentAuthorizationInput | undefined,
	owner: string,
	scheduleId: string,
): Record<string, string | boolean | null> {
	return {
		caller: optionalString(input?.caller) || owner,
		workflow_identity:
			input?.workflowIdentity === null
				? null
				: optionalString(input?.workflowIdentity) || `schedule:${scheduleId}`,
		repository_allowed:
			typeof input?.repositoryAllowed === "boolean"
				? input.repositoryAllowed
				: true,
		branch_allowed:
			typeof input?.branchAllowed === "boolean" ? input.branchAllowed : true,
	};
}

export function buildScheduledAgentBlueprint(
	input: ScheduledAgentSpecInput,
): ScheduledAgentBlueprint {
	const scheduleId = requiredString(input.scheduleId, "scheduleId");
	const repositoryScope = requiredString(input.repositoryScope, "repositoryScope");
	const workingDir = requiredString(input.workingDir, "workingDir");
	const prompt = requiredString(input.prompt, "prompt");
	const channel = input.channel ?? DEFAULT_CHANNEL;
	const approvalProfile = input.approvalProfile ?? DEFAULT_APPROVAL_PROFILE;
	const allowedWriteScope = normalizeWriteScope(
		approvalProfile,
		input.allowedWriteScope,
	);
	const configExtensions = normalizeConfigExtensions(input.configExtensions);
	const owner =
		optionalString(input.owner) || `scheduled-agent:${scheduleId}`;
	const enableSpawnAgent = input.enableSpawnAgent === true;
	const enableAgentTeams = input.enableAgentTeams === true;
	const profileDefaults = DEFAULT_APPROVAL_PROFILES[approvalProfile];
	if (enableSpawnAgent && !profileDefaults.allowSpawnAgent) {
		throw new Error(
			`enableSpawnAgent is not allowed for approval_profile=${approvalProfile}.`,
		);
	}
	if (enableAgentTeams && !profileDefaults.allowAgentTeams) {
		throw new Error(
			`enableAgentTeams is not allowed for approval_profile=${approvalProfile}.`,
		);
	}

	const automationOptions = normalizeAutomationOptions(input);
	const authorization = normalizeAuthorization(
		input.authorization,
		owner,
		scheduleId,
	);
	const idempotencyKey = deriveIdempotencyKey(
		optionalString(input.idempotencyKey),
		scheduleId,
		repositoryScope,
		prompt,
	);
	const normalizedLimits = normalizeLimits(input.limits);
	const normalizedEngine = normalizeEngine(input.engine, repositoryScope);
	const normalizedToolPolicies = normalizeToolPolicies(input.toolPolicies);
	const injectedContext = optionalString(input.injectedContext);
	const provider = optionalString(input.provider);
	const model = optionalString(input.model);
	const baseUrl = optionalString(input.baseUrl);
	const toolProfile = optionalString(input.toolProfile);
	const manifest: ScheduledAgentManifest = {
		schedule_id: scheduleId,
		owner,
		channel,
		repository_scope: repositoryScope,
		approval_profile: approvalProfile,
		allowed_write_scope: allowedWriteScope,
		config_extensions: configExtensions,
		idempotency_key: idempotencyKey,
		replay_of_run_id: input.replayOfRunId ?? null,
		enable_spawn_agent: enableSpawnAgent,
		enable_agent_teams: enableAgentTeams,
	};

	return {
		manifest,
		requestHeaders: { "x-session-owner": owner },
		automationOptions,
		sessionCreatePayload: {
			channel,
			working_dir: workingDir,
			prompt,
			repository_scope: repositoryScope,
			approval_profile: approvalProfile,
			allowed_write_scope: allowedWriteScope,
			idempotency_key: idempotencyKey,
			replay_of_run_id: input.replayOfRunId ?? null,
			...(injectedContext ? { injected_context: injectedContext } : {}),
			...(provider ? { provider } : {}),
			...(model ? { model } : {}),
			...(baseUrl ? { base_url: baseUrl } : {}),
			...(toolProfile ? { tool_profile: toolProfile } : {}),
			...(normalizedLimits ? { limits: normalizedLimits } : {}),
			...(normalizedToolPolicies
				? { tool_policies: normalizedToolPolicies }
				: {}),
			enable_spawn_agent: enableSpawnAgent,
			enable_agent_teams: enableAgentTeams,
			authorization: authorization,
			task_spec: {
				...(normalizedEngine ? { engine: normalizedEngine } : {}),
			},
		},
		runtimeBootstrap: {
			source: channel,
			interactive: false,
			localRuntime: {
				configExtensions: configExtensions,
			},
		},
	};
}

export function buildScheduledAgentManifest(
	input: ScheduledAgentSpecInput,
): ScheduledAgentManifest {
	return buildScheduledAgentBlueprint(input).manifest;
}

export function buildScheduledAgentSessionPayload(
	input: ScheduledAgentSpecInput,
): Record<string, unknown> {
	return buildScheduledAgentBlueprint(input).sessionCreatePayload;
}

export const scheduledAgentConfigExtensions = [...DEFAULT_CONFIG_EXTENSIONS];
