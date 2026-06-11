import { ClineCore } from "@cline/core";
import {
	buildStartConfig,
	type RunAgentArgs,
	resolveProviderConfig,
} from "../adapter";
import type { ProofRuntimeContext } from "../proofs";
import {
	approvalEventsForTurn,
	deriveToolCallEvidence,
	finalizeSessionArtifacts,
	onCoreSessionEvent,
} from "./artifacts";
import type { RuntimeIdentity, SessionRecord } from "./contracts";
import type { ServerState } from "./state";
import { clearBoundEngineEnvironment } from "./state";
import {
	appendSessionEvent,
	optionalString,
	updateSessionTimestamp,
} from "./utils";

function bindEngineEnvironment(
	state: ServerState,
	session: SessionRecord,
): void {
	if (!session.engine.enabled || !session.engine.url) {
		// A non-engine session must not run while another session holds the
		// process-global engine env, or it would inherit that session's
		// ALGENTA_ENGINE_URL / API key (cross-session contamination). Serialize
		// against the active engine session, symmetric with the guard below.
		if (
			state.activeEngineSessionId &&
			state.activeEngineSessionId !== session.sessionId
		) {
			throw new Error(
				`cannot start session ${session.sessionId} while engine-backed session ${state.activeEngineSessionId} holds the global engine environment`,
			);
		}
		clearBoundEngineEnvironment(state, session.sessionId);
		return;
	}
	if (
		state.activeEngineSessionId &&
		state.activeEngineSessionId !== session.sessionId
	) {
		throw new Error(
			`engine-backed session already active: ${state.activeEngineSessionId}`,
		);
	}
	process.env.ALGENTA_ENGINE_URL = session.engine.url;
	process.env.ALGENTA_REPOSITORY_ID = session.engine.repositoryId || "";
	process.env.ALGENTA_SNAPSHOT_ID = session.engine.snapshotId || "";
	process.env.ALGENTA_WORKING_DIR = session.workingDir;
	if (session.engine.apiKey) {
		process.env.ALGENTA_API_KEY = session.engine.apiKey;
	}
	state.activeEngineSessionId = session.sessionId;
}

export interface ExecutionContext {
	proofContext: ProofRuntimeContext;
	runtimeIdentity: RuntimeIdentity;
	state: ServerState;
}

export async function startSession(
	context: ExecutionContext,
	session: SessionRecord,
	promptOverride?: string,
): Promise<SessionRecord> {
	if (session.cline) {
		return session;
	}
	bindEngineEnvironment(context.state, session);
	const runArgs: RunAgentArgs = {
		working_dir: session.workingDir,
		prompt: session.prompt,
		injected_context: session.injectedContext,
		provider: session.provider,
		model: session.model,
		base_url: session.baseUrl,
		headers: session.headers,
		suppress_exploration: session.suppressExploration,
		tool_profile: session.toolProfile,
		limits: session.limits,
		enable_spawn_agent: session.enableSpawnAgent,
		enable_agent_teams: session.enableAgentTeams,
	};
	const provider = await resolveProviderConfig(runArgs);
	const cline = await ClineCore.create({
		clientName: "algenta-agent-core",
		backendMode: "local",
		toolPolicies: session.policy.toolPolicies,
	});
	const startInput = buildStartConfig(runArgs, provider);
	startInput.config.sessionId = session.sessionId;
	startInput.config.systemPrompt = `${
		startInput.config.systemPrompt
	}\n\n[ALGENTA EXECUTION POLICY]\napproval_profile=${session.approvalProfile}\nchannel=${session.channel}\nrepository_scope=${session.repositoryScope}\nallowed_write_scope=${session.policy.allowedWriteScope.join(",") || "none"}`;
	const unsubscribe = cline.subscribe((event) => {
		if (
			event.type === "ended" &&
			event.payload.sessionId !== session.sessionId
		) {
			return;
		}
		if (
			"payload" in event &&
			event.type !== "team_progress" &&
			optionalString(
				(event as { payload?: { sessionId?: string } }).payload?.sessionId,
			) &&
			(event as { payload: { sessionId?: string } }).payload.sessionId !==
				session.sessionId
		) {
			return;
		}
		onCoreSessionEvent(session, event);
	});
	session.cline = cline;
	session.unsubscribe = unsubscribe;
	appendSessionEvent(session, "session.start_requested", {
		provider: provider.providerId,
		model: provider.modelId,
	});
	const started = await cline.start(startInput);
	session.startedSession = {
		sessionId: started.sessionId,
		manifestPath: started.manifestPath,
		messagesPath: started.messagesPath,
	};
	session.provider = provider.providerId;
	session.model = provider.modelId;
	session.state = "started";
	updateSessionTimestamp(session);
	appendSessionEvent(session, "session.started", {
		session_id: started.sessionId,
		manifest_path: started.manifestPath,
		messages_path: started.messagesPath,
	});
	if (promptOverride) {
		await runSessionTurn(context, session, promptOverride);
	}
	return session;
}

export async function runSessionTurn(
	context: ExecutionContext,
	session: SessionRecord,
	prompt: string,
): Promise<SessionRecord> {
	if (!session.cline) {
		throw new Error("session has not been started");
	}
	bindEngineEnvironment(context.state, session);
	session.state = "running";
	updateSessionTimestamp(session);
	appendSessionEvent(session, "session.turn_requested", { prompt });
	const result = await (
		session.cline as unknown as {
			send: (input: {
				sessionId: string;
				prompt: string;
				mode: "act";
				timeoutMs?: number;
			}) => Promise<Record<string, unknown> | undefined>;
		}
	).send({
		sessionId: session.sessionId,
		prompt,
		mode: "act",
		timeoutMs: session.limits?.timeoutMs ?? 150000,
	});
	session.lastResult = result ?? {};
	try {
		const usage = await session.cline.getAccumulatedUsage(session.sessionId);
		session.lastUsage = usage?.aggregateUsage ?? usage?.usage ?? {};
	} catch {
		session.lastUsage = {};
	}
	try {
		session.lastMessages = await session.cline.readMessages(session.sessionId);
	} catch {
		session.lastMessages = [];
	}
	const evidence = deriveToolCallEvidence(session);
	session.approvalEvents = approvalEventsForTurn(
		session,
		evidence.toolCallsByName,
	);
	const finishReason = optionalString(result?.finishReason);
	session.state =
		finishReason === "aborted"
			? "aborted"
			: finishReason === "error"
				? "failed"
				: "completed";
	await finalizeSessionArtifacts(
		session,
		context.proofContext,
		context.runtimeIdentity,
	);
	return session;
}

export async function abortSession(
	context: ExecutionContext,
	session: SessionRecord,
): Promise<void> {
	if (session.cline) {
		await session.cline.abort(session.sessionId);
	}
	session.state = "aborted";
	updateSessionTimestamp(session);
	appendSessionEvent(session, "session.aborted", {});
	await finalizeSessionArtifacts(
		session,
		context.proofContext,
		context.runtimeIdentity,
	);
}

export async function stopSession(
	context: ExecutionContext,
	session: SessionRecord,
): Promise<void> {
	if (session.cline) {
		await session.cline.stop(session.sessionId);
	}
	session.state = "stopped";
	updateSessionTimestamp(session);
	appendSessionEvent(session, "session.stopped", {});
	await finalizeSessionArtifacts(
		session,
		context.proofContext,
		context.runtimeIdentity,
	);
}

export async function deleteSession(
	context: ExecutionContext,
	session: SessionRecord,
): Promise<void> {
	if (session.cline) {
		try {
			await session.cline.delete(session.sessionId);
		} catch {
			// Ignore delete failures; the in-memory contract remains authoritative here.
		}
	}
	try {
		session.unsubscribe?.();
	} catch {
		// Ignore cleanup failures.
	}
	context.state.sessions.delete(session.sessionId);
	if (session.idempotencyKey) {
		context.state.idempotencyIndex.delete(
			[session.channel, session.repositoryScope, session.idempotencyKey].join(
				":",
			),
		);
	}
	if (context.state.activeEngineSessionId === session.sessionId) {
		clearBoundEngineEnvironment(context.state, session.sessionId);
	}
}
