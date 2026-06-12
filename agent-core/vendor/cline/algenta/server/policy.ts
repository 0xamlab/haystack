import crypto from "node:crypto";
import type { RunAgentArgs } from "../adapter";
import {
	DEFAULT_APPROVAL_PROFILE,
	DEFAULT_APPROVAL_PROFILES,
	DEFAULT_CHANNEL,
	EXPLORATION_TOOLS,
	type SessionAuthorization,
	type SessionChannel,
	type SessionEngineConfig,
	type SessionPolicy,
	type SessionRecord,
	type ToolPolicy,
} from "./contracts";
import {
	asRecord,
	booleanValue,
	buildPrompt,
	ensureEnumValue,
	normalizeLimits,
	optionalString,
	stringArray,
	requiredString,
} from "./utils";

function disabledToolPolicy(): ToolPolicy {
	return { enabled: false, autoApprove: false };
}

function enabledToolPolicy(): ToolPolicy {
	return { enabled: true, autoApprove: true };
}

function suppressedToolsForArgs(args: RunAgentArgs): string[] {
	switch (args.tool_profile) {
		case "no_exploration_no_shell":
			return [...EXPLORATION_TOOLS, "run_commands"];
		case "no_exploration_local_validation":
			return [...EXPLORATION_TOOLS];
		default:
			return args.suppress_exploration ? [...EXPLORATION_TOOLS] : [];
	}
}

function requestedToolPolicies(value: unknown): Record<string, ToolPolicy> {
	const input = asRecord(value);
	const output: Record<string, ToolPolicy> = {};
	for (const [toolName, policyValue] of Object.entries(input)) {
		const policy = asRecord(policyValue);
		const next: ToolPolicy = {};
		if (typeof policy.enabled === "boolean") next.enabled = policy.enabled;
		if (typeof policy.autoApprove === "boolean") {
			next.autoApprove = policy.autoApprove;
		}
		if (Object.keys(next).length > 0) {
			output[toolName] = next;
		}
	}
	return output;
}

export function resolveAuthorization(
	payload: Record<string, unknown>,
): SessionAuthorization {
	const input = asRecord(payload.authorization);
	return {
		caller:
			optionalString(input.caller) ||
			optionalString(payload.caller) ||
			"local_user",
		workflow_identity:
			optionalString(input.workflow_identity) ||
			optionalString(payload.workflow_identity) ||
			null,
		repository_allowed:
			typeof input.repository_allowed === "boolean"
				? input.repository_allowed
				: true,
		branch_allowed:
			typeof input.branch_allowed === "boolean" ? input.branch_allowed : true,
	};
}

export function resolveSessionPolicy(
	payload: Record<string, unknown>,
	args: RunAgentArgs,
): SessionPolicy {
	// B7 fail-closed: a present-but-unrecognized approval_profile must NOT silently fall
	// back to a write-capable default — an authorization typo can't be allowed to grant
	// write tools. The documented default applies only when approval_profile is absent.
	const APPROVAL_PROFILES = [
		"repository_review",
		"repository_fix_gated",
		"local_validation",
		"ci_controlled_repo_automation",
	] as const;
	const rawProfile = optionalString(payload.approval_profile);
	if (rawProfile && !(APPROVAL_PROFILES as readonly string[]).includes(rawProfile)) {
		throw new Error(`unknown approval_profile: ${rawProfile}`);
	}
	const profile = (rawProfile as (typeof APPROVAL_PROFILES)[number]) || DEFAULT_APPROVAL_PROFILE;
	const defaults = DEFAULT_APPROVAL_PROFILES[profile];
	const requestedWriteScope = stringArray(payload.allowed_write_scope);
	const effectiveWriteScope =
		requestedWriteScope.length > 0
			? requestedWriteScope
			: [...defaults.allowedWriteScope];
	for (const scope of effectiveWriteScope) {
		if (!defaults.allowedWriteScope.includes(scope)) {
			throw new Error(
				`allowed_write_scope may only reduce profile permissions (${profile}).`,
			);
		}
	}
	if (booleanValue(payload.enable_spawn_agent) && !defaults.allowSpawnAgent) {
		throw new Error(
			`enable_spawn_agent is not allowed for approval_profile=${profile}.`,
		);
	}
	if (booleanValue(payload.enable_agent_teams) && !defaults.allowAgentTeams) {
		throw new Error(
			`enable_agent_teams is not allowed for approval_profile=${profile}.`,
		);
	}

	const policies: Record<string, ToolPolicy> = {
		"*": disabledToolPolicy(),
	};
	for (const toolName of defaults.allowedTools) {
		policies[toolName] = enabledToolPolicy();
	}
	for (const toolName of suppressedToolsForArgs(args)) {
		policies[toolName] = disabledToolPolicy();
	}
	if (profile === "repository_review") {
		policies.editor = disabledToolPolicy();
		policies.apply_patch = disabledToolPolicy();
		policies.run_commands = disabledToolPolicy();
		policies.localize = disabledToolPolicy();
		policies.graph_query = disabledToolPolicy();
		policies.simulate_patch = disabledToolPolicy();
	}

	const requestedPolicies = requestedToolPolicies(payload.tool_policies);
	for (const [toolName, requested] of Object.entries(requestedPolicies)) {
		const current = policies[toolName] ?? disabledToolPolicy();
		if (requested.enabled === true && current.enabled !== true) {
			throw new Error(
				`tool_policies may not enable disallowed tool '${toolName}'.`,
			);
		}
		if (requested.autoApprove === true && current.autoApprove !== true) {
			throw new Error(
				`tool_policies may not increase auto-approval for '${toolName}'.`,
			);
		}
		policies[toolName] = {
			enabled: requested.enabled === false ? false : current.enabled,
			autoApprove:
				requested.autoApprove === false ? false : current.autoApprove,
		};
	}

	return {
		profile,
		requestedPolicy: {
			tool_policies: requestedPolicies,
			allowed_write_scope: requestedWriteScope,
			approval_mode: optionalString(payload.approval_mode) || null,
		},
		effectivePolicy: {
			tool_policies: policies,
			allowed_write_scope: effectiveWriteScope,
			disallowed_write_scope: [
				"default_branch",
				"unrelated_branches",
				"workflow_files",
				"secrets_config",
			],
		},
		toolPolicies: policies,
		allowedWriteScope: effectiveWriteScope,
		disallowedWriteScope: [
			"default_branch",
			"unrelated_branches",
			"workflow_files",
			"secrets_config",
		],
		wildcardAutoApproveUsed: false,
	};
}

export function resolveEngineConfig(
	payload: Record<string, unknown>,
): SessionEngineConfig {
	const taskSpec = asRecord(payload.task_spec);
	const source = asRecord(payload.engine);
	const taskEngine = asRecord(taskSpec.engine);
	const engine = Object.keys(source).length > 0 ? source : taskEngine;
	const url = optionalString(engine.url);
	const requiredToolsRaw = stringArray(engine.required_tools);
	// B6: when engine mode is on but the caller didn't pin required tools, require the
	// engine to actually be exercised — default to simulate_patch so a real engine-mode
	// run that never calls the engine fails with engine_evidence_missing instead of
	// silently "succeeding" (the production verified_agentic path sends no required_tools).
	const requiredTools = url && requiredToolsRaw.length === 0 ? ["simulate_patch"] : requiredToolsRaw;
	const expectedCalls = stringArray(engine.expected_calls);
	return {
		enabled: Boolean(url),
		url,
		repositoryId:
			optionalString(engine.repository_id) ||
			optionalString(payload.repository_scope),
		snapshotId: optionalString(engine.snapshot_id),
		apiKey: optionalString(engine.api_key),
		requiredTools,
		expectedCalls,
		failOnZeroCalls:
			booleanValue(engine.fail_on_zero_calls, requiredTools.length > 0),
		requireGovernHook: booleanValue(
			engine.require_govern_hook,
			Boolean(url),
		),
	};
}

export function normalizeSessionPayload(
	payload: Record<string, unknown>,
	owner: string,
): SessionRecord {
	const taskSpec = asRecord(payload.task_spec);
	const engine = resolveEngineConfig(payload);
	const args: RunAgentArgs = {
		working_dir: requiredString(payload.working_dir, "working_dir"),
		prompt: buildPrompt(payload),
		injected_context:
			typeof payload.injected_context === "string"
				? payload.injected_context
				: JSON.stringify(payload.injected_context ?? {}),
		provider:
			optionalString(payload.provider) ||
			optionalString(asRecord(taskSpec.engine).provider),
		model:
			optionalString(payload.model) ||
			optionalString(asRecord(taskSpec.engine).model),
		// B10 PR11b: the per-tenant provider key + fail-closed flag ride alongside provider/model
		// (top-level or under task_spec.engine, matching how the Python engine sends them).
		provider_api_key:
			optionalString(payload.provider_api_key) ||
			optionalString(asRecord(taskSpec.engine).provider_api_key),
		require_provider_api_key:
			booleanValue(payload.require_provider_api_key) ||
			booleanValue(asRecord(taskSpec.engine).require_provider_api_key),
		base_url:
			optionalString(payload.base_url) ||
			optionalString(asRecord(taskSpec.engine).base_url),
		headers:
			Object.keys(asRecord(payload.headers)).length > 0
				? (asRecord(payload.headers) as Record<string, string>)
				: undefined,
		suppress_exploration: booleanValue(payload.suppress_exploration),
		tool_profile:
			optionalString(payload.tool_profile) ||
			optionalString(taskSpec.tool_profile),
		limits: normalizeLimits(payload.limits),
		enable_spawn_agent: booleanValue(payload.enable_spawn_agent),
		enable_agent_teams: booleanValue(payload.enable_agent_teams),
	};
	const policy = resolveSessionPolicy(payload, args);
	const authorization = resolveAuthorization(payload);
	const channel = ensureEnumValue(
		payload.channel,
		["api", "cli", "mcp", "github", "test"] as const,
		"channel",
		DEFAULT_CHANNEL,
	) as SessionChannel;
	const createdAt = new Date().toISOString();
	// B6 proof-honesty / path safety: a caller-supplied session_id must be a strict,
	// path-safe token (it can otherwise traverse/collide into another run's on-disk
	// artifact dir via proofRunDir). Validate it, and — crucially — derive the artifact
	// run id (agentRunId) from a SERVER-SIDE random value, never from the caller, so the
	// artifact path is never caller-controlled.
	const rawSessionId = optionalString(payload.session_id);
	if (rawSessionId && !/^[A-Za-z0-9_-]{1,64}$/.test(rawSessionId)) {
		throw new Error(
			"invalid session_id: must match ^[A-Za-z0-9_-]{1,64}$ (no path separators)",
		);
	}
	const sessionId = rawSessionId || `session_${crypto.randomUUID()}`;
	const repositoryScope =
		optionalString(payload.repository_scope) ||
		engine.repositoryId ||
		"repository_unknown";

	return {
		sessionId,
		agentRunId: `run_${crypto.randomUUID()}`,
		owner,
		channel,
		repositoryScope,
		approvalProfile: policy.profile,
		idempotencyKey: optionalString(payload.idempotency_key) || null,
		replayOfRunId: optionalString(payload.replay_of_run_id) || null,
		workingDir: args.working_dir,
		prompt: args.prompt,
		injectedContext: args.injected_context || "",
		provider: args.provider,
		model: args.model,
		providerApiKey: args.provider_api_key,
		requireProviderApiKey: Boolean(args.require_provider_api_key),
		baseUrl: args.base_url,
		headers:
			Object.keys(asRecord(payload.headers)).length > 0
				? (asRecord(payload.headers) as Record<string, string>)
				: undefined,
		toolProfile: args.tool_profile,
		suppressExploration: Boolean(args.suppress_exploration),
		enableSpawnAgent: Boolean(args.enable_spawn_agent),
		enableAgentTeams: Boolean(args.enable_agent_teams),
		limits: args.limits,
		engine,
		policy,
		authorization,
		state: "created",
		createdAt,
		updatedAt: createdAt,
		events: [],
		artifacts: {},
		secondaryReasons: [],
		terminalState: null,
		approvalEvents: [],
	};
}

export function toPublicSession(session: SessionRecord): Record<string, unknown> {
	return {
		session_id: session.sessionId,
		agent_run_id: session.agentRunId,
		owner: session.owner,
		channel: session.channel,
		repository_scope: session.repositoryScope,
		approval_profile: session.approvalProfile,
		allowed_write_scope: session.policy.allowedWriteScope,
		disallowed_write_scope: session.policy.disallowedWriteScope,
		idempotency_key: session.idempotencyKey,
		replay_of_run_id: session.replayOfRunId,
		state: session.state,
		terminal_state: session.terminalState,
		secondary_reasons: session.secondaryReasons,
		created_at: session.createdAt,
		updated_at: session.updatedAt,
		artifacts: session.artifacts,
	};
}
