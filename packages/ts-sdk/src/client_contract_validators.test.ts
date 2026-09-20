// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  assertApiKeyPrefixes,
  assertCapabilityPlaneApiContractPayload,
  assertCapabilityPlaneContractPayload,
  assertCapabilityPlaneDirectSdkContractPayload,
  assertCapabilityPlaneEnumsContractPayload,
  assertCapabilityPlaneMcpContractPayload,
  assertCapabilityPlaneRuntimeSdkContractPayload,
  assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload,
  assertCapabilityPlaneTypeScriptSdkContractPayload,
  assertCliContractPayload,
  assertCompatibilityContractPayload,
  assertDefaultsContractPayload,
  assertDirectPythonSdkContractPayload,
  assertDirectSdkContractPayload,
  assertDirectTypeScriptSdkContractPayload,
  assertGovernedFilterContractPayload,
  assertGovernedFilterOperatorsPayload,
  assertGovernedFilterTypeBehaviorPayload,
  assertGovernedFilterValidationPayload,
  assertIntegrationContractPayload,
  assertMcpContractPayload,
  assertPlatformContractPayload,
  assertPrimaryDataQueryApiPayload,
  assertPrimaryDataQueryContractExtension,
  assertPrimaryDataQueryContractPayload,
  assertPrivacyRegistryContractPayload,
  assertRecommendedFlowsPayload,
  assertRuntimePythonSdkContractPayload,
  assertRuntimeSdkContractPayload,
  assertRuntimeTypeScriptSdkContractPayload,
  buildPlatformContractFromOpenApi,
  wrapContractValidation,
} from "./_client_contract_validators.js";
import { DecisionEngineError } from "./_client_errors.js";
import { cloneJsonValue, makeContractPayload } from "./_client_test_helpers.js";
import {
  CAPABILITY_PLANE_CONTRACT,
  CONTRACT_VERSION,
  INTEGRATIONS,
  PRIMARY_DATA_QUERY_CONTRACT,
} from "./contract.js";

type JsonObject = Record<string, unknown>;
type SectionValidator = (payload: unknown, context: string) => unknown;

const CONTEXT = "Algenta contract response.section";

function captureError(run: () => unknown): DecisionEngineError {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(DecisionEngineError);
  return caught as DecisionEngineError;
}

function primaryDataQueryContract(): JsonObject {
  return cloneJsonValue(PRIMARY_DATA_QUERY_CONTRACT) as unknown as JsonObject;
}

function capabilityPlaneContract(): JsonObject {
  return cloneJsonValue(CAPABILITY_PLANE_CONTRACT) as unknown as JsonObject;
}

function nested(root: JsonObject, ...keys: string[]): JsonObject {
  return keys.reduce<JsonObject>((current, key) => current[key] as JsonObject, root);
}

// Each shared assert helper produces one fixed message suffix and error shape; the string-array
// helper predates the structured validation envelope and still throws a bare DecisionEngineError.
type FieldKind = "string" | "string_array" | "boolean" | "integer" | "object" | "array";

const FIELD_KIND_EXPECTATIONS: Record<FieldKind, { code: string; message: string }> = {
  string: { code: "invalid_payload_fragment", message: "must be a non-empty string." },
  string_array: { code: "unknown_error", message: "must be a list of non-empty strings." },
  boolean: { code: "invalid_payload_fragment", message: "must be a boolean." },
  integer: { code: "invalid_payload_fragment", message: "must be an integer." },
  object: { code: "invalid_payload_fragment", message: "must be a JSON object." },
  array: { code: "invalid_payload_fragment", message: "must be a JSON array." },
};

interface MissingFieldCase {
  validator: string;
  run: SectionValidator;
  section: () => JsonObject;
  field: string;
  kind: FieldKind;
}

const MISSING_FIELD_CASES: MissingFieldCase[] = [
  {
    validator: "assertApiKeyPrefixes",
    run: assertApiKeyPrefixes,
    section: () => makeContractPayload().api_key_prefixes as JsonObject,
    field: "test",
    kind: "string",
  },
  {
    validator: "assertCompatibilityContractPayload",
    run: assertCompatibilityContractPayload,
    section: () => makeContractPayload().compatibility as JsonObject,
    field: "legacy_headers",
    kind: "string_array",
  },
  {
    validator: "assertCompatibilityContractPayload",
    run: assertCompatibilityContractPayload,
    section: () => makeContractPayload().compatibility as JsonObject,
    field: "deprecation_window_days",
    kind: "integer",
  },
  {
    validator: "assertPrivacyRegistryContractPayload",
    run: assertPrivacyRegistryContractPayload,
    section: () => makeContractPayload().privacy_registry as JsonObject,
    field: "vendor_telemetry_hosts",
    kind: "string_array",
  },
  {
    validator: "assertDefaultsContractPayload",
    run: assertDefaultsContractPayload,
    section: () => makeContractPayload().defaults as JsonObject,
    field: "write_confirmation_required",
    kind: "boolean",
  },
  {
    validator: "assertDefaultsContractPayload",
    run: assertDefaultsContractPayload,
    section: () => makeContractPayload().defaults as JsonObject,
    field: "plan_limits",
    kind: "object",
  },
  {
    validator: "assertIntegrationContractPayload",
    run: assertIntegrationContractPayload,
    section: () => cloneJsonValue(INTEGRATIONS[0]) as unknown as JsonObject,
    field: "support_url",
    kind: "string",
  },
  {
    validator: "assertIntegrationContractPayload",
    run: assertIntegrationContractPayload,
    section: () => cloneJsonValue(INTEGRATIONS[0]) as unknown as JsonObject,
    field: "admin_controls",
    kind: "string_array",
  },
  {
    validator: "assertIntegrationContractPayload",
    run: assertIntegrationContractPayload,
    section: () => cloneJsonValue(INTEGRATIONS[0]) as unknown as JsonObject,
    field: "read_only_default",
    kind: "boolean",
  },
  {
    validator: "assertPrimaryDataQueryApiPayload",
    run: assertPrimaryDataQueryApiPayload,
    section: () => nested(primaryDataQueryContract(), "api"),
    field: "query_sql_report_endpoint",
    kind: "string",
  },
  {
    validator: "assertGovernedFilterOperatorsPayload",
    run: assertGovernedFilterOperatorsPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract", "operators"),
    field: "nullary",
    kind: "string_array",
  },
  {
    validator: "assertGovernedFilterTypeBehaviorPayload",
    run: assertGovernedFilterTypeBehaviorPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract", "type_behavior"),
    field: "null_checks",
    kind: "string_array",
  },
  {
    validator: "assertGovernedFilterValidationPayload",
    run: assertGovernedFilterValidationPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract", "validation"),
    field: "requires_selector",
    kind: "boolean",
  },
  {
    validator: "assertGovernedFilterValidationPayload",
    run: assertGovernedFilterValidationPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract", "validation"),
    field: "nullary_ops_forbid_value_and_values",
    kind: "string_array",
  },
  {
    validator: "assertGovernedFilterContractPayload",
    run: assertGovernedFilterContractPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract"),
    field: "conditions_field",
    kind: "string",
  },
  {
    validator: "assertGovernedFilterContractPayload",
    run: assertGovernedFilterContractPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract"),
    field: "operators",
    kind: "object",
  },
  {
    validator: "assertGovernedFilterContractPayload",
    run: assertGovernedFilterContractPayload,
    section: () => nested(primaryDataQueryContract(), "governed_filter_contract"),
    field: "supports_non_sql_backends",
    kind: "boolean",
  },
  {
    validator: "assertDirectPythonSdkContractPayload",
    run: assertDirectPythonSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "direct_sdk", "python"),
    field: "compatibility_async_client_class",
    kind: "string",
  },
  {
    validator: "assertDirectTypeScriptSdkContractPayload",
    run: assertDirectTypeScriptSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "direct_sdk", "typescript"),
    field: "import_package",
    kind: "string",
  },
  {
    validator: "assertRuntimePythonSdkContractPayload",
    run: assertRuntimePythonSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "runtime_sdk", "python"),
    field: "libraries_entrypoint",
    kind: "string",
  },
  {
    validator: "assertRuntimeTypeScriptSdkContractPayload",
    run: assertRuntimeTypeScriptSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "runtime_sdk", "typescript"),
    field: "runtime_class",
    kind: "string",
  },
  {
    validator: "assertDirectSdkContractPayload",
    run: assertDirectSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "direct_sdk"),
    field: "typescript",
    kind: "object",
  },
  {
    validator: "assertRuntimeSdkContractPayload",
    run: assertRuntimeSdkContractPayload,
    section: () => nested(primaryDataQueryContract(), "runtime_sdk"),
    field: "python",
    kind: "object",
  },
  {
    validator: "assertCliContractPayload",
    run: assertCliContractPayload,
    section: () => nested(primaryDataQueryContract(), "cli"),
    field: "runtime_execute_command",
    kind: "string",
  },
  {
    validator: "assertMcpContractPayload",
    run: assertMcpContractPayload,
    section: () => nested(primaryDataQueryContract(), "mcp"),
    field: "runtime_library_execute_tool",
    kind: "string",
  },
  {
    validator: "assertRecommendedFlowsPayload",
    run: assertRecommendedFlowsPayload,
    section: () => nested(primaryDataQueryContract(), "recommended_flows"),
    field: "wide_sql_report",
    kind: "string_array",
  },
  {
    validator: "assertPrimaryDataQueryContractPayload",
    run: assertPrimaryDataQueryContractPayload,
    section: primaryDataQueryContract,
    field: "recommended_flows",
    kind: "object",
  },
  {
    validator: "assertCapabilityPlaneApiContractPayload",
    run: assertCapabilityPlaneApiContractPayload,
    section: () => nested(capabilityPlaneContract(), "api"),
    field: "record_outcome_endpoint",
    kind: "string",
  },
  {
    validator: "assertCapabilityPlaneEnumsContractPayload",
    run: assertCapabilityPlaneEnumsContractPayload,
    section: () => nested(capabilityPlaneContract(), "enums"),
    field: "binding_statuses",
    kind: "string_array",
  },
  {
    validator: "assertCapabilityPlaneTypeScriptSdkContractPayload",
    run: assertCapabilityPlaneTypeScriptSdkContractPayload,
    section: () => nested(capabilityPlaneContract(), "direct_sdk", "typescript"),
    field: "list_mcp_providers_method",
    kind: "string",
  },
  {
    validator: "assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload",
    run: assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload,
    section: () => nested(capabilityPlaneContract(), "runtime_sdk", "typescript"),
    field: "register_adapter_method",
    kind: "string",
  },
  {
    validator: "assertCapabilityPlaneDirectSdkContractPayload",
    run: assertCapabilityPlaneDirectSdkContractPayload,
    section: () => nested(capabilityPlaneContract(), "direct_sdk"),
    field: "typescript",
    kind: "object",
  },
  {
    validator: "assertCapabilityPlaneRuntimeSdkContractPayload",
    run: assertCapabilityPlaneRuntimeSdkContractPayload,
    section: () => nested(capabilityPlaneContract(), "runtime_sdk"),
    field: "typescript",
    kind: "object",
  },
  {
    validator: "assertCapabilityPlaneMcpContractPayload",
    run: assertCapabilityPlaneMcpContractPayload,
    section: () => nested(capabilityPlaneContract(), "mcp"),
    field: "disable_skill_tool",
    kind: "string",
  },
  {
    validator: "assertCapabilityPlaneMcpContractPayload",
    run: assertCapabilityPlaneMcpContractPayload,
    section: () => nested(capabilityPlaneContract(), "mcp"),
    field: "compatibility_aliases",
    kind: "string_array",
  },
  {
    validator: "assertCapabilityPlaneContractPayload",
    run: assertCapabilityPlaneContractPayload,
    section: capabilityPlaneContract,
    field: "enums",
    kind: "object",
  },
  {
    validator: "assertPlatformContractPayload",
    run: assertPlatformContractPayload,
    section: () => makeContractPayload(),
    field: "auth_scheme",
    kind: "string",
  },
  {
    validator: "assertPlatformContractPayload",
    run: assertPlatformContractPayload,
    section: () => makeContractPayload(),
    field: "integrations",
    kind: "array",
  },
];

describe("contract section validators reject a missing field", () => {
  it.each(MISSING_FIELD_CASES)(
    "$validator rejects a payload without $field",
    ({ run, section, field, kind }) => {
      const payload = section();
      delete payload[field];
      const error = captureError(() => run(payload, CONTEXT));
      const expected = FIELD_KIND_EXPECTATIONS[kind];
      expect(error.errorCode).toBe(expected.code);
      expect(error.message).toBe(`${CONTEXT}.${field} ${expected.message}`);
      if (expected.code === "invalid_payload_fragment") {
        // The structured envelope strips the response prefix and keeps the field path.
        expect(error.validationErrors[0]?.path).toBe(`section.${field}`);
      } else {
        expect(error.validationErrors).toEqual([]);
      }
    },
  );

  it("rejects a non-object section at the section context", () => {
    const error = captureError(() => assertApiKeyPrefixes(["de_live_"], CONTEXT));
    expect(error.errorCode).toBe("invalid_payload_fragment");
    expect(error.message).toBe(`${CONTEXT} must be a JSON object.`);
    expect(error.validationErrors[0]?.path).toBe("section");
  });
});

describe("assertPrimaryDataQueryContractExtension", () => {
  it.each([null, undefined, "text", 42, ["x-primary-data-query-contract"]])(
    "rejects non-object payload %j",
    (payload) => {
      const error = captureError(() => assertPrimaryDataQueryContractExtension(payload));
      expect(error.errorCode).toBe("invalid_contract_payload");
      expect(error.message).toBe("OpenAPI contract fallback payload must be a JSON object.");
    },
  );

  it.each([
    {},
    { "x-primary-data-query-contract": null },
    { "x-primary-data-query-contract": "inline" },
    { "x-primary-data-query-contract": [] },
  ])("reports a missing or non-object extension for %j", (payload) => {
    const error = captureError(() => assertPrimaryDataQueryContractExtension(payload));
    expect(error.errorCode).toBe("contract_extension_missing");
    expect(error.message).toBe(
      "OpenAPI contract fallback is missing x-primary-data-query-contract.",
    );
  });

  it.each([{}, { api: null }, { api: "/v1/meta/contract" }, { api: [] }])(
    "rejects an extension whose api section is %j",
    (extension) => {
      const error = captureError(() =>
        assertPrimaryDataQueryContractExtension({ "x-primary-data-query-contract": extension }),
      );
      expect(error.errorCode).toBe("invalid_contract_payload");
      expect(error.message).toBe(
        "OpenAPI contract fallback is missing the api contract section.",
      );
    },
  );

  it("rejects an api section without a string contract_endpoint", () => {
    const error = captureError(() =>
      assertPrimaryDataQueryContractExtension({
        "x-primary-data-query-contract": { api: { contract_endpoint: 7 } },
      }),
    );
    expect(error.errorCode).toBe("invalid_contract_payload");
    expect(error.message).toBe("OpenAPI contract fallback is missing api.contract_endpoint.");
  });

  it("merges the extension over the bundled primary data query contract", () => {
    const result = assertPrimaryDataQueryContractExtension({
      "x-primary-data-query-contract": {
        api: { contract_endpoint: "/custom/meta/contract" },
        cli: { contract_command: "algenta custom contract" },
      },
    });
    expect(result.api.contract_endpoint).toBe("/custom/meta/contract");
    expect(result.api.discovery_endpoint).toBe(
      PRIMARY_DATA_QUERY_CONTRACT.api.discovery_endpoint,
    );
    expect(result.cli.contract_command).toBe("algenta custom contract");
    expect(result.cli.discovery_command).toBe(PRIMARY_DATA_QUERY_CONTRACT.cli.discovery_command);
    expect(result.mcp).toEqual(PRIMARY_DATA_QUERY_CONTRACT.mcp);
    // The merge must not alias the bundled constant.
    expect(result.mcp).not.toBe(PRIMARY_DATA_QUERY_CONTRACT.mcp);
    expect(PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint).not.toBe("/custom/meta/contract");
  });
});

describe("buildPlatformContractFromOpenApi", () => {
  const openApiPayload = (extra: JsonObject = {}): JsonObject => ({
    openapi: "3.1.0",
    "x-primary-data-query-contract": {
      api: { contract_endpoint: "/custom/meta/contract" },
    },
    ...extra,
  });

  it("rebases MCP endpoints onto a trailing-slash base URL and leaves capability_plane null", () => {
    const contract = buildPlatformContractFromOpenApi(
      "https://engine.customer.internal/",
      openApiPayload(),
    );
    expect(contract.api_base_url).toBe("https://engine.customer.internal");
    expect(contract.mcp_endpoint).toBe("https://engine.customer.internal/mcp");
    expect(contract.mcp_legacy_sse_endpoint).toBe("https://engine.customer.internal/mcp/sse");
    expect(contract.mcp_tools_endpoint).toBe("https://engine.customer.internal/mcp/tools");
    expect(contract.contract_version).toBe(CONTRACT_VERSION);
    expect(contract.capability_plane).toBeNull();
    expect(contract.primary_data_query_contract.api.contract_endpoint).toBe(
      "/custom/meta/contract",
    );
    expect(contract.integrations).toEqual(INTEGRATIONS);
    expect(contract.integrations).not.toBe(INTEGRATIONS);
    expect(contract.defaults.plan_limits).not.toBe(makeContractPayload().defaults);
  });

  it("keeps a base URL without trailing slash unchanged", () => {
    const contract = buildPlatformContractFromOpenApi(
      "https://engine.customer.internal",
      openApiPayload(),
    );
    expect(contract.api_base_url).toBe("https://engine.customer.internal");
    expect(contract.mcp_endpoint).toBe("https://engine.customer.internal/mcp");
  });

  it.each([null, "inline", 3, ["api"]])(
    "rejects an x-capability-plane-contract extension of %j",
    (extension) => {
      const error = captureError(() =>
        buildPlatformContractFromOpenApi(
          "https://engine.customer.internal",
          openApiPayload({ "x-capability-plane-contract": extension }),
        ),
      );
      expect(error.errorCode).toBe("invalid_contract_payload");
      expect(error.message).toBe(
        "OpenAPI contract fallback returned an invalid x-capability-plane-contract payload.",
      );
    },
  );

  it("merges a valid capability plane extension over the bundled contract", () => {
    const contract = buildPlatformContractFromOpenApi(
      "https://engine.customer.internal",
      openApiPayload({
        "x-capability-plane-contract": { enums: { provider_types: ["custom_provider"] } },
      }),
    );
    expect(contract.capability_plane).not.toBeNull();
    expect(contract.capability_plane?.enums.provider_types).toEqual(["custom_provider"]);
    expect(contract.capability_plane?.enums.capability_kinds).toEqual(
      CAPABILITY_PLANE_CONTRACT.enums.capability_kinds,
    );
    expect(contract.capability_plane?.api).toEqual(CAPABILITY_PLANE_CONTRACT.api);
    expect(CAPABILITY_PLANE_CONTRACT.enums.provider_types).not.toEqual(["custom_provider"]);
  });

  it("treats a non-object OpenAPI document as an empty schema and then fails the fallback check", () => {
    const error = captureError(() =>
      buildPlatformContractFromOpenApi("https://engine.customer.internal", "not-a-document"),
    );
    expect(error.errorCode).toBe("invalid_contract_payload");
    expect(error.message).toBe("OpenAPI contract fallback payload must be a JSON object.");
  });
});

describe("assertDefaultsContractPayload plan limits", () => {
  const defaultsWithLimit = (limit: unknown): JsonObject => {
    const defaults = makeContractPayload().defaults as JsonObject;
    nested(defaults, "plan_limits", "enterprise").requests_per_minute = limit;
    return defaults;
  };

  it.each(["unlimited", " 500/min ", 0, 12.5, -1])("accepts plan limit %j", (limit) => {
    expect(() => assertDefaultsContractPayload(defaultsWithLimit(limit), CONTEXT)).not.toThrow();
  });

  it.each(["", "   "])("rejects blank string plan limit %j", (limit) => {
    const error = captureError(() => assertDefaultsContractPayload(defaultsWithLimit(limit), CONTEXT));
    expect(error.errorCode).toBe("unknown_error");
    expect(error.message).toBe(
      `${CONTEXT}.plan_limits.enterprise.requests_per_minute must be a non-empty string.`,
    );
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, true, null, ["100"]])(
    "rejects non-finite or non-numeric plan limit %j",
    (limit) => {
      const error = captureError(() =>
        assertDefaultsContractPayload(defaultsWithLimit(limit), CONTEXT),
      );
      expect(error.errorCode).toBe("invalid_payload_fragment");
      expect(error.message).toBe(
        `${CONTEXT}.plan_limits.enterprise.requests_per_minute must be a finite number.`,
      );
      expect(error.validationErrors[0]?.path).toBe(
        "section.plan_limits.enterprise.requests_per_minute",
      );
    },
  );

  it("rejects a plan whose limits are not an object", () => {
    const defaults = makeContractPayload().defaults as JsonObject;
    (defaults.plan_limits as JsonObject).enterprise = 100;
    const error = captureError(() => assertDefaultsContractPayload(defaults, CONTEXT));
    expect(error.message).toBe(`${CONTEXT}.plan_limits.enterprise must be a JSON object.`);
    expect(error.validationErrors[0]?.path).toBe("section.plan_limits.enterprise");
  });
});

describe("contract payload validators return detached clones", () => {
  it("assertPrimaryDataQueryContractPayload returns an equal but independent copy", () => {
    const payload = primaryDataQueryContract();
    const result = assertPrimaryDataQueryContractPayload(payload, CONTEXT);
    expect(result).toEqual(payload);
    expect(result).not.toBe(payload);
    result.api.contract_endpoint = "/mutated";
    expect((payload.api as JsonObject).contract_endpoint).toBe(
      PRIMARY_DATA_QUERY_CONTRACT.api.contract_endpoint,
    );
  });

  it("assertCapabilityPlaneContractPayload returns an equal but independent copy", () => {
    const payload = capabilityPlaneContract();
    const result = assertCapabilityPlaneContractPayload(payload, CONTEXT);
    expect(result).toEqual(payload);
    expect(result).not.toBe(payload);
  });
});

describe("assertPlatformContractPayload", () => {
  const PLATFORM_CONTEXT = "Algenta contract response.platform";

  it("accepts a payload without capability_plane and preserves the absence", () => {
    const payload = makeContractPayload();
    expect(payload).not.toHaveProperty("capability_plane");
    const result = assertPlatformContractPayload(payload, PLATFORM_CONTEXT);
    expect(result).toEqual(payload);
    expect(result).not.toBe(payload);
    expect(result.capability_plane).toBeUndefined();
  });

  it("accepts an explicit null capability_plane", () => {
    const result = assertPlatformContractPayload(
      makeContractPayload({ capability_plane: null }),
      PLATFORM_CONTEXT,
    );
    expect(result.capability_plane).toBeNull();
  });

  it("validates and clones a present capability_plane", () => {
    const result = assertPlatformContractPayload(
      makeContractPayload({ capability_plane: capabilityPlaneContract() }),
      PLATFORM_CONTEXT,
    );
    expect(result.capability_plane).toEqual(CAPABILITY_PLANE_CONTRACT);
  });

  it("rejects an invalid capability_plane with the nested field path", () => {
    const error = captureError(() =>
      assertPlatformContractPayload(
        makeContractPayload({ capability_plane: { api: {} } }),
        PLATFORM_CONTEXT,
      ),
    );
    expect(error.errorCode).toBe("invalid_payload_fragment");
    expect(error.message).toBe(
      `${PLATFORM_CONTEXT}.capability_plane.api.list_providers_endpoint must be a non-empty string.`,
    );
    expect(error.validationErrors[0]?.path).toBe(
      "platform.capability_plane.api.list_providers_endpoint",
    );
  });

  it("rejects an invalid integrations entry with its index in the path", () => {
    const payload = makeContractPayload();
    (payload.integrations as JsonObject[])[0].status = "";
    const error = captureError(() => assertPlatformContractPayload(payload, PLATFORM_CONTEXT));
    expect(error.message).toBe(
      `${PLATFORM_CONTEXT}.integrations[0].status must be a non-empty string.`,
    );
    // Array indexes are normalised to dotted segments in the structured path.
    expect(error.validationErrors[0]?.path).toBe("platform.integrations.0.status");
  });
});

describe("wrapContractValidation", () => {
  const ENDPOINT = "Algenta contract endpoint";

  it("returns the validator result untouched on success", () => {
    const result = wrapContractValidation(ENDPOINT, { ok: true }, (value) => ({
      wrapped: value,
    }));
    expect(result).toEqual({ wrapped: { ok: true } });
  });

  it("preserves structured details from a DecisionEngineError", () => {
    const error = captureError(() =>
      wrapContractValidation(ENDPOINT, "text", (value) =>
        assertPlatformContractPayload(value, "Algenta contract response"),
      ),
    );
    expect(error.errorCode).toBe("invalid_contract_payload");
    expect(error.statusCode).toBe(0);
    expect(error.message).toBe(
      `${ENDPOINT} returned an invalid payload: Algenta contract response must be a JSON object.`,
    );
    expect(error.details).toEqual({
      cause: "Algenta contract response",
      validation_errors: [
        {
          path: "Algenta contract response",
          message: "Algenta contract response must be a JSON object.",
          type: "model_type",
        },
      ],
    });
    expect(error.validationErrors[0]?.path).toBe("Algenta contract response");
  });

  it("wraps a DecisionEngineError without details as a cause", () => {
    const error = captureError(() =>
      wrapContractValidation(ENDPOINT, {}, () => {
        throw new DecisionEngineError("legacy_headers must be a list of non-empty strings.");
      }),
    );
    expect(error.errorCode).toBe("invalid_contract_payload");
    expect(error.message).toBe(
      `${ENDPOINT} returned an invalid payload: legacy_headers must be a list of non-empty strings.`,
    );
    expect(error.details).toEqual({
      cause: "legacy_headers must be a list of non-empty strings.",
    });
    expect(error.validationErrors).toEqual([]);
  });

  it("treats array details as absent and falls back to the cause", () => {
    const error = captureError(() =>
      wrapContractValidation(ENDPOINT, {}, () => {
        throw new DecisionEngineError("boom", 400, "bad_request", {
          error: { code: "bad_request", details: [{ path: "x" }] },
        });
      }),
    );
    expect(error.details).toEqual({ cause: "boom" });
  });

  it("rethrows non-DecisionEngineError failures unchanged", () => {
    const failure = new TypeError("validator exploded");
    let caught: unknown;
    try {
      wrapContractValidation(ENDPOINT, {}, () => {
        throw failure;
      });
    } catch (error) {
      caught = error;
    }
    expect(caught).toBe(failure);
  });
});
