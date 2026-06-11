import type { SessionRecord } from "./contracts";

export interface ServerState {
	sessions: Map<string, SessionRecord>;
	idempotencyIndex: Map<string, string>;
	// B3: capacity + lifecycle. inFlight gates per-replica concurrency (429 when at
	// cap); draining flips on SIGTERM so /ready sheds load before the process exits.
	// (B3/PR8 removed activeEngineSessionId — engine config is now per-run via
	// AsyncLocalStorage, so there is no process-global engine env to serialize.)
	inFlight: number;
	draining: boolean;
}

export function createServerState(): ServerState {
	return {
		sessions: new Map<string, SessionRecord>(),
		idempotencyIndex: new Map<string, string>(),
		inFlight: 0,
		draining: false,
	};
}
