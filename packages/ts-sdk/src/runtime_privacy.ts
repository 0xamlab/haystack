import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { isIP } from "node:net";
import { homedir } from "node:os";
import { join } from "node:path";

import {
  ALGENTA_OWNED_HOSTS,
  ALGENTA_OWNED_SUFFIXES,
  DEFAULT_BASE_URL,
  PRIVATE_HOST_SUFFIXES,
  VENDOR_TELEMETRY_HOSTS,
} from "./contract.js";

function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.charCodeAt(end - 1) === 47 /* '/' */) {
    end--;
  }
  return end === value.length ? value : value.slice(0, end);
}



export type RuntimeTelemetryMode = "disabled" | "local_audit" | "control_plane_sync";
export type RuntimeMeteringMode = "disabled" | "local_audit" | "control_plane_sync";
export type RuntimeEgressClass =
  | "algenta_cloud"
  | "vendor_telemetry"
  | "customer_connector"
  | "operator_service"
  | "undeclared_public";

export interface RuntimeEgressDecision {
  surface: string;
  egressClass: RuntimeEgressClass;
  decision: "allow" | "deny";
  reason: string;
  destinationHostHash: string;
  destinationHostRedacted: string;
  deploymentMode: string;
  serviceName: "runtime";
  requestId: string | null;
}

export class RuntimeEgressPolicyDeniedError extends Error {
  constructor(public readonly decision: RuntimeEgressDecision) {
    super(
      `Egress blocked by privacy policy for surface '${decision.surface}' (${decision.reason}).`,
    );
    this.name = "RuntimeEgressPolicyDeniedError";
  }
}

const PRIVATE_DEPLOYMENT_MODES = new Set(["self_hosted", "air_gapped"]);
const ALGENTA_OWNED_HOST_SET = new Set<string>(ALGENTA_OWNED_HOSTS);
const VENDOR_TELEMETRY_HOST_SET = new Set<string>(VENDOR_TELEMETRY_HOSTS);
const VALID_TELEMETRY_MODES = new Set(["disabled", "local_audit", "control_plane_sync"]);

interface RuntimeEgressTarget {
  host: string;
  normalized: string;
}

function runtimeEnv(): Record<string, string | undefined> {
  if (typeof process === "undefined" || !process.env) {
    return {};
  }
  return process.env;
}

function envTruthy(value: string | undefined): boolean | undefined {
  if (value === undefined) {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }
  return undefined;
}

function runtimeDirectory(): string {
  return runtimeEnv().ALGENTA_RUNTIME_DIR ?? join(homedir(), ".algenta", "runtime");
}

function ledgerPath(): string {
  return join(runtimeDirectory(), "history.jsonl");
}

export function deploymentMode(): string {
  const value = (runtimeEnv().ALGENTA_DEPLOYMENT_MODE ?? "saas").trim().toLowerCase();
  return value.length > 0 ? value : "saas";
}

export function privateProfile(): boolean {
  return PRIVATE_DEPLOYMENT_MODES.has(deploymentMode());
}

export function cloudDisabled(): boolean {
  const explicit = envTruthy(runtimeEnv().ALGENTA_DISABLE_CLOUD);
  return explicit ?? privateProfile();
}

function telemetryDisabled(): boolean {
  const explicit = envTruthy(runtimeEnv().ALGENTA_DISABLE_TELEMETRY);
  return explicit ?? privateProfile();
}

function outboundNetworkAllowed(): boolean {
  const explicit = envTruthy(runtimeEnv().ALGENTA_ALLOW_OUTBOUND_NETWORK);
  return explicit ?? !privateProfile();
}

export function requireLocalLicense(): boolean {
  const explicit = envTruthy(runtimeEnv().ALGENTA_REQUIRE_LOCAL_LICENSE);
  return explicit ?? deploymentMode() === "air_gapped";
}

export function telemetryMode(): RuntimeTelemetryMode {
  const explicit = (runtimeEnv().ALGENTA_TELEMETRY_MODE ?? "").trim().toLowerCase();
  if (VALID_TELEMETRY_MODES.has(explicit)) {
    return explicit as RuntimeTelemetryMode;
  }
  if (telemetryDisabled()) {
    return privateProfile() ? "local_audit" : "disabled";
  }
  return "control_plane_sync";
}

export function meteringMode(): RuntimeMeteringMode {
  const explicit = (runtimeEnv().ALGENTA_METERING_MODE ?? "").trim().toLowerCase();
  if (VALID_TELEMETRY_MODES.has(explicit)) {
    return explicit as RuntimeMeteringMode;
  }
  return privateProfile() ? "local_audit" : "control_plane_sync";
}

function egressAllowlist(): string[] {
  const raw = runtimeEnv().ALGENTA_EGRESS_ALLOWLIST ?? "";
  return raw
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

export function resolveControlPlaneBaseUrl(baseUrl?: string): string {
  const env = runtimeEnv();
  const explicit =
    env.ALGENTA_CONTROL_PLANE_URL ??
    env.ALGENTA_BASE_URL ??
    env.DE_BASE_URL ??
    baseUrl;
  if (explicit && explicit.trim()) {
    return trimTrailingSlashes(explicit);
  }
  return cloudDisabled() ? "" : DEFAULT_BASE_URL;
}

function parseDestination(destination: string): RuntimeEgressTarget {
  const trimmed = destination.trim();
  const candidate = trimmed.includes("://") ? trimmed : `https://${trimmed}`;
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error("Egress destination must include a valid host.");
  }
  const host = parsed.hostname.trim().toLowerCase();
  if (!host) {
    throw new Error("Egress destination must include a valid host.");
  }
  const port = parsed.port.trim();
  return {
    host,
    normalized: port ? `${host}:${port}` : host,
  };
}

function destinationHash(normalizedHost: string): string {
  return createHash("sha256").update(normalizedHost).digest("hex");
}

function isAlgentaOwnedHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  if (ALGENTA_OWNED_HOST_SET.has(normalized)) {
    return true;
  }
  return ALGENTA_OWNED_SUFFIXES.some((suffix) => normalized.endsWith(suffix));
}

function isVendorTelemetryHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  if (VENDOR_TELEMETRY_HOST_SET.has(normalized)) {
    return true;
  }
  return normalized.endsWith(".sentry.io");
}

function isPrivateIPv4(host: string): boolean {
  const octets = host.split(".").map((part) => Number.parseInt(part, 10));
  if (octets.length !== 4 || octets.some((part) => Number.isNaN(part) || part < 0 || part > 255)) {
    return false;
  }
  const [first, second] = octets;
  if (first === 10 || first === 127) {
    return true;
  }
  if (first === 192 && second === 168) {
    return true;
  }
  if (first === 172 && second >= 16 && second <= 31) {
    return true;
  }
  if (first === 169 && second === 254) {
    return true;
  }
  if (first >= 224) {
    return true;
  }
  return false;
}

function isPrivateIPv6(host: string): boolean {
  const normalized = host.toLowerCase();
  return (
    normalized === "::1"
    || normalized.startsWith("fc")
    || normalized.startsWith("fd")
    || normalized.startsWith("fe8")
    || normalized.startsWith("fe9")
    || normalized.startsWith("fea")
    || normalized.startsWith("feb")
    || normalized.startsWith("ff")
  );
}

function privateHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  if (["localhost", "127.0.0.1", "::1"].includes(normalized)) {
    return true;
  }
  if (PRIVATE_HOST_SUFFIXES.some((suffix) => normalized.endsWith(suffix))) {
    return true;
  }
  const family = isIP(normalized);
  if (family === 4) {
    return isPrivateIPv4(normalized);
  }
  if (family === 6) {
    return isPrivateIPv6(normalized);
  }
  return normalized.endsWith(".internal");
}

function redactDestinationHost(host: string): string {
  const normalized = host.trim().toLowerCase();
  if (isAlgentaOwnedHost(normalized) || isVendorTelemetryHost(normalized)) {
    return normalized;
  }
  if (privateHost(normalized)) {
    return "internal-host";
  }
  const parts = normalized.split(".");
  if (parts.length >= 2) {
    return `*.${parts[parts.length - 2]}.${parts[parts.length - 1]}`;
  }
  return "public-host";
}

function destinationMatchesAllowlist(target: RuntimeEgressTarget, allowlist: string[]): boolean {
  for (const item of allowlist) {
    const pattern = item.trim().toLowerCase();
    if (!pattern) {
      continue;
    }
    if (pattern.startsWith("*.")) {
      if (target.host.endsWith(pattern.slice(1))) {
        return true;
      }
      continue;
    }
    if (pattern.includes(":")) {
      if (target.normalized === pattern) {
        return true;
      }
      continue;
    }
    if (target.host === pattern) {
      return true;
    }
  }
  return false;
}

function classifyEgressClass(
  target: RuntimeEgressTarget,
  explicitConfigured: boolean,
  explicitClass?: RuntimeEgressClass,
): RuntimeEgressClass {
  if (explicitClass) {
    return explicitClass;
  }
  if (isAlgentaOwnedHost(target.host)) {
    return "algenta_cloud";
  }
  if (isVendorTelemetryHost(target.host)) {
    return "vendor_telemetry";
  }
  if (explicitConfigured) {
    return "customer_connector";
  }
  return "undeclared_public";
}

export function evaluateRuntimeEgress(
  destination: string,
  options: {
    surface: string;
    explicitConfigured?: boolean;
    egressClass?: RuntimeEgressClass;
    requestId?: string | null;
  },
): RuntimeEgressDecision {
  const target = parseDestination(destination);
  const classified = classifyEgressClass(
    target,
    options.explicitConfigured ?? false,
    options.egressClass,
  );
  const destinationHostHash = destinationHash(target.normalized);
  const destinationHostRedacted = redactDestinationHost(target.host);

  if (classified === "algenta_cloud") {
    return {
      surface: options.surface,
      egressClass: classified,
      decision: cloudDisabled() || !outboundNetworkAllowed() ? "deny" : "allow",
      reason:
        cloudDisabled() || !outboundNetworkAllowed()
          ? "algenta_cloud_disabled"
          : "algenta_cloud_enabled",
      destinationHostHash,
      destinationHostRedacted,
      deploymentMode: deploymentMode(),
      serviceName: "runtime",
      requestId: options.requestId ?? null,
    };
  }

  if (classified === "vendor_telemetry") {
    const enabled = !telemetryDisabled()
      && telemetryMode() === "control_plane_sync"
      && outboundNetworkAllowed();
    return {
      surface: options.surface,
      egressClass: classified,
      decision: enabled ? "allow" : "deny",
      reason: enabled ? "vendor_telemetry_enabled" : "vendor_telemetry_disabled",
      destinationHostHash,
      destinationHostRedacted,
      deploymentMode: deploymentMode(),
      serviceName: "runtime",
      requestId: options.requestId ?? null,
    };
  }

  if (classified === "customer_connector" || classified === "operator_service") {
    if (outboundNetworkAllowed()) {
      return {
        surface: options.surface,
        egressClass: classified,
        decision: "allow",
        reason: "outbound_network_enabled",
        destinationHostHash,
        destinationHostRedacted,
        deploymentMode: deploymentMode(),
        serviceName: "runtime",
        requestId: options.requestId ?? null,
      };
    }
    if ((options.explicitConfigured ?? false) && destinationMatchesAllowlist(target, egressAllowlist())) {
      return {
        surface: options.surface,
        egressClass: classified,
        decision: "allow",
        reason: "destination_allowlisted",
        destinationHostHash,
        destinationHostRedacted,
        deploymentMode: deploymentMode(),
        serviceName: "runtime",
        requestId: options.requestId ?? null,
      };
    }
    return {
      surface: options.surface,
      egressClass: classified,
      decision: "deny",
      reason: "destination_not_allowlisted",
      destinationHostHash,
      destinationHostRedacted,
      deploymentMode: deploymentMode(),
      serviceName: "runtime",
      requestId: options.requestId ?? null,
    };
  }

  if (outboundNetworkAllowed()) {
    return {
      surface: options.surface,
      egressClass: classified,
      decision: "allow",
      reason: "undeclared_public_egress_enabled",
      destinationHostHash,
      destinationHostRedacted,
      deploymentMode: deploymentMode(),
      serviceName: "runtime",
      requestId: options.requestId ?? null,
    };
  }

  return {
    surface: options.surface,
    egressClass: classified,
    decision: "deny",
    reason: "undeclared_public_egress_disabled",
    destinationHostHash,
    destinationHostRedacted,
    deploymentMode: deploymentMode(),
    serviceName: "runtime",
    requestId: options.requestId ?? null,
  };
}

export function recordRuntimeEgressEvent(decision: RuntimeEgressDecision): void {
  const event = {
    event_id: `evt_${randomUUID().replace(/-/g, "")}`,
    task_id:
      decision.requestId
      ?? `privacy_${decision.surface}_${decision.destinationHostHash.slice(0, 16)}`,
    surface: "runtime",
    action: "privacy_egress",
    status: decision.decision,
    target: decision.destinationHostRedacted,
    request_id: decision.requestId,
    engine_used: null,
    latency_ms: null,
    success: decision.decision === "allow",
    error: decision.decision === "allow" ? null : decision.reason,
    sync_state: "local_only",
    details: {
      surface: decision.surface,
      egress_class: decision.egressClass,
      decision: decision.decision,
      reason: decision.reason,
      deployment_mode: decision.deploymentMode,
      service_name: decision.serviceName,
      request_id: decision.requestId,
      destination_host_redacted: decision.destinationHostRedacted,
      destination_host_hash: decision.destinationHostHash,
    },
    timestamp: Date.now() / 1000,
  };

  try {
    mkdirSync(runtimeDirectory(), { recursive: true });
    writeFileSync(ledgerPath(), `${JSON.stringify(event)}\n`, { flag: "a" });
  } catch {
    return;
  }
}

export function enforceRuntimeEgress(
  destination: string,
  options: {
    surface: string;
    explicitConfigured?: boolean;
    egressClass?: RuntimeEgressClass;
    requestId?: string | null;
    record?: boolean;
  },
): RuntimeEgressDecision {
  const decision = evaluateRuntimeEgress(destination, options);
  if (options.record ?? true) {
    recordRuntimeEgressEvent(decision);
  }
  if (decision.decision === "deny") {
    throw new RuntimeEgressPolicyDeniedError(decision);
  }
  return decision;
}

export function validatedRuntimeEgressUrl(
  destination: string,
  options: {
    surface: string;
    fieldName: string;
    explicitConfigured?: boolean;
    egressClass?: RuntimeEgressClass;
    requestId?: string | null;
    record?: boolean;
  },
): string {
  const normalized = trimTrailingSlashes(destination.trim());
  let parsed: URL;
  try {
    parsed = new URL(normalized);
  } catch {
    throw new Error(`${options.fieldName} must use an absolute http(s) URL.`);
  }
  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname.trim()) {
    throw new Error(`${options.fieldName} must use an absolute http(s) URL.`);
  }
  enforceRuntimeEgress(normalized, options);
  return normalized;
}

export function validatedControlPlaneBaseUrl(
  baseUrl: string | undefined,
  options: {
    surface: string;
    fieldName?: string;
    requestId?: string | null;
    record?: boolean;
  },
): string {
  const resolved = resolveControlPlaneBaseUrl(baseUrl);
  if (!resolved) {
    throw new Error(
      "ALGENTA_CONTROL_PLANE_URL must be configured explicitly before hosted registration can run in this deployment profile.",
    );
  }
  return validatedRuntimeEgressUrl(resolved, {
    surface: options.surface,
    fieldName: options.fieldName ?? "ALGENTA_CONTROL_PLANE_URL",
    explicitConfigured: true,
    egressClass: isAlgentaOwnedHost(parseDestination(resolved).host)
      ? "algenta_cloud"
      : "operator_service",
    requestId: options.requestId,
    record: options.record,
  });
}
