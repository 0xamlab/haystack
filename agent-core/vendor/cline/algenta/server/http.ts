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

export async function readJsonBody(
	request: IncomingMessage,
): Promise<Record<string, unknown>> {
	const chunks: Buffer[] = [];
	for await (const chunk of request) {
		chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
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
