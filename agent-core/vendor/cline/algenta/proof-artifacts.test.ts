import { expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { degradedProofRuntimeContext, readProofArtifacts } from "./proofs";

async function withProofRun(
	runId: string,
	files: Record<string, string>,
): Promise<{ root: string; ctx: ReturnType<typeof degradedProofRuntimeContext> }> {
	const root = await mkdtemp(path.join(os.tmpdir(), "algenta-proofs-"));
	const ctx = degradedProofRuntimeContext(root, "test");
	const runDir = path.join(root, "build", "proofs", "cline", "runs", runId);
	await mkdir(runDir, { recursive: true });
	for (const [name, body] of Object.entries(files)) {
		await writeFile(path.join(runDir, name), body, "utf8");
	}
	return { root, ctx };
}

test("readProofArtifacts returns the run's JSON + ndjson bundle", async () => {
	const { root, ctx } = await withProofRun("run-abc123", {
		"gate.json": JSON.stringify({ terminal_state: "succeeded", apply_allowed: true }),
		"messages.json": JSON.stringify({ sensitive: true, messages: [{ role: "user" }] }),
		"events.ndjson": '{"event":"a"}\n{"event":"b"}\n',
	});
	try {
		const bundle = await readProofArtifacts(ctx, "run-abc123");
		expect(bundle).not.toBeNull();
		expect(bundle!.run_id).toBe("run-abc123");
		expect((bundle!.artifacts["gate.json"] as { terminal_state: string }).terminal_state).toBe(
			"succeeded",
		);
		// missing artifacts (usage/tool_calls/...) are simply omitted, not errors
		expect(bundle!.artifacts["usage.json"]).toBeUndefined();
		expect((bundle!.artifacts["events.ndjson"] as unknown[]).length).toBe(2);
	} finally {
		await rm(root, { recursive: true, force: true });
	}
});

test("readProofArtifacts returns null when the run dir has no artifacts", async () => {
	const root = await mkdtemp(path.join(os.tmpdir(), "algenta-proofs-"));
	const ctx = degradedProofRuntimeContext(root, "test");
	try {
		expect(await readProofArtifacts(ctx, "never-finalized")).toBeNull();
	} finally {
		await rm(root, { recursive: true, force: true });
	}
});

test("readProofArtifacts rejects a path-unsafe runId", async () => {
	const ctx = degradedProofRuntimeContext(os.tmpdir(), "test");
	await expect(readProofArtifacts(ctx, "../../etc/passwd")).rejects.toThrow();
});
