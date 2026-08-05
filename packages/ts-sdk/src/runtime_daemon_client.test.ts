import { afterEach, describe, expect, it, vi } from "vitest";

const protoLoadMock = vi.fn();
const createInsecureMock = vi.fn(() => ({ insecure: true }));
const loadPackageDefinitionMock = vi.fn();

type RuntimeClientHandlers = {
  Health?: (request: unknown, options: unknown, callback: (error: unknown, response: unknown) => void) => void;
  ListModules?: (request: unknown, options: unknown, callback: (error: unknown, response: unknown) => void) => void;
  ExecuteModule?: (request: unknown, options: unknown, callback: (error: unknown, response: unknown) => void) => void;
  ExecuteQuery?: (request: unknown, options: unknown, callback: (error: unknown, response: unknown) => void) => void;
  close?: () => void;
};

let currentHandlers: RuntimeClientHandlers = {};

const ClientConstructorMock = vi.fn(function RuntimeClient(this: RuntimeClientHandlers) {
  Object.assign(this, currentHandlers);
});

loadPackageDefinitionMock.mockReturnValue({
  algenta: {
    runtime: {
      v1: {
        CodnaRuntime: ClientConstructorMock,
      },
    },
  },
});
protoLoadMock.mockResolvedValue({});

vi.mock("@grpc/proto-loader", () => ({
  load: protoLoadMock,
}));

vi.mock("@grpc/grpc-js", () => ({
  credentials: {
    createInsecure: createInsecureMock,
  },
  loadPackageDefinition: loadPackageDefinitionMock,
}));

describe("runtime daemon client", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    currentHandlers = {};
    loadPackageDefinitionMock.mockReturnValue({
      algenta: {
        runtime: {
          v1: {
            CodnaRuntime: ClientConstructorMock,
          },
        },
      },
    });
    protoLoadMock.mockResolvedValue({});
  });

  it("lists runtime-backed library modules and filters simulation engines", async () => {
    currentHandlers = {
      ListModules: (_request, _options, callback) =>
        callback(null, {
          modules: [
            { name: "monte_carlo", engine: "mojo", functions: ["run"] },
            { name: "ab_testing", engine: "mojo", functions: ["power", "sample_size"] },
            { name: "pricing", engine: "mojo", functions: ["elasticity"] },
          ],
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");
    const modules = await runtimeDaemonClient.listRuntimeLibraryModules({
      tcpAddress: "127.0.0.1:50099",
      timeout: 500,
    });

    expect(modules).toEqual([
      { name: "ab_testing", engine: "mojo", functions: ["power", "sample_size"] },
      { name: "pricing", engine: "mojo", functions: ["elasticity"] },
    ]);
    expect(protoLoadMock).toHaveBeenCalledOnce();
    expect(createInsecureMock).toHaveBeenCalledOnce();
    // Message-size options are explicit: gRPC's silent 4 MiB receive default is
    // far below what the local transport supports (the worker allows 64 MiB).
    expect(ClientConstructorMock).toHaveBeenCalledWith(
      "127.0.0.1:50099",
      { insecure: true },
      {
        "grpc.max_receive_message_length": 64 * 1024 * 1024,
        "grpc.max_send_message_length": 64 * 1024 * 1024,
      },
    );
  });

  it("maps structured execution failures to explicit runtime errors", async () => {
    currentHandlers = {
      ExecuteModule: (_request, _options, callback) =>
        callback(null, {
          result_json: "null",
          latency_ms: 0.4,
          engine_used: "unavailable",
          success: false,
          error: "module_not_registered: Unknown Mojo module.",
          request_id: "req_1",
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.executeRuntimeLibrary(
        { timeout: 500 },
        {
          module: "missing_module",
          function: "sample_size",
          args: {},
          request_id: "req_1",
        },
      ),
    ).rejects.toMatchObject({
      code: "module_not_registered",
      message: "Unknown Mojo module.",
    });
  });

  it("rejects duplicate runtime library descriptors", async () => {
    currentHandlers = {
      ListModules: (_request, _options, callback) =>
        callback(null, {
          modules: [
            { name: "ab_testing", engine: "mojo", functions: ["sample_size"] },
            { name: "ab_testing", engine: "mojo", functions: ["power"] },
          ],
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.listRuntimeLibraryModules({ timeout: 500 }),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The local runtime returned duplicate Mojo libraries.",
    });
  });

  it("rejects malformed runtime library inventory payloads", async () => {
    currentHandlers = {
      ListModules: (_request, _options, callback) =>
        callback(null, {
          modules: "ab_testing",
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.listRuntimeLibraryModules({ timeout: 500 }),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The local runtime returned a malformed Mojo library inventory.",
      details: {
        modules: "ab_testing",
      },
    });
  });

  it("rejects malformed runtime library descriptor objects", async () => {
    currentHandlers = {
      ListModules: (_request, _options, callback) =>
        callback(null, {
          modules: [null],
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.listRuntimeLibraryModules({ timeout: 500 }),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The local runtime returned a malformed Mojo library descriptor.",
      details: {
        descriptor: null,
      },
    });
  });

  it("rejects malformed runtime function descriptors", async () => {
    currentHandlers = {
      ListModules: (_request, _options, callback) =>
        callback(null, {
          modules: [
            { name: "ab_testing", engine: "mojo", functions: [""] },
          ],
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.listRuntimeLibraryModules({ timeout: 500 }),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "The local runtime returned a malformed function for 'ab_testing'.",
    });
  });

  it("sends a query plan as request_json and decodes the raw engine response", async () => {
    let capturedRequest: unknown;
    currentHandlers = {
      ExecuteQuery: (request, _options, callback) => {
        capturedRequest = request;
        callback(null, {
          response_json: JSON.stringify({
            result: { columns: ["a"], rows: [[1.0]] },
            lineage: [],
            plan_hash: "abc123",
            ops: 1,
          }),
          latency_ms: 5.5,
          engine_used: "mojo",
          success: true,
          request_id: "req_query_1",
        });
      },
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");
    const result = await runtimeDaemonClient.executeQuery(
      { timeout: 500 },
      {
        request: { type: "query_execute", columns: ["a"], rows: [[1]], ops: [], strict: false },
        request_id: "req_query_1",
      },
    );

    expect(capturedRequest).toEqual({
      request_json: JSON.stringify({
        type: "query_execute",
        columns: ["a"],
        rows: [[1]],
        ops: [],
        strict: false,
      }),
      request_id: "req_query_1",
    });
    expect(result.response).toEqual({
      result: { columns: ["a"], rows: [[1.0]] },
      lineage: [],
      plan_hash: "abc123",
      ops: 1,
    });
    expect(result.latency_ms).toBe(5.5);
    expect(result.engine_used).toBe("mojo");
    expect(result.request_id).toBe("req_query_1");
  });

  it("throws on a query transport failure, distinct from an engine-side plan refusal", async () => {
    currentHandlers = {
      ExecuteQuery: (_request, _options, callback) =>
        callback(null, {
          response_json: "null",
          latency_ms: 0,
          engine_used: "unavailable",
          success: false,
          error: "compute_runtime_unavailable: local Mojo runtime is not available.",
          request_id: "",
        }),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");

    await expect(
      runtimeDaemonClient.executeQuery(
        { timeout: 500 },
        { request: { type: "query_execute", columns: ["a"], rows: [], ops: [], strict: false } },
      ),
    ).rejects.toMatchObject({
      code: "compute_runtime_unavailable",
      message: "local Mojo runtime is not available.",
    });
  });

  it("returns unavailable health when the daemon transport cannot be reached", async () => {
    currentHandlers = {
      Health: (_request, _options, callback) =>
        callback({ details: "connect ECONNREFUSED 127.0.0.1:50099" }, undefined),
      close: vi.fn(),
    };

    const runtimeDaemonClient = await import("./runtime_daemon_client.js");
    const health = await runtimeDaemonClient.getRuntimeLibraryHealth({ timeout: 500 });

    expect(health).toEqual({
      status: "unavailable",
      engine: "unavailable",
      module_count: 0,
      runtime_available: false,
    });
  });
});
