import type { SessionRecord } from "./contracts";

export interface ServerState {
	sessions: Map<string, SessionRecord>;
	idempotencyIndex: Map<string, string>;
	activeEngineSessionId: string | null;
}

export function createServerState(): ServerState {
	return {
		sessions: new Map<string, SessionRecord>(),
		idempotencyIndex: new Map<string, string>(),
		activeEngineSessionId: null,
	};
}

export function clearBoundEngineEnvironment(
	state: ServerState,
	sessionId?: string,
): void {
	if (sessionId && state.activeEngineSessionId && state.activeEngineSessionId !== sessionId) {
		return;
	}
	delete process.env.ALGENTA_ENGINE_URL;
	delete process.env.ALGENTA_REPOSITORY_ID;
	delete process.env.ALGENTA_SNAPSHOT_ID;
	delete process.env.ALGENTA_WORKING_DIR;
	delete process.env.ALGENTA_API_KEY;
	state.activeEngineSessionId = null;
}
