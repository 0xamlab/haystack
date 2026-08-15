/** Auto-split sub-module of runtime.ts — internal helpers (part A). */

import type {
  APIKeyCreated,
  APIKeyInfo,
  AgentRunCheckpointListResponse,
  AgentRunCheckpointsResponse,
  AgentRunCreateRequest,
  AgentRunEventsResponse,
  AgentRunListResponse,
  AgentRunMissionEventListResponse,
  AgentRunMissionEventsResponse,
  AgentRunReplayResponse,
  AgentRunResponse,
  AgentRunStreamEventResponse,
  AgentRunTelemetryListResponse,
  AgentRunTelemetryResponse,
  AuditLogResponse,
  BillingInfoResponse,
  BillingSessionResponse,
  BatchResult,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
  CompareResponse,
  ConnectDataRequest,
  ConnectorBrowseResult,
  ConnectorInfo,
  ConnectorListResult,
  ConnectorTestInfo,
  CountTokensRequest,
  CountTokensResponse,
  CreditRefreshRequest,
  CreditRefreshResponse,
  CreateAPIKeyRequest,
  DecisionEnvelope,
  DecisionListResponse,
  DecisionLogResponse,
  DeviceListResponse,
  DeviceRevokeResponse,
  DistributionListResponse,
  DecisionPlanResponse,
  DecisionEngineClientConfig,
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
  ProductAgentRunRequest,
  ProductAgentRunResponse,
  ProductDecisionRequest,
  ProductDecisionResponse,
  ProductForecastRequest,
  ProductForecastResponse,
  ProductOptimizeRequest,
  ProductOptimizeResponse,
  ProductRetrieveRequest,
  ProductRetrieveResponse,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetListResult,
  DatasetSummaryResult,
  EmbeddingsRequest,
  EmbeddingsResponse,
  EmbeddingSimilarityRequest,
  EmbeddingSimilarityResponse,
  ExecuteDecisionRequest,
  ExecutionReceiptResponse,
  ExecutionPolicyResponse,
  ExecutionPolicySnapshotListResponse,
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  BindingScope,
  BindingStatus,
  CapabilityAdapter,
  CapabilityAdapterDescriptor,
  CapabilityAuthorizationCompleteRequest,
  CapabilityAuthorizationCompleteResponse,
  CapabilityAuthorizationStartRequest,
  CapabilityAuthorizationStartResponse,
  CapabilityBindingCreateRequest,
  CapabilityBindingPreviewRequest,
  CapabilityBindingResponse,
  CapabilityBindingTestResult,
  CapabilityBindingUpdateRequest,
  CapabilityCatalogEntry,
  CapabilityDiscoverResponse,
  CapabilityExecutionRequest,
  CapabilityExecutionResponse,
  CapabilityOutcomeRecord,
  CapabilityOutcomeRecordRequest,
  CapabilityProviderResponse,
  CapabilityRoutePlan,
  CapabilityRouteRequest,
  ExecutionOwner,
  ExecutionSessionStatus,
  JobStatusResponse,
  JobSubmitResponse,
  JobListResponse,
  WebhookTestResponse,
  LLMModelListResponse,
  LogDecisionRequest,
  MeteringBatchRequest,
  MeteringBatchResponse,
  MeResponse,
  PlatformContractResponse,
  QueryCandidate,
  QueryBatchResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryResponse,
  QueryWithMetadataResponse,
  RecordOutcomeRequest,
  RepositoryApplyRequest,
  RepositoryApplyResponse,
  RepositoryIntelligenceCapabilitiesResponse,
  RepositoryDecisionPlanCreateRequest,
  RepositoryDecisionPlanRevisionResponse,
  RepositoryGraphQueryRequest,
  RepositoryGraphQueryResponse,
  RepositorySimulationRequest,
  RepositorySnapshotCreateRequest,
  RepositorySnapshotResponse,
  RepositoryTriageRequest,
  RepositoryTriageResponse,
  RecommendResponse,
  ResolveResponse,
  ResolvedPlan,
  ResponseStreamEventResponse,
  ResponsesRequest,
  ResponsesResponse,
  RerankRequest,
  RerankResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeManifestResponse,
  RuntimeReleaseValidationResponse,
  ScoreResponse,
  SimulateRequest,
  SourceRegistrationResponse,
  TokenizeRequest,
  TokenizeResponse,
  TeamListResponse,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  TemplateListResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  RegisterTriggerRequest,
  UpdateMeRequest,
  UpdateExecutionPolicyRequest,
  UsageInfo,
  LimitsInfo,
  VerifyResponse,
} from "./types.js";
import {
  DecisionEngineClient,
  DecisionEngineError,
  assertPlatformContractResponse,
  assertRuntimeAdminBenchmarksResponse,
  assertRuntimeAdminModulesResponse,
  assertRuntimeManifestResponse,
  assertRuntimeReleaseValidationResponse,
} from "./client.js";
import { resolveClientBaseUrl } from "./privacy_profile.js";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash, createVerify } from "node:crypto";
import { homedir, hostname, platform, release } from "node:os";
import { extname, join, resolve as resolvePath } from "node:path";
import {
  RuntimeEgressPolicyDeniedError,
  deploymentMode,
  meteringMode,
  privateProfile,
  requireLocalLicense,
  resolveControlPlaneBaseUrl,
  telemetryMode,
  validatedControlPlaneBaseUrl,
} from "./runtime_privacy.js";


import {
  ACCENT,
  DEFAULT_GRACE_DAYS,
  LicenseExchangeResponse,
  LocalRuntimeLicense,
  MUTED,
  RESET,
  TITLE_ART,
  TITLE_COLORS,
  TRUSTED_TIME_PERSIST_INTERVAL_SECONDS,
  TRUSTED_TIME_VERSION,
  TrustedTimeState,
} from "./_runtime_constants.js";

export let trustedTimeSessionMonotonicBaseSeconds: number | null = null;
export let trustedTimeSessionTrustedBaseSeconds: number | null = null;
export let trustedTimeSessionRuntimeDir: string | null = null;
export const DIRECT_API_SOURCE_KEYS = new Set([
  "dataset_id",
  "source_id",
  "records",
  "csv",
  "json_str",
  "url",
  "excel_b64",
  "parquet_b64",
  "connection",
]);
export const SQL_PROVIDER_TYPES = new Set([
  "sql",
  "postgres",
  "postgresql",
  "mysql",
  "mssql",
  "sqlite",
  "snowflake",
  "bigquery",
]);
export const OBJECT_STORAGE_TYPES = new Set(["s3", "gcs", "azure_blob"]);
export const CANONICAL_FILE_TYPES = new Set(["csv", "tsv", "json", "excel", "xlsx", "xls", "parquet"]);
export const CANONICAL_API_TYPES = new Set(["rest", "rest_api", "api"]);
export const LOCAL_RUNTIME_CONNECTOR_TYPES = new Set([...CANONICAL_FILE_TYPES, "sqlite", "sqlite3"]);

export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(item => stableStringify(item)).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  return `{${keys.map(key => `${JSON.stringify(key)}:${stableStringify(record[key])}`).join(",")}}`;
}

export function stableHash(value: unknown): string {
  const input = stableStringify(value);
  let high = 0x9e3779b1;
  let low = 0x85ebca77;
  for (let index = 0; index < input.length; index += 1) {
    const code = input.charCodeAt(index);
    high = Math.imul(high ^ code, 0x45d9f3b) >>> 0;
    low = Math.imul(low ^ code, 0x119de1f3) >>> 0;
  }
  return `${high.toString(16).padStart(8, "0")}${low.toString(16).padStart(8, "0")}`;
}

export function runtimeEnv(): Record<string, string | undefined> {
  if (typeof globalThis === "undefined" || !("process" in globalThis)) {
    return {};
  }
  const globalProcess = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process;
  return globalProcess?.env ?? {};
}

export function runtimeDirectory(): string {
  return runtimeEnv().ALGENTA_RUNTIME_DIR ?? join(homedir(), ".algenta", "runtime");
}

export function runtimeLicensePath(): string {
  return join(runtimeDirectory(), "license.jwt");
}

export function runtimeTrustedTimePath(): string {
  return join(runtimeDirectory(), "trusted_time.json");
}

export function monotonicNowSeconds(): number {
  const perf = (globalThis as { performance?: { now?: () => number } }).performance;
  if (typeof perf?.now === "function") {
    return perf.now() / 1000;
  }
  return Date.now() / 1000;
}

export function ensureTrustedTimeSessionScope(): void {
  const runtimeDir = runtimeDirectory();
  if (trustedTimeSessionRuntimeDir === runtimeDir) {
    return;
  }
  trustedTimeSessionRuntimeDir = runtimeDir;
  trustedTimeSessionMonotonicBaseSeconds = null;
  trustedTimeSessionTrustedBaseSeconds = null;
}

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

export function base64UrlEncode(input: Buffer): string {
  return input.toString("base64url");
}

export function base64UrlDecode(input: string): Buffer {
  return Buffer.from(input, "base64url");
}

export function offlineLicensePublicKeys(): Array<{ key: string; source: string }> {
  const env = runtimeEnv();
  const candidates: Array<{ key: string; source: string }> = [];
  for (const name of ["ALGENTA_LOCAL_LICENSE_PUBLIC_KEY", "ALGENTA_LICENSE_PUBLIC_KEY"]) {
    const value = env[name as keyof typeof env];
    if (typeof value === "string" && value.trim()) {
      candidates.push({ key: value.trim(), source: "offline-local" });
    }
  }
  for (const name of ["ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE", "ALGENTA_LICENSE_PUBLIC_KEY_FILE"]) {
    const path = env[name as keyof typeof env];
    if (typeof path !== "string" || !path.trim()) {
      continue;
    }
    try {
      const key = readFileSync(path.trim(), "utf8").trim();
      if (key) {
        candidates.push({ key, source: "offline-local" });
      }
    } catch {
      continue;
    }
  }
  const seen = new Set<string>();
  return candidates.filter(candidate => {
    if (!candidate.key || seen.has(candidate.key)) {
      return false;
    }
    seen.add(candidate.key);
    return true;
  });
}

export function readStoredLicenseToken(): string | null {
  try {
    const path = runtimeLicensePath();
    if (!existsSync(path)) {
      return null;
    }
    return readFileSync(path, "utf8").trim();
  } catch {
    return null;
  }
}

export function saveStoredLicenseToken(token: string): void {
  const dir = runtimeDirectory();
  mkdirSync(dir, { recursive: true });
  writeFileSync(runtimeLicensePath(), token, { mode: 0o600 });
}

export function readTrustedTimeState(): TrustedTimeState | null {
  try {
    const path = runtimeTrustedTimePath();
    if (!existsSync(path)) {
      return null;
    }
    const data = JSON.parse(readFileSync(path, "utf8")) as Partial<TrustedTimeState>;
    if (
      typeof data.trusted_epoch !== "number"
      || !Number.isFinite(data.trusted_epoch)
      || data.trusted_epoch <= 0
      || typeof data.source !== "string"
      || data.source.trim().length === 0
    ) {
      return null;
    }
    return {
      version: typeof data.version === "number" ? data.version : TRUSTED_TIME_VERSION,
      trusted_epoch: data.trusted_epoch,
      source: data.source,
    };
  } catch {
    return null;
  }
}

export function writeTrustedTimeState(state: TrustedTimeState): void {
  try {
    const path = runtimeTrustedTimePath();
    mkdirSync(runtimeDirectory(), { recursive: true });
    const tmpPath = `${path}.tmp`;
    writeFileSync(tmpPath, `${JSON.stringify(state, null, 2)}\n`);
    renameSync(tmpPath, path);
  } catch {
    return;
  }
}

export function resetTrustedTimeSession(epoch: number, monotonicNow = monotonicNowSeconds()): number {
  ensureTrustedTimeSessionScope();
  trustedTimeSessionTrustedBaseSeconds = epoch;
  trustedTimeSessionMonotonicBaseSeconds = monotonicNow;
  return epoch;
}

export function sessionTrustedEpoch(currentFloor: number): number {
  ensureTrustedTimeSessionScope();
  const monotonicNow = monotonicNowSeconds();
  const localNow = Date.now() / 1000;
  const seed = Math.max(localNow, currentFloor);
  if (trustedTimeSessionMonotonicBaseSeconds === null || trustedTimeSessionTrustedBaseSeconds === null) {
    return resetTrustedTimeSession(seed, monotonicNow);
  }
  const elapsed = Math.max(0, monotonicNow - trustedTimeSessionMonotonicBaseSeconds);
  const sessionEpoch = trustedTimeSessionTrustedBaseSeconds + elapsed;
  if (seed > sessionEpoch) {
    return resetTrustedTimeSession(seed, monotonicNow);
  }
  return sessionEpoch;
}

export function observeTrustedTime(epoch: number, source: string): number {
  ensureTrustedTimeSessionScope();
  if (!Number.isFinite(epoch) || epoch <= 0) {
    return trustedNowEpoch();
  }
  const current = readTrustedTimeState();
  const currentFloor = current?.trusted_epoch ?? 0;
  const trustedEpoch = Math.max(currentFloor, epoch);
  resetTrustedTimeSession(trustedEpoch);
  if (!current || trustedEpoch > currentFloor || current.source !== source) {
    writeTrustedTimeState({
      version: TRUSTED_TIME_VERSION,
      trusted_epoch: trustedEpoch,
      source,
    });
  }
  return trustedEpoch;
}

export function trustedNowEpoch(): number {
  ensureTrustedTimeSessionScope();
  const current = readTrustedTimeState();
  const currentFloor = current?.trusted_epoch ?? 0;
  const trustedEpoch = sessionTrustedEpoch(currentFloor);
  if (!current || trustedEpoch > currentFloor + TRUSTED_TIME_PERSIST_INTERVAL_SECONDS) {
    writeTrustedTimeState({
      version: TRUSTED_TIME_VERSION,
      trusted_epoch: trustedEpoch,
      source: "local",
    });
  }
  return trustedEpoch;
}

export function deviceInfo(): {
  device_id: string;
  platform: string;
  platform_version: string;
  hostname_hash: string;
  sdk_version: string;
} {
  const machine = hostname();
  return {
    device_id: sha256Hex(`${machine}|${platform()}|${release()}`),
    platform: platform(),
    platform_version: release(),
    hostname_hash: sha256Hex(machine),
    sdk_version: "algenta-sdk/0.1.0",
  };
}

export function makeInvalidLicense(message: string, apiKey = ""): LocalRuntimeLicense {
  return {
    valid: false,
    plan: "unknown",
    deviceId: deviceInfo().device_id,
    deviceLimit: 0,
    permittedModules: [],
    expiresAt: 0,
    keyExpiresAt: 0,
    graceDays: DEFAULT_GRACE_DAYS,
    apiKeyPrefix: apiKey.slice(0, 12),
    issuedAt: Math.floor(Date.now() / 1000),
    message,
    source: "none",
  };
}

export function parseStoredLicenseToken(token: string, apiKey = ""): LocalRuntimeLicense | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  const [headerSegment, payloadSegment, signatureSegment] = parts;
  let header: { alg?: string };
  try {
    header = JSON.parse(base64UrlDecode(headerSegment).toString("utf8")) as { alg?: string };
  } catch {
    return null;
  }
  // Hard reject: RS256 (an asymmetric, publicly-verifiable signature) is the ONLY accepted
  // algorithm. There is no HS256/shared-secret fallback — a symmetric secret capable of
  // verifying a license is also capable of MINTING one, so accepting it here would make this
  // client-side check (which is optional UX preflight, never the entitlement authority) into a
  // forgeable rubber stamp. This is unconditional: it does not depend on requireLocalLicense()
  // or any other deployment profile.
  if (header.alg !== "RS256") {
    return null;
  }
  for (const candidate of offlineLicensePublicKeys()) {
    try {
      const verifier = createVerify("RSA-SHA256");
      verifier.update(`${headerSegment}.${payloadSegment}`);
      verifier.end();
      if (!verifier.verify(candidate.key, base64UrlDecode(signatureSegment))) {
        continue;
      }
      const payload = JSON.parse(base64UrlDecode(payloadSegment).toString("utf8")) as Record<string, unknown>;
      return {
        valid: true,
        plan: String(payload.plan ?? "enterprise"),
        deviceId: String(payload.device_id ?? ""),
        deviceLimit: Number(payload.device_limit ?? 0),
        permittedModules: Array.isArray(payload.permitted_modules)
          ? payload.permitted_modules.map(item => String(item))
          : ["*"],
        expiresAt: Number(payload.expires_at ?? 0),
        keyExpiresAt: Number(payload.key_expires_at ?? 0),
        graceDays: Number(payload.grace_days ?? DEFAULT_GRACE_DAYS),
        apiKeyPrefix: String(payload.api_key_prefix ?? apiKey.slice(0, 12)),
        issuedAt: Number(payload.issued_at ?? 0),
        message: String(payload.message ?? ""),
        source: candidate.source,
      };
    } catch {
      continue;
    }
  }
  return null;
}

export function licenseHardExpired(license: LocalRuntimeLicense): boolean {
  if (license.expiresAt === 0) {
    return false;
  }
  return Math.floor(trustedNowEpoch()) > license.expiresAt + license.graceDays * 86_400;
}

export function licenseInGrace(license: LocalRuntimeLicense): boolean {
  if (license.expiresAt === 0) {
    return false;
  }
  const now = Math.floor(trustedNowEpoch());
  return now > license.expiresAt && !licenseHardExpired(license);
}

export async function exchangeApiKeyForLicense(
  apiKey: string,
  baseUrl?: string,
): Promise<{ token: string | null; invalidMessage: string | null }> {
  let controlPlaneUrl = "";
  try {
    controlPlaneUrl = validatedControlPlaneBaseUrl(baseUrl, {
      surface: "device_register",
    });
  } catch (error) {
    if (error instanceof RuntimeEgressPolicyDeniedError) {
      return {
        token: null,
        invalidMessage: `Control-plane egress is blocked by the active privacy policy. Reason: ${error.decision.reason}.`,
      };
    }
    if (error instanceof Error) {
      return {
        token: null,
        invalidMessage: error.message,
      };
    }
    throw error;
  }
  try {
    const response = await fetch(`${controlPlaneUrl}/v1/device/register`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ device: deviceInfo() }),
    });
    const data = (await response.json()) as LicenseExchangeResponse;
    if (response.status === 402) {
      return {
        token: null,
        invalidMessage: data.detail?.message ?? "Device limit reached.",
      };
    }
    if (!response.ok || !data.license_token) {
      return {
        token: null,
        invalidMessage: "Control plane registration failed. First-time local login requires a reachable control plane.",
      };
    }
    observeTrustedTime(
      data.server_time ?? Math.floor(Date.now() / 1000),
      "control-plane-register",
    );
    return { token: data.license_token, invalidMessage: null };
  } catch {
    return {
      token: null,
      invalidMessage: "Control plane registration failed. First-time local login requires a reachable control plane.",
    };
  }
}

export async function loadLocalLicense(apiKey: string, baseUrl?: string): Promise<LocalRuntimeLicense> {
  trustedNowEpoch();
  const stored = readStoredLicenseToken();
  if (stored) {
    const parsed = parseStoredLicenseToken(stored, apiKey);
    if (parsed) {
      if (licenseHardExpired(parsed)) {
        return {
          ...parsed,
          valid: false,
          message: "License expired - run `algenta login` to renew.",
        };
      }
      if (licenseInGrace(parsed)) {
        return {
          ...parsed,
          message: "License in grace period - run `algenta login` to renew.",
        };
      }
      return parsed;
    }
  }
  if (requireLocalLicense()) {
    return makeInvalidLicense(
      "A valid local signed license is required for this deployment profile. Provision an offline license file before startup.",
      apiKey,
    );
  }
  if (apiKey) {
    const exchanged = await exchangeApiKeyForLicense(apiKey, baseUrl);
    if (exchanged.token) {
      saveStoredLicenseToken(exchanged.token);
      const parsed = parseStoredLicenseToken(exchanged.token, apiKey);
      if (parsed) {
        return parsed;
      }
    }
    return makeInvalidLicense(
      exchanged.invalidMessage ??
        "Control plane registration failed. First-time local login requires a reachable control plane.",
      apiKey,
    );
  }
  return makeInvalidLicense(
    "No stored license found. Run `algenta login` against the control plane before offline execution.",
    apiKey,
  );
}

export function supportsColor(): boolean {
  if (typeof globalThis === "undefined" || !("process" in globalThis)) {
    return false;
  }
  const globalProcess = (globalThis as {
    process?: { env?: Record<string, string | undefined>; stdout?: { isTTY?: boolean } };
  }).process;
  if (globalProcess?.env?.NO_COLOR) {
    return false;
  }
  if (globalProcess?.env?.TERM === "dumb") {
    return false;
  }
  return Boolean(globalProcess?.stdout?.isTTY);
}

export function runtimeBanner(title: string, lines: string[], color = supportsColor()): string {
  const detailLines = lines.length > 0 ? lines.map(line => line.trimEnd()) : [""];
  if (color) {
    const art = TITLE_ART.map((segment, index) => `${TITLE_COLORS[index]}${segment}${RESET}`).join("\n");
    const border = `${MUTED}┌${"─".repeat(60)}┐${RESET}`;
    const footer = `${MUTED}└${"─".repeat(60)}┘${RESET}`;
    const titlePadding = Math.max(0, 59 - title.length);
    const body = [
      `${MUTED}│${RESET} ${ACCENT}${title}${RESET}${" ".repeat(titlePadding)}${MUTED}│${RESET}`,
      ...detailLines.map(line => {
        const padded = line.slice(0, 58).padEnd(58, " ");
        return `${MUTED}│${RESET} ${padded} ${MUTED}│${RESET}`;
      }),
    ];
    return [art, border, ...body, footer].join("\n");
  }

  const art = TITLE_ART.join("\n");
  const width = 60;
  const border = `+${"-".repeat(width)}+`;
  const body = [
    `| ${title.slice(0, width - 2).padEnd(width - 2, " ")} |`,
    ...detailLines.map(line => `| ${line.slice(0, width - 2).padEnd(width - 2, " ")} |`),
  ];
  return [art, border, ...body, border].join("\n");
}

export function normalizeText(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

