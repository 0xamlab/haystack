/**
 * Shared example privacy-profile helpers.
 *
 * These helpers default example clients to the Cloud Managed base URL only
 * when the active deployment profile allows it. In `self_hosted` and `air_gapped`,
 * examples must point at an explicit self-hosted base URL and use the API key
 * provisioned by the self-hosted operator deployment. `ALGENTA_*` env vars stay
 * canonical, while legacy `DE_*` env vars and `ALGENTA_API_URL` remain accepted
 * for compatibility.
 * Private profiles fail closed and do not silently fall back to Algenta cloud.
 */

import { ALGENTA_OWNED_HOSTS, ALGENTA_OWNED_SUFFIXES } from "../../packages/ts-sdk/src/contract.js";

const PRIVATE_DEPLOYMENT_MODES = new Set(["self_hosted", "air_gapped"]);
const ALGENTA_OWNED_HOST_SET = new Set(ALGENTA_OWNED_HOSTS);

export type ExamplePrivacyEnv = Record<string, string | undefined>;

function envValue(env: ExamplePrivacyEnv, name: string): string | undefined {
  const value = env[name];
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : undefined;
}

function parseOptionalBoolean(value: string | undefined): boolean | undefined {
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
  throw new Error("ALGENTA_DISABLE_CLOUD must be a boolean-style value when set.");
}

function cloudDisabled(env: ExamplePrivacyEnv): boolean {
  const explicit = parseOptionalBoolean(envValue(env, "ALGENTA_DISABLE_CLOUD"));
  if (explicit !== undefined) {
    return explicit;
  }
  return PRIVATE_DEPLOYMENT_MODES.has((envValue(env, "ALGENTA_DEPLOYMENT_MODE") ?? "saas").toLowerCase());
}

function isAlgentaOwnedBaseUrl(baseUrl: string): boolean {
  const hostname = new URL(baseUrl).hostname.trim().toLowerCase();
  if (ALGENTA_OWNED_HOST_SET.has(hostname)) {
    return true;
  }
  return ALGENTA_OWNED_SUFFIXES.some((suffix) => hostname.endsWith(suffix));
}

function normalizeBaseUrl(baseUrl: string, component: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(normalized);
    if (!parsed.protocol || !parsed.hostname) {
      throw new Error("missing host");
    }
  } catch {
    throw new Error(`${component} baseUrl must be an absolute URL including scheme and host.`);
  }
  return normalized;
}

export function resolveExampleBaseUrl(options: {
  component: string;
  defaultBaseUrl?: string;
  env?: ExamplePrivacyEnv;
}): string {
  const env = options.env ?? ((globalThis as { process?: { env?: ExamplePrivacyEnv } }).process?.env ?? {});
  const configuredBaseUrl =
    envValue(env, "ALGENTA_BASE_URL") ?? envValue(env, "DE_BASE_URL") ?? envValue(env, "ALGENTA_API_URL");
  const normalized = normalizeBaseUrl(
    configuredBaseUrl ?? options.defaultBaseUrl ?? "https://api.algenta.ai",
    options.component,
  );
  if (cloudDisabled(env) && isAlgentaOwnedBaseUrl(normalized)) {
    throw new Error(
      `${options.component} private profiles cannot target Algenta-owned cloud URLs. Configure a self-hosted baseUrl or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.`,
    );
  }
  return normalized;
}

export function resolveExampleApiKey(options: {
  component: string;
  env?: ExamplePrivacyEnv;
}): string {
  const env = options.env ?? ((globalThis as { process?: { env?: ExamplePrivacyEnv } }).process?.env ?? {});
  const apiKey = envValue(env, "ALGENTA_API_KEY") ?? envValue(env, "DE_API_KEY");
  if (!apiKey) {
    throw new Error(`${options.component} requires ALGENTA_API_KEY or DE_API_KEY to be set.`);
  }
  return apiKey;
}
