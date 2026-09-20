// SPDX-License-Identifier: Apache-2.0
// Table-driven unit tests for the pure platform validators in
// _client_platform_validators_b1.ts and _client_platform_validators_b2.ts.
// Every acceptance case asserts the exact normalized shape (including
// defaulted nulls); every rejection case asserts both the error class and a
// distinctive message fragment. Structured validation errors additionally
// assert errorCode and the normalized validation path.
import { describe, expect, it } from "vitest";
import { DecisionEngineError } from "./_client_errors.js";
import {
  assertAuditLogResponse,
  assertDeploymentDeleteResponse,
  assertDeploymentRegionsResponse,
  assertDeploymentResponse,
  assertExecutionPolicyResponse,
  assertExecutionPolicySnapshotListResponse,
  normalizeApiKeyCreateRequest,
  normalizeCreateDeploymentRequest,
  normalizeCreditRefreshRequest,
  normalizeMeteringBatchRequest,
  normalizeTeamInviteRequest,
  normalizeTeamRole,
  normalizeUpdateExecutionPolicyRequest,
} from "./_client_platform_validators_b1.js";
import {
  assertArray,
  assertBoolean,
  assertConnectorListResponse,
  assertDatasetListResponse,
  assertDatasetSummaryResponse,
  assertDeploymentCostResponse,
  assertEnumArray,
  assertEnumKeyedCountRecord,
  assertEnumKeyedEnumRecord,
  assertEnumValue,
  assertFiniteNumber,
  assertInteger,
  assertJsonObject,
  assertNonEmptyString,
  assertRuntimeArtifactReference,
  assertRuntimeBenchmarkDiscoveryLane,
  assertRuntimeShippingContractSummary,
  assertRuntimeSignature,
  assertRuntimeSnapshotReference,
  assertUniqueRuntimeObjectField,
  assertUniqueRuntimeValues,
  buildStructuredValidationError,
  normalizeValidationPath,
} from "./_client_platform_validators_b2.js";
import {
  NON_SHIPPING_RULE,
  SHIPPING_BENCHMARK_DISCOVERY_RULE,
  makeBenchmarkDiscoveryLanePayload,
  makeDiscoveredSourceInventory,
} from "./_client_test_helpers.js";
import type {
  CreateAPIKeyRequest,
  CreateDeploymentRequest,
  CreditRefreshRequest,
  MeteringBatchRequest,
  TeamInviteRequest,
  UpdateExecutionPolicyRequest,
} from "./types.js";

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

const AUDIT_ENTRY = {
  id: "audit-1",
  timestamp: "2026-01-01T00:00:00Z",
  actor_email: "ann@example.com",
  action: "api_key.create",
  resource_type: "api_key",
  result: "success",
};

describe("assertAuditLogResponse", () => {
  const page = { entries: [AUDIT_ENTRY], total: 1, page: 1, limit: 50, pages: 1 };

  it("normalizes the page and every entry", () => {
    expect(assertAuditLogResponse({ ...page, extra: 1 })).toEqual({
      ...page,
      entries: [
        { ...AUDIT_ENTRY, resource_id: null, ip_address: null, content_hash: null, metadata: null },
      ],
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Audit logs response must be a JSON object/],
    ["a missing entries list", { total: 0 }, /Audit logs response is missing entries/],
    ["a negative total", { ...page, total: -1 }, /Audit logs response has an invalid total/],
    ["a zero page", { ...page, page: 0 }, /Audit logs response has an invalid page/],
    ["a string limit", { ...page, limit: "50" }, /Audit logs response has an invalid limit/],
    ["a zero pages", { ...page, pages: 0 }, /Audit logs response has an invalid pages value/],
    ["an invalid entry", { ...page, entries: [{}] }, /Audit log entry is missing id/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertAuditLogResponse(payload), fragment);
  });
});

const POLICY_REQUIRED = {
  org_id: "org-1",
  min_confidence: 0.8,
  require_calibration: true,
  allow_reexecution: false,
  updated_at: "2026-01-02T00:00:00Z",
};
const POLICY_OPTIONAL = {
  risk_floor: 0.2,
  snapshot_id: "snap-2",
  content_hash: "c".repeat(64),
  schema_revision: "rev-3",
  revision: 2,
  previous_snapshot_id: "snap-1",
  created_at: "2026-01-01T00:00:00Z",
};
const POLICY_NULLS = {
  risk_floor: null,
  snapshot_id: null,
  content_hash: null,
  schema_revision: null,
  revision: null,
  previous_snapshot_id: null,
  created_at: null,
};

describe("assertExecutionPolicyResponse", () => {
  it("keeps every populated field", () => {
    expect(
      assertExecutionPolicyResponse({ ...POLICY_REQUIRED, ...POLICY_OPTIONAL, extra: 1 }),
    ).toEqual({
      ...POLICY_REQUIRED,
      ...POLICY_OPTIONAL,
    });
  });

  it.each<[label: string, payload: Record<string, unknown>]>([
    ["absent", POLICY_REQUIRED],
    ["null", { ...POLICY_REQUIRED, ...POLICY_NULLS }],
  ])("defaults optional fields to null when %s", (_label, payload) => {
    expect(assertExecutionPolicyResponse(payload)).toEqual({ ...POLICY_REQUIRED, ...POLICY_NULLS });
  });

  const policy = POLICY_REQUIRED;
  it.each<RejectionCase>([
    ["an array", [], /Execution policy response must be a JSON object/],
    ["an empty org_id", { ...policy, org_id: "" }, /Execution policy response is missing org_id/],
    ["a NaN min_confidence", { ...policy, min_confidence: Number.NaN }, /invalid min_confidence/],
    ["a string min_confidence", { ...policy, min_confidence: "0.5" }, /invalid min_confidence/],
    ["a string risk_floor", { ...policy, risk_floor: "low" }, /invalid risk_floor/],
    ["a NaN risk_floor", { ...policy, risk_floor: Number.NaN }, /invalid risk_floor/],
    [
      "a string require_calibration",
      { ...policy, require_calibration: "yes" },
      /invalid require_calibration/,
    ],
    [
      "a numeric allow_reexecution",
      { ...policy, allow_reexecution: 1 },
      /invalid allow_reexecution/,
    ],
    ["an empty snapshot_id", { ...policy, snapshot_id: "" }, /invalid snapshot_id/],
    ["a numeric content_hash", { ...policy, content_hash: 5 }, /invalid content_hash/],
    ["an empty schema_revision", { ...policy, schema_revision: "" }, /invalid schema_revision/],
    ["a zero revision", { ...policy, revision: 0 }, /invalid revision/],
    ["a fractional revision", { ...policy, revision: 1.5 }, /invalid revision/],
    [
      "a numeric previous_snapshot_id",
      { ...policy, previous_snapshot_id: 5 },
      /invalid previous_snapshot_id/,
    ],
    ["an empty created_at", { ...policy, created_at: "" }, /invalid created_at/],
    ["a missing updated_at", { ...policy, updated_at: undefined }, /is missing updated_at/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertExecutionPolicyResponse(payload), fragment);
  });
});

describe("assertExecutionPolicySnapshotListResponse", () => {
  it("normalizes the org, snapshots and count", () => {
    expect(
      assertExecutionPolicySnapshotListResponse({
        org_id: "org-1",
        data: [POLICY_REQUIRED],
        total_snapshots: 1,
        extra: 1,
      }),
    ).toEqual({
      org_id: "org-1",
      data: [{ ...POLICY_REQUIRED, ...POLICY_NULLS }],
      total_snapshots: 1,
    });
  });

  const list = { org_id: "org-1", data: [POLICY_REQUIRED], total_snapshots: 1 };
  it.each<RejectionCase>([
    ["an array", [], /Execution policy snapshot list response must be a JSON object/],
    ["an empty org_id", { ...list, org_id: "" }, /snapshot list response is missing org_id/],
    ["a non-array data", { ...list, data: "snapshots" }, /snapshot list response is missing data/],
    ["a negative total_snapshots", { ...list, total_snapshots: -1 }, /invalid total_snapshots/],
    ["an invalid snapshot", { ...list, data: [{}] }, /Execution policy response is missing org_id/],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertExecutionPolicySnapshotListResponse(payload), fragment);
  });
});

describe("normalizeUpdateExecutionPolicyRequest", () => {
  it.each<
    [label: string, request: UpdateExecutionPolicyRequest, expected: Record<string, unknown>]
  >([
    ["min_confidence", { min_confidence: 0.75 }, { min_confidence: 0.75 }],
    ["a numeric risk_floor", { risk_floor: 0.1 }, { risk_floor: 0.1 }],
    // null explicitly clears the floor and must be forwarded as null, not dropped.
    ["a null risk_floor", { risk_floor: null }, { risk_floor: null }],
    ["require_calibration", { require_calibration: false }, { require_calibration: false }],
    ["allow_reexecution", { allow_reexecution: true }, { allow_reexecution: true }],
    [
      "every field",
      { min_confidence: 1, risk_floor: 0, require_calibration: true, allow_reexecution: false },
      { min_confidence: 1, risk_floor: 0, require_calibration: true, allow_reexecution: false },
    ],
  ])("forwards %s", (_label, request, expected) => {
    expect(normalizeUpdateExecutionPolicyRequest(request)).toEqual(expected);
  });

  it.each<RejectionCase>([
    ["null", null, /Execution policy update request must be a JSON object/],
    ["an array", [], /Execution policy update request must be a JSON object/],
    ["an empty request", {}, /must include at least one field/],
    [
      "a min_confidence above 1",
      { min_confidence: 1.5 },
      /min_confidence must be a number between 0 and 1/,
    ],
    [
      "a negative min_confidence",
      { min_confidence: -0.1 },
      /min_confidence must be a number between 0 and 1/,
    ],
    [
      "a NaN min_confidence",
      { min_confidence: Number.NaN },
      /min_confidence must be a number between 0 and 1/,
    ],
    [
      "a string min_confidence",
      { min_confidence: "0.5" },
      /min_confidence must be a number between 0 and 1/,
    ],
    [
      "a negative risk_floor",
      { risk_floor: -1 },
      /risk_floor must be a non-negative number or null/,
    ],
    [
      "a string risk_floor",
      { risk_floor: "low" },
      /risk_floor must be a non-negative number or null/,
    ],
    [
      "a string require_calibration",
      { require_calibration: "yes" },
      /require_calibration must be a boolean/,
    ],
    [
      "a numeric allow_reexecution",
      { allow_reexecution: 1 },
      /allow_reexecution must be a boolean/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(
      () => normalizeUpdateExecutionPolicyRequest(payload as UpdateExecutionPolicyRequest),
      fragment,
    );
  });
});

describe("normalizeMeteringBatchRequest", () => {
  it("trims the device id and string fields and forwards numbers and flags", () => {
    expect(
      normalizeMeteringBatchRequest({
        device_id: " device-1 ",
        events: [
          {
            event_type: " simulate ",
            module: "stat_tests",
            function: "t_test",
            engine_used: "mojo",
            latency_ms: 12.5,
            success: true,
            timestamp: 1_790_000_000,
            request_id: " req-1 ",
          },
          {},
        ],
      }),
    ).toEqual({
      device_id: "device-1",
      events: [
        {
          event_type: "simulate",
          module: "stat_tests",
          function: "t_test",
          engine_used: "mojo",
          latency_ms: 12.5,
          success: true,
          timestamp: 1_790_000_000,
          request_id: "req-1",
        },
        {},
      ],
    });
  });

  const events = [{ event_type: "simulate" }];
  it.each<RejectionCase>([
    ["null", null, /Metering ingest request must be a JSON object/],
    ["a blank device_id", { device_id: "  ", events }, /requires a non-empty device_id/],
    ["an empty events list", { device_id: "d", events: [] }, /requires a non-empty events array/],
    [
      "a non-array events",
      { device_id: "d", events: "simulate" },
      /requires a non-empty events array/,
    ],
    ["a null event", { device_id: "d", events: [null] }, /Metering event 0 must be a JSON object/],
    ["an array event", { device_id: "d", events: [[]] }, /Metering event 0 must be a JSON object/],
    [
      "an unsupported field",
      { device_id: "d", events: [{ tenant: "x" }] },
      /Metering event 0 contains unsupported field 'tenant'/,
    ],
    [
      "a numeric event_type",
      { device_id: "d", events: [{ event_type: 5 }] },
      /Metering event 0\.event_type must be a string/,
    ],
    // The index in the message must point at the offending event, not the first one.
    [
      "a numeric module on the second event",
      { device_id: "d", events: [{}, { module: 5 }] },
      /Metering event 1\.module must be a string/,
    ],
    [
      "a string latency_ms",
      { device_id: "d", events: [{ latency_ms: "1" }] },
      /Metering event 0\.latency_ms must be a finite number/,
    ],
    [
      "a NaN timestamp",
      { device_id: "d", events: [{ timestamp: Number.NaN }] },
      /Metering event 0\.timestamp must be a finite number/,
    ],
    [
      "a string success",
      { device_id: "d", events: [{ success: "yes" }] },
      /Metering event 0\.success must be a boolean/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeMeteringBatchRequest(payload as MeteringBatchRequest), fragment);
  });
});

describe("normalizeCreditRefreshRequest", () => {
  it("trims the device id and forwards credits_used", () => {
    expect(
      normalizeCreditRefreshRequest({
        device_id: " device-1 ",
        billing_period: "2026-09",
        credits_used: 3,
      }),
    ).toEqual({ device_id: "device-1", billing_period: "2026-09", credits_used: 3 });
  });

  it("defaults credits_used to 0", () => {
    expect(
      normalizeCreditRefreshRequest({ device_id: "device-1", billing_period: "2026-12" }),
    ).toEqual({
      device_id: "device-1",
      billing_period: "2026-12",
      credits_used: 0,
    });
  });

  const request = { device_id: "device-1", billing_period: "2026-09" };
  it.each<RejectionCase>([
    ["an array", [], /Credit refresh request must be a JSON object/],
    ["an empty device_id", { ...request, device_id: "" }, /requires a non-empty device_id/],
    [
      "a single-digit month",
      { ...request, billing_period: "2026-9" },
      /requires a YYYY-MM billing_period/,
    ],
    [
      "a numeric billing_period",
      { ...request, billing_period: 202_609 },
      /requires a YYYY-MM billing_period/,
    ],
    [
      "month 13",
      { ...request, billing_period: "2026-13" },
      /requires a valid billing_period month/,
    ],
    [
      "month 00",
      { ...request, billing_period: "2026-00" },
      /requires a valid billing_period month/,
    ],
    [
      "a negative credits_used",
      { ...request, credits_used: -1 },
      /credits_used must be a non-negative integer/,
    ],
    [
      "a fractional credits_used",
      { ...request, credits_used: 1.5 },
      /credits_used must be a non-negative integer/,
    ],
    [
      "a string credits_used",
      { ...request, credits_used: "3" },
      /credits_used must be a non-negative integer/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeCreditRefreshRequest(payload as CreditRefreshRequest), fragment);
  });
});

describe("normalizeTeamInviteRequest", () => {
  it("trims the email and forwards the role", () => {
    expect(normalizeTeamInviteRequest({ email: " ann@example.com ", role: "viewer" })).toEqual({
      email: "ann@example.com",
      role: "viewer",
    });
  });

  it("defaults the role to member", () => {
    expect(normalizeTeamInviteRequest({ email: "ann@example.com" })).toEqual({
      email: "ann@example.com",
      role: "member",
    });
  });

  it.each<RejectionCase>([
    ["null", null, /Team invite request must be a JSON object/],
    ["an empty email", { email: "" }, /requires a valid email/],
    ["an email without @", { email: "ann.example.com" }, /requires a valid email/],
    ["a numeric email", { email: 5 }, /requires a valid email/],
    // An explicit empty role is not nullish, so it bypasses the member default.
    [
      "an empty role",
      { email: "ann@example.com", role: "" },
      /inviteTeamMember requires a non-empty role/,
    ],
    [
      "an unknown role",
      { email: "ann@example.com", role: "root" },
      /inviteTeamMember\.role must be one of: owner, admin, member, viewer/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeTeamInviteRequest(payload as TeamInviteRequest), fragment);
  });
});

describe("normalizeTeamRole", () => {
  it.each<[input: string, expected: string]>([
    ["owner", "owner"],
    ["admin", "admin"],
    ["member", "member"],
    ["viewer", "viewer"],
    [" admin ", "admin"],
  ])("accepts %j", (input, expected) => {
    expect(normalizeTeamRole(input, "updateTeamRole")).toBe(expected);
  });

  it.each<RejectionCase>([
    ["an empty string", "", /updateTeamRole requires a non-empty role/],
    ["whitespace", "   ", /updateTeamRole requires a non-empty role/],
    ["a number", 5, /updateTeamRole requires a non-empty role/],
    ["null", null, /updateTeamRole requires a non-empty role/],
    [
      "an unknown role",
      "root",
      /updateTeamRole\.role must be one of: owner, admin, member, viewer/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeTeamRole(payload, "updateTeamRole"), fragment);
  });
});

describe("normalizeApiKeyCreateRequest", () => {
  const expiry = new Date("2027-01-01T00:00:00.000Z");
  it.each<[label: string, request: CreateAPIKeyRequest, expected: Record<string, unknown>]>([
    ["a label only", { label: "ci" }, { label: "ci" }],
    ["a null expires_at", { label: "ci", expires_at: null }, { label: "ci", expires_at: null }],
    [
      "a Date expires_at",
      { label: "ci", expires_at: expiry },
      { label: "ci", expires_at: "2027-01-01T00:00:00.000Z" },
    ],
    [
      "a string expires_at",
      { label: "ci", expires_at: "2027-01-01" },
      { label: "ci", expires_at: "2027-01-01" },
    ],
    [
      "a null device_limit",
      { label: "ci", device_limit: null },
      { label: "ci", device_limit: null },
    ],
    ["a zero device_limit", { label: "ci", device_limit: 0 }, { label: "ci", device_limit: 0 }],
    ["a positive device_limit", { label: "ci", device_limit: 3 }, { label: "ci", device_limit: 3 }],
  ])("forwards %s", (_label, request, expected) => {
    expect(normalizeApiKeyCreateRequest(request)).toEqual(expected);
  });

  it.each<RejectionCase>([
    ["null", null, /API key create request must be a JSON object/],
    ["an array", [], /API key create request must be a JSON object/],
    ["a missing label", {}, /label must be a non-empty string/],
    ["a blank label", { label: "  " }, /label must be a non-empty string/],
    ["a numeric label", { label: 5 }, /label must be a non-empty string/],
    [
      "an invalid Date expires_at",
      { label: "ci", expires_at: new Date("not a date") },
      /expires_at must be a valid Date, ISO-8601 string, or null/,
    ],
    [
      "a numeric expires_at",
      { label: "ci", expires_at: 1_790_000_000 },
      /expires_at must be a Date, ISO-8601 string, or null/,
    ],
    [
      "a negative device_limit",
      { label: "ci", device_limit: -1 },
      /device_limit must be an integer greater than or equal to 0, or null/,
    ],
    [
      "a fractional device_limit",
      { label: "ci", device_limit: 1.5 },
      /device_limit must be an integer greater than or equal to 0, or null/,
    ],
    [
      "a string device_limit",
      { label: "ci", device_limit: "2" },
      /device_limit must be an integer greater than or equal to 0, or null/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => normalizeApiKeyCreateRequest(payload as CreateAPIKeyRequest), fragment);
  });
});

describe("assertDeploymentRegionsResponse", () => {
  const provider = {
    id: "aws",
    name: "AWS",
    description: "Amazon Web Services",
    icon: "aws.svg",
    extra: true,
  };

  it("normalizes region names and labels while preserving extra fields", () => {
    expect(
      assertDeploymentRegionsResponse({
        providers: [
          {
            ...provider,
            regions: [
              { id: "us-east-1", name: "US East", label: "N. Virginia", location: "US" },
              { id: "eu-west-1", name: "EU West" },
              { id: "ap-south-1", label: "Mumbai" },
            ],
          },
        ],
      }),
    ).toEqual({
      providers: [
        {
          ...provider,
          regions: [
            { id: "us-east-1", name: "US East", label: "N. Virginia", location: "US" },
            // Without a label the name is mirrored; without a name the label is promoted.
            { id: "eu-west-1", name: "EU West", label: "EU West" },
            { id: "ap-south-1", name: "Mumbai", label: "Mumbai" },
          ],
        },
      ],
    });
  });

  it("accepts a provider with no regions", () => {
    expect(assertDeploymentRegionsResponse({ providers: [{ ...provider, regions: [] }] })).toEqual({
      providers: [{ ...provider, regions: [] }],
    });
  });

  const withRegions = (regions: unknown) => ({ providers: [{ ...provider, regions }] });
  it.each<RejectionCase>([
    ["null", null, /must be a JSON object with providers/],
    ["an object without providers", {}, /must be a JSON object with providers/],
    ["a non-array providers", { providers: "aws" }, /must be a JSON object with providers/],
    ["a null provider", { providers: [null] }, /Deployment provider entry must be a JSON object/],
    [
      "a provider with an empty id",
      { providers: [{ ...provider, id: "", regions: [] }] },
      /Deployment provider entry missing id/,
    ],
    [
      "a provider without a name",
      { providers: [{ ...provider, name: undefined, regions: [] }] },
      /Deployment provider entry missing name/,
    ],
    [
      "a provider with a numeric description",
      { providers: [{ ...provider, description: 1, regions: [] }] },
      /Deployment provider entry missing description/,
    ],
    [
      "a provider with an empty icon",
      { providers: [{ ...provider, icon: "", regions: [] }] },
      /Deployment provider entry missing icon/,
    ],
    [
      "a provider with non-array regions",
      withRegions("us-east-1"),
      /Deployment provider entry missing regions/,
    ],
    ["a null region", withRegions([null]), /Deployment region entry must be a JSON object/],
    [
      "a region with an empty id",
      withRegions([{ id: "", name: "US East" }]),
      /Deployment region entry missing id/,
    ],
    [
      "a region with neither name nor label",
      withRegions([{ id: "us-east-1" }]),
      /Deployment region entry missing name or label/,
    ],
    [
      "a region with empty name and label",
      withRegions([{ id: "us-east-1", name: "", label: "" }]),
      /missing name or label/,
    ],
    [
      "a region with non-string name and label",
      withRegions([{ id: "us-east-1", name: 5, label: 7 }]),
      /missing name or label/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeploymentRegionsResponse(payload), fragment);
  });
});

const DEPLOYMENT = {
  deployment_id: "dep-1",
  org_id: "org-1",
  provider: "algenta_shared",
  region: "algenta-shared",
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  cost_usd_month: 10,
  billable_cost_usd_month: 12,
  billing_markup_pct: 20,
};

describe("assertDeploymentResponse", () => {
  it("returns the payload unchanged", () => {
    expect(assertDeploymentResponse(DEPLOYMENT, "Deployment response")).toBe(DEPLOYMENT);
  });

  it.each<RejectionCase>([
    ["null", null, /Deployment response must be a JSON object/],
    [
      "an empty deployment_id",
      { ...DEPLOYMENT, deployment_id: "" },
      /Deployment response missing deployment_id/,
    ],
    [
      "a missing org_id",
      { ...DEPLOYMENT, org_id: undefined },
      /Deployment response missing org_id/,
    ],
    ["a numeric provider", { ...DEPLOYMENT, provider: 1 }, /Deployment response missing provider/],
    ["an empty region", { ...DEPLOYMENT, region: "" }, /Deployment response missing region/],
    ["a null status", { ...DEPLOYMENT, status: null }, /Deployment response missing status/],
    [
      "an empty created_at",
      { ...DEPLOYMENT, created_at: "" },
      /Deployment response missing created_at/,
    ],
    [
      "a string cost_usd_month",
      { ...DEPLOYMENT, cost_usd_month: "10" },
      /Deployment response missing cost_usd_month/,
    ],
    [
      "a NaN billable_cost_usd_month",
      { ...DEPLOYMENT, billable_cost_usd_month: Number.NaN },
      /missing billable_cost_usd_month/,
    ],
    [
      "an infinite billing_markup_pct",
      { ...DEPLOYMENT, billing_markup_pct: Number.POSITIVE_INFINITY },
      /missing billing_markup_pct/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeploymentResponse(payload, "Deployment response"), fragment);
  });
});

describe("normalizeCreateDeploymentRequest", () => {
  const defaults = {
    provider: "algenta_shared",
    region: "algenta-shared",
    config: null,
    billing_markup_pct: 20,
  };

  it("applies the shared-provider defaults when called without a request", () => {
    expect(normalizeCreateDeploymentRequest()).toEqual(defaults);
  });

  it("applies the shared-provider defaults for an empty request", () => {
    expect(normalizeCreateDeploymentRequest({})).toEqual(defaults);
  });

  it("forwards explicit provider, region, config and markup", () => {
    expect(
      normalizeCreateDeploymentRequest({
        provider: "aws",
        region: "us-east-1",
        config: { size: "small" },
        billing_markup_pct: 0,
      }),
    ).toEqual({
      provider: "aws",
      region: "us-east-1",
      config: { size: "small" },
      billing_markup_pct: 0,
    });
  });

  it.each<RejectionCase>([
    // Only undefined triggers the default parameter; null must still be rejected.
    ["null", null, /Deployment create request must be a JSON object/],
    ["an array", [], /Deployment create request must be a JSON object/],
    ["an empty provider", { provider: "" }, /provider must be a non-empty string/],
    ["a numeric provider", { provider: 5 }, /provider must be a non-empty string/],
    ["a blank region", { region: "  " }, /region must be a non-empty string/],
    [
      "a NaN billing_markup_pct",
      { billing_markup_pct: Number.NaN },
      /billing_markup_pct must be a finite number/,
    ],
    [
      "a string billing_markup_pct",
      { billing_markup_pct: "20" },
      /billing_markup_pct must be a finite number/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(
      () => normalizeCreateDeploymentRequest(payload as CreateDeploymentRequest),
      fragment,
    );
  });
});

describe("assertDeploymentDeleteResponse", () => {
  it("returns the payload unchanged", () => {
    const payload = { status: "deleted", deployment_id: "dep-1" };
    expect(assertDeploymentDeleteResponse(payload)).toBe(payload);
  });

  it.each<RejectionCase>([
    ["an array", [], /Deployment delete response must be a JSON object/],
    [
      "an empty status",
      { status: "", deployment_id: "dep-1" },
      /Deployment delete response missing status/,
    ],
    [
      "a missing deployment_id",
      { status: "deleted" },
      /Deployment delete response missing deployment_id/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeploymentDeleteResponse(payload), fragment);
  });
});

describe("assertDeploymentCostResponse", () => {
  const cost = {
    deployment_id: "dep-1",
    provider: "aws",
    region: "us-east-1",
    year: 2026,
    month: 9,
    cost_usd_month: 10,
    billable_cost_usd_month: 12,
    billing_markup_pct: 20,
  };

  it("returns the payload unchanged", () => {
    expect(assertDeploymentCostResponse(cost)).toBe(cost);
  });

  it.each<RejectionCase>([
    ["an array", [], /Deployment cost response must be a JSON object/],
    [
      "an empty deployment_id",
      { ...cost, deployment_id: "" },
      /Deployment cost response missing deployment_id/,
    ],
    ["a numeric provider", { ...cost, provider: 1 }, /Deployment cost response missing provider/],
    ["a missing region", { ...cost, region: undefined }, /Deployment cost response missing region/],
    ["a fractional year", { ...cost, year: 2026.5 }, /Deployment cost response missing year/],
    ["a string month", { ...cost, month: "9" }, /Deployment cost response missing month/],
    ["a string cost_usd_month", { ...cost, cost_usd_month: "10" }, /missing cost_usd_month/],
    [
      "a NaN billable_cost_usd_month",
      { ...cost, billable_cost_usd_month: Number.NaN },
      /missing billable_cost_usd_month/,
    ],
    [
      "an infinite billing_markup_pct",
      { ...cost, billing_markup_pct: Number.NEGATIVE_INFINITY },
      /missing billing_markup_pct/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertDeploymentCostResponse(payload), fragment);
  });
});

describe("assertConnectorListResponse", () => {
  const connectors = [{ id: "c1" }, { id: "c2" }];

  it("wraps a first-page raw array in synthetic pagination", () => {
    expect(assertConnectorListResponse(connectors, 1)).toEqual({
      connectors,
      total: 2,
      page: 1,
      limit: 2,
      pages: 1,
    });
  });

  it("uses limit=1 for an empty first page", () => {
    expect(assertConnectorListResponse([], 1)).toEqual({
      connectors: [],
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("returns a paginated object unchanged", () => {
    const page = { connectors, total: 10, page: 2, limit: 2, pages: 5 };
    expect(assertConnectorListResponse(page, 2)).toBe(page);
  });

  it("rejects a raw array beyond the first page", () => {
    expectRejection(
      () => assertConnectorListResponse(connectors, 2),
      /returned a raw array for page=2; paginated responses are required beyond the first page/,
    );
  });

  it.each<[label: string, payload: unknown]>([
    ["null", null],
    ["a string", "connectors"],
    ["an object without connectors", { total: 0 }],
    ["a non-array connectors", { connectors: "c1" }],
  ])("rejects %s", (_label, payload) => {
    expectRejection(
      () => assertConnectorListResponse(payload, 1),
      /Connector list response must be a JSON array or paginated object/,
    );
  });
});

describe("assertDatasetListResponse", () => {
  const datasets = [{ dataset_id: "d1" }];

  it("wraps a first-page raw array in synthetic pagination", () => {
    expect(assertDatasetListResponse(datasets, 1)).toEqual({
      datasets,
      count: 1,
      total: 1,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("uses limit=1 for an empty first page", () => {
    expect(assertDatasetListResponse([], 1)).toEqual({
      datasets: [],
      count: 0,
      total: 0,
      page: 1,
      limit: 1,
      pages: 1,
    });
  });

  it("returns a paginated object unchanged", () => {
    const page = { datasets, count: 1, total: 4, page: 3, limit: 1, pages: 4 };
    expect(assertDatasetListResponse(page, 3)).toBe(page);
  });

  it("rejects a raw array beyond the first page", () => {
    expectRejection(
      () => assertDatasetListResponse(datasets, 3),
      /returned a raw array for page=3; paginated responses are required beyond the first page/,
    );
  });

  it.each<[label: string, payload: unknown]>([
    ["null", null],
    ["a number", 1],
    ["an object without datasets", { count: 0 }],
    ["a non-array datasets", { datasets: {} }],
  ])("rejects %s", (_label, payload) => {
    expectRejection(
      () => assertDatasetListResponse(payload, 1),
      /Dataset list response must be a JSON array or paginated object/,
    );
  });
});

describe("assertDatasetSummaryResponse", () => {
  const summary = {
    dataset_id: "d1",
    name: "Orders",
    status: "ready",
    source_names: ["orders"],
    column_count: 12,
    query_hints: ["revenue by month"],
  };

  it("returns the payload unchanged", () => {
    expect(assertDatasetSummaryResponse(summary)).toBe(summary);
  });

  it.each<[label: string, payload: unknown]>([
    ["null", null],
    ["an array", []],
    ["a missing dataset_id", { ...summary, dataset_id: undefined }],
    ["a numeric name", { ...summary, name: 1 }],
    ["a null status", { ...summary, status: null }],
    ["a string source_names", { ...summary, source_names: "orders" }],
    ["a fractional column_count", { ...summary, column_count: 1.5 }],
    ["a missing query_hints", { ...summary, query_hints: undefined }],
  ])("rejects %s", (_label, payload) => {
    expectRejection(
      () => assertDatasetSummaryResponse(payload),
      /Dataset summary response must be a JSON object with the required discovery fields/,
    );
  });
});

describe("normalizeValidationPath", () => {
  it.each<[context: string, expected: string]>([
    ["Algenta contract response.plan_limits.free", "plan_limits.free"],
    ["Algenta runtime manifest response.modules[0].name", "modules.0.name"],
    ["Algenta runtime admin modules response.modules[12]", "modules.12"],
    ["Algenta runtime admin benchmarks response.classes[1].code", "classes.1.code"],
    ["Algenta runtime release validation response.conditions[0]", "conditions.0"],
    ["Unprefixed context[3].items[4]", "Unprefixed context.3.items.4"],
    // Only the first matching prefix is stripped.
    [
      "Algenta contract response.Algenta runtime manifest response.x",
      "Algenta runtime manifest response.x",
    ],
  ])("normalizes %j", (context, expected) => {
    expect(normalizeValidationPath(context)).toBe(expected);
  });
});

describe("buildStructuredValidationError", () => {
  it("builds a DecisionEngineError carrying the normalized path in its details", () => {
    const error = buildStructuredValidationError(
      "Algenta contract response.limits[0].plan",
      "plan is bad",
      "string_type",
    );
    const validationError = { path: "limits.0.plan", message: "plan is bad", type: "string_type" };
    expect(error).toBeInstanceOf(DecisionEngineError);
    expect(error.message).toBe("plan is bad");
    expect(error.statusCode).toBe(0);
    expect(error.errorCode).toBe("invalid_payload_fragment");
    expect(error.responseBody).toEqual({
      error: {
        code: "invalid_payload_fragment",
        details: { cause: "limits.0.plan", validation_errors: [validationError] },
      },
    });
    expect(error.details).toEqual({ cause: "limits.0.plan", validation_errors: [validationError] });
    expect(error.validationErrors).toEqual([validationError]);
  });
});

describe("primitive structured validators", () => {
  it.each<
    [
      label: string,
      run: (value: unknown) => unknown,
      accepted: unknown,
      rejected: unknown,
      fragment: RegExp,
      type: string,
    ]
  >([
    [
      "assertJsonObject",
      (value) => assertJsonObject(value, "ctx.field"),
      { a: 1 },
      [],
      /ctx\.field must be a JSON object/,
      "model_type",
    ],
    [
      "assertNonEmptyString",
      (value) => assertNonEmptyString(value, "ctx.field"),
      "ok",
      "  ",
      /ctx\.field must be a non-empty string/,
      "string_type",
    ],
    [
      "assertFiniteNumber",
      (value) => assertFiniteNumber(value, "ctx.field"),
      1.5,
      Number.POSITIVE_INFINITY,
      /ctx\.field must be a finite number/,
      "finite_number",
    ],
    [
      "assertInteger",
      (value) => assertInteger(value, "ctx.field"),
      3,
      3.5,
      /ctx\.field must be an integer/,
      "integer_type",
    ],
    [
      "assertBoolean",
      (value) => assertBoolean(value, "ctx.field"),
      false,
      "false",
      /ctx\.field must be a boolean/,
      "bool_type",
    ],
    [
      "assertArray",
      (value) => assertArray(value, "ctx.field"),
      [1],
      { length: 1 },
      /ctx\.field must be a JSON array/,
      "array_type",
    ],
  ])(
    "%s returns the accepted value and raises a typed structured error",
    (_label, run, accepted, rejected, fragment, type) => {
      expect(run(accepted)).toEqual(accepted);
      const error = captureError(() => run(rejected));
      expect(error.message).toMatch(fragment);
      expect(error.errorCode).toBe("invalid_payload_fragment");
      expect(error.validationErrors).toEqual([{ path: "ctx.field", message: error.message, type }]);
    },
  );
});

describe("assertEnumValue", () => {
  const allowed = ["a", "b"] as const;

  it("returns an allowed value", () => {
    expect(assertEnumValue("b", allowed, "ctx.field")).toBe("b");
  });

  it("rejects a non-string with the string_type error", () => {
    const error = captureError(() => assertEnumValue("", allowed, "ctx.field"));
    expect(error.message).toMatch(/ctx\.field must be a non-empty string/);
    expect(error.validationErrors[0]?.type).toBe("string_type");
  });

  it("rejects an unsupported value with the enum error", () => {
    const error = captureError(() => assertEnumValue("zzz", allowed, "ctx.field"));
    expect(error.message).toMatch(/ctx\.field has unsupported value 'zzz'/);
    expect(error.validationErrors).toEqual([
      { path: "ctx.field", message: error.message, type: "enum" },
    ]);
  });
});

describe("assertEnumArray", () => {
  const allowed = ["a", "b"] as const;

  it("returns the validated entries", () => {
    expect(assertEnumArray(["a", "b", "a"], allowed, "ctx.field")).toEqual(["a", "b", "a"]);
  });

  it("rejects a non-array", () => {
    expectRejection(
      () => assertEnumArray("a", allowed, "ctx.field"),
      /ctx\.field must be a JSON array/,
    );
  });

  it("reports the offending index in the path", () => {
    const error = captureError(() => assertEnumArray(["a", "c"], allowed, "ctx.field"));
    expect(error.message).toMatch(/ctx\.field\[1\] has unsupported value 'c'/);
    expect(error.validationErrors[0]?.path).toBe("ctx.field.1");
  });
});

describe("assertUniqueRuntimeValues", () => {
  it("accepts unique values", () => {
    expect(assertUniqueRuntimeValues(["a", "b", "c"], "ctx.field")).toBeUndefined();
  });

  it("lists each duplicate once, in first-repeat order", () => {
    const error = captureError(() =>
      assertUniqueRuntimeValues(["a", "b", "a", "a", "b"], "ctx.field"),
    );
    expect(error.message).toBe("ctx.field must be unique; duplicate entries: a, b");
    expect(error.validationErrors).toEqual([
      { path: "ctx.field", message: error.message, type: "value_error" },
    ]);
  });
});

describe("assertUniqueRuntimeObjectField", () => {
  it("accepts entries with unique field values", () => {
    expect(
      assertUniqueRuntimeObjectField([{ code: "B1" }, { code: "B2" }], "code", "ctx.list"),
    ).toBeUndefined();
  });

  it("rejects duplicate field values", () => {
    expectRejection(
      () => assertUniqueRuntimeObjectField([{ code: "B1" }, { code: "B1" }], "code", "ctx.list"),
      /ctx\.list must be unique; duplicate entries: B1/,
    );
  });

  it("rejects a non-object entry with its index in the path", () => {
    const error = captureError(() =>
      assertUniqueRuntimeObjectField([{ code: "B1" }, "B2"], "code", "ctx.list"),
    );
    expect(error.message).toMatch(/ctx\.list\[1\] must be a JSON object/);
    expect(error.validationErrors[0]?.path).toBe("ctx.list.1");
  });
});

describe("assertEnumKeyedCountRecord", () => {
  const keys = ["a", "b", "c"] as const;

  it("returns the record when every key is allowed and every count is an integer", () => {
    const record = { a: 1, b: 0 };
    expect(assertEnumKeyedCountRecord(record, keys, "ctx.counts")).toBe(record);
  });

  it("rejects a non-object", () => {
    expectRejection(
      () => assertEnumKeyedCountRecord([], keys, "ctx.counts"),
      /ctx\.counts must be a JSON object/,
    );
  });

  it("rejects an unsupported key with the extra_forbidden error", () => {
    const error = captureError(() =>
      assertEnumKeyedCountRecord({ a: 1, z: 2 }, keys, "ctx.counts"),
    );
    expect(error.message).toMatch(/ctx\.counts has unsupported key 'z'/);
    expect(error.validationErrors).toEqual([
      { path: "ctx.counts.z", message: error.message, type: "extra_forbidden" },
    ]);
  });

  it("rejects a non-integer count", () => {
    expectRejection(
      () => assertEnumKeyedCountRecord({ a: 1.5 }, keys, "ctx.counts"),
      /ctx\.counts\.a must be an integer/,
    );
  });
});

describe("assertEnumKeyedEnumRecord", () => {
  const keys = ["a", "b"] as const;
  const values = ["x", "y"] as const;

  it("accepts allowed keys mapped to allowed values", () => {
    expect(assertEnumKeyedEnumRecord({ a: "x", b: "y" }, keys, values, "ctx.map")).toBeUndefined();
  });

  it("rejects a non-object", () => {
    expectRejection(
      () => assertEnumKeyedEnumRecord(null, keys, values, "ctx.map"),
      /ctx\.map must be a JSON object/,
    );
  });

  it("rejects an unsupported key", () => {
    const error = captureError(() =>
      assertEnumKeyedEnumRecord({ z: "x" }, keys, values, "ctx.map"),
    );
    expect(error.message).toMatch(/ctx\.map has unsupported key 'z'/);
    expect(error.validationErrors[0]).toEqual({
      path: "ctx.map.z",
      message: error.message,
      type: "extra_forbidden",
    });
  });

  it("rejects an unsupported value", () => {
    expectRejection(
      () => assertEnumKeyedEnumRecord({ a: "nope" }, keys, values, "ctx.map"),
      /ctx\.map\.a has unsupported value 'nope'/,
    );
  });

  it("rejects a non-string value", () => {
    expectRejection(
      () => assertEnumKeyedEnumRecord({ a: 5 }, keys, values, "ctx.map"),
      /ctx\.map\.a must be a non-empty string/,
    );
  });
});

describe("assertRuntimeSignature", () => {
  const signature = {
    algorithm: "hmac-sha256",
    key_id: "runtime-manifest-signing-v1",
    digest_hex: "c".repeat(64),
    signature_hex: "d".repeat(64),
    scope: "control_plane_hmac_v1",
  };

  it("accepts a well-formed signature", () => {
    expect(assertRuntimeSignature(signature, "manifest.signature")).toBeUndefined();
  });

  it.each<RejectionCase>([
    ["null", null, /manifest\.signature must be a JSON object/],
    [
      "an unsupported algorithm",
      { ...signature, algorithm: "rsa" },
      /manifest\.signature\.algorithm has unsupported value 'rsa'/,
    ],
    [
      "an empty key_id",
      { ...signature, key_id: "" },
      /manifest\.signature\.key_id must be a non-empty string/,
    ],
    [
      "a numeric digest_hex",
      { ...signature, digest_hex: 5 },
      /manifest\.signature\.digest_hex must be a non-empty string/,
    ],
    [
      "a blank signature_hex",
      { ...signature, signature_hex: " " },
      /manifest\.signature\.signature_hex must be a non-empty string/,
    ],
    [
      "an unsupported scope",
      { ...signature, scope: "other" },
      /manifest\.signature\.scope has unsupported value 'other'/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertRuntimeSignature(payload, "manifest.signature"), fragment);
  });
});

describe("assertRuntimeSnapshotReference", () => {
  const snapshot = {
    snapshot_id: "policy-v1",
    sha256: "a".repeat(64),
    source: "governance/policies/current.json",
    description: "Signed policy snapshot",
  };

  it("accepts a well-formed snapshot reference", () => {
    expect(assertRuntimeSnapshotReference(snapshot, "manifest.policy_snapshot")).toBeUndefined();
  });

  it.each<RejectionCase>([
    ["an array", [], /manifest\.policy_snapshot must be a JSON object/],
    [
      "an empty snapshot_id",
      { ...snapshot, snapshot_id: "" },
      /policy_snapshot\.snapshot_id must be a non-empty string/,
    ],
    [
      "a missing sha256",
      { ...snapshot, sha256: undefined },
      /policy_snapshot\.sha256 must be a non-empty string/,
    ],
    [
      "a numeric source",
      { ...snapshot, source: 1 },
      /policy_snapshot\.source must be a non-empty string/,
    ],
    [
      "a blank description",
      { ...snapshot, description: "  " },
      /policy_snapshot\.description must be a non-empty string/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(
      () => assertRuntimeSnapshotReference(payload, "manifest.policy_snapshot"),
      fragment,
    );
  });
});

describe("assertRuntimeArtifactReference", () => {
  const artifact = {
    kind: "compiled_mojo_binary",
    path: "mojo_build/bpe_tokenizer",
    sha256: "e".repeat(64),
    size_bytes: 4096,
  };

  it("accepts a well-formed artifact reference", () => {
    expect(
      assertRuntimeArtifactReference(artifact, "manifest.compiled_artifacts[0]"),
    ).toBeUndefined();
  });

  it.each<RejectionCase>([
    ["a string", "artifact", /compiled_artifacts\[0\] must be a JSON object/],
    [
      "an unsupported kind",
      { ...artifact, kind: "zip" },
      /compiled_artifacts\[0\]\.kind has unsupported value 'zip'/,
    ],
    [
      "an empty path",
      { ...artifact, path: "" },
      /compiled_artifacts\[0\]\.path must be a non-empty string/,
    ],
    [
      "a numeric sha256",
      { ...artifact, sha256: 1 },
      /compiled_artifacts\[0\]\.sha256 must be a non-empty string/,
    ],
    [
      "a fractional size_bytes",
      { ...artifact, size_bytes: 1.5 },
      /compiled_artifacts\[0\]\.size_bytes must be an integer/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(
      () => assertRuntimeArtifactReference(payload, "manifest.compiled_artifacts[0]"),
      fragment,
    );
  });
});

describe("assertRuntimeShippingContractSummary", () => {
  const contract = {
    module_count: 1,
    function_count: 2,
    runtime_core_layer: "mojo_llm_runtime_core",
    benchmark_discovery_rule: SHIPPING_BENCHMARK_DISCOVERY_RULE,
  };

  it("returns the module and function counts", () => {
    expect(assertRuntimeShippingContractSummary(contract, "manifest.shipping_contract")).toEqual({
      moduleCount: 1,
      functionCount: 2,
    });
  });

  it.each<RejectionCase>([
    ["null", null, /shipping_contract must be a JSON object/],
    [
      "a string module_count",
      { ...contract, module_count: "1" },
      /shipping_contract\.module_count must be an integer/,
    ],
    [
      "a fractional function_count",
      { ...contract, function_count: 2.5 },
      /shipping_contract\.function_count must be an integer/,
    ],
    [
      "an unsupported runtime_core_layer",
      { ...contract, runtime_core_layer: "other" },
      /runtime_core_layer has unsupported value 'other'/,
    ],
    [
      "an unsupported benchmark_discovery_rule",
      { ...contract, benchmark_discovery_rule: "other" },
      /benchmark_discovery_rule has unsupported value 'other'/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(
      () => assertRuntimeShippingContractSummary(payload, "manifest.shipping_contract"),
      fragment,
    );
  });
});

describe("assertRuntimeBenchmarkDiscoveryLane", () => {
  const context = "manifest.benchmark_discovery_lane";
  const lane = (overrides: Record<string, unknown> = {}) =>
    makeBenchmarkDiscoveryLanePayload(overrides);

  it("returns the shipping counts and the discovered import paths", () => {
    expect(assertRuntimeBenchmarkDiscoveryLane(lane(), context)).toEqual({
      shippingManifestModules: 1,
      shippingManifestFunctions: 2,
      discoveredSourceImportPaths: ["bpe_tokenizer", "embeddings"],
    });
  });

  it("reports a non-array inventory with the list type error", () => {
    const error = captureError(() =>
      assertRuntimeBenchmarkDiscoveryLane(
        lane({ discovered_source_inventory: "bpe_tokenizer" }),
        context,
      ),
    );
    expect(error.message).toMatch(/discovered_source_inventory must be a JSON array/);
    expect(error.validationErrors).toEqual([
      {
        path: "manifest.benchmark_discovery_lane.discovered_source_inventory",
        message: error.message,
        type: "type_error.list",
      },
    ]);
  });

  it("reports a count mismatch as a value_error on the count field", () => {
    const error = captureError(() =>
      assertRuntimeBenchmarkDiscoveryLane(lane({ discovered_source_modules: 3 }), context),
    );
    expect(error.errorCode).toBe("invalid_payload_fragment");
    expect(error.validationErrors[0]).toEqual({
      path: "manifest.benchmark_discovery_lane.discovered_source_modules",
      message: error.message,
      type: "value_error",
    });
  });

  const inventory = makeDiscoveredSourceInventory();
  it.each<RejectionCase>([
    ["a string", "lane", /benchmark_discovery_lane must be a JSON object/],
    [
      "a string discovered_source_modules",
      lane({ discovered_source_modules: "2" }),
      /discovered_source_modules must be an integer/,
    ],
    [
      "a fractional discovered_public_functions",
      lane({ discovered_public_functions: 4.5 }),
      /discovered_public_functions must be an integer/,
    ],
    [
      "a non-object inventory entry",
      lane({ discovered_source_inventory: [5] }),
      /discovered_source_inventory\[0\] must be a JSON object/,
    ],
    [
      "an inventory entry with an empty import_path",
      lane({ discovered_source_inventory: [{ ...inventory[0], import_path: "" }] }),
      /discovered_source_inventory\[0\]\.import_path must be a non-empty string/,
    ],
    [
      "an inventory entry with a fractional public_function_count",
      lane({ discovered_source_inventory: [{ ...inventory[0], public_function_count: 1.5 }] }),
      /discovered_source_inventory\[0\]\.public_function_count must be an integer/,
    ],
    [
      "an inventory entry with zero public functions",
      lane({
        discovered_source_inventory: [{ ...inventory[0], public_function_count: 0 }, inventory[1]],
      }),
      /discovered_source_inventory\[0\]\.public_function_count must be greater than 0/,
    ],
    [
      "a duplicate import_path",
      lane({ discovered_source_inventory: [inventory[0], inventory[0]] }),
      /discovered_source_inventory must be unique; duplicate entries: bpe_tokenizer/,
    ],
    [
      "an unsorted inventory",
      lane({ discovered_source_inventory: [inventory[1], inventory[0]] }),
      /discovered_source_inventory must be sorted by import_path/,
    ],
    [
      "a module count that disagrees with the inventory",
      lane({ discovered_source_modules: 3 }),
      /discovered_source_modules must equal the number of discovered_source_inventory entries/,
    ],
    [
      "a function total that disagrees with the inventory",
      lane({ discovered_public_functions: 5 }),
      /discovered_public_functions must equal the total discovered_source_inventory public_function_count/,
    ],
    [
      "a string shipping_manifest_modules",
      lane({ shipping_manifest_modules: "1" }),
      /shipping_manifest_modules must be an integer/,
    ],
    [
      "a null shipping_manifest_functions",
      lane({ shipping_manifest_functions: null }),
      /shipping_manifest_functions must be an integer/,
    ],
    [
      "an unsupported non_shipping_rule",
      lane({ non_shipping_rule: "anything goes" }),
      /non_shipping_rule has unsupported value/,
    ],
    [
      "more shipping modules than discovered",
      lane({ shipping_manifest_modules: 3, non_shipping_rule: NON_SHIPPING_RULE }),
      /shipping_manifest_modules cannot exceed manifest\.benchmark_discovery_lane\.discovered_source_modules/,
    ],
    [
      "more shipping functions than discovered",
      lane({ shipping_manifest_functions: 5 }),
      /shipping_manifest_functions cannot exceed manifest\.benchmark_discovery_lane\.discovered_public_functions/,
    ],
  ])("rejects %s", (_label, payload, fragment) => {
    expectRejection(() => assertRuntimeBenchmarkDiscoveryLane(payload, context), fragment);
  });
});
