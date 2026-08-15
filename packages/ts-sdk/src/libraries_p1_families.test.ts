import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./runtime_daemon_client.js", () => ({
  executeRuntimeLibrary: vi.fn(),
  getRuntimeLibraryHealth: vi.fn(),
  listRuntimeLibraryModules: vi.fn(),
}));

import { MojoRuntime } from "./libraries.js";
import { MojoModuleNotRegisteredError } from "./mojo_errors.js";
import { executeRuntimeLibrary, listRuntimeLibraryModules } from "./runtime_daemon_client.js";

const listRuntimeLibraryModulesMock = vi.mocked(listRuntimeLibraryModules);
const executeRuntimeLibraryMock = vi.mocked(executeRuntimeLibrary);

/**
 * The twelve P1 analytical families, and one function of each that the TypeScript SDK is
 * required to reach.
 *
 * The catalog is generic — `LibraryCatalog` proxies whatever module descriptors the local
 * runtime reports, so no family is named anywhere in the SDK source and none has to be. That
 * makes reachability a property of the CONTRACT rather than of this package, and a property no
 * SDK test could observe unless it reads the contract. So this suite reads the generated
 * artifact and drives the real catalog with it. A family removed from the contract, a module
 * renamed, or a function dropped by a signature edit that slid past the inventory's nine-line
 * lookahead all fail here, at the layer that says "reachable from the TypeScript SDK".
 *
 * The functions below are the same twelve executed end to end against a local runtime; their
 * returned values are recorded in the pull request that added this file.
 */
const P1_FAMILY_ENTRY_POINTS: ReadonlyArray<readonly [string, string, string]> = [
  ["forecasting", "forecasting.point", "ets_ann_forecast"],
  ["inference", "inference.core", "inference_t_sf_two_sided"],
  ["causal_inference", "causal_inference.estimators", "naive_ate"],
  ["survival_analysis", "survival_analysis.km", "km_fit"],
  ["streaming", "streaming.quantiles", "quantile_ingest"],
  ["geospatial", "geospatial.polygon", "ring_area_flat"],
  ["discrete_event", "discrete_event.queue_sim", "qs_closed_form_flat"],
  ["evaluation", "evaluation.scores", "log_loss_flat"],
  ["data_quality", "data_quality.profile", "profile_column"],
  ["strategy", "strategy.equilibrium", "eq_exploitability_flat"],
  ["sparse_numerics", "sparse_numerics.spmv", "spmv_frobenius_norm_driver"],
  ["graph_analytics", "graph_analytics.centrality", "graph_degree_centrality"],
];

interface ContractFunction {
  name: string;
}

interface ContractModule {
  name: string;
  engine: string;
  functions: ContractFunction[];
}

interface RuntimeContract {
  module_count: number;
  function_count: number;
  modules: ContractModule[];
}

const CONTRACT_PATH = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "../../algenta/algenta/runtime_library_contract.json",
);

// CONTRACT_PATH points at the proprietary Algenta Engine's full function catalog
// (packages/algenta, the closed-source runtime/CLI). This file is mirrored into the public
// thyn-ai/algenta-sdk repo, which deliberately never contains packages/algenta — so there,
// CONTRACT_PATH never resolves. Skip rather than fail: this checks SDK-to-proprietary-engine
// reachability, which is only meaningful where both sides exist together (this repo). Nothing
// about the TypeScript SDK itself is untested by skipping this — see the rest of this file's
// suite for that.
const hasContract = existsSync(CONTRACT_PATH);

function loadContract(): RuntimeContract {
  return JSON.parse(readFileSync(CONTRACT_PATH, "utf8")) as RuntimeContract;
}

function familyOf(moduleName: string): string {
  const dot = moduleName.indexOf(".");
  return dot === -1 ? moduleName : moduleName.slice(0, dot);
}

/**
 * The descriptor shape the local runtime reports for a module, built from the contract exactly
 * as the runtime's own inventory does: canonical import path, engine, function names.
 */
function descriptorsForFamilies(contract: RuntimeContract, families: ReadonlySet<string>) {
  return contract.modules
    .filter(module => families.has(familyOf(module.name)))
    .map(module => ({
      name: module.name,
      engine: "mojo",
      functions: module.functions.map(fn => fn.name).sort((a, b) => a.localeCompare(b)),
    }));
}

describe.skipIf(!hasContract)("the twelve P1 families are reachable from the TypeScript MojoRuntime", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("keeps every family, module and entry point in the generated runtime contract", () => {
    const contract = loadContract();
    const byName = new Map(contract.modules.map(module => [module.name, module]));

    for (const [family, moduleName, functionName] of P1_FAMILY_ENTRY_POINTS) {
      const module = byName.get(moduleName);
      expect(module, `${moduleName} is absent from the runtime contract`).toBeDefined();
      expect(familyOf(moduleName)).toBe(family);
      expect(
        module!.functions.map(fn => fn.name),
        `${moduleName}.${functionName} is absent from the runtime contract`,
      ).toContain(functionName);
    }

    // A family reduced to a single module is a family one signature edit away from vanishing,
    // so the count is pinned as a floor rather than left implicit.
    for (const family of new Set(P1_FAMILY_ENTRY_POINTS.map(([name]) => name))) {
      const modules = contract.modules.filter(module => familyOf(module.name) === family);
      expect(modules.length, `${family} has no modules in the runtime contract`).toBeGreaterThan(2);
    }
  });

  it("resolves and dispatches one entry point per family through the catalog proxy", async () => {
    const contract = loadContract();
    const families = new Set(P1_FAMILY_ENTRY_POINTS.map(([family]) => family));
    listRuntimeLibraryModulesMock.mockResolvedValue(descriptorsForFamilies(contract, families));

    const runtime = new MojoRuntime();
    const catalog = await runtime.libraries();

    for (const [, moduleName, functionName] of P1_FAMILY_ENTRY_POINTS) {
      executeRuntimeLibraryMock.mockResolvedValueOnce({
        module: moduleName,
        function: functionName,
        result: { ok: true },
        latency_ms: 0.5,
        engine_used: "mojo",
        request_id: null,
      });

      const moduleProxy = catalog.module(moduleName);
      expect(moduleProxy.hasFunction(functionName)).toBe(true);

      // Attribute access on the proxy is the surface a user writes, so it is the surface tested:
      // `catalog.module("forecasting.point").ets_ann_forecast(...)`.
      const callable = moduleProxy[functionName];
      expect(typeof callable).toBe("function");
      await expect(callable([1, 2, 3], 0.5)).resolves.toEqual({ ok: true });

      const [, request] = executeRuntimeLibraryMock.mock.calls.at(-1)!;
      expect(request.module).toBe(moduleName);
      expect(request.function).toBe(functionName);
      expect(request.args).toEqual([[1, 2, 3], 0.5]);

      // The underscore alias is how a dotted module is reached as a property.
      const aliased = (catalog as unknown as Record<string, typeof moduleProxy>)[
        moduleName.replace(/\./g, "_")
      ];
      expect(aliased.name).toBe(moduleName);
    }

    expect(executeRuntimeLibraryMock).toHaveBeenCalledTimes(P1_FAMILY_ENTRY_POINTS.length);
  });

  it("refuses a family the local runtime does not report", async () => {
    const contract = loadContract();
    listRuntimeLibraryModulesMock.mockResolvedValue(
      descriptorsForFamilies(contract, new Set(["forecasting"])),
    );

    const catalog = await new MojoRuntime().libraries();

    // Non-vacuity for the assertion above: resolution really does depend on the inventory, so a
    // family that is not reported is an error and not a silently empty proxy.
    expect(() => catalog.module("survival_analysis.km")).toThrow(MojoModuleNotRegisteredError);
    expect(() => (catalog as unknown as Record<string, unknown>).survival_analysis_km).toThrow(
      MojoModuleNotRegisteredError,
    );
    expect(catalog.module("forecasting.point").hasFunction("ets_ann_forecast")).toBe(true);
  });
});
