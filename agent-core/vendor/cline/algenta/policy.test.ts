// B6/B7 PR10 (proof-honesty + fail-closed): engine-evidence default, unknown-profile
// fail-closed, caller session_id path-validated + artifact run id server-generated, and
// proofRunDir traversal-safe.
import { expect, test } from "bun:test";
import { normalizeSessionPayload, resolveEngineConfig, resolveSessionPolicy } from "./server/policy";
import { proofRunDir } from "./proofs";

const ARGS = { working_dir: "/work", prompt: "fix it" } as never;
const base = { working_dir: "/work", prompt: "fix it", task_spec: { issue_text: "fix it" } };

test("engine mode defaults to requiring engine evidence (simulate_patch / fail-on-zero)", () => {
	const cfg = resolveEngineConfig({ engine: { url: "http://engine:8000" } });
	expect(cfg.enabled).toBe(true);
	expect(cfg.requiredTools).toEqual(["simulate_patch"]);
	expect(cfg.failOnZeroCalls).toBe(true);
});

test("explicit fail_on_zero_calls:false is honored; no url => engine disabled", () => {
	expect(resolveEngineConfig({ engine: { url: "http://e:8000", fail_on_zero_calls: false } }).failOnZeroCalls).toBe(false);
	expect(resolveEngineConfig({}).enabled).toBe(false);
});

test("unknown approval_profile fails closed; absent => default; valid => ok", () => {
	expect(() => resolveSessionPolicy({ approval_profile: "totally_made_up" }, ARGS)).toThrow();
	expect(() => resolveSessionPolicy({}, ARGS)).not.toThrow();
	expect(() => resolveSessionPolicy({ approval_profile: "repository_review" }, ARGS)).not.toThrow();
});

test("session_id is path-validated; the artifact run id is server-generated (decoupled)", () => {
	const ok = normalizeSessionPayload({ ...base, session_id: "sess-123" }, "owner");
	expect(ok.sessionId).toBe("sess-123");
	expect(ok.agentRunId).not.toBe("sess-123");
	expect(ok.agentRunId.startsWith("run_")).toBe(true);
	expect(() => normalizeSessionPayload({ ...base, session_id: "../evil" }, "owner")).toThrow();
	expect(() => normalizeSessionPayload({ ...base, session_id: "a/b" }, "owner")).toThrow();
});

test("proofRunDir rejects unsafe run ids and confines to the runs root", () => {
	const ctx = { rootDir: "/tmp/root" } as never;
	expect(proofRunDir(ctx, "run_abc-123")).toBe("/tmp/root/build/proofs/cline/runs/run_abc-123");
	expect(() => proofRunDir(ctx, "../escape")).toThrow();
	expect(() => proofRunDir(ctx, "a/b")).toThrow();
});
