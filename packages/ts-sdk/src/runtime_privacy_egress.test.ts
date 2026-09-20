// SPDX-License-Identifier: Apache-2.0
/**
 * Egress policy evaluation in runtime_privacy.ts: destination classification,
 * per-class allow/deny decisions under each deployment profile, host redaction,
 * allowlist matching and the ledger record. runtime_privacy.test.ts covers the
 * operator-service allowlist flow end to end; this file covers the remaining
 * branches of the pure evaluation functions.
 */
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { PRIVATE_HOST_SUFFIXES, VENDOR_TELEMETRY_HOSTS } from "./contract.js";
import {
  RuntimeEgressPolicyDeniedError,
  cloudDisabled,
  deploymentMode,
  enforceRuntimeEgress,
  evaluateRuntimeEgress,
  meteringMode,
  privateProfile,
  recordRuntimeEgressEvent,
  requireLocalLicense,
  resolveControlPlaneBaseUrl,
  telemetryMode,
  validatedControlPlaneBaseUrl,
  validatedRuntimeEgressUrl,
} from "./runtime_privacy.js";

const ORIGINAL_ENV = { ...process.env };
const PRIVACY_ENV_KEYS = [
  "ALGENTA_RUNTIME_DIR",
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_DISABLE_TELEMETRY",
  "ALGENTA_ALLOW_OUTBOUND_NETWORK",
  "ALGENTA_REQUIRE_LOCAL_LICENSE",
  "ALGENTA_TELEMETRY_MODE",
  "ALGENTA_METERING_MODE",
  "ALGENTA_EGRESS_ALLOWLIST",
  "ALGENTA_CONTROL_PLANE_URL",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
];
const tempDirs: string[] = [];

function runtimeDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "algenta-ts-egress-"));
  tempDirs.push(dir);
  process.env.ALGENTA_RUNTIME_DIR = dir;
  return dir;
}

function ledger(dir: string): Array<Record<string, unknown>> {
  return readFileSync(join(dir, "history.jsonl"), "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map(line => JSON.parse(line) as Record<string, unknown>);
}

beforeEach(() => {
  for (const key of PRIVACY_ENV_KEYS) delete process.env[key];
});

afterEach(() => {
  for (const dir of tempDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("deployment profile switches", () => {
  it("derives the profile flags from the environment with sane defaults", () => {
    expect(deploymentMode()).toBe("saas");
    expect(privateProfile()).toBe(false);
    expect(cloudDisabled()).toBe(false);
    expect(requireLocalLicense()).toBe(false);
    expect(telemetryMode()).toBe("control_plane_sync");
    expect(meteringMode()).toBe("control_plane_sync");

    process.env.ALGENTA_DEPLOYMENT_MODE = "  ";
    expect(deploymentMode()).toBe("saas");

    process.env.ALGENTA_DEPLOYMENT_MODE = " Self_Hosted ";
    expect(deploymentMode()).toBe("self_hosted");
    expect(privateProfile()).toBe(true);
    expect(cloudDisabled()).toBe(true);
    expect(telemetryMode()).toBe("local_audit");
    expect(meteringMode()).toBe("local_audit");
    expect(requireLocalLicense()).toBe(false);

    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    expect(requireLocalLicense()).toBe(true);
  });

  it("honours explicit boolean overrides and ignores unparseable ones", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "off";
    expect(cloudDisabled()).toBe(false);
    process.env.ALGENTA_DISABLE_CLOUD = "maybe";
    expect(cloudDisabled()).toBe(true);
    process.env.ALGENTA_REQUIRE_LOCAL_LICENSE = "yes";
    expect(requireLocalLicense()).toBe(true);
    process.env.ALGENTA_DISABLE_TELEMETRY = "0";
    expect(telemetryMode()).toBe("control_plane_sync");
    process.env.ALGENTA_TELEMETRY_MODE = " Disabled ";
    expect(telemetryMode()).toBe("disabled");
    process.env.ALGENTA_METERING_MODE = "local_audit";
    expect(meteringMode()).toBe("local_audit");
    process.env.ALGENTA_METERING_MODE = "bogus";
    expect(meteringMode()).toBe("local_audit");
  });

  it("saas telemetry is disabled outright when the kill switch is set", () => {
    process.env.ALGENTA_DISABLE_TELEMETRY = "true";
    expect(telemetryMode()).toBe("disabled");
  });

  it("resolves the control-plane base URL from the first configured source", () => {
    process.env.DE_BASE_URL = "https://legacy.customer.internal///";
    expect(resolveControlPlaneBaseUrl("https://explicit.customer.internal")).toBe(
      "https://legacy.customer.internal",
    );
    process.env.ALGENTA_BASE_URL = "https://base.customer.internal";
    expect(resolveControlPlaneBaseUrl()).toBe("https://base.customer.internal");
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://control.customer.internal/";
    expect(resolveControlPlaneBaseUrl()).toBe("https://control.customer.internal");
    delete process.env.ALGENTA_CONTROL_PLANE_URL;
    delete process.env.ALGENTA_BASE_URL;
    delete process.env.DE_BASE_URL;
    expect(resolveControlPlaneBaseUrl("   ")).toMatch(/^https:\/\//);
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    expect(resolveControlPlaneBaseUrl()).toBe("");
  });
});

describe("evaluateRuntimeEgress classification", () => {
  it("allows Algenta cloud in saas and denies it once cloud or outbound network is off", () => {
    const allowed = evaluateRuntimeEgress("api.algenta.ai", { surface: "device_register" });
    expect(allowed).toMatchObject({
      surface: "device_register",
      egressClass: "algenta_cloud",
      decision: "allow",
      reason: "algenta_cloud_enabled",
      destinationHostRedacted: "api.algenta.ai",
      deploymentMode: "saas",
      serviceName: "runtime",
      requestId: null,
    });
    expect(allowed.destinationHostHash).toMatch(/^[0-9a-f]{64}$/);

    process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "false";
    expect(
      evaluateRuntimeEgress("https://api.algenta.ai/v1", { surface: "s", requestId: "req_1" }),
    ).toMatchObject({ decision: "deny", reason: "algenta_cloud_disabled", requestId: "req_1" });
  });

  it("recognizes the registry's vendor telemetry hosts exactly", () => {
    const exactHost = VENDOR_TELEMETRY_HOSTS.find(host => !host.endsWith(".sentry.io"));
    if (!exactHost) throw new Error("the contract must list a non-sentry telemetry host");
    expect(evaluateRuntimeEgress(exactHost, { surface: "telemetry" })).toMatchObject({
      egressClass: "vendor_telemetry",
      destinationHostRedacted: exactHost,
    });
  });

  it("gates vendor telemetry on telemetry mode and outbound network", () => {
    const enabled = evaluateRuntimeEgress("o1234.ingest.sentry.io", { surface: "telemetry" });
    expect(enabled).toMatchObject({
      egressClass: "vendor_telemetry",
      decision: "allow",
      reason: "vendor_telemetry_enabled",
      destinationHostRedacted: "o1234.ingest.sentry.io",
    });

    process.env.ALGENTA_DISABLE_TELEMETRY = "1";
    expect(evaluateRuntimeEgress("o1234.ingest.sentry.io", { surface: "telemetry" })).toMatchObject({
      decision: "deny",
      reason: "vendor_telemetry_disabled",
    });
    delete process.env.ALGENTA_DISABLE_TELEMETRY;
    process.env.ALGENTA_TELEMETRY_MODE = "local_audit";
    expect(evaluateRuntimeEgress("o1234.ingest.sentry.io", { surface: "telemetry" }).decision).toBe(
      "deny",
    );
    delete process.env.ALGENTA_TELEMETRY_MODE;
    process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "no";
    expect(evaluateRuntimeEgress("o1234.ingest.sentry.io", { surface: "telemetry" }).decision).toBe(
      "deny",
    );
  });

  it("treats explicitly configured destinations as customer connectors", () => {
    const open = evaluateRuntimeEgress("warehouse.example.com:5432", {
      surface: "connector",
      explicitConfigured: true,
    });
    expect(open).toMatchObject({
      egressClass: "customer_connector",
      decision: "allow",
      reason: "outbound_network_enabled",
      destinationHostRedacted: "*.example.com",
    });

    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    const closed = evaluateRuntimeEgress("warehouse.example.com:5432", {
      surface: "connector",
      explicitConfigured: true,
    });
    expect(closed).toMatchObject({ decision: "deny", reason: "destination_not_allowlisted" });

    // A non-explicit destination never consults the allowlist, even when it would match.
    process.env.ALGENTA_EGRESS_ALLOWLIST = "warehouse.example.com";
    expect(
      evaluateRuntimeEgress("warehouse.example.com", {
        surface: "connector",
        egressClass: "operator_service",
      }),
    ).toMatchObject({ egressClass: "operator_service", decision: "deny" });
  });

  it.each([
    ["an exact host", "warehouse.example.com", "warehouse.example.com:5432"],
    ["a wildcard suffix", " *.example.com ", "warehouse.example.com"],
    ["a host:port pair", "warehouse.example.com:5432", "warehouse.example.com:5432"],
    ["a later entry after blanks", " , ,warehouse.example.com", "warehouse.example.com"],
  ])("matches the allowlist by %s in a private profile", (_label, allowlist, destination) => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_EGRESS_ALLOWLIST = allowlist;
    expect(
      evaluateRuntimeEgress(destination, { surface: "connector", explicitConfigured: true }),
    ).toMatchObject({ decision: "allow", reason: "destination_allowlisted" });
  });

  it.each([
    ["a wildcard for another domain", "*.other.com"],
    ["a different port", "warehouse.example.com:5433"],
    ["a different host", "other.example.com"],
  ])("does not match the allowlist by %s", (_label, allowlist) => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_EGRESS_ALLOWLIST = allowlist;
    expect(
      evaluateRuntimeEgress("warehouse.example.com:5432", {
        surface: "connector",
        explicitConfigured: true,
      }).reason,
    ).toBe("destination_not_allowlisted");
  });

  it("classifies unknown destinations as undeclared public egress", () => {
    // A public IPv4 literal is not private and not vendor-owned either.
    expect(evaluateRuntimeEgress("8.8.8.8", { surface: "fetch" })).toMatchObject({
      egressClass: "undeclared_public",
      decision: "allow",
    });
    expect(evaluateRuntimeEgress("https://example.org/path", { surface: "fetch" })).toMatchObject({
      egressClass: "undeclared_public",
      decision: "allow",
      reason: "undeclared_public_egress_enabled",
      destinationHostRedacted: "*.example.org",
    });
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    expect(evaluateRuntimeEgress("example.org", { surface: "fetch" })).toMatchObject({
      decision: "deny",
      reason: "undeclared_public_egress_disabled",
      deploymentMode: "air_gapped",
    });
  });

  it("rejects destinations without a usable host", () => {
    expect(() => evaluateRuntimeEgress("http://", { surface: "s" })).toThrow(
      "Egress destination must include a valid host.",
    );
    // A scheme without an authority parses, but leaves the hostname empty.
    expect(() => evaluateRuntimeEgress("file:///etc/hosts", { surface: "s" })).toThrow(
      "Egress destination must include a valid host.",
    );
    expect(() => evaluateRuntimeEgress("::not a url::", { surface: "s" })).toThrow(
      "Egress destination must include a valid host.",
    );
  });
});

describe("destination redaction", () => {
  it.each([
    ["localhost", "localhost"],
    ["the IPv4 loopback", "127.0.0.1"],
    ["a 10/8 address", "10.1.2.3"],
    ["a 192.168/16 address", "192.168.0.10"],
    ["a 172.16/12 address", "172.20.0.1"],
    ["a link-local address", "169.254.1.1"],
    ["a multicast address", "224.0.0.1"],
    ["a .internal name", "db.internal"],
    ["a private suffix from the contract", `svc${PRIVATE_HOST_SUFFIXES[0]}`],
  ])("redacts %s as internal-host", (_label, destination) => {
    expect(evaluateRuntimeEgress(destination, { surface: "s" }).destinationHostRedacted).toBe(
      "internal-host",
    );
  });

  it("keeps only the registrable domain of public names and labels bare names", () => {
    expect(evaluateRuntimeEgress("intranet", { surface: "s" }).destinationHostRedacted).toBe(
      "public-host",
    );
    expect(
      evaluateRuntimeEgress("deep.sub.example.co.uk", { surface: "s" }).destinationHostRedacted,
    ).toBe("*.co.uk");
    expect(
      evaluateRuntimeEgress("edge.algenta.ai", { surface: "s" }).destinationHostRedacted,
    ).toBe("edge.algenta.ai");
  });
});

describe("egress enforcement and ledger", () => {
  it("records allow and deny decisions with the surface-derived task id", () => {
    const dir = runtimeDir();
    const allowed = evaluateRuntimeEgress("https://example.org", { surface: "fetch" });
    recordRuntimeEgressEvent(allowed);
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    recordRuntimeEgressEvent(
      evaluateRuntimeEgress("https://example.org", { surface: "fetch", requestId: "req_9" }),
    );

    const [first, second] = ledger(dir);
    expect(first).toMatchObject({
      task_id: `privacy_fetch_${allowed.destinationHostHash.slice(0, 16)}`,
      surface: "runtime",
      action: "privacy_egress",
      status: "allow",
      target: "*.example.org",
      request_id: null,
      success: true,
      error: null,
      sync_state: "local_only",
      details: { egress_class: "undeclared_public", reason: "undeclared_public_egress_enabled" },
    });
    expect(first.event_id).toMatch(/^evt_[0-9a-f]{32}$/);
    expect(second).toMatchObject({
      task_id: "req_9",
      status: "deny",
      success: false,
      error: "undeclared_public_egress_disabled",
      request_id: "req_9",
      details: { deployment_mode: "air_gapped", request_id: "req_9" },
    });
  });

  it("swallows ledger write failures", () => {
    // A regular file where a directory is expected makes mkdirSync fail with ENOTDIR.
    const dir = runtimeDir();
    writeFileSync(join(dir, "blocker"), "not a directory");
    process.env.ALGENTA_RUNTIME_DIR = join(dir, "blocker", "runtime");
    expect(() =>
      recordRuntimeEgressEvent(evaluateRuntimeEgress("example.org", { surface: "s" })),
    ).not.toThrow();
    expect(existsSync(join(dir, "blocker", "runtime"))).toBe(false);
  });

  it("enforceRuntimeEgress throws a typed error on deny and can skip the ledger", () => {
    const dir = runtimeDir();
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";

    let denied: unknown;
    try {
      enforceRuntimeEgress("example.org", { surface: "fetch", record: false });
    } catch (error) {
      denied = error;
    }
    expect(denied).toBeInstanceOf(RuntimeEgressPolicyDeniedError);
    expect((denied as RuntimeEgressPolicyDeniedError).message).toBe(
      "Egress blocked by privacy policy for surface 'fetch' (undeclared_public_egress_disabled).",
    );
    expect((denied as RuntimeEgressPolicyDeniedError).decision.decision).toBe("deny");
    expect(existsSync(join(dir, "history.jsonl"))).toBe(false);

    process.env.ALGENTA_EGRESS_ALLOWLIST = "example.org";
    const decision = enforceRuntimeEgress("example.org", {
      surface: "connector",
      explicitConfigured: true,
    });
    expect(decision.reason).toBe("destination_allowlisted");
    expect(ledger(dir)).toHaveLength(1);
  });

  it("validatedRuntimeEgressUrl insists on an absolute http(s) URL", () => {
    expect(() =>
      validatedRuntimeEgressUrl("example.org", { surface: "s", fieldName: "connector.url" }),
    ).toThrow("connector.url must use an absolute http(s) URL.");
    expect(() =>
      validatedRuntimeEgressUrl("ftp://example.org", { surface: "s", fieldName: "connector.url" }),
    ).toThrow("connector.url must use an absolute http(s) URL.");
    expect(
      validatedRuntimeEgressUrl("https://example.org/api//", {
        surface: "s",
        fieldName: "connector.url",
        record: false,
      }),
    ).toBe("https://example.org/api");
  });

  it("validatedControlPlaneBaseUrl fails closed without a configured URL", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    expect(() => validatedControlPlaneBaseUrl(undefined, { surface: "device_register" })).toThrow(
      "ALGENTA_CONTROL_PLANE_URL must be configured explicitly",
    );
    process.env.ALGENTA_EGRESS_ALLOWLIST = "control.customer.internal";
    expect(
      validatedControlPlaneBaseUrl("https://control.customer.internal/", {
        surface: "device_register",
        record: false,
      }),
    ).toBe("https://control.customer.internal");
  });
});
