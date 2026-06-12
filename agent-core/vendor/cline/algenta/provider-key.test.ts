// B10 PR11b: per-tenant LLM provider key plumbing — the per-tenant key (resolved server-side from
// the authenticated org by the Algenta engine) overrides the agent's env key; require_provider_api_key
// makes a missing per-tenant key fail closed (no shared-env borrow). The key never leaks to clients.
import { expect, test } from "bun:test";
import { type RunAgentArgs, selectProviderApiKey } from "./adapter";
import { normalizeSessionPayload, toPublicSession } from "./server/policy";

const ARGS = (over: Partial<RunAgentArgs> = {}): RunAgentArgs => ({
	working_dir: "/w",
	prompt: "p",
	...over,
});

test("selectProviderApiKey: per-tenant key overrides the env key", () => {
	process.env.TEST_PK_ENV = "env-key";
	try {
		expect(selectProviderApiKey(ARGS({ provider_api_key: "tenant-key" }), ["TEST_PK_ENV"])).toBe(
			"tenant-key",
		);
	} finally {
		delete process.env.TEST_PK_ENV;
	}
});

test("selectProviderApiKey: falls back to the pooled env key when no per-tenant key", () => {
	process.env.TEST_PK_ENV = "env-key";
	try {
		expect(selectProviderApiKey(ARGS(), ["TEST_PK_ENV"])).toBe("env-key");
	} finally {
		delete process.env.TEST_PK_ENV;
	}
});

test("selectProviderApiKey: require_provider_api_key forbids the env fallback (fail closed)", () => {
	process.env.TEST_PK_ENV = "env-key";
	try {
		// multi-tenant, no per-tenant key -> undefined (resolveProviderConfig then throws)
		expect(
			selectProviderApiKey(ARGS({ require_provider_api_key: true }), ["TEST_PK_ENV"]),
		).toBeUndefined();
		// ...but an explicit per-tenant key is still honored under the require flag
		expect(
			selectProviderApiKey(
				ARGS({ require_provider_api_key: true, provider_api_key: "tk" }),
				["TEST_PK_ENV"],
			),
		).toBe("tk");
	} finally {
		delete process.env.TEST_PK_ENV;
	}
});

test("normalizeSessionPayload reads provider_api_key + require flag from task_spec.engine", () => {
	const s = normalizeSessionPayload(
		{
			working_dir: "/w",
			task_spec: {
				issue_text: "x",
				engine: { provider: "openai", provider_api_key: "tk", require_provider_api_key: true },
			},
		},
		"owner",
	);
	expect(s.provider).toBe("openai");
	expect(s.providerApiKey).toBe("tk");
	expect(s.requireProviderApiKey).toBe(true);
});

test("normalizeSessionPayload also accepts a top-level provider_api_key (default require=false)", () => {
	const s = normalizeSessionPayload(
		{ working_dir: "/w", task_spec: { issue_text: "x" }, provider_api_key: "tk2" },
		"owner",
	);
	expect(s.providerApiKey).toBe("tk2");
	expect(s.requireProviderApiKey).toBe(false);
});

test("toPublicSession never leaks the per-tenant key material", () => {
	const s = normalizeSessionPayload(
		{ working_dir: "/w", task_spec: { issue_text: "x", engine: { provider_api_key: "SECRET-TK" } } },
		"owner",
	);
	expect(JSON.stringify(toPublicSession(s))).not.toContain("SECRET-TK");
});
