import {
  ALGENTA_OWNED_HOSTS,
  ALGENTA_OWNED_SUFFIXES,
  PRIVATE_HOST_SUFFIXES,
} from "./privacy_registry.js";

const PRIVATE_DEPLOYMENT_MODES = new Set(["self_hosted", "air_gapped"]);
const ALGENTA_OWNED_HOST_SET: ReadonlySet<string> = new Set<string>(ALGENTA_OWNED_HOSTS);
type EnvMap = Record<string, string | undefined>;

export class GatewayPrivacyConfigurationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GatewayPrivacyConfigurationError";
  }
}

function envValue(env: EnvMap, key: string): string | undefined {
  const value = env[key]?.trim();
  return value ? value : undefined;
}

function parseOptionalBoolean(value: string | undefined, fieldName: string): boolean | undefined {
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
  throw new GatewayPrivacyConfigurationError(
    `${fieldName} must be a boolean-style value when set.`,
  );
}

function deploymentMode(env: EnvMap): string {
  return (envValue(env, "ALGENTA_DEPLOYMENT_MODE") ?? "saas").toLowerCase();
}

function privateProfile(env: EnvMap): boolean {
  return PRIVATE_DEPLOYMENT_MODES.has(deploymentMode(env));
}

function cloudDisabled(env: EnvMap): boolean {
  const explicit = parseOptionalBoolean(envValue(env, "ALGENTA_DISABLE_CLOUD"), "ALGENTA_DISABLE_CLOUD");
  if (explicit !== undefined) {
    return explicit;
  }
  return privateProfile(env);
}

function allowOutboundNetwork(env: EnvMap): boolean {
  const explicit = parseOptionalBoolean(
    envValue(env, "ALGENTA_ALLOW_OUTBOUND_NETWORK"),
    "ALGENTA_ALLOW_OUTBOUND_NETWORK",
  );
  if (explicit !== undefined) {
    return explicit;
  }
  return !privateProfile(env);
}

function allowlistEntries(env: EnvMap): string[] {
  const raw = envValue(env, "ALGENTA_EGRESS_ALLOWLIST");
  if (!raw) {
    return [];
  }
  return raw
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function normalizeApiOrigin(rawOrigin: string): string {
  let parsed: URL;
  try {
    parsed = new URL(rawOrigin);
  } catch {
    throw new GatewayPrivacyConfigurationError(
      "API_ORIGIN must be an absolute http(s) URL.",
    );
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new GatewayPrivacyConfigurationError(
      "API_ORIGIN must use http or https.",
    );
  }
  return parsed.toString().replace(/\/$/, "");
}

function isAlgentaOwnedHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  if (ALGENTA_OWNED_HOST_SET.has(normalized)) {
    return true;
  }
  return ALGENTA_OWNED_SUFFIXES.some((suffix) => normalized.endsWith(suffix));
}

function isPrivateIpv4(host: string): boolean {
  const octets = host.split(".").map((value) => Number.parseInt(value, 10));
  if (octets.length !== 4 || octets.some((value) => Number.isNaN(value) || value < 0 || value > 255)) {
    return false;
  }
  if (octets[0] === 10) {
    return true;
  }
  if (octets[0] === 127) {
    return true;
  }
  if (octets[0] === 169 && octets[1] === 254) {
    return true;
  }
  if (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) {
    return true;
  }
  return octets[0] === 192 && octets[1] === 168;
}

function isPrivateIpv6(host: string): boolean {
  const normalized = host.toLowerCase();
  return normalized === "::1" || normalized.startsWith("fc") || normalized.startsWith("fd") || normalized.startsWith("fe80:");
}

function isPrivateHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  if (["localhost", "127.0.0.1", "::1"].includes(normalized)) {
    return true;
  }
  if (PRIVATE_HOST_SUFFIXES.some((suffix) => normalized.endsWith(suffix))) {
    return true;
  }
  if (/^\d+\.\d+\.\d+\.\d+$/.test(normalized)) {
    return isPrivateIpv4(normalized);
  }
  if (normalized.includes(":")) {
    return isPrivateIpv6(normalized);
  }
  return false;
}

function matchesAllowlist(origin: URL, entries: string[]): boolean {
  const host = origin.hostname.toLowerCase();
  const normalized = origin.port ? `${host}:${origin.port}` : host;
  return entries.some((entry) => {
    if (entry.startsWith("*.")) {
      return host.endsWith(entry.slice(1));
    }
    if (entry.includes(":")) {
      return normalized === entry;
    }
    return host === entry;
  });
}

export function resolveGatewayApiOrigin(env: EnvMap = process.env): string {
  const configuredOrigin = envValue(env, "API_ORIGIN");
  if (privateProfile(env) && !configuredOrigin) {
    throw new GatewayPrivacyConfigurationError(
      "Gateway private profiles require API_ORIGIN to be configured explicitly.",
    );
  }
  const rawOrigin = configuredOrigin ?? "http://localhost:8000";
  const normalized = normalizeApiOrigin(rawOrigin);
  const parsed = new URL(normalized);
  const host = parsed.hostname.toLowerCase();

  if (cloudDisabled(env) && isAlgentaOwnedHost(host)) {
    throw new GatewayPrivacyConfigurationError(
      "Gateway private profiles cannot target Algenta-owned cloud URLs. Configure API_ORIGIN for your self-hosted deployment.",
    );
  }

  if (allowOutboundNetwork(env) || isPrivateHost(host) || matchesAllowlist(parsed, allowlistEntries(env))) {
    return normalized;
  }

  throw new GatewayPrivacyConfigurationError(
    "Gateway private profiles require API_ORIGIN to point at a private/self-hosted origin or an allowlisted customer origin.",
  );
}
