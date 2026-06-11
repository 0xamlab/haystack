import type { CoreSessionEvent } from "../../sdk/packages/core/src/types/events";
import {
	createArtifactProvenance,
	type ProofRuntimeContext,
	redactSecrets,
	relativeArtifactPath,
	writeJsonArtifact,
	writeNdjsonArtifact,
} from "../proofs";
import {
	type ApprovalEventRecord,
	type GovernHookEvidence,
	type RuntimeIdentity,
	type SessionRecord,
	TERMINAL_PRECEDENCE,
	type TerminalState,
	type ToolCallEvidence,
} from "./contracts";
import {
	appendSessionEvent,
	optionalString,
	updateSessionTimestamp,
} from "./utils";

export function deriveToolCallEvidence(session: SessionRecord): {
	toolCallsByName: Record<string, ToolCallEvidence>;
	governHook: GovernHookEvidence;
} {
	const toolCallsByName: Record<string, ToolCallEvidence> = {};
	let governHook: GovernHookEvidence = session.engine.enabled
		? { status: "unobserved" }
		: { status: "disabled" };

	const touch = (toolName: string, eventId: string, status: string): void => {
		let entry = toolCallsByName[toolName];
		if (!entry) {
			entry = {
				count: 0,
				first_event_id: null,
				last_event_id: null,
				statuses: [],
			};
			toolCallsByName[toolName] = entry;
		}
		if (status === "started") entry.count += 1;
		if (!entry.first_event_id) entry.first_event_id = eventId;
		entry.last_event_id = eventId;
		if (!entry.statuses.includes(status)) entry.statuses.push(status);
	};

	// Record the govern-hook verdict from a text fragment carrying the marker.
	// Shared by the in-loop tool-output scan and the block-mode fallback below.
	const observeGateMarker = (text: string, eventId?: string): boolean => {
		if (governHook.status === "observed") return true;
		if (!text.includes("[algenta-risk-gate]")) return false;
		const verdictMatch = text.match(/recommended_action=([^\s"\\]+)/);
		governHook = {
			status: "observed",
			verdict: verdictMatch?.[1] || "unknown",
			...(eventId ? { event_id: eventId } : {}),
			policy_version: process.env.ALGENTA_GATE_MODE || "advisory",
		};
		return true;
	};

	for (const event of session.events) {
		if (event.event_type === "hook.tool_call") {
			const toolName = optionalString(event.payload.toolName);
			if (toolName) touch(toolName, event.event_id, "started");
			continue;
		}
		if (
			event.event_type === "agent.content_start" &&
			event.payload.contentType === "tool"
		) {
			const toolName = optionalString(event.payload.toolName);
			if (toolName) touch(toolName, event.event_id, "started");
			continue;
		}
		if (event.event_type === "agent.content_end") {
			if (event.payload.contentType === "tool") {
				const toolName = optionalString(event.payload.toolName);
				if (toolName) {
					touch(
						toolName,
						event.event_id,
						optionalString(event.payload.error) ? "failed" : "succeeded",
					);
				}
			}
			const rawOutput =
				typeof event.payload.output === "string"
					? event.payload.output
					: JSON.stringify(event.payload.output ?? "");
			observeGateMarker(rawOutput, event.event_id);
		}
	}

	// Block-mode gate stops short-circuit the tool-result path (the SDK ignores a
	// stopping hook's `result`; see session-runtime-orchestrator), so the
	// [algenta-risk-gate] marker can land in a stop/abort event or the final
	// result rather than in tool output. Scan those as a fallback so a gate that
	// fired-and-blocked reads as observed, not "evidence missing".
	if (session.engine.enabled && governHook.status !== "observed") {
		// Lazily scan the final result first, then events, stopping at the first
		// hit — avoids stringifying the whole event list once a match is found.
		if (!observeGateMarker(JSON.stringify(session.lastResult ?? {}))) {
			for (const event of session.events) {
				if (observeGateMarker(JSON.stringify(event.payload ?? ""))) break;
			}
		}
	}

	return { toolCallsByName, governHook };
}

export function determineTerminalState(
	session: SessionRecord,
	evidence: {
		toolCallsByName: Record<string, ToolCallEvidence>;
		governHook: GovernHookEvidence;
	},
): { terminalState: TerminalState; secondaryReasons: string[] } {
	const candidates: TerminalState[] = [];
	if (session.manifestError) {
		candidates.push("runtime_invalid");
	}
	if (
		session.channel === "github" &&
		(!session.authorization.repository_allowed ||
			!session.authorization.branch_allowed)
	) {
		candidates.push("policy_denied");
	}
	if (
		session.engine.enabled &&
		session.engine.requireGovernHook &&
		evidence.governHook.status !== "observed"
	) {
		candidates.push("plugin_evidence_missing");
	}
	if (
		session.engine.enabled &&
		session.engine.failOnZeroCalls &&
		session.engine.requiredTools.some(
			(toolName) => (evidence.toolCallsByName[toolName]?.count ?? 0) === 0,
		)
	) {
		candidates.push("engine_evidence_missing");
	}
	if (
		session.policy.allowedWriteScope.length === 0 &&
		Object.values(evidence.toolCallsByName).some((entry) =>
			entry.statuses.includes("succeeded"),
		)
	) {
		candidates.push("apply_blocked");
	}

	const finishReason = optionalString(session.lastResult?.finishReason);
	if (finishReason === "aborted") {
		candidates.push("aborted");
	} else if (session.state === "stopped") {
		candidates.push("stopped");
	} else if (finishReason === "error" || session.state === "failed") {
		candidates.push("failed");
	} else {
		candidates.push("succeeded");
	}

	for (const terminalState of TERMINAL_PRECEDENCE) {
		if (candidates.includes(terminalState)) {
			return {
				terminalState,
				secondaryReasons: candidates.filter(
					(candidate) => candidate !== terminalState,
				),
			};
		}
	}
	return { terminalState: "failed", secondaryReasons: [] };
}

export function legacyStatusForTerminalState(
	terminalState: TerminalState,
): string {
	switch (terminalState) {
		case "aborted":
			return "aborted";
		case "stopped":
			return "stopped";
		case "succeeded":
			return "completed";
		default:
			return "failed";
	}
}

export function createServerManifest(
	context: ProofRuntimeContext,
	identity: RuntimeIdentity,
): Record<string, unknown> {
	return {
		...createArtifactProvenance(
			context,
			"runtime_manifest",
			"cline-runtime-manifest/v1",
		),
		runtime: {
			kind: "cline",
			is_stub: false,
			entrypoint: identity.entrypoint,
			version: context.runtimeVersion,
			boot_id: identity.bootId,
		},
		backend: {
			mode: "local",
			provider: null,
			model: null,
			base_url_set: false,
			headers_set: false,
			headers_redacted: true,
		},
		capabilities: {
			sessions: true,
			streaming_events: true,
			approvals: true,
			plugins: true,
			mcp: false,
			automation: false,
			teams: true,
			local_models: true,
		},
		plugins: {
			localize: "conditional",
			graph_query: "conditional",
			simulate_patch: "conditional",
			govern_hook: "conditional",
		},
		engine: {
			enabled: false,
			required_tools: [],
			expected_calls: [],
			fail_on_zero_calls: false,
		},
		offline_contract_only: false,
	};
}

export function createRunManifest(
	session: SessionRecord,
	context: ProofRuntimeContext,
	identity: RuntimeIdentity,
): Record<string, unknown> {
	return {
		...createArtifactProvenance(
			context,
			session.agentRunId,
			"cline-runtime-manifest/v1",
		),
		runtime: {
			kind: "cline",
			is_stub: false,
			entrypoint: identity.entrypoint,
			version: context.runtimeVersion,
			boot_id: identity.bootId,
		},
		backend: {
			mode: "local",
			provider: session.provider || null,
			model: session.model || null,
			base_url_set: Boolean(session.baseUrl),
			headers_set: Boolean(
				session.headers && Object.keys(session.headers).length > 0,
			),
			headers_redacted: true,
		},
		capabilities: {
			sessions: true,
			streaming_events: true,
			approvals: true,
			plugins: true,
			mcp: false,
			automation: false,
			teams: session.enableAgentTeams,
			local_models: true,
		},
		plugins: {
			localize: session.engine.enabled ? "loaded" : "disabled",
			graph_query: session.engine.enabled ? "loaded" : "disabled",
			simulate_patch: session.engine.enabled ? "loaded" : "disabled",
			govern_hook: session.engine.enabled ? "loaded" : "disabled",
		},
		engine: {
			enabled: session.engine.enabled,
			url_present: Boolean(session.engine.url),
			required_tools: session.engine.requiredTools,
			expected_calls: session.engine.expectedCalls,
			fail_on_zero_calls: session.engine.failOnZeroCalls,
		},
		session: {
			session_id: session.sessionId,
			owner: session.owner,
			channel: session.channel,
			repository_scope: session.repositoryScope,
			approval_profile: session.approvalProfile,
			allowed_write_scope: session.policy.allowedWriteScope,
			disallowed_write_scope: session.policy.disallowedWriteScope,
			idempotency_key: session.idempotencyKey,
			replay_of_run_id: session.replayOfRunId,
		},
		offline_contract_only: false,
	};
}

export async function finalizeSessionArtifacts(
	session: SessionRecord,
	context: ProofRuntimeContext,
	identity: RuntimeIdentity,
): Promise<void> {
	const evidence = deriveToolCallEvidence(session);
	const gate = determineTerminalState(session, evidence);
	session.terminalState = gate.terminalState;
	session.secondaryReasons = gate.secondaryReasons;
	const manifest = createRunManifest(session, context, identity);
	// Redact secret-keyed fields (api keys, auth headers, tokens) from the
	// transcript before persisting; the artifact self-declares sensitive:true.
	const messages = redactSecrets(session.lastMessages ?? []);
	const usagePayload = {
		...createArtifactProvenance(context, session.agentRunId, "cline-usage/v1"),
		session_id: session.sessionId,
		usage: session.lastUsage ?? {},
	};
	const messagesPayload = {
		...createArtifactProvenance(
			context,
			session.agentRunId,
			"cline-messages/v1",
		),
		session_id: session.sessionId,
		sensitive: true,
		messages,
	};
	const toolCallsPayload = {
		...createArtifactProvenance(
			context,
			session.agentRunId,
			"cline-tool-calls/v1",
		),
		session_id: session.sessionId,
		tool_calls_by_name: evidence.toolCallsByName,
		govern_hook: evidence.governHook,
	};
	const approvalsPayload = {
		...createArtifactProvenance(
			context,
			session.agentRunId,
			"cline-approvals/v1",
		),
		session_id: session.sessionId,
		profile: session.approvalProfile,
		requested_policy: session.policy.requestedPolicy,
		effective_policy: session.policy.effectivePolicy,
		authorization: session.authorization,
		allowed_write_scope: session.policy.allowedWriteScope,
		disallowed_write_scope: session.policy.disallowedWriteScope,
		approval_events: session.approvalEvents,
		wildcard_auto_approve_used: session.policy.wildcardAutoApproveUsed,
	};
	const gatePayload = {
		...createArtifactProvenance(context, session.agentRunId, "cline-gate/v1"),
		session_id: session.sessionId,
		terminal_state: gate.terminalState,
		secondary_reasons: gate.secondaryReasons,
		apply_allowed:
			gate.terminalState === "succeeded" &&
			session.policy.allowedWriteScope.length > 0,
		allowed_write_scope: session.policy.allowedWriteScope,
		disallowed_write_scope: session.policy.disallowedWriteScope,
	};
	const eventRecords = session.events.map((event) => ({
		...createArtifactProvenance(
			context,
			session.agentRunId,
			"cline-session-event-record/v1",
		),
		record_type: "session_event",
		session_id: session.sessionId,
		event,
	}));

	const runtimeManifestPath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"runtime_manifest.json",
		manifest,
	);
	const messagesPath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"messages.json",
		messagesPayload,
	);
	const usagePath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"usage.json",
		usagePayload,
	);
	const toolCallsPath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"tool_calls.json",
		toolCallsPayload,
	);
	const approvalsPath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"approvals.json",
		approvalsPayload,
	);
	const gatePath = await writeJsonArtifact(
		context,
		session.agentRunId,
		"gate.json",
		gatePayload,
	);
	const eventsPath = await writeNdjsonArtifact(
		context,
		session.agentRunId,
		"events.ndjson",
		eventRecords,
	);

	session.artifacts = {
		runtime_manifest: relativeArtifactPath(context, runtimeManifestPath),
		messages: relativeArtifactPath(context, messagesPath),
		usage: relativeArtifactPath(context, usagePath),
		events_ndjson: relativeArtifactPath(context, eventsPath),
		tool_calls: relativeArtifactPath(context, toolCallsPath),
		approvals: relativeArtifactPath(context, approvalsPath),
		gate: relativeArtifactPath(context, gatePath),
	};
	updateSessionTimestamp(session);
}

export function approvalEventsForTurn(
	session: SessionRecord,
	evidence: Record<string, ToolCallEvidence>,
): ApprovalEventRecord[] {
	return Object.entries(evidence).map(([toolName, entry]) => ({
		tool: toolName,
		decision: entry.statuses.includes("failed") ? "denied" : "approved",
		reason: entry.statuses.includes("failed")
			? `tool execution failed under approval_profile=${session.approvalProfile}`
			: `allowed by approval_profile=${session.approvalProfile}`,
		auto_approved: true,
	}));
}

export function onCoreSessionEvent(
	session: SessionRecord,
	event: CoreSessionEvent,
): void {
	switch (event.type) {
		case "agent_event":
			appendSessionEvent(
				session,
				`agent.${event.payload.event.type}`,
				event.payload.event as unknown as Record<string, unknown>,
			);
			return;
		case "hook":
			appendSessionEvent(
				session,
				`hook.${event.payload.hookEventName}`,
				event.payload as unknown as Record<string, unknown>,
			);
			return;
		case "chunk":
			appendSessionEvent(
				session,
				`chunk.${event.payload.stream}`,
				event.payload,
			);
			return;
		case "status":
			appendSessionEvent(session, "status", event.payload);
			return;
		case "ended":
			appendSessionEvent(session, "ended", event.payload);
			return;
		case "session_snapshot":
			appendSessionEvent(session, "session_snapshot", event.payload);
			return;
		case "pending_prompts":
			appendSessionEvent(session, "pending_prompts", event.payload);
			return;
		case "pending_prompt_submitted":
			appendSessionEvent(session, "pending_prompt_submitted", event.payload);
			return;
		case "team_progress":
			appendSessionEvent(session, "team_progress", event.payload);
			return;
		default:
			appendSessionEvent(session, "unknown", { value: JSON.stringify(event) });
	}
}
