import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

export interface ProofRuntimeContext {
	rootDir: string;
	gitCommit: string;
	vendoredClineCommit: string;
	algentaCommit: string;
	docsSnapshotHash: string;
	declaredDocsSnapshotHash: string;
	docsRuntimeMismatch: boolean;
	parityLedgerHash: string;
	runtimeVersion: string;
	sourceTreeDirty: boolean;
}

export interface ArtifactProvenance {
	schema_version: string;
	generated_at: string;
	run_id: string;
	git_commit: string;
	runtime_version: string;
	parity_ledger_hash: string;
	source_tree_dirty: boolean;
	cline_docs_snapshot_hash: string;
	vendored_cline_commit: string;
	algenta_commit: string;
	// B4: a docs/runtime hash mismatch makes parity provenance untrustworthy. Surfaced on
	// every artifact so the proof layer can mark affected rows blocked_docs_runtime_mismatch.
	docs_runtime_mismatch: boolean;
}

const REDACTED = "[REDACTED]";
const SECRET_KEY_PATTERN =
	/(authorization|api[_-]?key|token|cookie|secret|password|headers?)/i;

export function repoRootFromImportMeta(importMetaUrl: string): string {
	return path.resolve(
		path.dirname(fileURLToPath(importMetaUrl)),
		"../../../..",
	);
}

export function sha256(value: string | Uint8Array): string {
	return crypto.createHash("sha256").update(value).digest("hex");
}

function stableValue(value: unknown): unknown {
	if (Array.isArray(value)) {
		return value.map((entry) => stableValue(entry));
	}
	if (value && typeof value === "object") {
		const input = value as Record<string, unknown>;
		return Object.fromEntries(
			Object.keys(input)
				.sort()
				.map((key) => [key, stableValue(input[key])]),
		);
	}
	return value;
}

export function stableStringify(value: unknown): string {
	return `${JSON.stringify(stableValue(value), null, 2)}\n`;
}

function gitOutput(rootDir: string, args: string[]): string {
	try {
		return execFileSync("git", ["-C", rootDir, ...args], {
			encoding: "utf8",
			stdio: ["ignore", "pipe", "ignore"],
		}).trim();
	} catch {
		return "";
	}
}

export async function loadProofRuntimeContext(
	rootDir: string,
): Promise<ProofRuntimeContext> {
	const docsSnapshotPath = path.join(
		rootDir,
		"build",
		"proofs",
		"cline",
		"cline_docs_snapshot.txt",
	);
	const docsSnapshotHashPath = path.join(
		rootDir,
		"build",
		"proofs",
		"cline",
		"cline_docs_snapshot.sha256",
	);
	// The proof docs snapshot is optional at boot: a missing snapshot degrades
	// provenance but must not crash the server before it binds a port. A present
	// snapshot is still integrity-checked against its declared hash.
	let computedDocsHash = "";
	let declaredHash = "";
	try {
		const docsSnapshot = await readFile(docsSnapshotPath);
		computedDocsHash = sha256(docsSnapshot);
		declaredHash = (await readFile(docsSnapshotHashPath, "utf8")).trim();
	} catch {
		computedDocsHash = "";
		declaredHash = "";
	}
	// A docs/runtime mismatch must NOT crash boot — the server must always bind a
	// port (Wave A1). Record it as a tracked flag so the proof layer can mark the
	// affected runs `blocked_docs_runtime_mismatch` (Wave B4) instead of silently
	// degrading to "partial".
	const docsRuntimeMismatch = Boolean(
		declaredHash && computedDocsHash && declaredHash !== computedDocsHash,
	);
	if (docsRuntimeMismatch) {
		console.error(
			`AGENT_CORE_DOCS_RUNTIME_MISMATCH declared=${declaredHash} computed=${computedDocsHash}`,
		);
	}

	const gitCommit = gitOutput(rootDir, ["rev-parse", "HEAD"]);
	const vendoredClineCommit =
		gitOutput(rootDir, ["rev-parse", "HEAD:agent-core/vendor/cline"]) ||
		gitCommit;
	const algentaCommit = gitCommit;
	const sourceTreeDirty = gitOutput(rootDir, ["status", "--porcelain"]) !== "";
	const parityLedgerHash = sha256(
		stableStringify({
			cline_docs_snapshot_hash: computedDocsHash,
			vendored_cline_commit: vendoredClineCommit,
			algenta_commit: algentaCommit,
		}),
	);

	return {
		rootDir,
		gitCommit,
		vendoredClineCommit,
		algentaCommit,
		docsSnapshotHash: computedDocsHash,
		declaredDocsSnapshotHash: declaredHash,
		docsRuntimeMismatch,
		parityLedgerHash,
		runtimeVersion: vendoredClineCommit,
		sourceTreeDirty,
	};
}

/**
 * A safe fallback context used if proof provenance cannot be loaded at boot.
 * Provenance is optional for the server to RUN (Wave A1); a degraded context is
 * marked untrusted (dirty + mismatch) so downstream proof gates never treat its
 * runs as authoritative.
 */
export function degradedProofRuntimeContext(
	rootDir: string,
	reason: string,
): ProofRuntimeContext {
	console.error(`AGENT_CORE_PROOF_DEGRADED ${reason}`);
	return {
		rootDir,
		gitCommit: "",
		vendoredClineCommit: "",
		algentaCommit: "",
		docsSnapshotHash: "",
		declaredDocsSnapshotHash: "",
		docsRuntimeMismatch: true,
		parityLedgerHash: "",
		runtimeVersion: "",
		sourceTreeDirty: true,
	};
}

export function createArtifactProvenance(
	context: ProofRuntimeContext,
	runId: string,
	schemaVersion: string,
): ArtifactProvenance {
	return {
		schema_version: schemaVersion,
		generated_at: new Date().toISOString(),
		run_id: runId,
		git_commit: context.gitCommit,
		runtime_version: context.runtimeVersion,
		parity_ledger_hash: context.parityLedgerHash,
		source_tree_dirty: context.sourceTreeDirty,
		cline_docs_snapshot_hash: context.docsSnapshotHash,
		vendored_cline_commit: context.vendoredClineCommit,
		algenta_commit: context.algentaCommit,
		docs_runtime_mismatch: context.docsRuntimeMismatch,
	};
}

export function redactSecrets(value: unknown): unknown {
	if (Array.isArray(value)) {
		return value.map((entry) => redactSecrets(entry));
	}
	if (value && typeof value === "object") {
		const input = value as Record<string, unknown>;
		return Object.fromEntries(
			Object.entries(input).map(([key, entry]) => {
				if (SECRET_KEY_PATTERN.test(key)) {
					return [key, REDACTED];
				}
				return [key, redactSecrets(entry)];
			}),
		);
	}
	return value;
}

export function proofRunDir(
	context: ProofRuntimeContext,
	runId: string,
): string {
	// Defense in depth (B6): runId is server-generated, but never let any value escape the
	// runs root via path separators / traversal — reject anything that isn't a single
	// path-safe segment, and resolve-confine the result under <rootDir>/.../runs.
	if (!/^[A-Za-z0-9_-]{1,128}$/.test(runId)) {
		throw new Error(`unsafe proof run id: ${runId}`);
	}
	const runsRoot = path.join(context.rootDir, "build", "proofs", "cline", "runs");
	const dir = path.resolve(runsRoot, runId);
	if (dir !== path.join(runsRoot, runId) || !dir.startsWith(runsRoot + path.sep)) {
		throw new Error(`proof run dir escaped the runs root: ${dir}`);
	}
	return dir;
}

export function relativeArtifactPath(
	context: ProofRuntimeContext,
	absolutePath: string,
): string {
	return path.relative(context.rootDir, absolutePath) || ".";
}

// B9: the JSON proof artifacts finalizeSessionArtifacts writes (already secret-redacted at write
// time). events.ndjson is read separately (newline-delimited records).
export const PROOF_JSON_ARTIFACTS = [
	"runtime_manifest.json",
	"messages.json",
	"usage.json",
	"tool_calls.json",
	"approvals.json",
	"gate.json",
] as const;

/**
 * Read back a run's finalized proof bundle from <rootDir>/build/proofs/cline/runs/<runId>/.
 * Returns null when the run directory holds no artifacts (e.g. the run finalized on a different
 * replica). Throws only for an unsafe runId (proofRunDir guards path traversal). Used by the
 * read-only /proofs/:runId endpoint so the durable object store can mirror the canonical artifacts.
 */
export async function readProofArtifacts(
	context: ProofRuntimeContext,
	runId: string,
): Promise<{ run_id: string; artifacts: Record<string, unknown> } | null> {
	const runDir = proofRunDir(context, runId);
	const isMissing = (error: unknown): boolean =>
		(error as NodeJS.ErrnoException)?.code === "ENOENT";
	const artifacts: Record<string, unknown> = {};
	for (const name of PROOF_JSON_ARTIFACTS) {
		try {
			artifacts[name] = JSON.parse(await readFile(path.join(runDir, name), "utf8"));
		} catch (error) {
			if (!isMissing(error)) throw error;
		}
	}
	try {
		const ndjson = await readFile(path.join(runDir, "events.ndjson"), "utf8");
		artifacts["events.ndjson"] = ndjson
			.split("\n")
			.filter((line) => line.length > 0)
			.map((line) => JSON.parse(line));
	} catch (error) {
		if (!isMissing(error)) throw error;
	}
	return Object.keys(artifacts).length > 0 ? { run_id: runId, artifacts } : null;
}

export async function writeJsonArtifact(
	context: ProofRuntimeContext,
	runId: string,
	fileName: string,
	payload: unknown,
): Promise<string> {
	const runDir = proofRunDir(context, runId);
	await mkdir(runDir, { recursive: true });
	const artifactPath = path.join(runDir, fileName);
	await writeFile(artifactPath, stableStringify(payload), "utf8");
	return artifactPath;
}

export async function writeNdjsonArtifact(
	context: ProofRuntimeContext,
	runId: string,
	fileName: string,
	events: unknown[],
): Promise<string> {
	const runDir = proofRunDir(context, runId);
	await mkdir(runDir, { recursive: true });
	const artifactPath = path.join(runDir, fileName);
	const body = events
		.map((event) => JSON.stringify(stableValue(event)))
		.join("\n");
	await writeFile(artifactPath, body ? `${body}\n` : "", "utf8");
	return artifactPath;
}
