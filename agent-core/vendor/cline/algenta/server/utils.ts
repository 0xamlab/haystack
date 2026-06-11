import type { IncomingMessage } from "node:http";
import { redactSecrets } from "../proofs";
import type { CanonicalEvent, SessionRecord } from "./contracts";

export function nowIso(): string {
	return new Date().toISOString();
}

export function asRecord(value: unknown): Record<string, unknown> {
	return value && typeof value === "object" && !Array.isArray(value)
		? (value as Record<string, unknown>)
		: {};
}

export function optionalString(value: unknown): string | undefined {
	if (typeof value !== "string") return undefined;
	const trimmed = value.trim();
	return trimmed ? trimmed : undefined;
}

export function requiredString(value: unknown, fieldName: string): string {
	const resolved = optionalString(value);
	if (!resolved) {
		throw new Error(`${fieldName} is required.`);
	}
	return resolved;
}

export function booleanValue(value: unknown, defaultValue = false): boolean {
	return typeof value === "boolean" ? value : defaultValue;
}

export function stringArray(value: unknown): string[] {
	if (!Array.isArray(value)) return [];
	return value
		.map((entry) => optionalString(entry))
		.filter((entry): entry is string => Boolean(entry));
}

export function ensureEnumValue<T extends string>(
	value: unknown,
	values: readonly T[],
	fieldName: string,
	defaultValue: T,
): T {
	const resolved = optionalString(value);
	if (!resolved) return defaultValue;
	if (!values.includes(resolved as T)) {
		throw new Error(`${fieldName} must be one of: ${values.join(", ")}.`);
	}
	return resolved as T;
}

export function normalizeLimits(
	value: unknown,
): { maxIterations?: number; timeoutMs?: number } {
	const input = asRecord(value);
	const maxIterationsRaw =
		input.maxIterations ?? input.max_iterations ?? input.max_turns;
	const timeoutRaw = input.timeoutMs ?? input.timeout_ms;
	const maxIterations =
		typeof maxIterationsRaw === "number" && Number.isFinite(maxIterationsRaw)
			? Math.max(1, Math.trunc(maxIterationsRaw))
			: undefined;
	const timeoutMs =
		typeof timeoutRaw === "number" && Number.isFinite(timeoutRaw)
			? Math.max(1, Math.trunc(timeoutRaw))
			: undefined;
	return {
		...(maxIterations ? { maxIterations } : {}),
		...(timeoutMs ? { timeoutMs } : {}),
	};
}

export function buildPrompt(payload: Record<string, unknown>): string {
	if (typeof payload.prompt === "string" && payload.prompt.trim()) {
		return payload.prompt.trim();
	}
	const task = asRecord(payload.task_spec);
	const injectedContext = asRecord(payload.injected_context);
	const issue = optionalString(task.issue_text) || "(see the evidence bundle)";
	const suspects = stringArray(injectedContext.suspect_files);
	const suspectLine = suspects.length
		? ` Likely files: ${suspects.join(", ")}.`
		: "";
	return `Fix this repository issue: ${issue}.${suspectLine} Make the minimal correct change with your file-editing tools, then stop.`;
}

export function createIdempotencyKey(session: SessionRecord): string | null {
	if (!session.idempotencyKey) return null;
	return [session.channel, session.repositoryScope, session.idempotencyKey].join(":");
}

export function sessionOwnerForRequest(request: IncomingMessage): string {
	return (
		optionalString(request.headers["x-session-owner"]) ||
		optionalString(request.headers["x-owner"]) ||
		"anonymous"
	);
}

export function matchesOwner(request: IncomingMessage, session: SessionRecord): boolean {
	return sessionOwnerForRequest(request) === session.owner;
}

export function updateSessionTimestamp(session: SessionRecord): void {
	session.updatedAt = nowIso();
}

export function appendSessionEvent(
	session: SessionRecord,
	eventType: string,
	payload: Record<string, unknown>,
): CanonicalEvent {
	const event: CanonicalEvent = {
		schema_version: "cline-session-event/v1",
		event_id: `evt_${session.sessionId}_${session.events.length + 1}`,
		event_index: session.events.length + 1,
		session_id: session.sessionId,
		observed_at: nowIso(),
		event_type: eventType,
		payload: redactSecrets(payload) as Record<string, unknown>,
	};
	session.events.push(event);
	updateSessionTimestamp(session);
	return event;
}
