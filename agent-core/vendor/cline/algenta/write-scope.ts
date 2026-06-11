// B7 write-scope enforcement (PR10c): block out-of-scope writes BEFORE they hit disk,
// regardless of approval profile or engine mode. Wired as an always-on beforeTool hook
// (adapter.buildStartConfig). The agent may only edit files inside the materialized
// repository working dir; absolute paths, traversal, and protected files (CI workflows,
// git internals, secrets) are hard-denied — a violation stops the run rather than letting
// a supply-chain/secret edit reach the apply path.

import type { AgentBeforeToolContext, AgentBeforeToolResult } from "@cline/shared";

const WRITE_TOOLS = new Set(["editor", "apply_patch", "write_to_file", "new_file"]);

// Denied regardless of profile (T11a CI-safety + secret protection):
const PROTECTED_PATTERNS: RegExp[] = [
	/(^|\/)\.github\/workflows\//, // CI workflow files — supply-chain
	/(^|\/)\.git\//, // git internals
	/(^|\/)\.env(\.[^/]*)?$/, // .env / .env.* secret files
	/(^|\/)secrets?\//, // secrets directories
];

function extractWritePaths(input: unknown): string[] {
	if (!input || typeof input !== "object") return [];
	const o = input as Record<string, unknown>;
	const paths: string[] = [];
	for (const v of [o.path, o.file, o.file_path, o.filePath, o.target_file]) {
		if (typeof v === "string") paths.push(v);
	}
	if (Array.isArray(o.files)) {
		for (const f of o.files) if (typeof f === "string") paths.push(f);
	}
	return paths;
}

/** Return a human-readable violation reason for an out-of-scope path, or null if allowed. */
export function scopeViolation(rawPath: string): string | null {
	const p = rawPath.replace(/\\/g, "/").trim();
	if (!p) return null;
	if (p.startsWith("/") || /^[A-Za-z]:\//.test(p)) {
		return "absolute path (outside the repository working dir)";
	}
	if (p.split("/").includes("..")) {
		return "path traversal ('..')";
	}
	for (const re of PROTECTED_PATTERNS) {
		if (re.test(p)) return `protected path (${re.source})`;
	}
	return null;
}

export function writeScopeBeforeTool(
	ctx: AgentBeforeToolContext,
): AgentBeforeToolResult | undefined {
	if (!WRITE_TOOLS.has(ctx.toolCall.toolName)) return undefined;
	for (const path of extractWritePaths(ctx.input)) {
		const violation = scopeViolation(path);
		if (violation) {
			return { stop: true, reason: `write-scope violation: ${violation}: '${path}'` };
		}
	}
	return undefined;
}
