// SPDX-License-Identifier: Apache-2.0
// Table-driven unit tests for the pure platform validators in
// _client_platform_validators_a1.ts and _client_platform_validators_a2.ts.
// Every acceptance case asserts the exact normalized shape (including
// defaulted nulls); every rejection case asserts both the error class and a
// distinctive message fragment.
import { describe, expect, it } from "vitest";
import { DecisionEngineError } from "./_client_errors.js";
import {
  assertApiKeyCreateResponse,
  assertApiKeyListResponse,
  assertApiKeyPrefix,
  assertBillingInfoResponse,
  assertDistributionInfoResponse,
  assertDistributionListResponse,
  assertJsonRecord,
  assertLimitsInfoResponse,
  assertMeResponse,
  assertOptionalApiKeyDeviceLimit,
  assertPlatformContractResponse,
  assertStringArray,
  assertTemplateInfoResponse,
  assertTemplateListResponse,
  assertUsageInfoResponse,
  buildExplainResponse,
  dedupeStrings,
  normalizeUpdateMeRequest,
  sourceSetFromRequest,
  splitResolvedSources,
} from "./_client_platform_validators_a1.js";
import {
  assertAuditLogEntry,
  assertBillingSessionResponse,
  assertCreditRefreshResponse,
  assertDeviceListEntryResponse,
  assertDeviceListResponse,
  assertDeviceRegistrationResponse,
  assertDeviceRevokeResponse,
  assertMeteringBatchResponse,
  assertTeamInviteResponse,
  assertTeamListResponse,
  assertTeamMemberInfo,
  assertTeamRemoveResponse,
  assertTeamRoleUpdateResponse,
} from "./_client_platform_validators_a2.js";
import { makeContractPayload, makeQueryResponse } from "./_client_test_helpers.js";
import type { QueryResponse, UpdateMeRequest } from "./types.js";

type RejectionCase = [label: string, payload: unknown, fragment: RegExp];

function expectRejection(run: () => unknown, fragment: RegExp): void {
  expect(run).toThrow(DecisionEngineError);
  expect(run).toThrow(fragment);
}

function captureError(run: () => unknown): DecisionEngineError {
  try {
    run();
  } catch (error) {
    expect(error).toBeInstanceOf(DecisionEngineError);
    return error as DecisionEngineError;
  }
  throw new Error("expected the validator to throw");
}

// Payloads that trip the shared "must be a JSON object" guard.
const NON_OBJECT_PAYLOADS: Array<[label: string, payload: unknown]> = [
  ["null", null],
  ["a string", "payload"],
  ["an array", []],
];

// The helper spreads a Record<string, unknown>, so its literal type carries an
// index signature that is not assignable to QueryResponse's optional fields.
function queryResponse(overrides: Record<string, unknown> = {}): QueryResponse {
  return makeQueryResponse(overrides) as unknown as QueryResponse;
}

describe("assertPlatformContractResponse", () => {
  it("returns the validated contract payload", () => {
    const payload = makeContractPayload();
    expect(assertPlatformContractResponse(payload)).toEqual(payload);
  });

  it("wraps a structural failure with the contract-endpoint context", () => {
    const error = captureError(() => assertPlatformContractResponse(null));
    expect(error.message).toBe(
      "Algenta contract endpoint returned an invalid payload: Algenta contract response must be a JSON object.",
    );
    expect(error.errorCode).toBe("invalid_contract_payload");
    // The inner structured error's details survive the wrap. The root context has no
    // trailing dot, so the response-prefix strip does not apply and the path is the root.
    expect(error.validationErrors).toEqual([
      {
        path: "Algenta contract response",
        message: "Algenta contract response must be a JSON object.",
        type: "model_type",
      },
    ]);
  });
});

describe("dedupeStrings", () => {
  it("trims, drops blanks and keeps the first occurrence in order", () => {
    expect(dedupeStrings([" orders ", "customers", "orders", "", "   ", "customers "])).toEqual([
      "orders",
      "customers",
    ]);
  });

  it("returns an empty list for empty input", () => {
    expect(dedupeStrings([])).toEqual([]);
  });
});

describe("sourceSetFromRequest", () => {
  it("collects every source-bearing field and dedupes the result", () => {
    expect(
      sourceSetFromRequest({
        source_name: "orders",
        join_source_name: "customers",
        sources: [{ name: "orders" }, { name: "regions" }, { title: "unnamed" }, null, "text"],
        join_path: {
          base_source: "orders",
          group_source: "regions",
          edges: [
            { left_source: "orders", right_source: "customers" },
            { left_source: "customers", right_source: "shipments" },
            null,
            "edge",
            { left_source: 7 },
          ],
        },
      }),
    ).toEqual(["orders", "customers", "regions", "shipments"]);
  });

  it.each<[label: string, request: Record<string, unknown>, expected: string[]]>([
    ["an empty request", {}, []],
    [
      "non-string scalar fields",
      { source_name: 1, join_source_name: null, sources: "orders", join_path: "orders" },
      [],
    ],
    // A non-array edges value is skipped while base_source is still collected.
    [
      "a join_path without an edges array",
      { join_path: { base_source: "orders", edges: "orders->customers" } },
      ["orders"],
    ],
    [
      "a join_path with a non-string base_source",
      { join_path: { base_source: 5, group_source: "regions" } },
      ["regions"],
    ],
  ])("handles %s", (_label, request, expected) => {
    expect(sourceSetFromRequest(request)).toEqual(expected);
  });
});

describe("splitResolvedSources", () => {
  it.each<[label: string, resolvedSource: string | undefined, expected: string[]]>([
    ["undefined", undefined, []],
    ["an empty string", "", []],
    ["a single source", "orders", ["orders"]],
    [
      "a join expression with a repeated source",
      "orders ⋈ customers ⋈ orders",
      ["orders", "customers"],
    ],
  ])("splits %s", (_label, resolvedSource, expected) => {
    expect(splitResolvedSources(resolvedSource)).toEqual(expected);
  });
});

describe("buildExplainResponse", () => {
  it("prefers the join_path, source_set and planner_mode carried by the result", () => {
    const result = queryResponse({
      source_set: ["orders", "customers"],
      join_path: [{ left_source: "orders", right_source: "customers", kind: "result" }],
      planner_mode: "join_planner",
    });
    const explain = buildExplainResponse(
      { join_path: { edges: [{ left_source: "ignored", right_source: "ignored" }] } },
      result,
    );
    expect(explain.join_path).toEqual([
      { left_source: "orders", right_source: "customers", kind: "result" },
    ]);
    expect(explain.source_set).toEqual(["orders", "customers"]);
    expect(explain.planner_mode).toBe("join_planner");
  });

  it("falls back to the request edges and the split resolved_source", () => {
    const result = queryResponse({ join_path: [], resolved_source: "orders ⋈ customers" });
    const explain = buildExplainResponse(
      {
        join_path: {
          edges: [{ left_source: "orders", right_source: "customers" }, null, "edge"],
        },
      },
      result,
    );
    expect(explain).toEqual({
      source_set: ["orders", "customers"],
      join_path: [{ left_source: "orders", right_source: "customers" }],
      // exact_spec=true wins over decision_path when planner_mode is absent.
      planner_mode: "exact_spec",
      decision_path: "exact_spec",
      plan_hash: "plan-1",
      schema_revision: undefined,
      validated: true,
      clarification_required: undefined,
      rejection_reason: undefined,
      resolved_source: "orders ⋈ customers",
      resolved_column: "revenue",
      resolved_role: "metric",
      confidence: 0.98,
      confidence_source: "schema_truth",
      deterministic_scope: "exact",
      plan: ["resolve metric", "execute query"],
      explanation: ["used exact spec"],
      request_id: undefined,
    });
  });

  it("synthesizes a join chain from the request source set and uses decision_path", () => {
    const result = queryResponse({
      source_set: [],
      planner_mode: null,
      exact_spec: false,
      decision_path: "planner_fallback",
    });
    const explain = buildExplainResponse(
      { source_name: "orders", sources: [{ name: "customers" }, { name: "regions" }] },
      result,
    );
    expect(explain.source_set).toEqual(["orders", "customers", "regions"]);
    expect(explain.join_path).toEqual([
      { left_source: "orders", right_source: "customers" },
      { left_source: "customers", right_source: "regions" },
    ]);
    expect(explain.planner_mode).toBe("planner_fallback");
  });

  it.each<[label: string, request: Record<string, unknown>]>([
    ["a join_path without edges", { join_path: { base_source: "orders" } }],
    ["a non-object join_path", { join_path: "orders", source_name: "orders" }],
  ])("leaves join_path empty for a single-source request with %s", (_label, request) => {
    const explain = buildExplainResponse(request, queryResponse({ resolved_source: "" }));
    expect(explain.source_set).toEqual(["orders"]);
    expect(explain.join_path).toEqual([]);
  });
});

describe("assertApiKeyPrefix", () => {
  it("returns the key prefix", () => {
    expect(assertApiKeyPrefix({ key_prefix: "de_test_abc" }, "API key")).toBe("de_test_abc");
  });

  it.each<RejectionCase>([
    ...NON_OBJECT_PAYLOADS.map(
      ([label, payload]): RejectionCase => [label, payload, /API key must be a JSON object/],
    ),
    ["a missing key_prefix", {}, /API key missing key_prefix/],
    ["an empty key_prefix", { key_prefix: "" }, /API key missing key_prefix/],
    ["a non-string key_prefix", { key_prefix: 5 }, /API key missing key_prefix/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertApiKeyPrefix(payload, "API key"), fragment);
  });
});

describe("assertOptionalApiKeyDeviceLimit", () => {
  it.each<[label: string, payload: unknown]>([
    ["a null payload", null],
    ["an array payload", []],
    ["an absent device_limit", {}],
    ["a null device_limit", { device_limit: null }],
    ["a zero device_limit", { device_limit: 0 }],
    ["a positive device_limit", { device_limit: 3 }],
  ])("accepts %s", (_label, payload) => {
    expect(assertOptionalApiKeyDeviceLimit(payload, "API key")).toBeUndefined();
  });

  it.each<[label: string, deviceLimit: unknown]>([
    ["a negative integer", -1],
    ["a fraction", 1.5],
    ["a numeric string", "3"],
  ])("rejects %s", (_label, deviceLimit) => {
    expectRejection(
      () => assertOptionalApiKeyDeviceLimit({ device_limit: deviceLimit }, "API key"),
      /API key has an invalid device_limit/,
    );
  });
});

describe("assertApiKeyListResponse", () => {
  const items = [{ key_prefix: "de_test_a", device_limit: 2 }, { key_prefix: "de_test_b" }];

  it("accepts a raw array and returns it unchanged", () => {
    expect(assertApiKeyListResponse(items)).toBe(items);
  });

  it("accepts the paginated {api_keys} form and returns the inner list", () => {
    expect(assertApiKeyListResponse({ api_keys: items, total: 2 })).toBe(items);
  });

  it.each<RejectionCase>([
    ["null", null, /must be a JSON array or paginated object/],
    ["a string", "keys", /must be a JSON array or paginated object/],
    ["an object without api_keys", { total: 0 }, /must be a JSON array or paginated object/],
    ["a non-array api_keys", { api_keys: "keys" }, /must be a JSON array or paginated object/],
    ["an item without key_prefix", [{}], /API key list item missing key_prefix/],
    [
      "an item with an invalid device_limit",
      [{ key_prefix: "de_test_a", device_limit: -1 }],
      /API key list item has an invalid device_limit/,
    ],
    [
      "an item leaking raw_key",
      [{ key_prefix: "de_test_a", raw_key: "de_test_a_secret" }],
      /leaked one-time secret material/,
    ],
    [
      "an item leaking key",
      [{ key_prefix: "de_test_a", key: "secret" }],
      /leaked one-time secret material/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertApiKeyListResponse(payload), fragment);
  });
});

describe("assertApiKeyCreateResponse", () => {
  it("returns the payload when raw_key starts with key_prefix", () => {
    const payload = { key_prefix: "de_test_abc", raw_key: "de_test_abc_123", device_limit: null };
    expect(assertApiKeyCreateResponse(payload)).toBe(payload);
  });

  it.each<RejectionCase>([
    ["null", null, /API key create response must be a JSON object/],
    [
      "a missing key_prefix",
      { raw_key: "de_test_abc" },
      /API key create response missing key_prefix/,
    ],
    [
      "an invalid device_limit",
      { key_prefix: "de_test_abc", raw_key: "de_test_abc_1", device_limit: "2" },
      /API key create response has an invalid device_limit/,
    ],
    ["a missing raw_key", { key_prefix: "de_test_abc" }, /missing raw_key/],
    ["an empty raw_key", { key_prefix: "de_test_abc", raw_key: "" }, /missing raw_key/],
    // The prefix must be a real prefix of the secret; a mismatch is treated as missing.
    [
      "a raw_key with a different prefix",
      { key_prefix: "de_test_abc", raw_key: "de_live_x" },
      /missing raw_key/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertApiKeyCreateResponse(payload), fragment);
  });
});

describe("assertUsageInfoResponse", () => {
  const usage = {
    org_id: "org-1",
    billing_period: "2026-09",
    simulations_run: 12,
    api_calls: 40,
    quota_limit: 1000,
    quota_used_pct: 4.5,
  };

  it("returns only the normalized usage fields", () => {
    expect(assertUsageInfoResponse({ ...usage, extra: true })).toEqual(usage);
  });

  it.each<RejectionCase>([
    ["an array", [], /Usage response must be a JSON object/],
    ["a missing org_id", { ...usage, org_id: undefined }, /Usage response missing org_id/],
    [
      "an empty billing_period",
      { ...usage, billing_period: "" },
      /Usage response missing billing_period/,
    ],
    ["a negative simulations_run", { ...usage, simulations_run: -1 }, /invalid simulations_run/],
    ["a fractional api_calls", { ...usage, api_calls: 1.5 }, /invalid api_calls/],
    ["a string quota_limit", { ...usage, quota_limit: "1000" }, /invalid quota_limit/],
    ["a NaN quota_used_pct", { ...usage, quota_used_pct: Number.NaN }, /invalid quota_used_pct/],
    ["a negative quota_used_pct", { ...usage, quota_used_pct: -0.1 }, /invalid quota_used_pct/],
    ["a string quota_used_pct", { ...usage, quota_used_pct: "4" }, /invalid quota_used_pct/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertUsageInfoResponse(payload), fragment);
  });
});

describe("assertMeResponse", () => {
  const user = {
    id: "user-1",
    email: "ann@example.com",
    name: "Ann",
    role: "admin",
    email_verified: true,
    created_at: "2026-01-01T00:00:00Z",
  };
  const org = {
    id: "org-1",
    name: "Acme",
    slug: "acme",
    plan: "team",
    status: "active",
    created_at: "2025-06-01T00:00:00Z",
  };
  const flattened = {
    email: "ann@example.com",
    org_id: "org-1",
    org_name: "Acme",
    plan: "team",
    organization: "Acme",
  };

  it("normalizes nested user/org objects and mirrors the legacy flat fields", () => {
    expect(assertMeResponse({ user: { ...user, extra: 1 }, org: { ...org, extra: 1 } })).toEqual({
      user,
      org,
      ...flattened,
    });
  });

  it("rebuilds user/org from explicit legacy flat fields", () => {
    expect(
      assertMeResponse({
        user_id: "user-1",
        email: "ann@example.com",
        name: "Ann",
        role: "admin",
        email_verified: true,
        created_at: "2026-01-01T00:00:00Z",
        org_id: "org-1",
        org_name: "Acme",
        org_slug: "acme",
        plan: "team",
        org_status: "active",
        org_created_at: "2025-06-01T00:00:00Z",
      }),
    ).toEqual({ user, org, ...flattened });
  });

  it("honours the legacy alias keys (id, user_name, organization, slug, created_at)", () => {
    expect(
      assertMeResponse({
        id: "user-2",
        email: "bob@example.com",
        user_name: "Bob",
        plan: "free",
        organization: "Bob Org",
        slug: "bob-org",
        created_at: "2026-01-02T00:00:00Z",
      }),
    ).toEqual({
      user: {
        id: "user-2",
        email: "bob@example.com",
        name: "Bob",
        role: "member",
        email_verified: true,
        created_at: "2026-01-02T00:00:00Z",
      },
      org: {
        id: "current_org",
        name: "Bob Org",
        slug: "bob-org",
        plan: "free",
        status: "active",
        // org_created_at is absent, so the user-level created_at is reused.
        created_at: "2026-01-02T00:00:00Z",
      },
      email: "bob@example.com",
      org_id: "current_org",
      org_name: "Bob Org",
      plan: "free",
      organization: "Bob Org",
    });
  });

  it("fills every legacy default when only email, plan and org_name are present", () => {
    expect(assertMeResponse({ email: "x@example.com", plan: "free", org_name: "X" })).toEqual({
      user: {
        id: "current_user",
        email: "x@example.com",
        name: "current_user",
        role: "member",
        email_verified: true,
        created_at: "1970-01-01T00:00:00Z",
      },
      org: {
        id: "current_org",
        name: "X",
        slug: "current-org",
        plan: "free",
        status: "active",
        created_at: "1970-01-01T00:00:00Z",
      },
      email: "x@example.com",
      org_id: "current_org",
      org_name: "X",
      plan: "free",
      organization: "X",
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Me response must be a JSON object/],
    ["an array", [], /Me response must be a JSON object/],
    // An array-valued user/org is not a nested object, so the legacy path runs and misses email/name.
    ["an array user", { user: [], org }, /Me response\.user\.email must be a non-empty string/],
    ["an array org", { user, org: [] }, /Me response\.org\.name must be a non-empty string/],
    [
      "a numeric user.id",
      { user: { ...user, id: 5 }, org },
      /Me response\.user\.id must be a non-empty string/,
    ],
    [
      "an empty user.email",
      { user: { ...user, email: "" }, org },
      /Me response\.user\.email must be a non-empty string/,
    ],
    [
      "a null user.name",
      { user: { ...user, name: null }, org },
      /Me response\.user\.name must be a non-empty string/,
    ],
    [
      "a numeric user.role",
      { user: { ...user, role: 7 }, org },
      /Me response\.user\.role must be a non-empty string/,
    ],
    [
      "a string user.email_verified",
      { user: { ...user, email_verified: "yes" }, org },
      /Me response\.user\.email_verified must be a boolean/,
    ],
    [
      "a blank user.created_at",
      { user: { ...user, created_at: "  " }, org },
      /Me response\.user\.created_at must be a non-empty string/,
    ],
    [
      "an empty org.id",
      { user, org: { ...org, id: "" } },
      /Me response\.org\.id must be a non-empty string/,
    ],
    [
      "a missing org.name",
      { user, org: { ...org, name: undefined } },
      /Me response\.org\.name must be a non-empty string/,
    ],
    [
      "a numeric org.slug",
      { user, org: { ...org, slug: 1 } },
      /Me response\.org\.slug must be a non-empty string/,
    ],
    [
      "a missing org.plan",
      { user, org: { ...org, plan: undefined } },
      /Me response\.org\.plan must be a non-empty string/,
    ],
    [
      "an empty org.status",
      { user, org: { ...org, status: "" } },
      /Me response\.org\.status must be a non-empty string/,
    ],
    [
      "a numeric org.created_at",
      { user, org: { ...org, created_at: 3 } },
      /Me response\.org\.created_at must be a non-empty string/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertMeResponse(payload), fragment);
  });

  it("raises a structured validation error for a bad nested field", () => {
    const error = captureError(() => assertMeResponse({ user: { ...user, email: "" }, org }));
    expect(error.errorCode).toBe("invalid_payload_fragment");
    expect(error.validationErrors).toEqual([
      {
        path: "Me response.user.email",
        message: "Me response.user.email must be a non-empty string.",
        type: "string_type",
      },
    ]);
  });
});

describe("normalizeUpdateMeRequest", () => {
  it.each<[label: string, request: UpdateMeRequest, expected: Record<string, unknown>]>([
    ["name only", { name: "  Ann " }, { name: "Ann" }],
    ["org_name only", { org_name: " Acme " }, { org_name: "Acme" }],
    ["both fields", { name: "Ann", org_name: "Acme" }, { name: "Ann", org_name: "Acme" }],
  ])("trims and forwards %s", (_label, request, expected) => {
    expect(normalizeUpdateMeRequest(request)).toEqual(expected);
  });

  it.each<RejectionCase>([
    ["null", null, /Account update request must be a JSON object/],
    ["an array", [], /Account update request must be a JSON object/],
    ["an empty request", {}, /must include name and\/or org_name/],
    ["an empty name", { name: "" }, /Account update name must be a non-empty string/],
    ["a numeric name", { name: 5 }, /Account update name must be a non-empty string/],
    ["a blank org_name", { org_name: "   " }, /Account update org_name must be a non-empty string/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeUpdateMeRequest(payload as UpdateMeRequest), fragment);
  });
});

describe("assertStringArray", () => {
  it("returns a copy of a list of non-empty strings", () => {
    const input = ["a", "b"];
    const result = assertStringArray(input, "Fields");
    expect(result).toEqual(input);
    expect(result).not.toBe(input);
  });

  it.each<[label: string, value: unknown]>([
    ["a string", "a"],
    ["null", null],
    ["a list containing an empty string", ["a", ""]],
    ["a list containing a number", ["a", 1]],
  ])("rejects %s", (_label, value) => {
    expectRejection(
      () => assertStringArray(value, "Fields"),
      /Fields must be a list of non-empty strings/,
    );
  });
});

describe("assertJsonRecord", () => {
  it("returns the same object", () => {
    const value = { a: 1 };
    expect(assertJsonRecord(value, "Record")).toBe(value);
  });

  it.each([...NON_OBJECT_PAYLOADS, ["a number", 1] as [string, unknown]])(
    "rejects %s",
    (_label, payload) => {
      expectRejection(() => assertJsonRecord(payload, "Record"), /Record must be a JSON object/);
    },
  );
});

describe("assertDistributionInfoResponse", () => {
  const distribution = {
    name: "normal",
    description: "Gaussian",
    required_params: ["mean", "std"],
    optional_params: [],
    example: { mean: 0, std: 1 },
  };

  it("returns only the normalized distribution fields", () => {
    expect(assertDistributionInfoResponse({ ...distribution, extra: 1 })).toEqual(distribution);
  });

  it.each<RejectionCase>([
    ["null", null, /Distribution entry must be a JSON object/],
    [
      "an empty name",
      { ...distribution, name: "" },
      /Distribution entry\.name must be a non-empty string/,
    ],
    [
      "a missing description",
      { ...distribution, description: undefined },
      /Distribution entry\.description/,
    ],
    [
      "a string required_params",
      { ...distribution, required_params: "mean" },
      /Distribution entry\.required_params must be a list/,
    ],
    [
      "a numeric optional_params entry",
      { ...distribution, optional_params: [1] },
      /Distribution entry\.optional_params must be a list/,
    ],
    [
      "an array example",
      { ...distribution, example: [] },
      /Distribution entry\.example must be a JSON object/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDistributionInfoResponse(payload), fragment);
  });
});

describe("assertDistributionListResponse", () => {
  const distribution = {
    name: "normal",
    description: "Gaussian",
    required_params: ["mean"],
    optional_params: ["std"],
    example: { mean: 0 },
  };

  it("wraps a raw array in synthetic pagination", () => {
    expect(assertDistributionListResponse([distribution, distribution])).toEqual({
      distributions: [distribution, distribution],
      total: 2,
      page: 1,
      limit: 2,
      pages: 1,
    });
  });

  it("uses limit=1 for an empty array so the page stays well-formed", () => {
    expect(assertDistributionListResponse([])).toEqual({
      distributions: [],
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("normalizes a paginated object", () => {
    expect(
      assertDistributionListResponse({
        distributions: [distribution],
        total: 7,
        page: 2,
        limit: 5,
        pages: 2,
      }),
    ).toEqual({ distributions: [distribution], total: 7, page: 2, limit: 5, pages: 2 });
  });

  const page = { distributions: [distribution], total: 1, page: 1, limit: 1, pages: 1 };
  it.each<RejectionCase>([
    ["null", null, /Distribution list response must be a JSON object/],
    [
      "a missing distributions list",
      { total: 0 },
      /Distribution list response is missing distributions/,
    ],
    ["a negative total", { ...page, total: -1 }, /Distribution list response has an invalid total/],
    ["a zero page", { ...page, page: 0 }, /Distribution list response has an invalid page/],
    ["a zero limit", { ...page, limit: 0 }, /Distribution list response has an invalid limit/],
    ["a string pages", { ...page, pages: "1" }, /Distribution list response has an invalid pages/],
    [
      "an invalid entry",
      { ...page, distributions: [{}] },
      /Distribution entry\.name must be a non-empty string/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDistributionListResponse(payload), fragment);
  });
});

describe("assertTemplateInfoResponse", () => {
  const template = {
    id: "pricing",
    name: "Pricing",
    category: "revenue",
    description: "Pricing template",
    example_request: { mode: "auto" },
  };

  it("returns only the normalized template fields", () => {
    expect(assertTemplateInfoResponse({ ...template, extra: 1 })).toEqual(template);
  });

  it.each<RejectionCase>([
    ["an array", [], /Template entry must be a JSON object/],
    ["an empty id", { ...template, id: "" }, /Template entry\.id must be a non-empty string/],
    ["a numeric name", { ...template, name: 1 }, /Template entry\.name must be a non-empty string/],
    ["a missing category", { ...template, category: undefined }, /Template entry\.category/],
    ["a blank description", { ...template, description: " " }, /Template entry\.description/],
    [
      "a null example_request",
      { ...template, example_request: null },
      /Template entry\.example_request must be a JSON object/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTemplateInfoResponse(payload), fragment);
  });
});

describe("assertTemplateListResponse", () => {
  const template = {
    id: "pricing",
    name: "Pricing",
    category: "revenue",
    description: "Pricing template",
    example_request: {},
  };

  it("wraps a raw array in synthetic pagination", () => {
    expect(assertTemplateListResponse([template])).toEqual({
      templates: [template],
      total: 1,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("uses limit=1 for an empty array so the page stays well-formed", () => {
    expect(assertTemplateListResponse([])).toEqual({
      templates: [],
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("normalizes a paginated object", () => {
    expect(
      assertTemplateListResponse({ templates: [template], total: 3, page: 1, limit: 2, pages: 2 }),
    ).toEqual({ templates: [template], total: 3, page: 1, limit: 2, pages: 2 });
  });

  const page = { templates: [template], total: 1, page: 1, limit: 1, pages: 1 };
  it.each<RejectionCase>([
    ["a string", "templates", /Template list response must be a JSON object/],
    ["a missing templates list", {}, /Template list response is missing templates/],
    ["a fractional total", { ...page, total: 0.5 }, /Template list response has an invalid total/],
    ["a negative page", { ...page, page: -1 }, /Template list response has an invalid page/],
    ["a null limit", { ...page, limit: null }, /Template list response has an invalid limit/],
    ["a zero pages", { ...page, pages: 0 }, /Template list response has an invalid pages/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTemplateListResponse(payload), fragment);
  });
});

describe("assertLimitsInfoResponse", () => {
  it("normalizes a fully populated limits payload", () => {
    const limits = {
      plan: "pro",
      simulations_per_month: "unlimited",
      max_simulations_per_month: 100,
      max_runs_per_simulation: 1000,
      max_batch_items: 50,
      rate_limit_per_minute: 60,
      connectors: 3,
      jobs_enabled: true,
      async_jobs_enabled: false,
      webhooks_enabled: true,
    };
    expect(assertLimitsInfoResponse({ ...limits, extra: 1 })).toEqual(limits);
  });

  it("derives simulations_per_month from max_simulations_per_month when absent", () => {
    expect(
      assertLimitsInfoResponse({
        plan: "free",
        max_simulations_per_month: 10,
        rate_limit_per_minute: 5,
      }),
    ).toEqual({
      plan: "free",
      simulations_per_month: 10,
      max_simulations_per_month: 10,
      max_runs_per_simulation: undefined,
      max_batch_items: undefined,
      rate_limit_per_minute: 5,
      connectors: undefined,
      jobs_enabled: undefined,
      async_jobs_enabled: undefined,
      webhooks_enabled: undefined,
    });
  });

  it("keeps explicit nulls and falls back from jobs_enabled to async_jobs_enabled", () => {
    expect(
      assertLimitsInfoResponse({
        plan: "free",
        simulations_per_month: 20,
        rate_limit_per_minute: 5,
        connectors: null,
        jobs_enabled: null,
        async_jobs_enabled: true,
        webhooks_enabled: null,
      }),
    ).toEqual({
      plan: "free",
      simulations_per_month: 20,
      max_simulations_per_month: undefined,
      max_runs_per_simulation: undefined,
      max_batch_items: undefined,
      rate_limit_per_minute: 5,
      connectors: null,
      jobs_enabled: true,
      async_jobs_enabled: true,
      webhooks_enabled: null,
    });
  });

  const base = { plan: "pro", simulations_per_month: 100, rate_limit_per_minute: 60 };
  it.each<RejectionCase>([
    ["null", null, /Limits response must be a JSON object/],
    ["a missing plan", { ...base, plan: undefined }, /Limits response missing plan/],
    [
      "a negative max_simulations_per_month",
      { ...base, max_simulations_per_month: -1 },
      /invalid max_simulations_per_month/,
    ],
    [
      "a fractional max_simulations_per_month",
      { ...base, max_simulations_per_month: 1.5 },
      /invalid max_simulations_per_month/,
    ],
    // Neither simulations_per_month nor the max fallback is present.
    [
      "no simulations_per_month at all",
      { plan: "pro", rate_limit_per_minute: 60 },
      /invalid simulations_per_month/,
    ],
    [
      "a boolean simulations_per_month",
      { ...base, simulations_per_month: true },
      /invalid simulations_per_month/,
    ],
    [
      "a string max_runs_per_simulation",
      { ...base, max_runs_per_simulation: "10" },
      /invalid max_runs_per_simulation/,
    ],
    ["a negative max_batch_items", { ...base, max_batch_items: -5 }, /invalid max_batch_items/],
    [
      "a missing rate_limit_per_minute",
      { ...base, rate_limit_per_minute: undefined },
      /invalid rate_limit_per_minute/,
    ],
    ["a string connectors", { ...base, connectors: "3" }, /invalid connectors count/],
    ["a negative connectors", { ...base, connectors: -1 }, /invalid connectors count/],
    ["a string jobs_enabled", { ...base, jobs_enabled: "yes" }, /invalid jobs_enabled flag/],
    [
      "a numeric async_jobs_enabled",
      { ...base, async_jobs_enabled: 1 },
      /invalid async_jobs_enabled flag/,
    ],
    [
      "a string webhooks_enabled",
      { ...base, webhooks_enabled: "no" },
      /invalid webhooks_enabled flag/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertLimitsInfoResponse(payload), fragment);
  });
});

describe("assertBillingInfoResponse", () => {
  it("keeps every populated field", () => {
    const info = {
      plan: "team",
      stripe_customer_id: "cus_1",
      subscription_status: "active",
      current_period_end: "2026-10-01T00:00:00Z",
    };
    expect(assertBillingInfoResponse({ ...info, extra: 1 })).toEqual(info);
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", { plan: "free" }],
    [
      "null",
      {
        plan: "free",
        stripe_customer_id: null,
        subscription_status: null,
        current_period_end: null,
      },
    ],
  ])("defaults optional fields to null when %s", (_label, payload) => {
    expect(assertBillingInfoResponse(payload)).toEqual({
      plan: "free",
      stripe_customer_id: null,
      subscription_status: null,
      current_period_end: null,
    });
  });

  it.each<RejectionCase>([
    ["an array", [], /Billing info response must be a JSON object/],
    ["a missing plan", {}, /Billing info response missing plan/],
    [
      "a numeric stripe_customer_id",
      { plan: "free", stripe_customer_id: 5 },
      /invalid stripe_customer_id/,
    ],
    [
      "a boolean subscription_status",
      { plan: "free", subscription_status: true },
      /invalid subscription_status/,
    ],
    [
      "a numeric current_period_end",
      { plan: "free", current_period_end: 1 },
      /invalid current_period_end/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertBillingInfoResponse(payload), fragment);
  });
});

describe("assertBillingSessionResponse", () => {
  it("returns only the url", () => {
    expect(assertBillingSessionResponse({ url: "https://billing.example/s/1", extra: 1 })).toEqual({
      url: "https://billing.example/s/1",
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Billing session response must be a JSON object/],
    ["a missing url", {}, /Billing session response missing url/],
    ["an empty url", { url: "" }, /Billing session response missing url/],
    ["a numeric url", { url: 5 }, /Billing session response missing url/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertBillingSessionResponse(payload), fragment);
  });
});

describe("assertMeteringBatchResponse", () => {
  it("returns the accepted count and billing period", () => {
    expect(
      assertMeteringBatchResponse({ accepted: 3, billing_period: "2026-09", extra: 1 }),
    ).toEqual({
      accepted: 3,
      billing_period: "2026-09",
    });
  });

  it.each<RejectionCase>([
    ["an array", [], /Metering response must be a JSON object/],
    ["a negative accepted", { accepted: -1, billing_period: "2026-09" }, /invalid accepted count/],
    [
      "a fractional accepted",
      { accepted: 1.5, billing_period: "2026-09" },
      /invalid accepted count/,
    ],
    ["a missing billing_period", { accepted: 1 }, /missing billing_period/],
    ["an empty billing_period", { accepted: 1, billing_period: "" }, /missing billing_period/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertMeteringBatchResponse(payload), fragment);
  });
});

describe("assertCreditRefreshResponse", () => {
  const refresh = {
    credits_granted: 100,
    credits_issued_this_month: 300,
    monthly_limit: 1000,
    monthly_remaining: 700,
    billing_period: "2026-09",
    expires_at: 1_790_000_000.5,
    refresh_after: 1_789_990_000,
    server_time: 1_789_980_000,
  };

  it("returns only the normalized credit fields", () => {
    expect(assertCreditRefreshResponse({ ...refresh, extra: 1 })).toEqual(refresh);
  });

  it.each<RejectionCase>([
    ["a string", "credits", /Credit refresh response must be a JSON object/],
    ["a negative credits_granted", { ...refresh, credits_granted: -1 }, /invalid credits_granted/],
    [
      "a string credits_issued_this_month",
      { ...refresh, credits_issued_this_month: "1" },
      /invalid credits_issued_this_month/,
    ],
    ["a fractional monthly_limit", { ...refresh, monthly_limit: 1.5 }, /invalid monthly_limit/],
    [
      "a null monthly_remaining",
      { ...refresh, monthly_remaining: null },
      /invalid monthly_remaining/,
    ],
    ["an empty billing_period", { ...refresh, billing_period: "" }, /missing billing_period/],
    ["a NaN expires_at", { ...refresh, expires_at: Number.NaN }, /invalid expires_at/],
    ["a string refresh_after", { ...refresh, refresh_after: "soon" }, /invalid refresh_after/],
    [
      "an infinite server_time",
      { ...refresh, server_time: Number.POSITIVE_INFINITY },
      /invalid server_time/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertCreditRefreshResponse(payload), fragment);
  });
});

describe("assertTeamMemberInfo", () => {
  const member = {
    user_id: "user-1",
    name: "Ann",
    email: "ann@example.com",
    role: "admin",
    status: "active",
  };

  it("keeps a string last_active", () => {
    expect(
      assertTeamMemberInfo({ ...member, last_active: "2026-01-01T00:00:00Z", extra: 1 }),
    ).toEqual({
      ...member,
      last_active: "2026-01-01T00:00:00Z",
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", member],
    ["null", { ...member, last_active: null }],
  ])("defaults last_active to null when %s", (_label, payload) => {
    expect(assertTeamMemberInfo(payload)).toEqual({ ...member, last_active: null });
  });

  it.each<RejectionCase>([
    ["null", null, /Team member entry must be a JSON object/],
    ["an empty user_id", { ...member, user_id: "" }, /Team member entry is missing user_id/],
    ["a numeric name", { ...member, name: 1 }, /Team member entry is missing name/],
    ["a missing email", { ...member, email: undefined }, /Team member entry is missing email/],
    ["a null role", { ...member, role: null }, /Team member entry is missing role/],
    ["an empty status", { ...member, status: "" }, /Team member entry is missing status/],
    ["a numeric last_active", { ...member, last_active: 5 }, /invalid last_active value/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTeamMemberInfo(payload), fragment);
  });
});

describe("assertTeamListResponse", () => {
  const member = {
    user_id: "user-1",
    name: "Ann",
    email: "ann@example.com",
    role: "admin",
    status: "active",
    last_active: null,
  };

  it("wraps a raw array in synthetic pagination", () => {
    expect(assertTeamListResponse([member, member])).toEqual({
      members: [member, member],
      total: 2,
      page: 1,
      limit: 2,
      pages: 1,
    });
  });

  it("uses limit=1 for an empty array so the page stays well-formed", () => {
    expect(assertTeamListResponse([])).toEqual({
      members: [],
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("normalizes a paginated object", () => {
    expect(
      assertTeamListResponse({ members: [member], total: 9, page: 2, limit: 4, pages: 3 }),
    ).toEqual({
      members: [member],
      total: 9,
      page: 2,
      limit: 4,
      pages: 3,
    });
  });

  const page = { members: [member], total: 1, page: 1, limit: 1, pages: 1 };
  it.each<RejectionCase>([
    ["null", null, /Team response must be a JSON object or list/],
    ["a string", "team", /Team response must be a JSON object or list/],
    ["a missing members list", { total: 0 }, /Team response is missing members/],
    ["a negative total", { ...page, total: -1 }, /Team response has an invalid total/],
    ["a zero page", { ...page, page: 0 }, /Team response has an invalid page/],
    ["a zero limit", { ...page, limit: 0 }, /Team response has an invalid limit/],
    ["a fractional pages", { ...page, pages: 1.5 }, /Team response has an invalid pages value/],
    ["an invalid member", { ...page, members: [{}] }, /Team member entry is missing user_id/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTeamListResponse(payload), fragment);
  });
});

describe("assertTeamInviteResponse", () => {
  it("returns the message and invite_id", () => {
    expect(assertTeamInviteResponse({ message: "Invited", invite_id: "inv-1", extra: 1 })).toEqual({
      message: "Invited",
      invite_id: "inv-1",
    });
  });

  it.each<RejectionCase>([
    ["an array", [], /Team invite response must be a JSON object/],
    ["a missing message", { invite_id: "inv-1" }, /Team invite response is missing message/],
    [
      "an empty invite_id",
      { message: "Invited", invite_id: "" },
      /Team invite response is missing invite_id/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTeamInviteResponse(payload), fragment);
  });
});

describe("assertTeamRoleUpdateResponse", () => {
  it("returns the message and user_id", () => {
    expect(
      assertTeamRoleUpdateResponse({ message: "Updated", user_id: "user-1", extra: 1 }),
    ).toEqual({
      message: "Updated",
      user_id: "user-1",
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Team role update response must be a JSON object/],
    [
      "an empty message",
      { message: "", user_id: "user-1" },
      /Team role update response is missing message/,
    ],
    [
      "a numeric user_id",
      { message: "Updated", user_id: 1 },
      /Team role update response is missing user_id/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertTeamRoleUpdateResponse(payload), fragment);
  });
});

describe("assertTeamRemoveResponse", () => {
  it("keeps an explicit removed flag and user_id", () => {
    expect(assertTeamRemoveResponse({ removed: false, user_id: "user-9" }, "user-1")).toEqual({
      removed: false,
      user_id: "user-9",
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", {}],
    ["malformed", { removed: "no", user_id: "" }],
  ])(
    "defaults removed=true and the requested user_id when the fields are %s",
    (_label, payload) => {
      expect(assertTeamRemoveResponse(payload, "user-1")).toEqual({
        removed: true,
        user_id: "user-1",
      });
    },
  );

  it("rejects a non-object payload", () => {
    expectRejection(
      () => assertTeamRemoveResponse([], "user-1"),
      /Team remove response must be a JSON object/,
    );
  });
});

describe("assertDeviceRegistrationResponse", () => {
  const required = {
    id: "reg-1",
    org_id: "org-1",
    api_key_id: "key-1",
    device_id: "device-1",
    status: "active",
    heartbeat_count: 3,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  };
  const optionalFields = [
    "platform",
    "platform_version",
    "hostname_hash",
    "sdk_version",
    "last_heartbeat_at",
  ] as const;
  const optional = {
    platform: "darwin",
    platform_version: "25.6.0",
    hostname_hash: "h".repeat(16),
    sdk_version: "1.0.16",
    last_heartbeat_at: "2026-01-02T00:00:00Z",
  };
  const nulls = Object.fromEntries(optionalFields.map((field) => [field, null]));

  it("keeps every populated field", () => {
    expect(assertDeviceRegistrationResponse({ ...required, ...optional, extra: 1 })).toEqual({
      ...required,
      ...optional,
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", required],
    ["null", { ...required, ...nulls }],
  ])("defaults optional fields to null when %s", (_label, payload) => {
    expect(assertDeviceRegistrationResponse(payload)).toEqual({ ...required, ...nulls });
  });

  it("uses the caller-supplied context in error messages", () => {
    expectRejection(
      () => assertDeviceRegistrationResponse(null, "Device registration response"),
      /Device registration response must be a JSON object/,
    );
  });

  it.each<RejectionCase>([
    ["an array", [], /Device registration entry must be a JSON object/],
    ...(
      ["id", "org_id", "api_key_id", "device_id", "status", "created_at", "updated_at"] as const
    ).map(
      (field): RejectionCase => [
        `an empty ${field}`,
        { ...required, [field]: "" },
        new RegExp(`Device registration entry is missing ${field}\\.`),
      ],
    ),
    ["a negative heartbeat_count", { ...required, heartbeat_count: -1 }, /invalid heartbeat_count/],
    ["a string heartbeat_count", { ...required, heartbeat_count: "3" }, /invalid heartbeat_count/],
    ...optionalFields.map(
      (field): RejectionCase => [
        `a numeric ${field}`,
        { ...required, [field]: 42 },
        new RegExp(`Device registration entry has an invalid ${field}\\.`),
      ],
    ),
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeviceRegistrationResponse(payload), fragment);
  });
});

describe("assertDeviceListEntryResponse", () => {
  const required = { id: "reg-1", device_id: "device-1", status: "active", heartbeat_count: 0 };
  const optionalFields = [
    "platform",
    "platform_version",
    "sdk_version",
    "api_key_label",
    "api_key_prefix",
    "registered_at",
    "last_heartbeat_at",
  ] as const;
  const optional = Object.fromEntries(optionalFields.map((field) => [field, `${field}-value`]));
  const nulls = Object.fromEntries(optionalFields.map((field) => [field, null]));

  it("keeps every populated field", () => {
    expect(assertDeviceListEntryResponse({ ...required, ...optional, extra: 1 })).toEqual({
      ...required,
      ...optional,
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", required],
    ["null", { ...required, ...nulls }],
  ])("defaults optional fields to null when %s", (_label, payload) => {
    expect(assertDeviceListEntryResponse(payload)).toEqual({ ...required, ...nulls });
  });

  it.each<RejectionCase>([
    ["null", null, /Device list item must be a JSON object/],
    ["an empty id", { ...required, id: "" }, /Device list item is missing id/],
    [
      "a missing device_id",
      { ...required, device_id: undefined },
      /Device list item is missing device_id/,
    ],
    ["a numeric status", { ...required, status: 1 }, /Device list item is missing status/],
    [
      "a fractional heartbeat_count",
      { ...required, heartbeat_count: 0.5 },
      /invalid heartbeat_count/,
    ],
    ...optionalFields.map(
      (field): RejectionCase => [
        `a numeric ${field}`,
        { ...required, [field]: 42 },
        new RegExp(`Device list item has an invalid ${field}\\.`),
      ],
    ),
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeviceListEntryResponse(payload), fragment);
  });
});

describe("assertDeviceListResponse", () => {
  const entry = { id: "reg-1", device_id: "device-1", status: "active", heartbeat_count: 2 };
  const page = {
    devices: [entry],
    device_count: 1,
    total: 1,
    page: 1,
    limit: 25,
    pages: 1,
    device_limit: 5,
    plan: "team",
  };

  it("normalizes the page and every device entry", () => {
    expect(assertDeviceListResponse({ ...page, extra: 1 })).toEqual({
      ...page,
      devices: [
        {
          ...entry,
          platform: null,
          platform_version: null,
          sdk_version: null,
          api_key_label: null,
          api_key_prefix: null,
          registered_at: null,
          last_heartbeat_at: null,
        },
      ],
    });
  });

  it.each<RejectionCase>([
    ["an array", [], /Device list response must be a JSON object/],
    [
      "a missing devices list",
      { ...page, devices: undefined },
      /Device list response is missing devices/,
    ],
    ["a negative device_count", { ...page, device_count: -1 }, /invalid device_count/],
    ["a string total", { ...page, total: "1" }, /Device list response has an invalid total/],
    ["a zero page", { ...page, page: 0 }, /Device list response has an invalid page/],
    ["a zero limit", { ...page, limit: 0 }, /Device list response has an invalid limit/],
    ["a zero pages", { ...page, pages: 0 }, /Device list response has an invalid pages value/],
    ["a negative device_limit", { ...page, device_limit: -1 }, /invalid device_limit/],
    ["an empty plan", { ...page, plan: "" }, /Device list response is missing plan/],
    ["an invalid device entry", { ...page, devices: [{}] }, /Device list item is missing id/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeviceListResponse(payload), fragment);
  });
});

describe("assertDeviceRevokeResponse", () => {
  it("returns the revoked flag and registration_id", () => {
    expect(
      assertDeviceRevokeResponse({ revoked: true, registration_id: "reg-1", extra: 1 }),
    ).toEqual({
      revoked: true,
      registration_id: "reg-1",
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Device revoke response must be a JSON object/],
    [
      "a string revoked",
      { revoked: "yes", registration_id: "reg-1" },
      /Device revoke response is missing revoked/,
    ],
    ["an empty registration_id", { revoked: true, registration_id: "" }, /missing registration_id/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeviceRevokeResponse(payload), fragment);
  });
});

describe("assertAuditLogEntry", () => {
  const required = {
    id: "audit-1",
    timestamp: "2026-01-01T00:00:00Z",
    actor_email: "ann@example.com",
    action: "api_key.create",
    resource_type: "api_key",
    result: "success",
  };
  const optional = {
    resource_id: "key-1",
    ip_address: "203.0.113.5",
    content_hash: "c".repeat(64),
    metadata: { label: "ci", nested: { ok: true } },
  };
  const nulls = { resource_id: null, ip_address: null, content_hash: null, metadata: null };

  it("keeps every populated field including a metadata object", () => {
    expect(assertAuditLogEntry({ ...required, ...optional, extra: 1 })).toEqual({
      ...required,
      ...optional,
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", required],
    ["null", { ...required, ...nulls }],
  ])("defaults optional fields to null when %s", (_label, payload) => {
    expect(assertAuditLogEntry(payload)).toEqual({ ...required, ...nulls });
  });

  it.each<RejectionCase>([
    ["a string", "entry", /Audit log entry must be a JSON object/],
    ...(Object.keys(required) as Array<keyof typeof required>).map(
      (field): RejectionCase => [
        `an empty ${field}`,
        { ...required, [field]: "" },
        new RegExp(`Audit log entry is missing ${field}\\.`),
      ],
    ),
    [
      "a numeric resource_id",
      { ...required, resource_id: 5 },
      /Audit log entry has an invalid resource_id/,
    ],
    [
      "a numeric ip_address",
      { ...required, ip_address: 5 },
      /Audit log entry has an invalid ip_address/,
    ],
    [
      "a numeric content_hash",
      { ...required, content_hash: 5 },
      /Audit log entry has an invalid content_hash/,
    ],
    // metadata must be a plain object: arrays and scalars are both rejected.
    ["an array metadata", { ...required, metadata: [] }, /Audit log entry has invalid metadata/],
    [
      "a string metadata",
      { ...required, metadata: "meta" },
      /Audit log entry has invalid metadata/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertAuditLogEntry(payload), fragment);
  });
});
