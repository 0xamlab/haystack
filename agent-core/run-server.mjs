import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const USE_STUB =
	process.env.ALGENTA_ALLOW_STUB_RUNTIME === "1" &&
	process.env.ALGENTA_RUN_CLASS === "offline_contract_only" &&
	(process.env.NODE_ENV === "test" ||
		process.env.CI_OFFLINE_CONTRACT_TEST === "1");

const command = USE_STUB ? process.execPath : "bun";
const args = USE_STUB
	? [path.join(DIR, "run-server.stub.mjs"), ...process.argv.slice(2)]
	: [path.join(DIR, "vendor", "cline", "algenta", "run-server.ts"), ...process.argv.slice(2)];

// Wave A1 supervision: respawn the child on a crash with bounded exponential
// backoff so a fatal fault self-heals instead of leaving agentic planning down
// until a human restarts it. A deliberate signal is propagated (no restart); a
// crash-loop beyond MAX_RESTARTS in the window gives up non-zero so the outer
// supervisor (Docker `restart: unless-stopped` / k8s) takes over with its own
// backoff. B3 fronts N replicas so one crash is never an outage.
const MAX_RESTARTS = Number(process.env.AGENT_CORE_MAX_RESTARTS || 10);
const RESTART_WINDOW_MS = Number(process.env.AGENT_CORE_RESTART_WINDOW_MS || 60_000);
const BASE_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 10_000;

let restartTimestamps = [];
let shuttingDown = false;
let child;

function childEnv() {
	return {
		...process.env,
		ALGENTA_RUN_CLASS: USE_STUB
			? "offline_contract_only"
			: process.env.ALGENTA_RUN_CLASS || "live",
	};
}

function spawnChild() {
	child = spawn(command, args, { cwd: DIR, env: childEnv(), stdio: "inherit" });

	child.on("exit", (code, signal) => {
		// Deliberate shutdown (we forwarded SIGTERM/SIGINT to the child): exit, don't restart.
		if (shuttingDown) {
			process.exit(0);
			return;
		}
		// Clean, unprompted exit: nothing to supervise.
		if (code === 0) {
			process.exit(0);
			return;
		}
		// Otherwise it's a CRASH — a non-zero exit OR death by signal (SIGKILL/SIGSEGV/
		// OOM/…). Self-heal with bounded exponential backoff.
		const now = Date.now();
		restartTimestamps = restartTimestamps.filter((t) => now - t < RESTART_WINDOW_MS);
		restartTimestamps.push(now);
		if (restartTimestamps.length > MAX_RESTARTS) {
			console.error(
				`agent-core: ${restartTimestamps.length} restarts within ${RESTART_WINDOW_MS}ms — giving up (last exit code ${code} signal ${signal}).`,
			);
			process.exit(1);
			return;
		}
		const backoff = Math.min(BASE_BACKOFF_MS * 2 ** (restartTimestamps.length - 1), MAX_BACKOFF_MS);
		console.error(
			`agent-core child exited (code ${code} signal ${signal}); restarting in ${backoff}ms (restart ${restartTimestamps.length}/${MAX_RESTARTS}).`,
		);
		setTimeout(spawnChild, backoff);
	});

	child.on("error", (error) => {
		console.error(String(error));
		if (!shuttingDown) process.exit(1);
	});
}

for (const signal of ["SIGTERM", "SIGINT"]) {
	process.on(signal, () => {
		shuttingDown = true;
		if (child) child.kill(signal);
	});
}

spawnChild();
