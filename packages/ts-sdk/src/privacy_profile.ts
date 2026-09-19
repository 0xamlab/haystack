// SPDX-License-Identifier: Apache-2.0
import { ALGENTA_OWNED_HOSTS, ALGENTA_OWNED_SUFFIXES, DEFAULT_BASE_URL } from "./contract.js";

function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.charCodeAt(end - 1) === 47 /* '/' */) {
    end--;
  }
  return end === value.length ? value : value.slice(0, end);
}



const PRIVATE_DEPLOYMENT_MODES = new Set(["self_hosted", "air_gapped"]);
const ALGENTA_OWNED_HOST_SET = new Set<string>(ALGENTA_OWNED_HOSTS);
const DEFAULT_CONSOLE_BASE_URL = "https://app.algenta.ai";
const CONSOLE_BASE_URL_ENV_VARS = ["ALGENTA_APP_BASE_URL", "APP_BASE_URL", "DE_APP_BASE_URL"] as const;

function envValue(name: string): string | undefined {
  if (typeof globalThis === "undefined" || !("process" in globalThis)) {
    return undefined;
  }
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
  const value = env?.[name];
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

export function cloudDisabled(): boolean {
  const explicit = parseOptionalBoolean(envValue("ALGENTA_DISABLE_CLOUD"));
  if (explicit !== undefined) {
    return explicit;
  }
  return PRIVATE_DEPLOYMENT_MODES.has((envValue("ALGENTA_DEPLOYMENT_MODE") ?? "saas").toLowerCase());
}

export function privateProfileEnabled(): boolean {
  return (
    PRIVATE_DEPLOYMENT_MODES.has((envValue("ALGENTA_DEPLOYMENT_MODE") ?? "saas").toLowerCase()) ||
    cloudDisabled()
  );
}

export function normalizeBaseUrl(baseUrl: string, component: string): string {
  const normalized = trimTrailingSlashes(baseUrl.trim());
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

function joinUrlPath(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${trimTrailingSlashes(baseUrl)}${normalizedPath}`;
}

function configuredConsoleBaseUrl(): string | undefined {
  for (const key of CONSOLE_BASE_URL_ENV_VARS) {
    const value = envValue(key);
    if (value) {
      return value;
    }
  }
  return undefined;
}

export function isAlgentaOwnedBaseUrl(baseUrl: string): boolean {
  const hostname = new URL(baseUrl).hostname.trim().toLowerCase();
  if (ALGENTA_OWNED_HOST_SET.has(hostname)) {
    return true;
  }
  return ALGENTA_OWNED_SUFFIXES.some((suffix) => hostname.endsWith(suffix));
}

export function resolveClientBaseUrl(
  explicitBaseUrl: string | undefined,
  component: string,
): string {
  const configuredBaseUrl =
    envValue("ALGENTA_BASE_URL") ?? envValue("DE_BASE_URL") ?? envValue("ALGENTA_API_URL");
  const normalized = normalizeBaseUrl(
    explicitBaseUrl ?? configuredBaseUrl ?? DEFAULT_BASE_URL,
    component,
  );
  if (cloudDisabled() && isAlgentaOwnedBaseUrl(normalized)) {
    throw new Error(
      `${component} private profiles cannot target Algenta-owned cloud URLs. Configure a self-hosted baseUrl or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.`,
    );
  }
  return normalized;
}

export function resolveConsoleBaseUrl(
  component: string,
  fallbackBaseUrl?: string,
): string {
  const configuredConsoleUrl = configuredConsoleBaseUrl();
  if (configuredConsoleUrl) {
    const normalized = normalizeBaseUrl(configuredConsoleUrl, `${component} console`);
    if (privateProfileEnabled() && isAlgentaOwnedBaseUrl(normalized)) {
      throw new Error(
        `${component} private profiles cannot target Algenta-owned cloud URLs. Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted baseUrl.`,
      );
    }
    return normalized;
  }

  if (privateProfileEnabled()) {
    const rawBaseUrl =
      fallbackBaseUrl ??
      envValue("ALGENTA_BASE_URL") ??
      envValue("DE_BASE_URL") ??
      envValue("ALGENTA_API_URL");
    if (!rawBaseUrl) {
      throw new Error(
        `${component} private profiles require an explicit self-hosted dashboard or API baseUrl. Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.`,
      );
    }
    const normalized = normalizeBaseUrl(
      rawBaseUrl,
      `${component} console`,
    );
    if (isAlgentaOwnedBaseUrl(normalized)) {
      throw new Error(
        `${component} private profiles cannot target Algenta-owned cloud URLs. Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted baseUrl.`,
      );
    }
    return normalized;
  }

  return DEFAULT_CONSOLE_BASE_URL;
}

export function resolveApiKeysUrl(
  component: string,
  fallbackBaseUrl?: string,
): string {
  return joinUrlPath(resolveConsoleBaseUrl(component, fallbackBaseUrl), "/dashboard/api-keys");
}

export function apiKeyHelpText(
  component: string,
  fallbackBaseUrl?: string,
): string {
  if (privateProfileEnabled() && !configuredConsoleBaseUrl()) {
    return `Create a key from your self-hosted admin surface or API base URL: ${resolveConsoleBaseUrl(component, fallbackBaseUrl)}`;
  }
  return `Get a key at: ${resolveApiKeysUrl(component, fallbackBaseUrl)}`;
}
