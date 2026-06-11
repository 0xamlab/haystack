// B7 (PR10b): the agent-core sidecar requires the internal bearer when a token is
// configured; it stays open for local loopback dev when none is set.
import { afterEach, expect, test } from "bun:test";
import { isAuthorizedRequest } from "./server/http";

const SAVED = { ...process.env };
afterEach(() => {
	process.env = { ...SAVED };
});

const req = (auth?: string) =>
	({ headers: auth ? { authorization: auth } : {} }) as never;

test("open when no token is configured (loopback dev / backward compatible)", () => {
	delete process.env.AGENT_CORE_AUTH_TOKEN;
	delete process.env.AGENT_CORE_REQUIRE_AUTH;
	expect(isAuthorizedRequest(req())).toBe(true);
});

test("with a token configured, only the matching bearer is authorized", () => {
	process.env.AGENT_CORE_AUTH_TOKEN = "secret-123";
	delete process.env.AGENT_CORE_REQUIRE_AUTH;
	expect(isAuthorizedRequest(req())).toBe(false);
	expect(isAuthorizedRequest(req("Bearer wrong"))).toBe(false);
	expect(isAuthorizedRequest(req("secret-123"))).toBe(false); // missing "Bearer "
	expect(isAuthorizedRequest(req("Bearer secret-123"))).toBe(true);
});

test("REQUIRE_AUTH=1 without a token fails closed", () => {
	delete process.env.AGENT_CORE_AUTH_TOKEN;
	process.env.AGENT_CORE_REQUIRE_AUTH = "1";
	expect(isAuthorizedRequest(req("Bearer anything"))).toBe(false);
});
