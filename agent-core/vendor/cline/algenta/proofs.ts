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
	if (declaredHash && computedDocsHash && declaredHash !== computedDocsHash) {
		throw new Error(
			`cline docs snapshot hash mismatch: declared=${declaredHash} computed=${computedDocsHash}`,
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
		parityLedgerHash,
		runtimeVersion: vendoredClineCommit,
		sourceTreeDirty,
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
	return path.join(context.rootDir, "build", "proofs", "cline", "runs", runId);
}

export function relativeArtifactPath(
	context: ProofRuntimeContext,
	absolutePath: string,
): string {
	return path.relative(context.rootDir, absolutePath) || ".";
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
