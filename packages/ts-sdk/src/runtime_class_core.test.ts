// SPDX-License-Identifier: Apache-2.0
/**
 * The Runtime class core in _runtime_class.ts: constructor validation of mode and
 * control-plane configuration, lazy client construction, and the normalization of
 * upstream contract errors into RuntimeValidationError. Runtime behaviour beyond
 * construction lives in the runtime_*.test.ts suites.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DecisionEngineClient, DecisionEngineError } from "./client.js";
import { DEFAULT_BASE_URL } from "./contract.js";
import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
} from "./runtime.js";
import { makeRuntimeManifestPayload } from "./_runtime_test_helpers.js";

const ORIGINAL_ENV = { ...process.env };

const RUNTIME_ENV_KEYS = [
  "ALGENTA_API_KEY",
  "DE_API_KEY",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
  "ALGENTA_API_URL",
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_TELEMETRY_MODE",
  "ALGENTA_METERING_MODE",
  "ALGENTA_CONTROL_PLANE_URL",
  "ALGENTA_RUNTIME_DIR",
];

beforeEach(() => {
  for (const key of RUNTIME_ENV_KEYS) delete process.env[key];
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

function expectConfigurationError(build: () => unknown, code: string, fragment: string): void {
  expect(build).toThrow(RuntimeConfigurationError);
  try {
    build();
  } catch (error) {
    expect(error).toMatchObject({ code, message: expect.stringContaining(fragment) });
  }
}

describe("Runtime construction", () => {
  it("rejects an unknown mode", () => {
    expect(() => new Runtime({ mode: "hosted" as never })).toThrow(RuntimeValidationError);
    expect(() => new Runtime({ mode: "hosted" as never })).toThrow("Expected 'local', 'api', or 'self_hosted'");
    try {
      new Runtime({ mode: "hosted" as never });
    } catch (error) {
      expect(error).toMatchObject({ code: "invalid_mode", details: { mode: "hosted" } });
    }
  });

  it("describes itself without leaking the key", () => {
    expect(String(new Runtime({ mode: "local" }))).toBe('Runtime(mode="local", apiKey=not set)');
    expect(String(new Runtime({ mode: "api", apiKey: "de_test_secret" }))).toBe(
      'Runtime(mode="api", apiKey=set)',
    );
  });

  it("picks the API key up from the environment in either spelling", () => {
    process.env.DE_API_KEY = "de_legacy";
    expect(new Runtime({ mode: "api" }).apiKey).toBe("de_legacy");
    process.env.ALGENTA_API_KEY = "de_primary";
    expect(new Runtime({ mode: "api" }).apiKey).toBe("de_primary");
    // An explicit key wins and, in local mode, switches hosted limits on by default.
    const explicit = new Runtime({ mode: "local", apiKey: "de_explicit" });
    expect(explicit.apiKey).toBe("de_explicit");
    expect(explicit.enforceLimits).toBe(true);
    expect(new Runtime({ mode: "local" }).enforceLimits).toBe(false);
    expect(new Runtime({ mode: "local", apiKey: "de_explicit", enforceLimits: false }).enforceLimits).toBe(false);
  });

  it("normalizes base URLs per mode and threads client options through", () => {
    const selfHosted = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_key",
      baseUrl: "  https://engine.customer.internal/  ",
      timeout: 5_000,
      maxRetries: 1,
      defaultHeaders: { "X-Trace": "1" },
    });
    expect(selfHosted.baseUrl).toBe("https://engine.customer.internal");
    expect(selfHosted.clientConfig).toEqual({
      apiKey: "de_test_key",
      baseUrl: "https://engine.customer.internal",
      timeout: 5_000,
      maxRetries: 1,
      defaultHeaders: { "X-Trace": "1" },
    });
    expect(new Runtime({ mode: "api", apiKey: "de_test_key" }).baseUrl).toBe(DEFAULT_BASE_URL);
    // Local mode keeps the caller's spelling; the URL is still checked as a control-plane
    // destination because saas defaults to control_plane_sync telemetry.
    expect(new Runtime({ mode: "local", baseUrl: "https://engine.customer.internal/" }).baseUrl).toBe(
      "https://engine.customer.internal/",
    );
  });

  it("forbids control-plane sync in air_gapped deployments", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    process.env.ALGENTA_TELEMETRY_MODE = "control_plane_sync";
    expectConfigurationError(
      () => new Runtime({ mode: "local" }),
      "air_gapped_control_plane_sync_forbidden",
      "air_gapped deployments cannot use control_plane_sync",
    );
    delete process.env.ALGENTA_TELEMETRY_MODE;
    process.env.ALGENTA_METERING_MODE = "control_plane_sync";
    expectConfigurationError(
      () => new Runtime({ mode: "local" }),
      "air_gapped_control_plane_sync_forbidden",
      "metering",
    );
  });

  it("requires a control-plane URL when sync is on and the cloud default is disabled", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_METERING_MODE = "control_plane_sync";
    expectConfigurationError(
      () => new Runtime({ mode: "local" }),
      "control_plane_url_required",
      "requires a non-empty ALGENTA_CONTROL_PLANE_URL",
    );
    // A trailing-slash URL satisfies the check and passes egress validation.
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://control.customer.internal/";
    process.env.ALGENTA_EGRESS_ALLOWLIST = "control.customer.internal";
    expect(() => new Runtime({ mode: "local" })).not.toThrow();
  });

  it("maps control-plane egress and URL failures to configuration errors", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://api.algenta.ai";
    expect(() => new Runtime({ mode: "local" })).toThrow(RuntimeConfigurationError);
    try {
      new Runtime({ mode: "local" });
    } catch (error) {
      expect(error).toMatchObject({
        code: "egress_policy_denied",
        message: expect.stringContaining("Reason: algenta_cloud_disabled"),
        details: {
          reason: "algenta_cloud_disabled",
          surface: "runtime_control_plane_config",
          egress_class: "algenta_cloud",
        },
      });
    }

    process.env.ALGENTA_CONTROL_PLANE_URL = "control.customer.internal";
    expectConfigurationError(
      () => new Runtime({ mode: "local" }),
      "control_plane_url_invalid",
      "must use an absolute http(s) URL",
    );
  });
});

describe("Runtime.client", () => {
  it("prefers an injected client, otherwise builds one lazily and caches it", () => {
    const injected = { marker: "injected" };
    expect(new Runtime({ mode: "api", apiKey: "k", client: injected as never }).client()).toBe(injected);

    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", timeout: 1234 });
    const built = runtime.client();
    expect(built).toBeInstanceOf(DecisionEngineClient);
    expect(built.timeout).toBe(1234);
    expect(runtime.client()).toBe(built);
  });

  it("fails closed without an API key", () => {
    const runtime = new Runtime({ mode: "api" });
    expectConfigurationError(
      () => runtime.client(),
      "api_key_required",
      "Set ALGENTA_API_KEY / DE_API_KEY or pass apiKey",
    );
  });

  it("names the method that needs the API transport", () => {
    const runtime = new Runtime({ mode: "local" });
    expectConfigurationError(
      () => runtime.requireApiTransport("getRuntimeModules"),
      "local_mode_not_supported",
      "getRuntimeModules() is not supported for Runtime({ mode: 'local' })",
    );
    expect(() =>
      new Runtime({ mode: "api", apiKey: "k" }).requireApiTransport("anything"),
    ).not.toThrow();
  });
});

describe("Runtime contract payload normalization", () => {
  const upstreamContractError = new DecisionEngineError(
    "Bad contract",
    502,
    "invalid_contract_payload",
    { error: { code: "invalid_contract_payload", details: { field: "brand" } } },
  );

  it("builds normalized details with and without structured upstream details", () => {
    const runtime = new Runtime({ mode: "local" });
    expect(runtime.buildNormalizedContractErrorDetails(upstreamContractError)).toEqual({
      cause: "Bad contract",
      source_error_code: "invalid_contract_payload",
      source_status_code: 502,
      source_error_details: { field: "brand" },
    });
    expect(
      runtime.buildNormalizedContractErrorDetails(new DecisionEngineError("Plain", 500, "server_error")),
    ).toEqual({ cause: "Plain", source_error_code: "server_error", source_status_code: 500 });
  });

  it("rethrows only the listed upstream codes as runtime validation errors", () => {
    const runtime = new Runtime({ mode: "local" });
    expect(() =>
      runtime.rethrowNormalizedContractError(upstreamContractError, "runtime_code", "Normalized.", [
        "invalid_contract_payload",
      ]),
    ).toThrow(RuntimeValidationError);

    const unrelated = new DecisionEngineError("Nope", 403, "forbidden");
    expect(() =>
      runtime.rethrowNormalizedContractError(unrelated, "runtime_code", "Normalized.", ["other"]),
    ).toThrow(unrelated);
    const plain = new TypeError("not a client error");
    expect(() =>
      runtime.rethrowNormalizedContractError(plain, "runtime_code", "Normalized.", ["other"]),
    ).toThrow(plain);
  });

  it("validateContractPayload and validateRuntimeProofPayload wrap validator failures", () => {
    const runtime = new Runtime({ mode: "local" });
    const failing = () => {
      throw new DecisionEngineError("Invalid field", 0, "invalid_payload_fragment");
    };
    const exploding = () => {
      throw new RangeError("validator crashed");
    };

    expect(() => runtime.validateContractPayload("getContract", {}, failing)).toThrow(
      expect.objectContaining({
        code: "invalid_contract_payload",
        message: "getContract() returned an invalid payload.",
      }),
    );
    expect(() => runtime.validateContractPayload("getContract", {}, exploding)).toThrow(RangeError);

    expect(() => runtime.validateRuntimeProofPayload("getRuntimeManifest", {}, failing)).toThrow(
      expect.objectContaining({
        code: "invalid_runtime_contract_payload",
        message: "getRuntimeManifest() returned an invalid signed payload.",
      }),
    );
    expect(() => runtime.validateRuntimeProofPayload("getRuntimeManifest", {}, exploding)).toThrow(
      RangeError,
    );
    expect(runtime.validateContractPayload("x", { ok: true }, value => value)).toEqual({ ok: true });
  });

  it("getRuntimeManifest normalizes upstream and validator failures and returns valid payloads", async () => {
    const manifest = makeRuntimeManifestPayload();
    const getRuntimeManifest = vi
      .fn()
      .mockResolvedValueOnce(manifest)
      .mockRejectedValueOnce(
        new DecisionEngineError("Signed payload rejected", 502, "invalid_runtime_contract_payload"),
      )
      .mockRejectedValueOnce(new DecisionEngineError("Unauthorized", 401, "authentication_error"))
      .mockResolvedValueOnce({ runtime_version: "" });
    const runtime = new Runtime({ mode: "api", apiKey: "k", client: { getRuntimeManifest } as never });

    expect(await runtime.getRuntimeManifest()).toEqual(manifest);

    await expect(runtime.getRuntimeManifest()).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      message: "getRuntimeManifest() returned an invalid signed payload.",
      details: { cause: "Signed payload rejected", source_status_code: 502 },
    });
    await expect(runtime.getRuntimeManifest()).rejects.toMatchObject({ errorCode: "authentication_error" });
    await expect(runtime.getRuntimeManifest()).rejects.toMatchObject({
      code: "invalid_runtime_contract_payload",
      details: { cause: expect.stringContaining("runtime_version") },
    });
  });

  it("queryBatch, querySqlReport and getDatasetSummary pass straight through to the client", async () => {
    const client = {
      queryBatch: vi.fn(async () => ({ results: [] })),
      querySqlReport: vi.fn(async () => ({ rows: [] })),
      getDatasetSummary: vi.fn(async () => ({ dataset_id: "ds_1" })),
    };
    const runtime = new Runtime({ mode: "api", apiKey: "k", client: client as never });
    const batch = { shared: null, queries: [{ key: "a", request: { metric: "revenue" } }] };
    const report = { sources: [], sql: "select 1" } as never;

    expect(await runtime.queryBatch(batch)).toEqual({ results: [] });
    expect(await runtime.querySqlReport(report)).toEqual({ rows: [] });
    expect(await runtime.getDatasetSummary("ds_1")).toEqual({ dataset_id: "ds_1" });
    expect(client.queryBatch).toHaveBeenCalledWith(batch);
    expect(client.querySqlReport).toHaveBeenCalledWith(report);
    expect(client.getDatasetSummary).toHaveBeenCalledWith("ds_1");

    const local = new Runtime({ mode: "local" });
    for (const call of [
      () => local.queryBatch(batch),
      () => local.querySqlReport(report),
      () => local.getDatasetSummary("ds_1"),
    ]) {
      await expect(call()).rejects.toMatchObject({ code: "local_mode_not_supported" });
    }
  });

  it("the runtime proof getters are API-only", async () => {
    const runtime = new Runtime({ mode: "local" });
    for (const call of [
      () => runtime.getRuntimeManifest(),
      () => runtime.getRuntimeModules(),
      () => runtime.getRuntimeBenchmarks(),
      () => runtime.getRuntimeReleaseValidation(),
    ]) {
      await expect(call()).rejects.toMatchObject({ code: "local_mode_not_supported" });
    }
  });
});
