export type SessionChannel = "api" | "cli" | "mcp" | "github" | "test";

export type ApprovalProfile =
	| "repository_review"
	| "repository_fix_gated"
	| "local_validation"
	| "ci_controlled_repo_automation";

export type TerminalState =
	| "runtime_invalid"
	| "policy_denied"
	| "plugin_evidence_missing"
	| "engine_evidence_missing"
	| "apply_blocked"
	| "aborted"
	| "stopped"
	| "failed"
	| "succeeded";

export type SessionLifecycleState =
	| "created"
	| "started"
	| "running"
	| "completed"
	| "failed"
	| "aborted"
	| "stopped"
	| "deleted";

export type ToolPolicy = { enabled?: boolean; autoApprove?: boolean };

export interface CanonicalEvent {
	schema_version: "cline-session-event/v1";
	event_id: string;
	event_index: number;
	session_id: string;
	observed_at: string;
	event_type: string;
	payload: Record<string, unknown>;
}

export interface ApprovalEventRecord {
	tool: string;
	decision: "approved" | "denied";
	reason: string;
	auto_approved: boolean;
}

export interface ToolCallEvidence {
	count: number;
	first_event_id: string | null;
	last_event_id: string | null;
	statuses: string[];
}

export interface GovernHookEvidence {
	status: "disabled" | "unobserved" | "observed";
	verdict?: string;
	event_id?: string;
	policy_version?: string;
}

export interface SessionArtifacts {
	runtime_manifest?: string;
	messages?: string;
	usage?: string;
	events_ndjson?: string;
	tool_calls?: string;
	approvals?: string;
	gate?: string;
}

export interface SessionAuthorization {
	caller: string;
	workflow_identity: string | null;
	repository_allowed: boolean;
	branch_allowed: boolean;
}

export interface SessionEngineConfig {
	enabled: boolean;
	url?: string;
	repositoryId?: string;
	snapshotId?: string;
	apiKey?: string;
	requiredTools: string[];
	expectedCalls: string[];
	failOnZeroCalls: boolean;
	requireGovernHook: boolean;
}

export interface SessionPolicy {
	profile: ApprovalProfile;
	requestedPolicy: Record<string, unknown>;
	effectivePolicy: Record<string, unknown>;
	toolPolicies: Record<string, ToolPolicy>;
	allowedWriteScope: string[];
	disallowedWriteScope: string[];
	wildcardAutoApproveUsed: boolean;
}

export interface SessionRecord {
	sessionId: string;
	agentRunId: string;
	owner: string;
	channel: SessionChannel;
	repositoryScope: string;
	approvalProfile: ApprovalProfile;
	idempotencyKey: string | null;
	replayOfRunId: string | null;
	workingDir: string;
	prompt: string;
	injectedContext: string;
	provider?: string;
	model?: string;
	// B10 PR11b: per-tenant LLM provider key (server-derived from the authenticated org) + the
	// fail-closed flag. Never returned by toPublicSession (key material stays server-side).
	providerApiKey?: string;
	requireProviderApiKey?: boolean;
	baseUrl?: string;
	headers?: Record<string, string>;
	toolProfile?: string;
	suppressExploration: boolean;
	enableSpawnAgent: boolean;
	enableAgentTeams: boolean;
	limits?: { maxIterations?: number; timeoutMs?: number };
	engine: SessionEngineConfig;
	policy: SessionPolicy;
	authorization: SessionAuthorization;
	state: SessionLifecycleState;
	createdAt: string;
	updatedAt: string;
	events: CanonicalEvent[];
	artifacts: SessionArtifacts;
	secondaryReasons: string[];
	terminalState: TerminalState | null;
	approvalEvents: ApprovalEventRecord[];
	cline?: import("@cline/core").ClineCore;
	unsubscribe?: () => void;
	startedSession?: {
		sessionId: string;
		manifestPath: string;
		messagesPath: string;
	};
	lastResult?: Record<string, unknown>;
	lastUsage?: Record<string, number>;
	lastMessages?: unknown[];
	manifestError?: string;
}

export interface RuntimeIdentity {
	bootId: string;
	entrypoint: string;
}

export const HOST = "127.0.0.1";

export const DEFAULT_CHANNEL: SessionChannel = "api";

export const DEFAULT_APPROVAL_PROFILE: ApprovalProfile = "repository_fix_gated";

export const EXPLORATION_TOOLS = [
	"read_files",
	"search_codebase",
	"fetch_web_content",
	"ask_question",
];

export const DEFAULT_APPROVAL_PROFILES: Record<
	ApprovalProfile,
	{
		allowedTools: string[];
		allowedWriteScope: string[];
		allowSpawnAgent: boolean;
		allowAgentTeams: boolean;
	}
> = {
	repository_review: {
		allowedTools: [
			"read_files",
			"search_codebase",
			"fetch_web_content",
			"skills",
			"ask_question",
		],
		allowedWriteScope: [],
		allowSpawnAgent: false,
		allowAgentTeams: false,
	},
	repository_fix_gated: {
		allowedTools: [
			"read_files",
			"search_codebase",
			"fetch_web_content",
			"editor",
			"apply_patch",
			"skills",
			"localize",
			"graph_query",
			"simulate_patch",
		],
		allowedWriteScope: ["patch_artifact", "bot_branch"],
		allowSpawnAgent: false,
		allowAgentTeams: false,
	},
	local_validation: {
		allowedTools: [
			"read_files",
			"search_codebase",
			"fetch_web_content",
			"run_commands",
			"editor",
			"apply_patch",
			"skills",
			"localize",
			"graph_query",
			"simulate_patch",
		],
		allowedWriteScope: ["patch_artifact", "working_tree"],
		allowSpawnAgent: false,
		allowAgentTeams: false,
	},
	ci_controlled_repo_automation: {
		allowedTools: [
			"read_files",
			"search_codebase",
			"fetch_web_content",
			"run_commands",
			"editor",
			"apply_patch",
			"skills",
			"localize",
			"graph_query",
			"simulate_patch",
			"spawn_agent",
		],
		allowedWriteScope: [
			"patch_artifact",
			"bot_branch",
			"pr_comment",
			"check_summary",
		],
		allowSpawnAgent: true,
		allowAgentTeams: true,
	},
};

export const TERMINAL_PRECEDENCE: TerminalState[] = [
	"runtime_invalid",
	"policy_denied",
	"plugin_evidence_missing",
	"engine_evidence_missing",
	"apply_blocked",
	"aborted",
	"stopped",
	"failed",
	"succeeded",
];
