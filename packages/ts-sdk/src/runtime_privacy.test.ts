// SPDX-License-Identifier: Apache-2.0
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  RuntimeEgressPolicyDeniedError,
  validatedControlPlaneBaseUrl,
  validatedRuntimeEgressUrl,
} from "./runtime_privacy.js";

const ORIGINAL_ENV = { ...process.env };

function runtimeTempDir(): string {
  return mkdtempSync(join(tmpdir(), "algenta-ts-runtime-privacy-"));
}

function ledgerEvents(runtimeDir: string): Array<Record<string, unknown>> {
  const path = join(runtimeDir, "history.jsonl");
  return readFileSync(path, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

beforeEach(() => {
  delete process.env.ALGENTA_RUNTIME_DIR;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK;
  delete process.env.ALGENTA_EGRESS_ALLOWLIST;
  delete process.env.ALGENTA_CONTROL_PLANE_URL;
});

afterEach(() => {
  const runtimeDir = process.env.ALGENTA_RUNTIME_DIR;
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
  if (runtimeDir && runtimeDir.includes("algenta-ts-runtime-privacy-")) {
    rmSync(runtimeDir, { force: true, recursive: true });
  }
});

describe("runtime privacy policy", () => {
  it("records allowlisted operator-service egress with sanitized metadata", () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_EGRESS_ALLOWLIST = "control.customer.internal";

    expect(
      validatedRuntimeEgressUrl("https://control.customer.internal", {
        surface: "credits_refresh",
        fieldName: "ALGENTA_CONTROL_PLANE_URL",
        explicitConfigured: true,
        egressClass: "operator_service",
      }),
    ).toBe("https://control.customer.internal");

    const [event] = ledgerEvents(runtimeDir);
    expect(event.action).toBe("privacy_egress");
    expect(event.status).toBe("allow");
    expect(event.target).toBe("internal-host");
    expect(event.success).toBe(true);
    expect(event.error).toBeNull();
    expect(event.details).toMatchObject({
      surface: "credits_refresh",
      egress_class: "operator_service",
      decision: "allow",
      reason: "destination_allowlisted",
      deployment_mode: "self_hosted",
      service_name: "runtime",
      destination_host_redacted: "internal-host",
    });
  });

  it("records denied operator-service egress when the destination is not allowlisted", () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";

    expect(() =>
      validatedRuntimeEgressUrl("https://control.customer.com", {
        surface: "device_heartbeat",
        fieldName: "ALGENTA_CONTROL_PLANE_URL",
        explicitConfigured: true,
        egressClass: "operator_service",
      }),
    ).toThrowError(RuntimeEgressPolicyDeniedError);

    const [event] = ledgerEvents(runtimeDir);
    expect(event.action).toBe("privacy_egress");
    expect(event.status).toBe("deny");
    expect(event.target).toBe("*.customer.com");
    expect(event.success).toBe(false);
    expect(event.error).toBe("destination_not_allowlisted");
    expect(event.details).toMatchObject({
      surface: "device_heartbeat",
      egress_class: "operator_service",
      decision: "deny",
      reason: "destination_not_allowlisted",
      deployment_mode: "self_hosted",
      service_name: "runtime",
      destination_host_redacted: "*.customer.com",
    });
  });

  it("rejects Algenta-owned control-plane urls when cloud is disabled", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://api.algenta.ai";

    expect(() =>
      validatedControlPlaneBaseUrl(undefined, {
        surface: "device_register",
        record: false,
      }),
    ).toThrowError(RuntimeEgressPolicyDeniedError);
  });
});
