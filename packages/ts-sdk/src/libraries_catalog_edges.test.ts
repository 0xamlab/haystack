// SPDX-License-Identifier: Apache-2.0
// Catalog and proxy edge cases for MojoRuntime that libraries.test.ts leaves
// open: invocation shapes, proxy caching and await-safety, alias collisions,
// unknown-module errors, refresh, and the tolerant decoding of query envelopes.
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./runtime_daemon_client.js", () => ({
  executeQuery: vi.fn(),
  executeRuntimeLibrary: vi.fn(),
  getRuntimeLibraryHealth: vi.fn(),
  listRuntimeLibraryModules: vi.fn(),
}));

vi.mock("./native_worker_client.js", () => ({
  callNativeWorker: vi.fn(),
  nativeWorkerAvailable: vi.fn(() => false),
}));

import {
  type LibraryCatalog,
  type LibraryModuleProxy,
  MojoRuntime,
  libraries,
} from "./libraries.js";
import {
  MojoFunctionNotRegisteredError,
  MojoModuleNotRegisteredError,
  MojoRuntimeConfigurationError,
} from "./mojo_errors.js";
import { Query, QueryError } from "./query.js";
import { executeQuery, executeRuntimeLibrary, listRuntimeLibraryModules } from "./runtime_daemon_client.js";
import type { LibraryModuleDescriptor } from "./types.js";

const listRuntimeLibraryModulesMock = vi.mocked(listRuntimeLibraryModules);
const executeRuntimeLibraryMock = vi.mocked(executeRuntimeLibrary);
const executeQueryMock = vi.mocked(executeQuery);

const PRICING: LibraryModuleDescriptor = {
  name: "pricing",
  engine: "mojo",
  functions: ["elasticity", "margin"],
};
const SIGNALS: LibraryModuleDescriptor = {
  name: "signals",
  engine: "mojo",
  functions: ["zscore"],
};
const LOCAL = { mode: "local" as const };

function execution(module: string, functionName: string, result: unknown) {
  return { module, function: functionName, result, latency_ms: 0.5, engine_used: "mojo", request_id: null };
}

async function catalogFor(descriptors: LibraryModuleDescriptor[]): Promise<LibraryCatalog> {
  listRuntimeLibraryModulesMock.mockResolvedValue(descriptors);
  return libraries(LOCAL);
}

function selectA(): Query {
  return new Query({ columns: ["a"], rows: [[1]] }).select("a");
}

describe("MojoRuntime configuration and catalog lifecycle", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("rejects a mode other than local before touching the daemon", () => {
    let caught: unknown;
    try {
      new MojoRuntime({ mode: "hosted" as never });
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(MojoRuntimeConfigurationError);
    expect(caught).toMatchObject({
      code: "compute_runtime_unavailable",
      message: expect.stringContaining("only supports the local Algenta runtime daemon"),
      details: { mode: "hosted" },
    });
    expect(listRuntimeLibraryModulesMock).not.toHaveBeenCalled();
  });

  it("libraries() with no config lists modules with an empty daemon config", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([PRICING]);

    const catalog = await libraries();

    expect(catalog.names()).toEqual(["pricing"]);
    expect(listRuntimeLibraryModulesMock).toHaveBeenCalledWith({});
  });

  it("caches the catalog promise and rebuilds it through refresh()", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([PRICING]);
    const runtime = new MojoRuntime(LOCAL);

    const first = await runtime.libraries();
    const again = await runtime.libraries();
    listRuntimeLibraryModulesMock.mockResolvedValue([PRICING, SIGNALS]);
    const refreshed = await first.refresh();

    // Identity is checked with Object.is: a failing matcher would try to format the
    // catalog proxy, whose unknown-attribute trap throws.
    expect(Object.is(again, first)).toBe(true);
    expect(Object.is(refreshed, first)).toBe(false);
    expect(refreshed.names()).toEqual(["pricing", "signals"]);
    expect(first.names()).toEqual(["pricing"]);
    // refresh() replaces the cached promise, so later callers see the new catalog.
    expect(Object.is(await runtime.libraries(), refreshed)).toBe(true);
    expect(listRuntimeLibraryModulesMock).toHaveBeenCalledTimes(2);
  });

  it("listFunctions() resolves through the catalog and names an unknown module", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([PRICING]);
    const runtime = new MojoRuntime(LOCAL);

    await expect(runtime.listFunctions("pricing")).resolves.toEqual(["elasticity", "margin"]);
    await expect(runtime.listFunctions("missing")).rejects.toBeInstanceOf(
      MojoModuleNotRegisteredError,
    );
    await expect(runtime.listFunctions("missing")).rejects.toMatchObject({
      code: "module_not_registered",
      message: "Unknown runtime library 'missing'.",
      details: { module: "missing" },
    });
  });
});

describe("module proxies", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ["no arguments", [], undefined],
    ["one argument", [{ price: 12 }], { price: 12 }],
    ["several arguments", [12, 24, "eu"], [12, 24, "eu"]],
  ])("forwards %s as the runtime call's args", async (_label, args, expectedArgs) => {
    const catalog = await catalogFor([PRICING]);
    executeRuntimeLibraryMock.mockResolvedValue(execution("pricing", "elasticity", 1.5));

    await expect(catalog.pricing.elasticity(...args)).resolves.toBe(1.5);

    expect(executeRuntimeLibraryMock).toHaveBeenCalledWith(LOCAL, {
      module: "pricing",
      function: "elasticity",
      args: expectedArgs,
      request_id: undefined,
    });
  });

  it("caches callables and module proxies so identity is stable", async () => {
    const catalog = await catalogFor([PRICING]);

    expect(catalog.pricing.elasticity).toBe(catalog.pricing.elasticity);
    expect(catalog.pricing).toBe(catalog.module("pricing"));
    expect(catalog.module("pricing")).toBe(catalog.module("pricing"));
  });

  it("is await-safe: then is undefined and symbol lookups fall through", async () => {
    const catalog = await catalogFor([PRICING]);
    const pricing = catalog.pricing as unknown as Record<string | symbol, unknown>;

    expect(pricing.then).toBeUndefined();
    expect(pricing[Symbol.toPrimitive]).toBeUndefined();
    expect((catalog as unknown as Record<string, unknown>).then).toBeUndefined();
    // Awaiting a proxy must yield the proxy itself rather than hang on a fake thenable.
    expect(await catalog.pricing).toBe(catalog.pricing);
    expect(await catalog).toBe(catalog);
  });

  it("execute() rejects an undeclared function before calling the runtime", async () => {
    const catalog = await catalogFor([PRICING]);

    expect(catalog.pricing.hasFunction("margin")).toBe(true);
    expect(catalog.pricing.hasFunction("nope")).toBe(false);
    await expect(catalog.pricing.execute("nope", {})).rejects.toBeInstanceOf(
      MojoFunctionNotRegisteredError,
    );
    await expect(catalog.pricing.execute("nope", {})).rejects.toMatchObject({
      code: "function_not_registered",
      message: "Module 'pricing' does not expose 'nope'.",
      details: { module: "pricing", function: "nope" },
    });
    expect(executeRuntimeLibraryMock).not.toHaveBeenCalled();
  });

  it("execute() with a declared function returns the runtime result", async () => {
    const catalog = await catalogFor([PRICING]);
    executeRuntimeLibraryMock.mockResolvedValue(execution("pricing", "margin", 0.42));

    await expect(catalog.pricing.execute("margin", { cost: 5 })).resolves.toBe(0.42);
    expect(executeRuntimeLibraryMock).toHaveBeenCalledWith(LOCAL, {
      module: "pricing",
      function: "margin",
      args: { cost: 5 },
      request_id: undefined,
    });
  });
});

describe("catalog lookups", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("throws module_not_registered for an unknown attribute or module()", async () => {
    const catalog = await catalogFor([PRICING]);

    expect(() => (catalog as unknown as Record<string, unknown>).nope).toThrowError(
      MojoModuleNotRegisteredError,
    );
    expect(() => catalog.module("nope")).toThrowError(MojoModuleNotRegisteredError);
    let caught: unknown;
    try {
      catalog.module("nope");
    } catch (error) {
      caught = error;
    }
    expect(caught).toMatchObject({ details: { module: "nope" } });
  });

  it("gives a colliding alias to its first claimant and keeps both full names", async () => {
    // Both names flatten to `a_b_c`, and neither module is literally called that.
    const catalog = await catalogFor([
      { name: "a_b.c", engine: "mojo", functions: ["second"] },
      { name: "a.b_c", engine: "mojo", functions: ["first"] },
    ]);
    const modules = catalog as unknown as Record<string, LibraryModuleProxy>;

    // Modules are ordered by localeCompare, so the claimant is whichever the
    // collation puts first; the alias must resolve to exactly that module.
    const [claimant, other] = catalog.names();
    expect(new Set([claimant, other])).toEqual(new Set(["a.b_c", "a_b.c"]));
    expect(modules.a_b_c.name).toBe(claimant);
    expect(modules[other].name).toBe(other);
    expect(modules["a.b_c"].functions).toEqual(["first"]);
    expect(modules["a_b.c"].functions).toEqual(["second"]);
  });
});

describe("query envelope decoding", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("reports opIndex as null when the engine's op_index is not a number", async () => {
    executeQueryMock.mockResolvedValue({
      response: { error_code: "query_op_failed", error_message: "bad op", op_index: "2" },
      latency_ms: 1,
      engine_used: "mojo",
      request_id: null,
    });

    const error = await new MojoRuntime(LOCAL).query(selectA()).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(QueryError);
    expect(error).toMatchObject({ code: "query_op_failed", message: "bad op", opIndex: null });
  });

  it.each([
    ["error_message", { error_message: "from message", error: "ignored" }, "from message"],
    ["error", { error: "from error" }, "from error"],
    ["nothing", {}, ""],
  ])("takes the refusal message from %s", async (_label, fields, message) => {
    executeQueryMock.mockResolvedValue({
      response: { error_code: "invalid_arguments", ...fields },
      latency_ms: 1,
      engine_used: "mojo",
      request_id: null,
    });

    await expect(new MojoRuntime(LOCAL).query(selectA())).rejects.toMatchObject({
      code: "invalid_arguments",
      message,
    });
  });

  it("decodes an envelope with no result, lineage, hash or op count as empty", async () => {
    executeQueryMock.mockResolvedValue({
      response: {},
      latency_ms: 1,
      engine_used: "mojo",
      request_id: null,
    });

    const result = await new MojoRuntime(LOCAL).query(selectA());

    expect(result.columns).toEqual([]);
    expect(result.rows).toEqual([]);
    expect(result.lineage).toEqual([]);
    expect(result.planHash).toBe("");
    expect(result.ops).toBe(0);
    expect(result.nonFiniteCells).toBe(0);
  });

  it("drops a non-array lineage and keeps a non-finite cell count", async () => {
    executeQueryMock.mockResolvedValue({
      response: {
        result: { columns: ["a"], rows: [[null]] },
        lineage: "not a list",
        plan_hash: "h1",
        ops: 2,
        non_finite_cells: 3,
      },
      latency_ms: 1,
      engine_used: "mojo",
      request_id: null,
    });

    const result = await new MojoRuntime(LOCAL).query(selectA());

    expect(result.lineage).toEqual([]);
    expect(result.rows).toEqual([[null]]);
    expect(result.planHash).toBe("h1");
    expect(result.ops).toBe(2);
    expect(result.nonFiniteCells).toBe(3);
  });

  it("measures latency around the whole round trip, not the daemon's own figure", async () => {
    vi.useFakeTimers();
    executeQueryMock.mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 25));
      return {
        response: { result: { columns: ["a"], rows: [[1]] }, plan_hash: "h", ops: 1 },
        latency_ms: 1,
        engine_used: "mojo",
        request_id: null,
      };
    });

    const pending = new MojoRuntime(LOCAL).query(selectA());
    await vi.advanceTimersByTimeAsync(25);

    expect((await pending).latencyMs).toBe(25);
  });
});
