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
import { isAuthorizedRequest, jsonError, jsonResponse, ndjsonResponse, readJsonBody, requireSession, routeMatch, sseResponse } from "./server/http";
import { normalizeSessionPayload, toPublicSession } from "./server/policy";
import { createServerState } from "./server/state";
import { appendSessionEvent, createIdempotencyKey, optionalString, sessionOwnerForRequest, requiredString } from "./server/utils";
import { degradedProofRuntimeContext, loadProofRuntimeContext, proofRunDir, repoRootFromImportMeta } from "./proofs";

const PORT = Number(process.env.AGENT_CORE_PORT || process.argv[2] || 0);
// Bind loopback by default (safe for local dev); containers set AGENT_CORE_HOST=0.0.0.0
// so peer services (worker/api) can reach the sidecar over the internal network (B3).
const BIND_HOST = process.env.AGENT_CORE_HOST || HOST;
const ROOT_DIR = repoRootFromImportMeta(import.meta.url);
// Provenance is optional for the server to RUN: a load failure (e.g. a docs/runtime
// hash issue) must never crash boot before the port binds (Wave A1). Degrade instead.
const PROOF_CONTEXT = await loadProofRuntimeContext(ROOT_DIR).catch((error) =>
	degradedProofRuntimeContext(ROOT_DIR, String(error)),
);
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
			// B4: runtime truth on the wire so the Python consumer can refuse to treat a
			// stub / offline-contract / docs-mismatched run as a live result.
			runtime: {
				kind: "cline",
				is_stub: false,
				offline_contract_only: process.env.ALGENTA_RUN_CLASS === "offline_contract_only",
				docs_runtime_mismatch: PROOF_CONTEXT.docsRuntimeMismatch,
			},
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

// --- B3: capacity, readiness, and session lifecycle ------------------------------
const MAX_CONCURRENCY = Number(process.env.AGENT_CORE_MAX_CONCURRENCY || 8);
const SESSION_TTL_MS = Number(process.env.AGENT_CORE_SESSION_TTL_MS || 30 * 60 * 1000);
const MAX_SESSIONS = Number(process.env.AGENT_CORE_MAX_SESSIONS || 500);
const SWEEP_INTERVAL_MS = Number(process.env.AGENT_CORE_SWEEP_INTERVAL_MS || 60 * 1000);

function isReady(): boolean {
	return !SERVER_STATE.draining && SERVER_STATE.inFlight < MAX_CONCURRENCY;
}

// Gate the agent-running routes: shed load while draining (503) or saturated (429) so
// the load balancer routes to a healthy replica; otherwise count the run as in-flight.
async function withCapacity(response: ServerResponse, handler: () => Promise<void>): Promise<void> {
	if (SERVER_STATE.draining) {
		jsonError(response, 503, "agent_core_draining", "Sidecar is draining; retry on another replica.");
		return;
	}
	if (SERVER_STATE.inFlight >= MAX_CONCURRENCY) {
		response.setHeader("retry-after", "5");
		jsonError(response, 429, "agent_core_saturated", `At capacity (${MAX_CONCURRENCY} concurrent runs).`);
		return;
	}
	SERVER_STATE.inFlight++;
	try {
		await handler();
	} finally {
		SERVER_STATE.inFlight--;
	}
}

// Evict idle sessions (and prune the idempotency index) so the in-memory store can't
// grow without bound on a long-lived replica. Replica-local: durable run state lives in
// the Job row + object store (Wave B), not here.
function sweepSessions(): void {
	const now = Date.now();
	for (const [id, session] of SERVER_STATE.sessions) {
		if (now - (Date.parse(session.updatedAt) || 0) > SESSION_TTL_MS) {
			SERVER_STATE.sessions.delete(id);
		}
	}
	if (SERVER_STATE.sessions.size > MAX_SESSIONS) {
		const oldestFirst = [...SERVER_STATE.sessions.entries()].sort(
			(a, b) => (Date.parse(a[1].updatedAt) || 0) - (Date.parse(b[1].updatedAt) || 0),
		);
		for (const [id] of oldestFirst.slice(0, SERVER_STATE.sessions.size - MAX_SESSIONS)) {
			SERVER_STATE.sessions.delete(id);
		}
	}
	for (const [key, sessionId] of SERVER_STATE.idempotencyIndex) {
		if (!SERVER_STATE.sessions.has(sessionId)) {
			SERVER_STATE.idempotencyIndex.delete(key);
		}
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

	// Readiness (≠ liveness): a load balancer routes only to /ready replicas. Reflects
	// drain state + per-replica capacity + runtime truth, so a saturated or draining
	// replica sheds load instead of accepting work it can't run.
	if (request.method === "GET" && path === "/ready") {
		const ready = isReady();
		jsonResponse(response, ready ? 200 : 503, {
			ready,
			draining: SERVER_STATE.draining,
			in_flight: SERVER_STATE.inFlight,
			max_concurrency: MAX_CONCURRENCY,
			sessions: SERVER_STATE.sessions.size,
			runtime: { kind: "cline", is_stub: false },
		});
		return;
	}

	// B7: everything past the liveness/readiness probes requires the internal bearer
	// (no-op when no token is configured — local loopback dev stays open).
	if (!isAuthorizedRequest(request)) {
		jsonError(response, 401, "unauthorized", "missing or invalid agent-core bearer token.");
		return;
	}

	if (request.method === "GET" && path === "/manifest") {
		jsonResponse(response, 200, createServerManifest(PROOF_CONTEXT, RUNTIME_IDENTITY));
		return;
	}

	if (request.method === "POST" && path === "/run") {
		await withCapacity(response, () => handleRunCompatibility(request, response));
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
			await withCapacity(response, () => handleStart(request, response, session));
			return;
		}

		if (request.method === "POST" && parts[2] === "turns") {
			await withCapacity(response, () => handleTurn(request, response, session));
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

// --- process-level safety (Wave A1): never die silently; let the supervisor
// (run-server.mjs respawn / Docker restart) bring us back on a fatal fault. A
// basic SIGTERM/SIGINT close here; full in-flight draining lands in B3.
process.on("unhandledRejection", (reason) => {
	// Log but don't exit: a stray rejection in one request must not kill the only
	// process and take down every co-tenant session. uncaughtException is fatal.
	console.error(`AGENT_CORE_UNHANDLED_REJECTION ${String(reason)}`);
});
process.on("uncaughtException", (error) => {
	console.error(`AGENT_CORE_UNCAUGHT_EXCEPTION ${String(error)}`);
	process.exit(1); // non-zero ⇒ the supervisor restarts a clean process
});
for (const signal of ["SIGTERM", "SIGINT"] as const) {
	process.on(signal, () => {
		console.log(`AGENT_CORE_SHUTDOWN ${signal}`);
		// B3 graceful drain: flip /ready -> 503 first so the LB stops routing NEW work,
		// then close (which waits for in-flight requests), with a hard cap as a backstop.
		SERVER_STATE.draining = true;
		server.close(() => process.exit(0));
		setTimeout(() => process.exit(0), 15_000).unref();
	});
}

// --- HTTP server timeouts (Wave A1): cap slow-loris / oversized headers and stop a
// stuck request from holding the single process forever. requestTimeout sits above
// the per-turn budget so the turn-timeout fires first with a clean error.
const TURN_BUDGET_MS = Number(process.env.AGENT_CORE_TURN_TIMEOUT_MS || 150_000);
server.requestTimeout = Number(process.env.AGENT_CORE_REQUEST_TIMEOUT_MS || TURN_BUDGET_MS + 30_000);
server.headersTimeout = Number(process.env.AGENT_CORE_HEADERS_TIMEOUT_MS || 60_000);
server.keepAliveTimeout = Number(process.env.AGENT_CORE_KEEPALIVE_TIMEOUT_MS || 65_000);

server.listen(PORT, BIND_HOST, () => {
	const addr = server.address() as { port: number };
	console.log(`AGENT_CORE_LISTENING ${addr.port}`);
	console.log(`AGENT_CORE_PROOFS ${proofRunDir(PROOF_CONTEXT, "example")}`);
});

// B3: periodically evict idle sessions so a long-lived replica's memory stays bounded.
setInterval(sweepSessions, SWEEP_INTERVAL_MS).unref();
