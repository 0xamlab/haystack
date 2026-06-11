import crypto from "node:crypto";
import http, { type IncomingMessage, type ServerResponse } from "node:http";
import { collectFilesChangedFromToolCalls } from "./adapter";
import { createServerManifest, legacyStatusForTerminalState, finalizeSessionArtifacts } from "./server/artifacts";
import {
	DEFAULT_CHANNEL,
	HOST,
	type RuntimeIdentity,
	type SessionRecord,
} from "./server/contracts";
import { abortSession, deleteSession, runSessionTurn, startSession, stopSession, type ExecutionContext } from "./server/execution";
import { jsonError, jsonResponse, ndjsonResponse, readJsonBody, requireSession, routeMatch, sseResponse } from "./server/http";
import { normalizeSessionPayload, toPublicSession } from "./server/policy";
import { createServerState } from "./server/state";
import { appendSessionEvent, createIdempotencyKey, optionalString, sessionOwnerForRequest, requiredString } from "./server/utils";
import { loadProofRuntimeContext, proofRunDir, repoRootFromImportMeta } from "./proofs";

const PORT = Number(process.env.AGENT_CORE_PORT || process.argv[2] || 0);
const ROOT_DIR = repoRootFromImportMeta(import.meta.url);
const PROOF_CONTEXT = await loadProofRuntimeContext(ROOT_DIR);
const RUNTIME_IDENTITY: RuntimeIdentity = {
	bootId: crypto.randomUUID(),
	entrypoint: "agent-core/vendor/cline/algenta/run-server.ts",
};
const SERVER_STATE = createServerState();
const EXECUTION_CONTEXT: ExecutionContext = {
	proofContext: PROOF_CONTEXT,
	runtimeIdentity: RUNTIME_IDENTITY,
	state: SERVER_STATE,
};

async function handleCreateSession(
	request: IncomingMessage,
	response: ServerResponse,
): Promise<void> {
	let payload: Record<string, unknown>;
	try {
		payload = await readJsonBody(request);
	} catch (error) {
		jsonError(response, 400, "invalid_json", String(error));
		return;
	}
	try {
		const owner = optionalString(payload.owner) || sessionOwnerForRequest(request);
		const session = normalizeSessionPayload(payload, owner);
		if (
			session.channel === "github" &&
			(!session.authorization.repository_allowed ||
				!session.authorization.branch_allowed)
		) {
			session.manifestError =
				"github authorization denied for repository or branch scope";
		}
		appendSessionEvent(session, "session.created", {
			owner: session.owner,
			channel: session.channel,
			repository_scope: session.repositoryScope,
			approval_profile: session.approvalProfile,
		});
		const existingKey = createIdempotencyKey(session);
		if (existingKey && SERVER_STATE.idempotencyIndex.has(existingKey)) {
			const existing = SERVER_STATE.sessions.get(
				SERVER_STATE.idempotencyIndex.get(existingKey)!,
			);
			if (existing) {
				jsonResponse(response, 200, toPublicSession(existing));
				return;
			}
		}
		SERVER_STATE.sessions.set(session.sessionId, session);
		if (existingKey) {
			SERVER_STATE.idempotencyIndex.set(existingKey, session.sessionId);
		}
		jsonResponse(response, 201, toPublicSession(session));
	} catch (error) {
		jsonError(response, 400, "session_invalid", String(error));
	}
}

async function handleRunCompatibility(
	request: IncomingMessage,
	response: ServerResponse,
): Promise<void> {
	let payload: Record<string, unknown>;
	try {
		payload = await readJsonBody(request);
	} catch (error) {
		ndjsonResponse(response, [
			{ type: "final", status: "failed", error: String(error) },
		]);
		return;
	}
	try {
		const owner = optionalString(payload.owner) || sessionOwnerForRequest(request);
		const session = normalizeSessionPayload(payload, owner);
		appendSessionEvent(session, "session.created", {
			owner: session.owner,
			channel: session.channel,
			repository_scope: session.repositoryScope,
			approval_profile: session.approvalProfile,
		});
		SERVER_STATE.sessions.set(session.sessionId, session);
		const idempotencyKey = createIdempotencyKey(session);
		if (idempotencyKey) {
			SERVER_STATE.idempotencyIndex.set(idempotencyKey, session.sessionId);
		}
		await startSession(EXECUTION_CONTEXT, session, session.prompt);
		const finalUsage = session.lastUsage ?? {};
		const finalResult = session.lastResult ?? {};
		const finalFrame = {
			type: "final",
			status: legacyStatusForTerminalState(session.terminalState ?? "failed"),
			terminal_state: session.terminalState,
			secondary_reasons: session.secondaryReasons,
			agent_run_id: session.agentRunId,
			session_id: session.sessionId,
			transcript_ref: session.artifacts.messages || null,
			working_tree_diff: null,
			telemetry: {
				turns:
					typeof finalResult.iterations === "number"
						? finalResult.iterations
						: 0,
				tokens_in_uncached: finalUsage.inputTokens ?? 0,
				tokens_out: finalUsage.outputTokens ?? 0,
				cache_read_tokens: finalUsage.cacheReadTokens ?? 0,
				cache_write_tokens: finalUsage.cacheWriteTokens ?? 0,
				total_cost: finalUsage.totalCost ?? 0,
				provider: session.provider || null,
				model: session.model || null,
			},
			files_changed: collectFilesChangedFromToolCalls(
				finalResult.toolCalls as
					| { name: string; input?: unknown; error?: string }[]
					| undefined,
			),
			text: typeof finalResult.text === "string" ? finalResult.text : "",
			artifacts: session.artifacts,
		};
		ndjsonResponse(response, [...session.events, finalFrame]);
	} catch (error) {
		ndjsonResponse(response, [
			{
				type: "final",
				status: "failed",
				terminal_state: "runtime_invalid",
				error: String(error),
			},
		]);
	}
}

async function handleStart(
	request: IncomingMessage,
	response: ServerResponse,
	session: SessionRecord,
): Promise<void> {
	try {
		const payload = await readJsonBody(request);
		const promptOverride = optionalString(payload.prompt) || session.prompt;
		await startSession(EXECUTION_CONTEXT, session, promptOverride);
		jsonResponse(response, 200, toPublicSession(session));
	} catch (error) {
		session.manifestError = String(error);
		await finalizeSessionArtifacts(
			session,
			PROOF_CONTEXT,
			RUNTIME_IDENTITY,
		).catch(() => undefined);
		jsonError(response, 409, "session_start_failed", String(error), {
			session_id: session.sessionId,
		});
	}
}

async function handleTurn(
	request: IncomingMessage,
	response: ServerResponse,
	session: SessionRecord,
): Promise<void> {
	try {
		const payload = await readJsonBody(request);
		const prompt = requiredString(payload.prompt, "prompt");
		if (!session.cline) {
			await startSession(EXECUTION_CONTEXT, session);
		}
		await runSessionTurn(EXECUTION_CONTEXT, session, prompt);
		jsonResponse(response, 200, toPublicSession(session));
	} catch (error) {
		session.manifestError = String(error);
		await finalizeSessionArtifacts(
			session,
			PROOF_CONTEXT,
			RUNTIME_IDENTITY,
		).catch(() => undefined);
		jsonError(response, 409, "session_turn_failed", String(error), {
			session_id: session.sessionId,
		});
	}
}

const server = http.createServer(async (request, response) => {
	const { path, parts } = routeMatch(request, HOST);

	if (request.method === "GET" && path === "/health") {
		jsonResponse(response, 200, {
			status: "ok",
			runtime: {
				kind: "cline",
				is_stub: false,
				boot_id: RUNTIME_IDENTITY.bootId,
			},
		});
		return;
	}

	if (request.method === "GET" && path === "/manifest") {
		jsonResponse(response, 200, createServerManifest(PROOF_CONTEXT, RUNTIME_IDENTITY));
		return;
	}

	if (request.method === "POST" && path === "/run") {
		await handleRunCompatibility(request, response);
		return;
	}

	if (request.method === "POST" && path === "/sessions") {
		await handleCreateSession(request, response);
		return;
	}

	if (request.method === "GET" && path === "/sessions") {
		const owner = sessionOwnerForRequest(request);
		const rows = [...SERVER_STATE.sessions.values()]
			.filter((session) => session.owner === owner)
			.map((session) => toPublicSession(session));
		jsonResponse(response, 200, { sessions: rows });
		return;
	}

	if (parts[0] === "sessions" && parts[1]) {
		const session = requireSession(request, response, SERVER_STATE, parts[1]);
		if (!session) return;

		if (request.method === "GET" && parts.length === 2) {
			jsonResponse(response, 200, toPublicSession(session));
			return;
		}

		if (request.method === "POST" && parts[2] === "start") {
			await handleStart(request, response, session);
			return;
		}

		if (request.method === "POST" && parts[2] === "turns") {
			await handleTurn(request, response, session);
			return;
		}

		if (request.method === "GET" && parts[2] === "messages") {
			jsonResponse(response, 200, {
				session_id: session.sessionId,
				messages: session.lastMessages ?? [],
				artifacts: session.artifacts,
			});
			return;
		}

		if (request.method === "GET" && parts[2] === "usage") {
			jsonResponse(response, 200, {
				session_id: session.sessionId,
				usage: session.lastUsage ?? {},
				artifacts: session.artifacts,
			});
			return;
		}

		if (request.method === "GET" && parts[2] === "events") {
			if (parts[3] === "ndjson") {
				ndjsonResponse(response, session.events);
				return;
			}
			if (parts[3] === "sse") {
				sseResponse(response, session.events);
				return;
			}
			jsonResponse(response, 200, {
				session_id: session.sessionId,
				events: session.events,
			});
			return;
		}

		if (request.method === "POST" && parts[2] === "abort") {
			await abortSession(EXECUTION_CONTEXT, session);
			jsonResponse(response, 200, toPublicSession(session));
			return;
		}

		if (request.method === "POST" && parts[2] === "stop") {
			await stopSession(EXECUTION_CONTEXT, session);
			jsonResponse(response, 200, toPublicSession(session));
			return;
		}

		if (request.method === "DELETE" && parts.length === 2) {
			await deleteSession(EXECUTION_CONTEXT, session);
			jsonResponse(response, 200, {
				deleted: true,
				session_id: session.sessionId,
			});
			return;
		}
	}

	jsonError(response, 404, "not_found", "Route not found.", {
		method: request.method || "GET",
		path,
		default_channel: DEFAULT_CHANNEL,
	});
});

server.listen(PORT, HOST, () => {
	const addr = server.address() as { port: number };
	console.log(`AGENT_CORE_LISTENING ${addr.port}`);
	console.log(`AGENT_CORE_PROOFS ${proofRunDir(PROOF_CONTEXT, "example")}`);
});
