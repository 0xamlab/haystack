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
import { type EngineContext, engineContext } from "../tools";
import {
	appendSessionEvent,
	optionalString,
	updateSessionTimestamp,
} from "./utils";

// Per-run engine config (B3/PR8): build the engine context for THIS session. No
// process-global env, no activeEngineSessionId mutex — each run threads its own context
// via AsyncLocalStorage (engineContext.run), so concurrent engine-backed sessions are
// fully isolated: no cross-tenant API-key bleed and no serialization.
function engineContextFor(session: SessionRecord): EngineContext | null {
	if (!session.engine.enabled || !session.engine.url) {
		return null;
	}
	return {
		url: session.engine.url,
		repositoryId: session.engine.repositoryId || "",
		snapshotId: session.engine.snapshotId || "",
		apiKey: session.engine.apiKey || "",
		workingDir: session.workingDir,
	};
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
	const engine = engineContextFor(session);
	const runArgs: RunAgentArgs = {
		working_dir: session.workingDir,
		prompt: session.prompt,
		injected_context: session.injectedContext,
		provider: session.provider,
		model: session.model,
		provider_api_key: session.providerApiKey,
		require_provider_api_key: session.requireProviderApiKey,
		base_url: session.baseUrl,
		headers: session.headers,
		suppress_exploration: session.suppressExploration,
		tool_profile: session.toolProfile,
		limits: session.limits,
		enable_spawn_agent: session.enableSpawnAgent,
		enable_agent_teams: session.enableAgentTeams,
		// gates the Algenta tools/govern-hook in buildStartConfig (engineEnabled)
		engine: engine ? { enabled: true, ...engine } : undefined,
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

/**
 * Enforce the per-turn timeout budget at the server layer (Wave A1). The SDK
 * runtime host does not currently honor `timeoutMs` (the 14-minute hang); race the
 * send against the budget and best-effort abort the run so a stuck/looping turn
 * surfaces a clean timeout instead of holding the single process. B-wave moves this
 * onto a provider-level AbortController.
 */
async function sendTurnWithTimeout(
	session: SessionRecord,
	prompt: string,
	timeoutMs: number,
): Promise<Record<string, unknown> | undefined> {
	const send = (
		session.cline as unknown as {
			send: (input: {
				sessionId: string;
				prompt: string;
				mode: "act";
				timeoutMs?: number;
			}) => Promise<Record<string, unknown> | undefined>;
		}
	).send({ sessionId: session.sessionId, prompt, mode: "act", timeoutMs });

	let timer: ReturnType<typeof setTimeout> | undefined;
	const timeout = new Promise<never>((_, reject) => {
		timer = setTimeout(() => {
			// best-effort: stop the underlying run so it isn't left burning tokens
			Promise.resolve(session.cline?.abort(session.sessionId)).catch(() => undefined);
			reject(new Error(`turn exceeded timeout budget of ${timeoutMs}ms`));
		}, timeoutMs);
	});
	try {
		return await Promise.race([send, timeout]);
	} finally {
		if (timer) clearTimeout(timer);
	}
}

export async function runSessionTurn(
	context: ExecutionContext,
	session: SessionRecord,
	prompt: string,
): Promise<SessionRecord> {
	if (!session.cline) {
		throw new Error("session has not been started");
	}
	session.state = "running";
	updateSessionTimestamp(session);
	appendSessionEvent(session, "session.turn_requested", { prompt });
	// Run the turn (and the tool calls it triggers) inside this session's engine context
	// so the Algenta tools read THIS run's engine URL/key — never a shared global.
	const engine = engineContextFor(session);
	const runTurn = () => sendTurnWithTimeout(session, prompt, session.limits?.timeoutMs ?? 150000);
	const result = engine ? await engineContext.run(engine, runTurn) : await runTurn();
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
}
