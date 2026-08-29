// Track A3b: the TypeScript equivalent of Track A3's Python conformance suite
// (tests/test_mcp_official_sdk_e2e.py) -- drives Algenta's REAL production MCP Server with the
// OFFICIAL @modelcontextprotocol/sdk TypeScript client, never Algenta's own client code and never
// a raw HTTP status code inspected by hand.
//
// Algenta's MCP server is a Python process (apps/mcp_server + apps/api_server); there is no
// in-process way to embed it under Node the way Track A3's InMemoryTransport tests embed the
// real stdio Server directly in the same Python process. So this suite spawns the real server as
// a subprocess -- tests/_mcp_ts_conformance_server.py, which reuses tests/_mcp_live_server_fixture.py
// (live_api_server + seed_owner_org_and_key) VERBATIM, the exact same real-stack helper Track A3's
// own live-HTTP tests already use -- and drives it exclusively over a real loopback socket with the
// official TS client's StreamableHTTPClientTransport / SSEClientTransport.
//
// Behavioral matrix ported from Track A3 (see tests/test_mcp_official_sdk_e2e.py for the Python
// original):
//   - modern discover/list/call over Streamable HTTP, with discovery public and tools/call gated
//   - the legacy (deprecated) HTTP+SSE initialize handshake still works end to end
//   - product-edition tool-profile filtering (X-Algenta-Product), enforced on both list AND call
//   - a downstream auth failure surfaces as a normal (isError-false) tool result, never a raised
//     transport error -- ported as the HTTP-side analogue of Track A3's stdio "no ambient
//     credential" case: here, a *present but invalid* bearer clears the ASGI-layer auth challenge
//     (which only checks for a credential's presence) and fails for real against Postgres-backed
//     auth, so the resulting MCPAPIError is caught and serialized into the tool result exactly the
//     way Track A3 proved for the ambient-credential case
//
// Deliberately NOT ported (scope, documented rather than silently dropped):
//   - two-independent-replica statelessness: Track A3's own version of this
//     (tests/test_mcp_multi_replica_lb.py) already skips itself in exactly this kind of sandboxed
//     dev environment -- it needs a private ghcr.io/thyn-ai/codna sidecar image this environment
//     has no registry credentials for, plus a 3-replica docker-compose + nginx LB stack. Standing
//     up an equivalent from a vitest file would not be a lighter-weight proof, it would just be a
//     second copy of the same infra-gated test. A single-process, two-independent-client-sessions
//     check is included below instead -- it proves the stateless session manager does not leak
//     state between two official-SDK client connections, which is a real (if narrower) slice of
//     the same property, not a stand-in for the multi-replica LB proof.

import { spawn, type ChildProcess } from "node:child_process";
import { createInterface } from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const REPO_ROOT = fileURLToPath(new URL("../../..", import.meta.url));
const LAUNCHER_SCRIPT = path.join(REPO_ROOT, "scripts", "run_repo_python.sh");
const SERVER_ENTRY = path.join(REPO_ROOT, "tests", "_mcp_ts_conformance_server.py");

const SERVER_BOOT_TIMEOUT_MS = 90_000;
const SERVER_STOP_TIMEOUT_MS = 15_000;
const CLIENT_INFO = { name: "algenta-ts-official-sdk-conformance", version: "1.0.0" };

interface ReadyPayload {
  base_url: string;
  owner_key: string;
  org_id: string;
}

interface LiveServer {
  child: ChildProcess;
  baseUrl: string;
  ownerKey: string;
}

function isReadyPayload(value: unknown): value is ReadyPayload {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).base_url === "string" &&
    typeof (value as Record<string, unknown>).owner_key === "string"
  );
}

/** Spawn the real Algenta MCP server (tests/_mcp_ts_conformance_server.py) and wait for its
 * one-line JSON readiness handshake on stdout. `detached: true` makes the child the leader of its
 * own process group so teardown can signal the whole tree (run_repo_python.sh -> pixi -> python ->
 * the real uvicorn subprocess it boots), not just the immediate child. */
async function bootLiveServer(): Promise<LiveServer> {
  const child = spawn(LAUNCHER_SCRIPT, [SERVER_ENTRY], {
    cwd: REPO_ROOT,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
    // A direct `python /abs/path/script.py` invocation puts the SCRIPT's own directory on
    // sys.path, not the repo root or cwd -- so the script's `from tests....` absolute imports
    // need PYTHONPATH set explicitly (mirrors tests/conftest.py's own `sys.path.insert(0, ...)`
    // for the same reason, and the PYTHONPATH tests/conftest.py's _build_live_subprocess_env sets
    // for the uvicorn subprocess it launches in turn).
    env: { ...process.env, PYTHONPATH: REPO_ROOT },
  });

  const stderrChunks: string[] = [];
  child.stderr?.on("data", (chunk: Buffer) => stderrChunks.push(chunk.toString("utf-8")));

  return await new Promise<LiveServer>((resolve, reject) => {
    let settled = false;

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGKILL");
      reject(
        new Error(
          `Timed out after ${SERVER_BOOT_TIMEOUT_MS}ms waiting for the live MCP conformance ` +
            `server (${SERVER_ENTRY}) to become ready.\nstderr so far:\n${stderrChunks.join("")}`,
        ),
      );
    }, SERVER_BOOT_TIMEOUT_MS);

    child.once("exit", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(
        new Error(
          `Live MCP conformance server exited before becoming ready (code=${code}, ` +
            `signal=${signal}).\nstderr:\n${stderrChunks.join("")}`,
        ),
      );
    });

    if (!child.stdout) {
      settled = true;
      clearTimeout(timeout);
      reject(new Error("Live MCP conformance server child process has no stdout pipe."));
      return;
    }
    const rl = createInterface({ input: child.stdout });
    rl.on("line", line => {
      if (settled) return;
      let parsed: unknown;
      try {
        parsed = JSON.parse(line);
      } catch {
        return; // incidental log noise before the handshake line -- not our concern
      }
      if (!isReadyPayload(parsed)) return;
      settled = true;
      clearTimeout(timeout);
      resolve({ child, baseUrl: parsed.base_url, ownerKey: parsed.owner_key });
    });
  });
}

/** Terminate the whole spawned process group (see bootLiveServer's `detached: true` note above),
 * escalating to SIGKILL if the real uvicorn subprocess doesn't wind down in time. */
async function stopLiveServer(server: LiveServer): Promise<void> {
  const pid = server.child.pid;
  if (pid === undefined) return;
  await new Promise<void>(resolve => {
    let exited = false;
    server.child.once("exit", () => {
      exited = true;
      resolve();
    });
    try {
      process.kill(-pid, "SIGTERM");
    } catch {
      // Process group already gone.
    }
    setTimeout(() => {
      if (!exited) {
        try {
          process.kill(-pid, "SIGKILL");
        } catch {
          // Already gone.
        }
      }
      resolve();
    }, SERVER_STOP_TIMEOUT_MS);
  });
}

function firstTextContent(result: { content: unknown[] }): string {
  const first = result.content[0] as { type?: string; text?: string } | undefined;
  if (!first || first.type !== "text" || typeof first.text !== "string") {
    throw new Error(`Expected a text content block as content[0], got: ${JSON.stringify(first)}`);
  }
  return first.text;
}

async function connectStreamable(
  baseUrl: string,
  headers: Record<string, string> = {},
): Promise<Client> {
  const transport = new StreamableHTTPClientTransport(new URL("/mcp", baseUrl), {
    requestInit: { headers },
  });
  const client = new Client(CLIENT_INFO, { capabilities: {} });
  await client.connect(transport);
  return client;
}

async function connectLegacySse(
  baseUrl: string,
  headers: Record<string, string> = {},
): Promise<Client> {
  const transport = new SSEClientTransport(new URL("/mcp/sse", baseUrl), {
    requestInit: { headers },
  });
  const client = new Client(CLIENT_INFO, { capabilities: {} });
  await client.connect(transport);
  return client;
}

describe("official @modelcontextprotocol/sdk TypeScript client vs. Algenta's real MCP server", () => {
  let server: LiveServer;

  beforeAll(async () => {
    server = await bootLiveServer();
  }, SERVER_BOOT_TIMEOUT_MS + 5_000);

  afterAll(async () => {
    if (server) await stopLiveServer(server);
  }, SERVER_STOP_TIMEOUT_MS + 5_000);

  it(
    "modern Streamable HTTP: initialize + list_tools + call_tool succeed for real",
    async () => {
      const client = await connectStreamable(server.baseUrl, {
        Authorization: `Bearer ${server.ownerKey}`,
      });
      try {
        expect(client.getServerVersion()?.name).toBe("algenta-mcp");

        const { tools } = await client.listTools();
        expect(tools.length).toBeGreaterThan(100); // the real full registry, unscoped key
        expect(tools.some(tool => tool.name === "list_decisions")).toBe(true);
        expect(tools.some(tool => tool.name === "execute_decision")).toBe(true);

        const result = await client.callTool({ name: "list_decisions", arguments: {} });
        expect(result.isError).toBeFalsy();
        const text = firstTextContent(result);
        expect(text).toContain('"decisions"');
        expect(text).toContain('"total"');
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "discovery (initialize/list_tools) stays open with NO Authorization header at all",
    async () => {
      const client = await connectStreamable(server.baseUrl); // no headers whatsoever
      try {
        expect(client.getServerVersion()?.name).toBe("algenta-mcp");
        const { tools } = await client.listTools();
        expect(tools.some(tool => tool.name === "list_decisions")).toBe(true);
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "call_tool with no credential at all raises a real transport-level error (never silently empty)",
    async () => {
      const client = await connectStreamable(server.baseUrl);
      try {
        // Cross-SDK behavioral difference found while porting this test (documented rather than
        // assumed): the official PYTHON client decodes the ASGI challenge's embedded JSON-RPC
        // error body into a proper MCPError with code -32001 (see
        // tests/test_mcp_official_sdk_e2e.py::test_live_http_official_sdk_call_tool_without_bearer_surfaces_real_mcp_error).
        // The official TypeScript client does not: StreamableHTTPClientTransport treats any
        // non-2xx HTTP response as a hard transport failure before it ever parses the body as
        // JSON-RPC, so the thrown StreamableHTTPError's `.code` is the raw HTTP status (401) and
        // the embedded JSON-RPC error only survives as text inside `.message`. Asserted against
        // the TS client's real, verified behavior rather than the Python-side shape it does not
        // actually produce.
        await expect(
          client.callTool({ name: "list_decisions", arguments: {} }),
        ).rejects.toMatchObject({
          code: 401,
          message: expect.stringMatching(/authentication required/i),
        });
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "an invalid (but present) bearer clears the auth challenge, then surfaces the real " +
      "downstream auth failure as a normal tool result -- never a transport crash",
    async () => {
      const client = await connectStreamable(server.baseUrl, {
        // Well-formed enough to pass the ASGI-layer "a credential was presented" gate, but not a
        // real key -- Postgres-backed auth rejects it for real.
        Authorization: "Bearer de_live_ts_conformance_does_not_exist_in_postgres",
      });
      try {
        const result = await client.callTool({ name: "list_decisions", arguments: {} });
        expect(result.isError).toBeFalsy();
        const text = firstTextContent(result);
        expect(text).toContain("invalid_api_key");
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "X-Algenta-Product: codna scopes list_tools/call_tool to the real codna edition allowlist",
    async () => {
      const client = await connectStreamable(server.baseUrl, {
        Authorization: `Bearer ${server.ownerKey}`,
        "X-Algenta-Product": "codna",
      });
      try {
        const { tools } = await client.listTools();
        const names = new Set(tools.map(tool => tool.name));
        // Real curated edition (packages/mcp/algenta_mcp/products.py ALGENTA_CODING_TOOLS): well
        // under the full registry, and it does include the coding/decision-memory tools.
        expect(tools.length).toBeLessThan(100);
        expect(names.has("list_decisions")).toBe(true);
        // Real tools that exist in the full registry but are NOT part of this edition -- the
        // filter must actually narrow the set, not just relabel it.
        expect(names.has("execute_decision")).toBe(false);
        expect(names.has("approve_agent_run")).toBe(false);

        // The edition boundary is enforced on call, not just on the list -- a tool outside the
        // scoped edition is rejected as unknown (fail closed), surfaced as a normal tool result.
        const blocked = await client.callTool({ name: "execute_decision", arguments: {} });
        expect(blocked.isError).toBeFalsy();
        expect(firstTextContent(blocked)).toContain("unknown_tool");
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "legacy (deprecated) HTTP+SSE transport still completes initialize/list/call with a real bearer",
    async () => {
      const client = await connectLegacySse(server.baseUrl, {
        Authorization: `Bearer ${server.ownerKey}`,
      });
      try {
        expect(client.getServerVersion()?.name).toBe("algenta-mcp");
        const { tools } = await client.listTools();
        expect(tools.some(tool => tool.name === "list_decisions")).toBe(true);

        const result = await client.callTool({ name: "list_decisions", arguments: {} });
        expect(result.isError).toBeFalsy();
        expect(firstTextContent(result)).toContain('"decisions"');
      } finally {
        await client.close();
      }
    },
    30_000,
  );

  it(
    "legacy transport requires auth on EVERY method (unlike the modern mount's open discovery)",
    async () => {
      const transport = new SSEClientTransport(new URL("/mcp/sse", server.baseUrl)); // no headers
      const client = new Client(CLIENT_INFO, { capabilities: {} });
      await expect(client.connect(transport)).rejects.toMatchObject({ code: 401 });
      await client.close().catch(() => undefined);
    },
    30_000,
  );

  it(
    "two independent official-SDK client sessions against the same stateless endpoint don't interfere",
    async () => {
      // Not the multi-replica LB proof (see the file header) -- a single-process, two-session
      // check that the stateless streamable-HTTP session manager keeps concurrent callers apart.
      const [clientA, clientB] = await Promise.all([
        connectStreamable(server.baseUrl, { Authorization: `Bearer ${server.ownerKey}` }),
        connectStreamable(server.baseUrl, { Authorization: `Bearer ${server.ownerKey}` }),
      ]);
      try {
        const [resultA, resultB] = await Promise.all([
          clientA.callTool({ name: "list_decisions", arguments: {} }),
          clientB.callTool({ name: "list_decisions", arguments: {} }),
        ]);
        expect(resultA.isError).toBeFalsy();
        expect(resultB.isError).toBeFalsy();
        expect(firstTextContent(resultA)).toContain('"decisions"');
        expect(firstTextContent(resultB)).toContain('"decisions"');
      } finally {
        await Promise.all([clientA.close(), clientB.close()]);
      }
    },
    30_000,
  );
});
