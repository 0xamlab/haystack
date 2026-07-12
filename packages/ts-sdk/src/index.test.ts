import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  AUTH_SCHEME,
  AlgentaClient,
  API_KEY_PREFIX_LIVE,
  BRAND,
  DEPRECATION_WINDOW_DAYS,
  DEFAULT_BASE_URL,
  DecisionEngineClient,
  INTEGRATIONS,
  LEGACY_HEADERS,
  MojoRuntime,
  MCP_ENDPOINT,
  PRIMARY_DATA_QUERY_CONTRACT,
  libraries,
  PLAN_LIMITS,
  READ_ONLY_DEFAULT,
  Runtime,
} from "./index.js";
import { expectManifestBackedIntegrationsEqual } from "./test_contract_helpers.js";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_BASE_URL;
  delete process.env.DE_BASE_URL;
  delete process.env.ALGENTA_API_URL;
  delete process.env.ALGENTA_APP_BASE_URL;
  delete process.env.APP_BASE_URL;
  delete process.env.DE_APP_BASE_URL;
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("public Algenta SDK aliases", () => {
  it("re-exports the Algenta-branded direct client alias without breaking compatibility", () => {
    expect(AlgentaClient).toBe(DecisionEngineClient);
  });

  it("keeps the runtime-backed Mojo surface on the package root", () => {
    expect(typeof MojoRuntime).toBe("function");
    expect(typeof libraries).toBe("function");
  });

  it("keeps the governed data/query helpers on the public direct client alias", () => {
    const client = new AlgentaClient({
      apiKey: "de_test_surface",
      baseUrl: "https://api.algenta.ai",
    });

    expect(typeof client.getContract).toBe("function");
    expect(typeof client.listDatasets).toBe("function");
    expect(typeof client.getDatasetSummary).toBe("function");
    expect(typeof client.queryWithMetadata).toBe("function");
    expect(typeof client.queryBatch).toBe("function");
    expect(typeof client.querySqlReport).toBe("function");
    expect(typeof client.createRepositorySnapshot).toBe("function");
    expect(typeof client.getRepositoryIntelligenceCapabilities).toBe("function");
    expect(typeof client.getRepositorySnapshot).toBe("function");
    expect(typeof client.triageRepository).toBe("function");
    expect(typeof client.createRepositoryDecisionPlan).toBe("function");
    expect(typeof client.queryRepositoryGraph).toBe("function");
    expect(typeof client.simulateRepository).toBe("function");
    expect(typeof client.applyRepository).toBe("function");
    expect(typeof client.usage).toBe("function");
    expect(typeof client.limits).toBe("function");
  });

  it("keeps the account and proof helpers on the public runtime alias", () => {
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_test_surface",
      baseUrl: "http://localhost:8000",
    });

    expect(typeof runtime.getContract).toBe("function");
    expect(typeof runtime.getRuntimeManifest).toBe("function");
    expect(typeof runtime.getRuntimeModules).toBe("function");
    expect(typeof runtime.getRuntimeBenchmarks).toBe("function");
    expect(typeof runtime.getRuntimeReleaseValidation).toBe("function");
    expect(typeof runtime.createRepositorySnapshot).toBe("function");
    expect(typeof runtime.getRepositoryIntelligenceCapabilities).toBe("function");
    expect(typeof runtime.getRepositorySnapshot).toBe("function");
    expect(typeof runtime.triageRepository).toBe("function");
    expect(typeof runtime.createRepositoryDecisionPlan).toBe("function");
    expect(typeof runtime.queryRepositoryGraph).toBe("function");
    expect(typeof runtime.simulateRepository).toBe("function");
    expect(typeof runtime.applyRepository).toBe("function");
    expect(typeof runtime.usage).toBe("function");
    expect(typeof runtime.limits).toBe("function");
  });

  it("fails closed on the package root for direct clients in private profiles without a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    expect(() => new AlgentaClient({ apiKey: "de_live_surface" })).toThrow(
      "private profiles cannot target Algenta-owned cloud URLs",
    );
    expect(() => new DecisionEngineClient({ apiKey: "de_live_surface" })).toThrow(
      "private profiles cannot target Algenta-owned cloud URLs",
    );
  });

  it("fails closed on the package root for api Runtime in private profiles without a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    expect(() => new Runtime({ mode: "api", apiKey: "de_live_surface" })).toThrow(
      "private profiles cannot target Algenta-owned cloud URLs",
    );
  });

  it("allows the package root to target an explicit self-hosted baseUrl in private profiles", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const client = new AlgentaClient({
      apiKey: "de_live_surface",
      baseUrl: "http://localhost:8000",
    });
    const runtime = new Runtime({
      mode: "self_hosted",
      apiKey: "de_live_surface",
      baseUrl: "http://localhost:8000",
    });

    expect(client.baseUrl).toBe("http://localhost:8000");
    expect(runtime.baseUrl).toBe("http://localhost:8000");
  });

  it("re-exports the shared public contract from the package root", () => {
    expect(BRAND).toBe("Algenta");
    expect(DEFAULT_BASE_URL).toBe("https://api.algenta.ai");
    expect(AUTH_SCHEME).toBe("bearer_api_key");
    expect(API_KEY_PREFIX_LIVE).toBe("de_live_");
    expect(MCP_ENDPOINT).toBe("https://api.algenta.ai/mcp");
    expect(LEGACY_HEADERS).toEqual(["X-API-Key"]);
    expect(DEPRECATION_WINDOW_DAYS).toBe(90);
    expect(READ_ONLY_DEFAULT).toBe(true);
    expect(Object.keys(PLAN_LIMITS).sort()).toEqual([
      "algenta_free",
      "algenta_pro",
      "algenta_team",
      "enterprise",
    ]);
    for (const limits of Object.values(PLAN_LIMITS)) {
      expect(limits.requests_per_minute).toBe(0);
      expect(limits.simulations_per_month).toBe(0);
    }
    expectManifestBackedIntegrationsEqual(INTEGRATIONS, INTEGRATIONS);
    expect(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint).toBe("/v1/meta/contract");
    expect(PRIMARY_DATA_QUERY_CONTRACT.api.discovery_endpoint).toBe("/v1/data");
    expect(PRIMARY_DATA_QUERY_CONTRACT.api.query_batch_endpoint).toBe("/v1/query/batch");
    expect(PRIMARY_DATA_QUERY_CONTRACT.direct_sdk.typescript.contract_method).toBe(
      "getContract",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.direct_sdk.typescript.summary_method).toBe(
      "getDatasetSummary",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.direct_sdk.typescript.query_batch_method).toBe(
      "queryBatch",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.direct_sdk.typescript.query_sql_report_method).toBe(
      "querySqlReport",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.typescript.runtime_class).toBe("Runtime");
    expect(PRIMARY_DATA_QUERY_CONTRACT.runtime_sdk.typescript.libraries_entrypoint).toBe(
      "libraries",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.cli.query_sql_report_command).toBe(
      "de data sql-report <request.json>",
    );
    expect(PRIMARY_DATA_QUERY_CONTRACT.cli.contract_command).toBe("de contract");
    expect(PRIMARY_DATA_QUERY_CONTRACT.mcp.contract_tool).toBe("get_contract");
  });
});
