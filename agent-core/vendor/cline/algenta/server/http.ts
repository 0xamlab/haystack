import type { IncomingMessage, ServerResponse } from "node:http";
import type { ServerState } from "./state";
import type { SessionRecord } from "./contracts";
import { matchesOwner } from "./utils";

export function jsonResponse(
	response: ServerResponse,
	statusCode: number,
	payload: unknown,
): void {
	response.writeHead(statusCode, { "content-type": "application/json" });
	response.end(JSON.stringify(payload));
}

export function jsonError(
	response: ServerResponse,
	statusCode: number,
	code: string,
	message: string,
	details: Record<string, unknown> = {},
): void {
	jsonResponse(response, statusCode, {
		error: {
			code,
			message,
			details,
		},
	});
}

export function ndjsonResponse(
	response: ServerResponse,
	frames: unknown[],
): void {
	response.writeHead(200, { "content-type": "application/x-ndjson" });
	for (const frame of frames) {
		response.write(`${JSON.stringify(frame)}\n`);
	}
	response.end();
}

export function sseResponse(response: ServerResponse, frames: unknown[]): void {
	response.writeHead(200, {
		"content-type": "text/event-stream",
		"cache-control": "no-cache",
		connection: "keep-alive",
	});
	for (const frame of frames) {
		response.write(`event: session_event\ndata: ${JSON.stringify(frame)}\n\n`);
	}
	response.end();
}

// Wave A1: cap request bodies so an oversized/streaming payload can't exhaust
// memory on the single process. Tunable via AGENT_CORE_MAX_BODY_BYTES.
const MAX_BODY_BYTES = Number(process.env.AGENT_CORE_MAX_BODY_BYTES || 8 * 1024 * 1024);

export async function readJsonBody(
	request: IncomingMessage,
): Promise<Record<string, unknown>> {
	const chunks: Buffer[] = [];
	let total = 0;
	for await (const chunk of request) {
		const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		total += buf.length;
		if (total > MAX_BODY_BYTES) {
			request.destroy();
			throw new Error(`request body too large (>${MAX_BODY_BYTES} bytes)`);
		}
		chunks.push(buf);
	}
	if (chunks.length === 0) return {};
	try {
		return JSON.parse(Buffer.concat(chunks).toString("utf8"));
	} catch {
		throw new Error("invalid json body");
	}
}

export function routeMatch(request: IncomingMessage, host: string): {
	path: string;
	parts: string[];
} {
	const url = new URL(request.url || "/", `http://${host}`);
	const pathName = url.pathname.replace(/\/+$/, "") || "/";
	return {
		path: pathName,
		parts: pathName.split("/").filter(Boolean),
	};
}

// B7 (PR10b): the agent-core sidecar is an internal service; gate it so only the trusted
// caller (the API server / worker, which holds the shared bearer) can reach the
// session/run surface. With a token configured (or AGENT_CORE_REQUIRE_AUTH=1) an
// unauthenticated request is rejected; with neither set the server stays open for local
// loopback dev (backward compatible). /health and /ready stay open for probes.
export function isAuthorizedRequest(request: IncomingMessage): boolean {
	const token = process.env.AGENT_CORE_AUTH_TOKEN;
	const required = process.env.AGENT_CORE_REQUIRE_AUTH === "1" || Boolean(token);
	if (!required) return true;
	if (!token) return false; // auth required but no token configured => fail closed
	const header = request.headers.authorization;
	const value = Array.isArray(header) ? header[0] : header;
	return typeof value === "string" && value === `Bearer ${token}`;
}

export function requireSession(
	request: IncomingMessage,
	response: ServerResponse,
	state: ServerState,
	sessionId: string,
): SessionRecord | undefined {
	const session = state.sessions.get(sessionId);
	if (!session) {
		jsonError(response, 404, "session_not_found", `Unknown session: ${sessionId}`, {
			session_id: sessionId,
		});
		return undefined;
	}
	if (!matchesOwner(request, session)) {
		jsonError(
			response,
			403,
			"session_owner_mismatch",
			`Session ${sessionId} is owned by ${session.owner}.`,
			{ session_id: sessionId, owner: session.owner },
		);
		return undefined;
	}
	return session;
}
