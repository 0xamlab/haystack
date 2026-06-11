// B3/PR8: prove per-run engine config is isolated via AsyncLocalStorage — concurrent
// engine-backed runs never read each other's engine URL or API key (the cross-tenant
// secret bleed the old process-global env + activeEngineSessionId mutex caused).
import { expect, test } from "bun:test";
import { ENGINE, REPO, SNAPSHOT, WORKING_DIR, type EngineContext, enginePost, engineContext } from "./tools";

const ctxA: EngineContext = {
	url: "http://engine-a:8000/",
	repositoryId: "repo-a",
	snapshotId: "snap-a",
	apiKey: "key-a",
	workingDir: "/work/a",
};
const ctxB: EngineContext = {
	url: "http://engine-b:8000",
	repositoryId: "repo-b",
	snapshotId: "snap-b",
	apiKey: "key-b",
	workingDir: "/work/b",
};

test("engine seam is inert outside a run", () => {
	expect(ENGINE()).toBe("");
	expect(REPO()).toBe("");
	expect(SNAPSHOT()).toBe("");
	expect(WORKING_DIR()).toBe("");
});

test("concurrent runs never see each other's engine config (interleaved awaits)", async () => {
	const read = (ctx: EngineContext, delayMs: number) =>
		engineContext.run(ctx, async () => {
			await new Promise((r) => setTimeout(r, delayMs));
			return { engine: ENGINE(), repo: REPO(), snapshot: SNAPSHOT(), dir: WORKING_DIR() };
		});
	// A awaits longer, so B's run is fully in-flight while A is suspended: if config were a
	// process global, A would observe B's values on resume. With ALS each run is isolated.
	const [a, b] = await Promise.all([read(ctxA, 25), read(ctxB, 3)]);
	expect(a).toEqual({ engine: "http://engine-a:8000", repo: "repo-a", snapshot: "snap-a", dir: "/work/a" });
	expect(b).toEqual({ engine: "http://engine-b:8000", repo: "repo-b", snapshot: "snap-b", dir: "/work/b" });
});

test("the engine API key is per-run: concurrent enginePost calls carry their own bearer", async () => {
	const seen: Record<string, string | undefined> = {};
	const original = globalThis.fetch;
	globalThis.fetch = (async (url: unknown, init: { headers?: Record<string, string> } | undefined) => {
		seen[String(url)] = init?.headers?.authorization;
		return { ok: true, json: async () => ({}) } as unknown as Response;
	}) as typeof fetch;
	try {
		await Promise.all([
			engineContext.run(ctxA, () => enginePost("/triage", {})),
			engineContext.run(ctxB, () => enginePost("/triage", {})),
		]);
		expect(seen["http://engine-a:8000/triage"]).toBe("Bearer key-a");
		expect(seen["http://engine-b:8000/triage"]).toBe("Bearer key-b");
	} finally {
		globalThis.fetch = original;
	}
});
