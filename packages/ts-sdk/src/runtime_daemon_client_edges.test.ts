// SPDX-License-Identifier: Apache-2.0
// Edge cases of the gRPC daemon client that runtime_daemon_client.test.ts leaves
// open: timeout validation, transport-load failures, the error-code mapping of
// failed executions, inventory normalization, health classification, and the
// request_id fallbacks of library and query execution.
//
// Errors are matched on `name` rather than with instanceof: every test imports
// a fresh copy of the client after vi.resetModules(), and with it a fresh copy
// of the error classes, so a statically imported class would never match.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const protoLoadMock = vi.fn();
const createInsecureMock = vi.fn(() => ({ insecure: true }));
const loadPackageDefinitionMock = vi.fn();

type Callback = (error: unknown, response: unknown) => void;
type Handler = (request: unknown, options: unknown, callback: Callback) => void;
type RuntimeClientHandlers = {
  Health?: Handler;
  ListModules?: Handler;
  ExecuteModule?: Handler;
  ExecuteQuery?: Handler;
  close?: () => void;
};

let currentHandlers: RuntimeClientHandlers = {};

const ClientConstructorMock = vi.fn(function RuntimeClient(this: RuntimeClientHandlers) {
  Object.assign(this, currentHandlers);
});

function grpcModule() {
  return {
    credentials: { createInsecure: createInsecureMock },
    loadPackageDefinition: loadPackageDefinitionMock,
  };
}

function resetPackageDefinition(): void {
  loadPackageDefinitionMock.mockReturnValue({
    algenta: { runtime: { v1: { CodnaRuntime: ClientConstructorMock } } },
  });
  protoLoadMock.mockResolvedValue({});
}
resetPackageDefinition();

vi.mock("@grpc/proto-loader", () => ({
  load: protoLoadMock,
}));

vi.mock("@grpc/grpc-js", () => grpcModule());

const ORIGINAL_DAEMON_TCP = process.env.ALGENTA_DAEMON_TCP;
const CONFIGURATION_ERROR = "MojoRuntimeConfigurationError";
const MODULES = [
  { name: "ab_testing", engine: "mojo", functions: ["power"] },
  { name: "pricing", engine: "mojo", functions: ["elasticity"] },
];
const EXECUTE_REQUEST = { module: "pricing", function: "elasticity", args: { p: 1 } };

function reply(response: unknown): Handler {
  return (_request, _options, callback) => callback(null, response);
}

function fail(error: unknown): Handler {
  return (_request, _options, callback) => callback(error, undefined);
}

function executeResponse(overrides: Record<string, unknown>) {
  return { latency_ms: 0.4, engine_used: "mojo", success: false, ...overrides };
}

async function loadClient() {
  return import("./runtime_daemon_client.js");
}

describe("runtime daemon client edges", () => {
  beforeEach(() => {
    // The default target is read at module load, so it must be absent before import.
    delete process.env.ALGENTA_DAEMON_TCP;
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.useRealTimers();
    // resetModules() keeps mocked modules cached; unmock first so the base
    // factory is evaluated again after a test swapped it out.
    vi.doUnmock("@grpc/grpc-js");
    vi.doMock("@grpc/grpc-js", () => grpcModule());
    currentHandlers = {};
    resetPackageDefinition();
    if (ORIGINAL_DAEMON_TCP === undefined) {
      delete process.env.ALGENTA_DAEMON_TCP;
    } else {
      process.env.ALGENTA_DAEMON_TCP = ORIGINAL_DAEMON_TCP;
    }
  });

  describe("configuration", () => {
    it.each([0, -5, Number.NaN, Number.POSITIVE_INFINITY])(
      "rejects a timeout of %s and still closes the client",
      async timeout => {
        const close = vi.fn();
        currentHandlers = { ListModules: reply({ modules: MODULES }), close };
        const client = await loadClient();

        await expect(client.listRuntimeLibraryModules({ timeout })).rejects.toMatchObject({
          name: CONFIGURATION_ERROR,
          code: "compute_runtime_unavailable",
          message: "Mojo runtime timeout must be a positive number of milliseconds.",
          details: { timeout },
        });
        expect(close).toHaveBeenCalledOnce();
      },
    );

    it("uses the default target and a 30 s deadline when nothing is configured", async () => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(1_700_000_000_000));
      let capturedOptions: unknown;
      currentHandlers = {
        ListModules: (_request, options, callback) => {
          capturedOptions = options;
          callback(null, { modules: MODULES });
        },
        close: vi.fn(),
      };
      const client = await loadClient();

      await client.listRuntimeLibraryModules();

      expect(ClientConstructorMock).toHaveBeenCalledWith(
        "127.0.0.1:50099",
        { insecure: true },
        expect.any(Object),
      );
      expect(capturedOptions).toEqual({ deadline: 1_700_000_030_000 });
    });

    it("fails closed when the loaded package exposes no CodnaRuntime service", async () => {
      loadPackageDefinitionMock.mockReturnValue({ algenta: { runtime: { v1: {} } } });
      const client = await loadClient();

      await expect(client.listRuntimeLibraryModules()).rejects.toMatchObject({
        name: CONFIGURATION_ERROR,
        code: "compute_runtime_unavailable",
        message: "The Algenta runtime gRPC contract is unavailable.",
        details: { proto_path: expect.stringMatching(/proto[\\/]runtime\.proto$/) },
      });
      expect(ClientConstructorMock).not.toHaveBeenCalled();
    });

    it("fails closed when the gRPC transport packages cannot be imported", async () => {
      vi.doUnmock("@grpc/grpc-js");
      vi.doMock("@grpc/grpc-js", () => {
        throw new Error("Cannot find module '@grpc/grpc-js'");
      });
      const client = await loadClient();

      await expect(client.listRuntimeLibraryModules()).rejects.toMatchObject({
        name: CONFIGURATION_ERROR,
        code: "compute_runtime_unavailable",
        message: expect.stringContaining("TypeScript gRPC runtime client is unavailable"),
        // vitest reports a throwing factory with its own wrapper text, so only the
        // presence of the underlying import error is asserted here.
        details: { error: expect.any(String) },
      });
      expect(ClientConstructorMock).not.toHaveBeenCalled();
    });
  });

  describe("library execution", () => {
    // module_not_registered is covered by runtime_daemon_client.test.ts.
    it.each([
      [
        "function_not_registered: Unknown function.",
        "mojo",
        "MojoFunctionNotRegisteredError",
        "function_not_registered",
        "Unknown function.",
      ],
      [
        "compute_runtime_unavailable: Worker is down.",
        "unavailable",
        CONFIGURATION_ERROR,
        "compute_runtime_unavailable",
        "Worker is down.",
      ],
      ["kernel_panic: Divide by zero.", "mojo", "MojoExecutionError", "kernel_panic", "Divide by zero."],
      [
        "plain failure text",
        "unavailable",
        CONFIGURATION_ERROR,
        "compute_runtime_unavailable",
        "plain failure text",
      ],
      [
        "   ",
        "mojo",
        CONFIGURATION_ERROR,
        "compute_runtime_unavailable",
        "Runtime-backed Mojo execution failed.",
      ],
      [
        undefined,
        "mojo",
        CONFIGURATION_ERROR,
        "compute_runtime_unavailable",
        "Runtime-backed Mojo execution failed.",
      ],
    ])("maps the failure %j to a typed error", async (error, engineUsed, name, code, message) => {
      currentHandlers = {
        ExecuteModule: reply(executeResponse({ error, engine_used: engineUsed, request_id: "resp-1" })),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(
        client.executeRuntimeLibrary({ timeout: 500 }, EXECUTE_REQUEST),
      ).rejects.toMatchObject({
        name,
        code,
        message,
        details: {
          module: "pricing",
          function: "elasticity",
          engine_used: engineUsed,
          request_id: "resp-1",
        },
      });
    });

    it.each([
      ["the response's request_id", "resp-1", "req-1", "resp-1"],
      ["the request's request_id", undefined, "req-1", "req-1"],
      ["null", undefined, undefined, null],
    ])("reports %s in failure details", async (_label, responseId, requestId, expected) => {
      currentHandlers = {
        ExecuteModule: reply(
          executeResponse({ error: "kernel_panic: Boom.", request_id: responseId }),
        ),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(
        client.executeRuntimeLibrary({ timeout: 500 }, { ...EXECUTE_REQUEST, request_id: requestId }),
      ).rejects.toMatchObject({ details: { request_id: expected } });
    });

    it("rejects a successful call whose result_json is not JSON", async () => {
      currentHandlers = {
        ExecuteModule: reply(executeResponse({ success: true, result_json: "{nope" })),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(
        client.executeRuntimeLibrary({ timeout: 500 }, EXECUTE_REQUEST),
      ).rejects.toMatchObject({
        name: "MojoExecutionError",
        code: "compute_runtime_unavailable",
        message: "The local runtime returned malformed JSON for a runtime call.",
        details: { result_json: "{nope", error: expect.stringContaining("JSON") },
      });
    });

    it.each([
      ["a JSON result and the response id", '{"value":2}', "resp-1", "req-1", { value: 2 }, "resp-1"],
      ["a null result and the request id", undefined, "", "req-1", null, "req-1"],
      ["a null result and no id at all", "null", "", undefined, null, null],
    ])(
      "decodes a successful execution with %s",
      async (_label, resultJson, responseId, requestId, result, expectedId) => {
        let captured: unknown;
        currentHandlers = {
          ExecuteModule: (request, _options, callback) => {
            captured = request;
            callback(
              null,
              executeResponse({
                success: true,
                result_json: resultJson,
                latency_ms: 2.5,
                request_id: responseId,
              }),
            );
          },
          close: vi.fn(),
        };
        const client = await loadClient();

        const response = await client.executeRuntimeLibrary(
          { timeout: 500 },
          { module: "pricing", function: "elasticity", request_id: requestId },
        );

        expect(response).toEqual({
          module: "pricing",
          function: "elasticity",
          result,
          latency_ms: 2.5,
          engine_used: "mojo",
          request_id: expectedId,
        });
        // Absent args serialize as JSON null and an absent id as the empty string.
        expect(captured).toEqual({
          module: "pricing",
          function: "elasticity",
          args_json: "null",
          request_id: requestId ?? "",
        });
      },
    );
  });

  describe("inventory normalization", () => {
    it.each([
      [
        "a non-string module name",
        { modules: [{ name: 42, engine: "mojo", functions: ["f"] }] },
        "The local runtime returned a malformed Mojo library descriptor.",
        { module: 42 },
      ],
      [
        "a blank engine",
        { modules: [{ name: "m", engine: "  ", functions: ["f"] }] },
        "The local runtime returned a malformed engine for 'm'.",
        { module: "m", engine: "  " },
      ],
      [
        "a functions field that is not a list",
        { modules: [{ name: "m", engine: "mojo", functions: "f" }] },
        "The local runtime returned malformed functions for 'm'.",
        { module: "m", functions: "f" },
      ],
      [
        "a non-string function",
        { modules: [{ name: "m", engine: "mojo", functions: [1] }] },
        "The local runtime returned a malformed function for 'm'.",
        { module: "m", function: 1 },
      ],
      [
        "a duplicate function (after trimming)",
        { modules: [{ name: "m", engine: "mojo", functions: ["f", " f "] }] },
        "The local runtime returned duplicate functions for 'm'.",
        { module: "m", function: "f" },
      ],
      [
        "a module with no functions",
        { modules: [{ name: "m", engine: "mojo", functions: [] }] },
        "The local runtime exposed 'm' without executable functions.",
        { module: "m" },
      ],
      [
        "a null inventory",
        null,
        "The local runtime returned a malformed Mojo library inventory.",
        { response: null },
      ],
      [
        "a string inventory",
        "text",
        "The local runtime returned a malformed Mojo library inventory.",
        { response: "text" },
      ],
    ])("rejects %s", async (_label, response, message, details) => {
      currentHandlers = { ListModules: reply(response), close: vi.fn() };
      const client = await loadClient();

      await expect(client.listRuntimeLibraryModules({ timeout: 500 })).rejects.toMatchObject({
        name: CONFIGURATION_ERROR,
        code: "compute_runtime_unavailable",
        message,
        details,
      });
    });

    it.each([[{ modules: null }], [{}]])("treats %j as an empty inventory", async response => {
      currentHandlers = { ListModules: reply(response), close: vi.fn() };
      const client = await loadClient();

      await expect(client.listRuntimeLibraryModules({ timeout: 500 })).resolves.toEqual([]);
    });

    it("trims names and engines, sorts functions and modules", async () => {
      currentHandlers = {
        ListModules: reply({
          modules: [
            { name: " zeta ", engine: " mojo ", functions: ["b", "a"] },
            { name: "alpha", engine: "mojo", functions: ["only"] },
          ],
        }),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(client.listRuntimeLibraryModules({ timeout: 500 })).resolves.toEqual([
        { name: "alpha", engine: "mojo", functions: ["only"] },
        { name: "zeta", engine: "mojo", functions: ["a", "b"] },
      ]);
    });
  });

  describe("transport failures", () => {
    it.each([
      ["a gRPC status object with details", { code: 14, details: "connect ECONNREFUSED" }, "connect ECONNREFUSED"],
      ["an Error", new Error("boom"), "boom"],
      ["a string", "string failure", "string failure"],
      ["an object without string details", { code: 14 }, "[object Object]"],
    ])("wraps %s as a daemon-unavailable configuration error", async (_label, error, expected) => {
      const close = vi.fn();
      currentHandlers = { ListModules: fail(error), close };
      const client = await loadClient();

      await expect(
        client.listRuntimeLibraryModules({ tcpAddress: "10.0.0.5:1", timeout: 500 }),
      ).rejects.toMatchObject({
        name: CONFIGURATION_ERROR,
        code: "compute_runtime_unavailable",
        message: expect.stringContaining("The local Algenta runtime daemon is unavailable."),
        details: { daemon_target: "10.0.0.5:1", error: expected },
      });
      expect(close).toHaveBeenCalledOnce();
    });
  });

  describe("health", () => {
    it.each([
      [{ ok: true, engine: "mojo" }, "ok", "mojo", true],
      [{ ok: true, engine: "python_fallback" }, "unavailable", "unavailable", false],
      [{ ok: false, engine: "mojo" }, "unavailable", "unavailable", false],
    ])("classifies the health reply %j", async (health, status, engine, runtimeAvailable) => {
      currentHandlers = {
        Health: reply({ ...health, version: "1.0", uptime_seconds: 5 }),
        ListModules: reply({ modules: MODULES }),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(client.getRuntimeLibraryHealth({ timeout: 500 })).resolves.toEqual({
        status,
        engine,
        module_count: 2,
        runtime_available: runtimeAvailable,
      });
    });

    it("reports unavailable when the inventory fails even though Health succeeded", async () => {
      currentHandlers = {
        Health: reply({ ok: true, engine: "mojo", version: "1.0", uptime_seconds: 5 }),
        ListModules: fail(new Error("inventory exploded")),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(client.getRuntimeLibraryHealth({ timeout: 500 })).resolves.toEqual({
        status: "unavailable",
        engine: "unavailable",
        module_count: 0,
        runtime_available: false,
      });
    });
  });

  describe("query execution", () => {
    it.each([
      [
        "an unprefixed error and the request's id",
        { error: "plain refusal", request_id: undefined },
        "req-q",
        { code: "compute_runtime_unavailable", message: "plain refusal", requestId: "req-q" },
      ],
      [
        "a blank error and no id",
        { error: "", request_id: undefined },
        undefined,
        {
          code: "compute_runtime_unavailable",
          message: "Local runtime query execution failed.",
          requestId: null,
        },
      ],
      [
        "a prefixed error and the response's id",
        { error: "bad_plan: nope", request_id: "resp-q" },
        "req-q",
        { code: "bad_plan", message: "nope", requestId: "resp-q" },
      ],
    ])("fails a query with %s", async (_label, fields, requestId, expected) => {
      currentHandlers = {
        ExecuteQuery: reply({ latency_ms: 0, engine_used: "unavailable", success: false, ...fields }),
        close: vi.fn(),
      };
      const client = await loadClient();

      await expect(
        client.executeQuery(
          { timeout: 500 },
          { request: { columns: ["a"], ops: [] }, request_id: requestId },
        ),
      ).rejects.toMatchObject({
        name: CONFIGURATION_ERROR,
        code: expected.code,
        message: expected.message,
        details: { engine_used: "unavailable", request_id: expected.requestId },
      });
    });

    it.each([
      ["the request's id", "", "req-q", "req-q"],
      ["no id at all", "", undefined, null],
    ])("decodes an empty response body with %s", async (_label, responseId, requestId, expectedId) => {
      let captured: unknown;
      currentHandlers = {
        ExecuteQuery: (request, _options, callback) => {
          captured = request;
          callback(null, {
            response_json: undefined,
            latency_ms: 3,
            engine_used: "mojo",
            success: true,
            request_id: responseId,
          });
        },
        close: vi.fn(),
      };
      const client = await loadClient();

      const result = await client.executeQuery(
        { timeout: 500 },
        { request: undefined as never, request_id: requestId },
      );

      expect(result).toEqual({
        response: {},
        latency_ms: 3,
        engine_used: "mojo",
        request_id: expectedId,
      });
      expect(captured).toEqual({ request_json: "{}", request_id: requestId ?? "" });
    });
  });
});
