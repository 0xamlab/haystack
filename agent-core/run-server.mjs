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

const child = spawn(command, args, {
	cwd: DIR,
	env: {
		...process.env,
		ALGENTA_RUN_CLASS: USE_STUB
			? "offline_contract_only"
			: process.env.ALGENTA_RUN_CLASS || "live",
	},
	stdio: "inherit",
});

child.on("exit", (code, signal) => {
	if (signal) {
		process.kill(process.pid, signal);
		return;
	}
	process.exit(code ?? 0);
});

child.on("error", (error) => {
	console.error(String(error));
	process.exit(1);
});
