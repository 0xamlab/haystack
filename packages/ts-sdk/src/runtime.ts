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
import { createHash, createHmac, createVerify, timingSafeEqual } from "node:crypto";
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

export type RuntimeMode = "local" | "api" | "self_hosted";

export interface RuntimeConfig {
  mode?: RuntimeMode;
  apiKey?: string;
  enforceLimits?: boolean;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  defaultHeaders?: Record<string, string>;
  client?: DecisionEngineClient;
  capabilityAdapters?: CapabilityAdapter[];
}

const RUNTIME_DATASET_SCOPE_KEY = "__runtime_dataset_id__";

export interface RuntimeConnectOptions {
  name?: string;
  description?: string;
  connectorId?: string;
  connector?: Record<string, unknown>;
  selection?: Record<string, unknown>;
  datasetName?: string;
  persist?: boolean;
  visibility?: string;
  connectionName?: string;
}

type LocalRecord = Record<string, unknown>;

interface LocalSource {
  name: string;
  records: LocalRecord[];
  fields: string[];
  schemaRevision: string;
  datasetId: string;
}

interface LocalResolvedFilterCondition {
  column: string;
  op: string;
  value?: unknown;
  values?: unknown[];
}

export interface ImportPreviewOptions {
  name?: string;
  description?: string;
  sourceRef?: string;
  color?: boolean;
}

export interface ImportPreviewResult {
  registration: SourceRegistrationResponse;
  preview: string;
}

export interface ImportFailureResult {
  sourceRef: string;
  code: string;
  message: string;
  name?: string;
}

export interface ImportBundlePreviewOptions {
  names?: Array<string | undefined>;
  sourceRefs?: Array<string | undefined>;
  description?: string;
  color?: boolean;
}

export interface ImportBundlePreviewResult {
  registrations: SourceRegistrationResponse[];
  failures: ImportFailureResult[];
  preview: string;
}

interface RankedField {
  field: string;
  score: number;
  reasons: string[];
}

interface LocalRuntimeLicense {
  valid: boolean;
  plan: string;
  deviceId: string;
  deviceLimit: number;
  permittedModules: string[];
  expiresAt: number;
  keyExpiresAt: number;
  graceDays: number;
  apiKeyPrefix: string;
  issuedAt: number;
  message: string;
  source: string;
}

interface LocalCreditState {
  credits_remaining: number;
  credits_total: number;
  issued_at: number;
  expires_at: number;
  billing_period: string;
  refresh_after: number;
}

interface LicenseExchangeResponse {
  license_token?: string;
  plan?: string;
  device_count?: number;
  device_limit?: number;
  credits_granted?: number;
  credits_billing_period?: string;
  credits_expires_at?: number;
  server_time?: number;
  detail?: {
    message?: string;
  };
}

interface TrustedTimeState {
  version: number;
  trusted_epoch: number;
  source: string;
}

const AGGREGATION_KEYWORDS: Array<[string, string]> = [
  ["average", "avg"],
  ["mean", "avg"],
  ["avg", "avg"],
  ["count", "count"],
  ["total", "sum"],
  ["sum", "sum"],
  ["minimum", "min"],
  ["min", "min"],
  ["maximum", "max"],
  ["max", "max"],
];

const METRIC_SYNONYMS: Record<string, string[]> = {
  revenue: ["sales", "net sales", "income", "gmv"],
  profit: ["margin", "net profit"],
  cost: ["expense", "spend"],
  quantity: ["qty", "units", "count"],
};

const TITLE_ART = [
  " █████╗ ██╗      ██████╗ ███████╗███╗   ██╗████████╗ █████╗ ",
  "██╔══██╗██║     ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔══██╗",
  "███████║██║     ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████║",
  "██╔══██║██║     ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██╔══██║",
  "██║  ██║███████╗╚██████╔╝███████╗██║ ╚████║   ██║   ██║  ██║",
  "╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝",
];

const TITLE_COLORS = [
  "\u001b[38;5;75m",
  "\u001b[38;5;81m",
  "\u001b[38;5;111m",
  "\u001b[38;5;141m",
  "\u001b[38;5;176m",
  "\u001b[38;5;204m",
];

const MUTED = "\u001b[38;5;245m";
const ACCENT = "\u001b[38;5;183m";
const RESET = "\u001b[0m";
const MEASURE_TOKENS = new Set([
  "amount",
  "avg",
  "cost",
  "count",
  "days",
  "expense",
  "hours",
  "loss",
  "margin",
  "pct",
  "percent",
  "price",
  "profit",
  "qty",
  "quantity",
  "rate",
  "revenue",
  "sales",
  "score",
  "total",
  "value",
  "volume",
  "weight",
]);
const CSV_INT_RE = /^[+-]?\d+$/;
const CSV_FLOAT_RE = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;
const CSV_LEADING_ZERO_INT_RE = /^[+-]?0\d+$/;
const CSV_CURRENCY_PREFIX_RE = /^[\$£€¥]+/;
const CSV_TOKEN_RE = /[a-z0-9]+/g;
const FILTER_SUPPORTED_OPS = new Set(["eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"]);
const FILTER_NUMERIC_OPS = new Set(["gt", "gte", "lt", "lte"]);
const FILTER_NULL_OPS = new Set(["is_null", "is_not_null"]);
const FILTER_TRUE_VALUES = new Set(["1", "true", "t", "yes", "y"]);
const FILTER_FALSE_VALUES = new Set(["0", "false", "f", "no", "n"]);
const LOCAL_TIME_FIELD_CUES = ["date", "time", "timestamp", "month", "day", "year"];
const SQLITE_DSN_RE = /^sqlite(?:\+pysqlite)?:\/\/\/(.+)$/i;
const SQL_IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_$]*$/;
const SQL_DSN_SCHEMES: Record<string, string> = {
  postgres: "postgresql",
  postgresql: "postgresql",
  mysql: "mysql",
  mssql: "mssql",
  redshift: "redshift",
};
const SQL_DEFAULT_PORTS: Record<string, number> = {
  postgres: 5432,
  postgresql: 5432,
  mysql: 3306,
  mssql: 1433,
  redshift: 5439,
};
const HEADER_ALIAS_MIN_COLUMNS = 3;
const HEADER_ALIAS_MAX_COLUMNS = 8;
const HEADER_ALIAS_MIN_MATCH_RATIO = 0.6;
const HEADER_ALIAS_MATCH_SCORE = 0.34;
const HEADER_ALIAS_AVG_SCORE = 0.45;
const DEV_LICENSE_SECRET = "algenta-dev-local-v1-not-for-production";
const LICENSE_VERSION = 1;
const DEFAULT_GRACE_DAYS = 14;
const CREDIT_TTL_SECONDS = 86_400;
const CREDIT_REFRESH_THRESHOLD = 0.1;
const TRUSTED_TIME_VERSION = 1;
const TRUSTED_TIME_PERSIST_INTERVAL_SECONDS = 60;
let trustedTimeSessionMonotonicBaseSeconds: number | null = null;
let trustedTimeSessionTrustedBaseSeconds: number | null = null;
let trustedTimeSessionRuntimeDir: string | null = null;
const DIRECT_API_SOURCE_KEYS = new Set([
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
const SQL_PROVIDER_TYPES = new Set([
  "sql",
  "postgres",
  "postgresql",
  "mysql",
  "mssql",
  "sqlite",
  "snowflake",
  "bigquery",
]);
const OBJECT_STORAGE_TYPES = new Set(["s3", "gcs", "azure_blob"]);
const CANONICAL_FILE_TYPES = new Set(["csv", "tsv", "json", "excel", "xlsx", "xls", "parquet"]);
const CANONICAL_API_TYPES = new Set(["rest", "rest_api", "api"]);
const LOCAL_RUNTIME_CONNECTOR_TYPES = new Set([...CANONICAL_FILE_TYPES, "sqlite", "sqlite3"]);

function stableStringify(value: unknown): string {
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

function stableHash(value: unknown): string {
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

function runtimeEnv(): Record<string, string | undefined> {
  if (typeof globalThis === "undefined" || !("process" in globalThis)) {
    return {};
  }
  const globalProcess = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process;
  return globalProcess?.env ?? {};
}

function runtimeDirectory(): string {
  return runtimeEnv().ALGENTA_RUNTIME_DIR ?? join(homedir(), ".algenta", "runtime");
}

function runtimeLicensePath(): string {
  return join(runtimeDirectory(), "license.jwt");
}

function runtimeCreditsPath(): string {
  return join(runtimeDirectory(), "credits.json");
}

function runtimeTrustedTimePath(): string {
  return join(runtimeDirectory(), "trusted_time.json");
}

function monotonicNowSeconds(): number {
  const perf = (globalThis as { performance?: { now?: () => number } }).performance;
  if (typeof perf?.now === "function") {
    return perf.now() / 1000;
  }
  return Date.now() / 1000;
}

function ensureTrustedTimeSessionScope(): void {
  const runtimeDir = runtimeDirectory();
  if (trustedTimeSessionRuntimeDir === runtimeDir) {
    return;
  }
  trustedTimeSessionRuntimeDir = runtimeDir;
  trustedTimeSessionMonotonicBaseSeconds = null;
  trustedTimeSessionTrustedBaseSeconds = null;
}

function sha256Hex(input: string): string {
  return createHash("sha256").update(input).digest("hex");
}

function base64UrlEncode(input: Buffer): string {
  return input.toString("base64url");
}

function base64UrlDecode(input: string): Buffer {
  return Buffer.from(input, "base64url");
}

function timingSafeEquals(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}

function licenseVerificationSecrets(): Array<{ secret: string; source: string }> {
  const env = runtimeEnv();
  const candidates: Array<{ secret: string; source: string }> = [];
  const explicitSecret = env.ALGENTA_LICENSE_SIGNING_SECRET ?? env.LICENSE_SIGNING_SECRET;
  if (explicitSecret) {
    candidates.push({ secret: explicitSecret, source: "control-plane" });
  }
  const jwtSeed = env.ALGENTA_JWT_SECRET ?? env.JWT_SECRET ?? "change-me-in-production-use-256-bit-random-value";
  candidates.push({
    secret: sha256Hex(`${jwtSeed}:license-signing`),
    source: "control-plane",
  });

  const seen = new Set<string>();
  return candidates.filter(candidate => {
    if (!candidate.secret || candidate.secret === DEV_LICENSE_SECRET || seen.has(candidate.secret)) {
      return false;
    }
    seen.add(candidate.secret);
    return true;
  });
}

function offlineLicensePublicKeys(): Array<{ key: string; source: string }> {
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

function readStoredLicenseToken(): string | null {
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

function saveStoredLicenseToken(token: string): void {
  const dir = runtimeDirectory();
  mkdirSync(dir, { recursive: true });
  writeFileSync(runtimeLicensePath(), token, { mode: 0o600 });
}

function readTrustedTimeState(): TrustedTimeState | null {
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

function writeTrustedTimeState(state: TrustedTimeState): void {
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

function resetTrustedTimeSession(epoch: number, monotonicNow = monotonicNowSeconds()): number {
  ensureTrustedTimeSessionScope();
  trustedTimeSessionTrustedBaseSeconds = epoch;
  trustedTimeSessionMonotonicBaseSeconds = monotonicNow;
  return epoch;
}

function sessionTrustedEpoch(currentFloor: number): number {
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

function observeTrustedTime(epoch: number, source: string): number {
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

function trustedNowEpoch(): number {
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

function writeCreditState(state: LocalCreditState): void {
  const path = runtimeCreditsPath();
  mkdirSync(runtimeDirectory(), { recursive: true });
  const tmpPath = `${path}.tmp`;
  writeFileSync(tmpPath, `${JSON.stringify(state, null, 2)}\n`);
  renameSync(tmpPath, path);
}

function readCreditState(): LocalCreditState | null {
  try {
    const path = runtimeCreditsPath();
    if (!existsSync(path)) {
      return null;
    }
    return JSON.parse(readFileSync(path, "utf8")) as LocalCreditState;
  } catch {
    return null;
  }
}

function isRuntimeDevModeEnabled(): boolean {
  const value = (runtimeEnv().ALGENTA_RUNTIME_DEV_MODE ?? "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function deviceInfo(): {
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

function makeInvalidLicense(message: string, apiKey = ""): LocalRuntimeLicense {
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

function makeDevLicense(apiKey = ""): LocalRuntimeLicense {
  return {
    valid: true,
    plan: "dev",
    deviceId: deviceInfo().device_id,
    deviceLimit: 0,
    permittedModules: ["*"],
    expiresAt: 0,
    keyExpiresAt: 0,
    graceDays: DEFAULT_GRACE_DAYS,
    apiKeyPrefix: apiKey ? apiKey.slice(0, 12) : "dev-local",
    issuedAt: Math.floor(Date.now() / 1000),
    message: "Dev mode - self-signed local license",
    source: "dev-stub",
  };
}

function parseStoredLicenseToken(token: string, apiKey = ""): LocalRuntimeLicense | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  const [headerSegment, payloadSegment, signatureSegment] = parts;
  try {
    const header = JSON.parse(base64UrlDecode(headerSegment).toString("utf8")) as { alg?: string };
    if (header.alg === "RS256") {
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
    if (requireLocalLicense()) {
      return null;
    }
  } catch {
    return null;
  }
  for (const candidate of [
    { secret: DEV_LICENSE_SECRET, source: "dev-stub" },
    ...licenseVerificationSecrets(),
  ]) {
    try {
      const header = JSON.parse(base64UrlDecode(headerSegment).toString("utf8")) as { alg?: string };
      if (header.alg !== "HS256") {
        continue;
      }
      const expected = base64UrlEncode(
        createHmac("sha256", candidate.secret).update(`${headerSegment}.${payloadSegment}`).digest(),
      );
      if (!timingSafeEquals(expected, signatureSegment)) {
        continue;
      }
      const payload = JSON.parse(base64UrlDecode(payloadSegment).toString("utf8")) as Record<string, unknown>;
      return {
        valid: true,
        plan: String(payload.plan ?? "dev"),
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

function licenseHardExpired(license: LocalRuntimeLicense): boolean {
  if (license.expiresAt === 0) {
    return false;
  }
  return Math.floor(trustedNowEpoch()) > license.expiresAt + license.graceDays * 86_400;
}

function licenseInGrace(license: LocalRuntimeLicense): boolean {
  if (license.expiresAt === 0) {
    return false;
  }
  const now = Math.floor(trustedNowEpoch());
  return now > license.expiresAt && !licenseHardExpired(license);
}

function initializeCredits(granted: number, billingPeriod: string, ttlSeconds = CREDIT_TTL_SECONDS): void {
  const now = trustedNowEpoch();
  writeCreditState({
    credits_remaining: granted,
    credits_total: granted,
    issued_at: now,
    expires_at: now + ttlSeconds,
    billing_period: billingPeriod,
    refresh_after: now + ttlSeconds * 0.9,
  });
}

function stateNeedsRefresh(state: LocalCreditState | null): boolean {
  if (!state) {
    return true;
  }
  if (state.credits_total <= 0) {
    return true;
  }
  if (trustedNowEpoch() > state.expires_at) {
    return true;
  }
  return state.credits_remaining / state.credits_total <= CREDIT_REFRESH_THRESHOLD;
}

function decrementCredit(): { permitted: boolean; state: LocalCreditState | null } {
  const state = readCreditState();
  if (!state) {
    return { permitted: isRuntimeDevModeEnabled(), state };
  }
  if (state.credits_remaining <= 0) {
    return { permitted: false, state };
  }
  const nextState: LocalCreditState = {
    ...state,
    credits_remaining: state.credits_remaining - 1,
  };
  writeCreditState(nextState);
  return { permitted: true, state: nextState };
}

function hasOfflineExecutionEntitlement(license: LocalRuntimeLicense | undefined): boolean {
  if (!license?.valid || license.keyExpiresAt <= 0) {
    return false;
  }
  return !licenseHardExpired(license);
}

async function exchangeApiKeyForLicense(
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
    if ((data.credits_granted ?? 0) > 0) {
      const now = trustedNowEpoch();
      const expiresAt = data.credits_expires_at ?? now + CREDIT_TTL_SECONDS;
      const ttlSeconds = Math.max(1, expiresAt - now);
      initializeCredits(
        data.credits_granted ?? 0,
        data.credits_billing_period ?? "",
        ttlSeconds,
      );
    }
    return { token: data.license_token, invalidMessage: null };
  } catch {
    return {
      token: null,
      invalidMessage: "Control plane registration failed. First-time local login requires a reachable control plane.",
    };
  }
}

async function loadLocalLicense(apiKey: string, baseUrl?: string): Promise<LocalRuntimeLicense> {
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
  if (isRuntimeDevModeEnabled()) {
    return makeDevLicense(apiKey);
  }
  return makeInvalidLicense(
    "No stored license found. Run `algenta login` against the control plane before offline execution.",
    apiKey,
  );
}

function supportsColor(): boolean {
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

function runtimeBanner(title: string, lines: string[], color = supportsColor()): string {
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

function normalizeText(value: string | null | undefined): string {
  return (value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function isExactFieldMatch(field: string, hint: string): boolean {
  return normalizeText(field) === normalizeText(hint);
}

function metricSynonymSet(hint: string): Set<string> {
  const normalized = normalizeText(hint);
  const terms = new Set<string>([normalized]);
  for (const [canonical, synonyms] of Object.entries(METRIC_SYNONYMS)) {
    const normalizedCanonical = normalizeText(canonical);
    const normalizedSynonyms = synonyms.map(term => normalizeText(term));
    if (normalized === normalizedCanonical || normalizedSynonyms.includes(normalized)) {
      terms.add(normalizedCanonical);
      for (const synonym of normalizedSynonyms) {
        terms.add(synonym);
      }
    }
  }
  return terms;
}

function parseRawText(rawText: string): Record<string, unknown> {
  const text = rawText.toLowerCase().trim();
  const parsed: Record<string, unknown> = {};
  for (const [keyword, aggregation] of AGGREGATION_KEYWORDS) {
    if (text.includes(keyword)) {
      parsed.aggregation = aggregation;
      break;
    }
  }
  for (const [canonical, synonyms] of Object.entries(METRIC_SYNONYMS)) {
    if ([canonical, ...synonyms].some(term => text.includes(term.toLowerCase()))) {
      parsed.metric = canonical;
      break;
    }
  }
  const groupMatch = text.match(/\b(?:by|per|grouped by|group by|for each)\s+([a-z0-9_ ]+)/);
  if (groupMatch?.[1]) {
    parsed.group_by = groupMatch[1].trim();
  }
  return parsed;
}

function mergeRequest(
  request: Record<string, unknown> | undefined,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const merged = { ...(request ?? {}), ...overrides };
  if (typeof merged.raw_text === "string") {
    const parsed = parseRawText(merged.raw_text);
    for (const [key, value] of Object.entries(parsed)) {
      if (!(key in merged)) {
        merged[key] = value;
      }
    }
  }
  return merged;
}

function resolveAggregation(request: Record<string, unknown>): string {
  if (typeof request.aggregation === "string" && request.aggregation.trim()) {
    return request.aggregation.trim().toLowerCase();
  }
  if (typeof request.raw_text === "string") {
    const parsed = parseRawText(request.raw_text);
    if (typeof parsed.aggregation === "string") {
      return parsed.aggregation;
    }
  }
  return "sum";
}

function orderedFields(records: LocalRecord[]): string[] {
  const seen = new Set<string>();
  const fields: string[] = [];
  for (const record of records) {
    for (const field of Object.keys(record)) {
      if (seen.has(field)) continue;
      seen.add(field);
      fields.push(field);
    }
  }
  return fields;
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function booleanValue(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value) && (value === 0 || value === 1)) {
    return Boolean(value);
  }
  if (typeof value === "string" && value.trim()) {
    const normalized = value.trim().toLowerCase();
    if (FILTER_TRUE_VALUES.has(normalized)) return true;
    if (FILTER_FALSE_VALUES.has(normalized)) return false;
  }
  return null;
}

function isNullishFilterValue(value: unknown): boolean {
  if (value == null) return true;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return normalized === "" || normalized === "none" || normalized === "null" || normalized === "nan";
  }
  if (typeof value === "number") {
    return !Number.isFinite(value);
  }
  return false;
}

function valuesEqual(rowValue: unknown, expected: unknown): boolean {
  const rowBool = booleanValue(rowValue);
  const expectedBool = booleanValue(expected);
  if (rowBool !== null && expectedBool !== null) {
    return rowBool === expectedBool;
  }

  const rowNumber = numericValue(rowValue);
  const expectedNumber = numericValue(expected);
  if (rowNumber !== null && expectedNumber !== null) {
    return rowNumber === expectedNumber;
  }

  if (isNullishFilterValue(rowValue) || isNullishFilterValue(expected)) {
    return false;
  }
  return String(rowValue).trim().toLowerCase() === String(expected).trim().toLowerCase();
}

function parseDateValue(value: unknown): Date | null {
  if (value == null) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const direct = new Date(raw);
  if (!Number.isNaN(direct.getTime())) {
    return new Date(Date.UTC(direct.getUTCFullYear(), direct.getUTCMonth(), direct.getUTCDate()));
  }
  const monthMatch = raw.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) {
    const [, year, month] = monthMatch;
    return new Date(Date.UTC(Number(year), Number(month) - 1, 1));
  }
  return null;
}

function timeRange(filterName: string): { start: Date; end: Date } | null {
  const now = new Date();
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const year = today.getUTCFullYear();
  const month = today.getUTCMonth();
  if (filterName === "this_month") {
    return {
      start: new Date(Date.UTC(year, month, 1)),
      end: today,
    };
  }
  if (filterName === "last_month") {
    const lastMonthEnd = new Date(Date.UTC(year, month, 0));
    return {
      start: new Date(Date.UTC(lastMonthEnd.getUTCFullYear(), lastMonthEnd.getUTCMonth(), 1)),
      end: lastMonthEnd,
    };
  }
  if (filterName === "this_year") {
    return {
      start: new Date(Date.UTC(year, 0, 1)),
      end: today,
    };
  }
  if (filterName === "last_year") {
    return {
      start: new Date(Date.UTC(year - 1, 0, 1)),
      end: new Date(Date.UTC(year - 1, 11, 31)),
    };
  }
  const currentQuarterStartMonth = Math.floor(month / 3) * 3;
  if (filterName === "this_quarter") {
    return {
      start: new Date(Date.UTC(year, currentQuarterStartMonth, 1)),
      end: today,
    };
  }
  if (filterName === "last_quarter") {
    const previousQuarterMonth = currentQuarterStartMonth - 3;
    const previousQuarterYear = previousQuarterMonth < 0 ? year - 1 : year;
    const normalizedQuarterMonth = previousQuarterMonth < 0 ? previousQuarterMonth + 12 : previousQuarterMonth;
    return {
      start: new Date(Date.UTC(previousQuarterYear, normalizedQuarterMonth, 1)),
      end: new Date(Date.UTC(previousQuarterYear, normalizedQuarterMonth + 3, 0)),
    };
  }
  return null;
}

function sampleBooleanField(records: LocalRecord[], fieldName: string): boolean {
  let observed = 0;
  for (const record of records.slice(0, 50)) {
    if (!(fieldName in record)) continue;
    const value = record[fieldName];
    if (isNullishFilterValue(value)) continue;
    observed += 1;
    if (booleanValue(value) === null) return false;
  }
  return observed > 0;
}

function fieldMatchScore(fieldName: string, hint: string): { score: number; exact: boolean } {
  const normalizedField = normalizeText(fieldName);
  const normalizedHint = normalizeText(hint);
  if (!normalizedField || !normalizedHint) return { score: 0, exact: false };
  if (normalizedField === normalizedHint) return { score: 1, exact: true };
  if (normalizedField.startsWith(normalizedHint) || normalizedHint.startsWith(normalizedField)) {
    return { score: 0.95, exact: false };
  }
  if (normalizedField.includes(normalizedHint) || normalizedHint.includes(normalizedField)) {
    return { score: 0.9, exact: false };
  }
  const fieldTokens = new Set(normalizedField.split(" "));
  const hintTokens = new Set(normalizedHint.split(" "));
  if (fieldTokens.size === 0 || hintTokens.size === 0) return { score: 0, exact: false };
  let overlap = 0;
  for (const token of fieldTokens) {
    if (hintTokens.has(token)) overlap += 1;
  }
  const forward = overlap / fieldTokens.size;
  const backward = overlap / hintTokens.size;
  return { score: Number(((forward + backward) / 2).toFixed(4)), exact: false };
}

function preferredFilterValueType(condition: Record<string, unknown>): "numeric" | "boolean" | null {
  const op = typeof condition.op === "string" ? condition.op : "eq";
  if (FILTER_NUMERIC_OPS.has(op)) return "numeric";
  if (FILTER_NULL_OPS.has(op)) return null;
  if (op === "in" && Array.isArray(condition.values)) {
    if (condition.values.length > 0 && condition.values.every(value => booleanValue(value) !== null)) {
      return "boolean";
    }
    if (condition.values.length > 0 && condition.values.every(value => numericValue(value) !== null)) {
      return "numeric";
    }
    return null;
  }
  if (booleanValue(condition.value) !== null) return "boolean";
  if (numericValue(condition.value) !== null) return "numeric";
  return null;
}

function resolveLocalFilterColumn(source: LocalSource, condition: Record<string, unknown>): string {
  if (typeof condition.column === "string" && condition.column.trim()) {
    const normalizedColumn = normalizeText(condition.column);
    const field = source.fields.find(candidate => normalizeText(candidate) === normalizedColumn);
    if (field) return field;
    throw new RuntimeValidationError(
      "invalid_filter_condition",
      `Filter column '${condition.column}' is not present on source '${source.name}'.`,
    );
  }

  if (typeof condition.dimension_hint !== "string" || !condition.dimension_hint.trim()) {
    throw new RuntimeValidationError(
      "invalid_filter_condition",
      "Filter condition requires column or dimension_hint.",
    );
  }

  const preferredType = preferredFilterValueType(condition);
  const candidates = source.fields
    .map(fieldName => {
      const { score: lexicalScore, exact } = fieldMatchScore(fieldName, condition.dimension_hint as string);
      const isNumeric = source.records.length > 0 && isNumericField(fieldName, source.records);
      const isBoolean = sampleBooleanField(source.records, fieldName);
      let suitability = 0;
      if (preferredType === "numeric") {
        suitability = isNumeric ? 0.35 : -0.25;
      } else if (preferredType === "boolean") {
        suitability = isBoolean ? 0.35 : isNumeric ? -0.1 : 0;
      } else if (condition.op === "eq" || condition.op === "in") {
        suitability = isNumeric ? -0.08 : 0.1;
      }
      return {
        fieldName,
        exact,
        score: Number((lexicalScore + suitability).toFixed(4)),
      };
    })
    .filter(candidate => candidate.score >= 0.6 || candidate.exact)
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      if (left.exact !== right.exact) return left.exact ? -1 : 1;
      return right.fieldName.localeCompare(left.fieldName);
    });

  if (candidates.length === 0) {
    throw new RuntimeValidationError(
      "invalid_filter_condition",
      `Filter dimension_hint '${condition.dimension_hint}' did not resolve on source '${source.name}'.`,
    );
  }
  if (!candidates[0].exact && candidates.length > 1 && candidates[1].score >= candidates[0].score - 0.05) {
    throw new RuntimeValidationError(
      "invalid_filter_condition",
      `Filter dimension_hint '${condition.dimension_hint}' is ambiguous on source '${source.name}': ${candidates.slice(0, 3).map(candidate => candidate.fieldName).join(", ")}.`,
    );
  }
  if (preferredType === "numeric" && !isNumericField(candidates[0].fieldName, source.records)) {
    throw new RuntimeValidationError(
      "invalid_filter_condition",
      `Filter column '${candidates[0].fieldName}' on source '${source.name}' is not numeric.`,
    );
  }
  return candidates[0].fieldName;
}

function resolveLocalFilterConditions(
  source: LocalSource,
  filterValue: unknown,
): LocalResolvedFilterCondition[] {
  if (!filterValue || typeof filterValue !== "object") return [];
  const filterRecord = filterValue as Record<string, unknown>;
  if (!Array.isArray(filterRecord.conditions)) return [];
  return filterRecord.conditions.map(rawCondition => {
    if (!rawCondition || typeof rawCondition !== "object") {
      throw new RuntimeValidationError("invalid_filter_condition", "Filter conditions must be objects.");
    }
    const conditionRecord = rawCondition as Record<string, unknown>;
    const op = typeof conditionRecord.op === "string" ? conditionRecord.op : "";
    if (!op) {
      throw new RuntimeValidationError("invalid_filter_condition", "Filter condition op is required.");
    }
    if (!FILTER_SUPPORTED_OPS.has(op)) {
      throw new RuntimeValidationError("invalid_filter_condition", `Unsupported filter operator '${op}'.`);
    }
    const value = conditionRecord.value;
    const values = Array.isArray(conditionRecord.values) ? [...conditionRecord.values] : undefined;
    if (op === "in") {
      if (value !== undefined && value !== null) {
        throw new RuntimeValidationError(
          "invalid_filter_condition",
          "filter condition op='in' does not accept value",
        );
      }
      if (!values || values.length === 0) {
        throw new RuntimeValidationError(
          "invalid_filter_condition",
          "filter condition op='in' requires non-empty values",
        );
      }
    } else if (FILTER_NULL_OPS.has(op)) {
      if (value !== undefined && value !== null || conditionRecord.values !== undefined) {
        throw new RuntimeValidationError(
          "invalid_filter_condition",
          "filter condition null checks do not accept value or values",
        );
      }
    } else {
      if (conditionRecord.values !== undefined) {
        throw new RuntimeValidationError(
          "invalid_filter_condition",
          `filter condition op='${op}' does not accept values`,
        );
      }
      if (value === undefined || value === null) {
        throw new RuntimeValidationError(
          "invalid_filter_condition",
          `filter condition op='${op}' requires value`,
        );
      }
    }
    return {
      column: resolveLocalFilterColumn(source, conditionRecord),
      op,
      value,
      values,
    };
  });
}

function rowMatchesFilterCondition(
  record: LocalRecord,
  condition: LocalResolvedFilterCondition,
): boolean {
  const rowValue = record[condition.column];
  switch (condition.op) {
    case "eq":
      return valuesEqual(rowValue, condition.value);
    case "in":
      return (condition.values ?? []).some(value => valuesEqual(rowValue, value));
    case "gt": {
      const rowNumber = numericValue(rowValue);
      const expectedNumber = numericValue(condition.value);
      return rowNumber !== null && expectedNumber !== null && rowNumber > expectedNumber;
    }
    case "gte": {
      const rowNumber = numericValue(rowValue);
      const expectedNumber = numericValue(condition.value);
      return rowNumber !== null && expectedNumber !== null && rowNumber >= expectedNumber;
    }
    case "lt": {
      const rowNumber = numericValue(rowValue);
      const expectedNumber = numericValue(condition.value);
      return rowNumber !== null && expectedNumber !== null && rowNumber < expectedNumber;
    }
    case "lte": {
      const rowNumber = numericValue(rowValue);
      const expectedNumber = numericValue(condition.value);
      return rowNumber !== null && expectedNumber !== null && rowNumber <= expectedNumber;
    }
    case "is_null":
      return isNullishFilterValue(rowValue);
    case "is_not_null":
      return !isNullishFilterValue(rowValue);
    default:
      throw new RuntimeValidationError(
        "invalid_filter_condition",
        `Unsupported filter operator '${condition.op}'.`,
      );
  }
}

function applyLocalFilterConditions(
  records: LocalRecord[],
  conditions: LocalResolvedFilterCondition[],
): { records: LocalRecord[]; planSteps: string[] } {
  let filtered = records;
  const planSteps: string[] = [];
  for (const condition of conditions) {
    const before = filtered.length;
    filtered = filtered.filter(record => rowMatchesFilterCondition(record, condition));
    const rhs = FILTER_NULL_OPS.has(condition.op)
      ? ""
      : condition.op === "in"
        ? ` ${JSON.stringify(condition.values ?? [])}`
        : ` ${JSON.stringify(condition.value)}`;
    planSteps.push(
      `Filter '${condition.column} ${condition.op}${rhs}': ${before}->${filtered.length} rows.`,
    );
  }
  return { records: filtered, planSteps };
}

function findLocalTimeField(source: LocalSource): string | null {
  let bestField: string | null = null;
  let bestScore = -1;
  for (const fieldName of source.fields) {
    let parseableCount = 0;
    for (const record of source.records.slice(0, 25)) {
      if (parseDateValue(record[fieldName]) !== null) {
        parseableCount += 1;
      }
    }
    if (parseableCount === 0) continue;
    const normalizedField = normalizeText(fieldName);
    const cueBonus = LOCAL_TIME_FIELD_CUES.reduce(
      (sum, cue) => sum + (normalizedField.includes(cue) ? 1 : 0),
      0,
    );
    const score = parseableCount + cueBonus;
    if (score > bestScore) {
      bestScore = score;
      bestField = fieldName;
    }
  }
  return bestField;
}

function isNumericField(field: string, records: LocalRecord[]): boolean {
  let seen = false;
  for (const record of records) {
    if (!(field in record)) continue;
    const parsed = numericValue(record[field]);
    if (parsed === null) return false;
    seen = true;
  }
  return seen;
}

function semanticScore(field: string, hint: string): { score: number; reasons: string[] } {
  const normalizedField = normalizeText(field);
  const normalizedHint = normalizeText(hint);
  if (!normalizedField || !normalizedHint) {
    return { score: 0, reasons: [] };
  }
  if (normalizedField === normalizedHint) {
    return { score: 1, reasons: ["exact field match"] };
  }

  const fieldTokens = new Set(normalizedField.split(" "));
  const hintTokens = new Set(normalizedHint.split(" "));
  const overlap = [...hintTokens].filter(token => fieldTokens.has(token)).length;
  const union = new Set([...fieldTokens, ...hintTokens]).size || 1;
  let score = overlap / union;
  const reasons = overlap > 0 ? ["token overlap"] : ["schema similarity"];

  if (normalizedField.includes(normalizedHint) || normalizedHint.includes(normalizedField)) {
    score = Math.max(score, 0.9);
    reasons.push("substring match");
  }
  return { score: Math.min(1, Number(score.toFixed(4))), reasons };
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    ordered.push(normalized);
  }
  return ordered;
}

function sourceSetFromRequest(request: Record<string, unknown>): string[] {
  const values: string[] = [];
  if (typeof request.source_name === "string") values.push(request.source_name);
  if (typeof request.join_source_name === "string") values.push(request.join_source_name);
  return dedupeStrings(values);
}

function buildExplainJoinPath(sourceSet: string[]): Array<Record<string, unknown>> {
  if (sourceSet.length < 2) return [];
  return sourceSet.slice(0, -1).map((source, index) => ({
    left_source: source,
    right_source: sourceSet[index + 1],
  }));
}

function roundLatency(startMs: number): number {
  return Number((Date.now() - startMs).toFixed(3));
}

function registrationFields(registration: SourceRegistrationResponse): string[] {
  const schema =
    (registration.source_schema as Record<string, unknown> | null | undefined) ??
    (registration.schema as Record<string, unknown> | null | undefined);
  const rawFields = schema?.fields;
  if (Array.isArray(rawFields)) {
    return rawFields.filter((field): field is string => typeof field === "string" && field.trim().length > 0);
  }
  const rawColumns = schema?.columns;
  if (!Array.isArray(rawColumns)) {
    return [];
  }
  return rawColumns
    .map(column => {
      if (!column || typeof column !== "object") return null;
      const name = (column as Record<string, unknown>).name;
      return typeof name === "string" && name.trim() ? name : null;
    })
    .filter((field): field is string => Boolean(field));
}

function registrationResolvedSourceName(
  registration: SourceRegistrationResponse,
): string | null {
  const schema =
    (registration.source_schema as Record<string, unknown> | null | undefined) ??
    (registration.schema as Record<string, unknown> | null | undefined);
  const canonicalSource = schema?.source;
  if (typeof canonicalSource === "string" && canonicalSource.trim()) {
    return canonicalSource.trim();
  }
  if (typeof registration.name === "string" && registration.name.trim()) {
    return registration.name.trim();
  }
  if (typeof registration.dataset_name === "string" && registration.dataset_name.trim()) {
    return registration.dataset_name.trim();
  }
  return null;
}

function registrationDatasetId(
  registration: SourceRegistrationResponse,
): string | null {
  if (typeof registration.dataset_id === "string" && registration.dataset_id.trim()) {
    return registration.dataset_id.trim();
  }
  if (typeof registration.source_id === "string" && registration.source_id.trim()) {
    return registration.source_id.trim();
  }
  return null;
}

function bundleFieldTokens(field: string): Set<string> {
  return new Set(normalizeText(baseHeaderName(field)).match(/[a-z0-9]+/g) ?? []);
}

function fieldOverlapScore(left: string, right: string): number {
  const leftTokens = bundleFieldTokens(left);
  const rightTokens = bundleFieldTokens(right);
  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0;
  }
  const shared = [...leftTokens].filter(token => rightTokens.has(token)).length;
  if (shared === 0) {
    return 0;
  }
  return shared / Math.min(leftTokens.size, rightTokens.size);
}

function bundleOverlapLines(registrations: SourceRegistrationResponse[]): string[] {
  const lines: Array<{ line: string; score: number }> = [];
  for (let leftIndex = 0; leftIndex < registrations.length; leftIndex += 1) {
    const leftRegistration = registrations[leftIndex];
    const leftName = leftRegistration.name ?? leftRegistration.dataset_name ?? `source_${leftIndex + 1}`;
    for (let rightIndex = leftIndex + 1; rightIndex < registrations.length; rightIndex += 1) {
      const rightRegistration = registrations[rightIndex];
      const rightName = rightRegistration.name ?? rightRegistration.dataset_name ?? `source_${rightIndex + 1}`;
      for (const leftField of registrationFields(leftRegistration)) {
        for (const rightField of registrationFields(rightRegistration)) {
          const score = fieldOverlapScore(leftField, rightField);
          if (score >= 0.6) {
            lines.push({
              line: `${leftName}.${leftField} <-> ${rightName}.${rightField}`,
              score,
            });
          }
        }
      }
    }
  }
  return lines
    .sort((left, right) => right.score - left.score || left.line.localeCompare(right.line))
    .slice(0, 3)
    .map(item => item.line);
}

function sourceReference(
  source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
  explicitSourceRef?: string,
): string {
  if (explicitSourceRef && explicitSourceRef.trim()) {
    return explicitSourceRef.trim();
  }
  if (typeof source === "string" && source.trim()) {
    return source.trim().split(/[\\/]/).pop() ?? source.trim();
  }
  if (Array.isArray(source)) {
    return "in-memory records";
  }
  const sourceRecord = isCanonicalConnectorEnvelope(source as Record<string, unknown>)
    ? flattenConnectorEnvelope(source as Record<string, unknown>)
    : (source as Record<string, unknown>);
  const descriptorPath = sourceDescriptorPath(sourceRecord);
  if (descriptorPath) {
    const baseName = descriptorPath.split(/[\\/]/).pop() ?? descriptorPath;
    const tableCandidate = sourceRecord.table;
    if (typeof tableCandidate === "string" && tableCandidate.trim()) {
      return `${baseName}#${tableCandidate.trim()}`;
    }
    if (typeof sourceRecord.query === "string") {
      return `${baseName}#query`;
    }
    return baseName;
  }
  const nameCandidate = sourceRecord.name;
  if (typeof nameCandidate === "string" && nameCandidate.trim()) {
    return nameCandidate.trim();
  }
  return "structured source descriptor";
}

function sourceDescriptorPath(source: Record<string, unknown>): string | null {
  const pathCandidate = source.path;
  if (typeof pathCandidate === "string" && pathCandidate.trim()) {
    return pathCandidate.trim();
  }
  const connectionString = source.connection_string;
  if (typeof connectionString === "string" && connectionString.trim()) {
    const match = SQLITE_DSN_RE.exec(connectionString.trim());
    if (match?.[1]) {
      return match[1];
    }
  }
  return null;
}

function stripUndefined(record: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(record).filter(([, value]) => value !== undefined && value !== null));
}

function isCanonicalConnectorEnvelope(source: Record<string, unknown>): boolean {
  return "location" in source || "auth" in source || "options" in source;
}

function mergeConnectorSection(
  target: Record<string, unknown>,
  section: unknown,
  sectionName: string,
): void {
  if (section === undefined || section === null) {
    return;
  }
  if (!section || typeof section !== "object" || Array.isArray(section)) {
    throw new RuntimeValidationError(
      "invalid_connector",
      `Canonical connector ${sectionName} must be an object.`,
      { section: sectionName },
    );
  }
  for (const [key, value] of Object.entries(section)) {
    if (Object.prototype.hasOwnProperty.call(target, key) && target[key] !== value) {
      throw new RuntimeValidationError(
        "connector_conflict",
        `Canonical connector defines conflicting values for '${key}'.`,
        { field: key, section: sectionName },
      );
    }
    target[key] = value;
  }
}

function normalizeConnectorAuth(flattened: Record<string, unknown>): void {
  const mode = String(flattened.auth_mode ?? "").trim().toLowerCase();
  delete flattened.auth_mode;
  if (!mode || mode === "none") {
    return;
  }

  const headersValue = flattened.headers;
  const headers =
    headersValue && typeof headersValue === "object" && !Array.isArray(headersValue)
      ? { ...(headersValue as Record<string, unknown>) }
      : {};
  if (headersValue !== undefined && (typeof headersValue !== "object" || Array.isArray(headersValue))) {
    throw new RuntimeValidationError(
      "invalid_connector_auth",
      "Canonical connector headers must be an object.",
      { field: "headers" },
    );
  }

  if (mode === "token" || mode === "bearer" || mode === "oauth") {
    const token = flattened.token ?? flattened.access_token ?? flattened.api_key;
    delete flattened.token;
    delete flattened.access_token;
    if (typeof token !== "string" || !token.trim()) {
      throw new RuntimeValidationError(
        "invalid_connector_auth",
        "Bearer-style connector auth requires token, access_token, or api_key.",
        { mode },
      );
    }
    if (headers.Authorization === undefined) {
      headers.Authorization = `Bearer ${token.trim()}`;
    }
  } else if (mode === "basic") {
    const username = flattened.username ?? flattened.user;
    const password = flattened.password;
    delete flattened.username;
    delete flattened.password;
    if (typeof username !== "string" || typeof password !== "string") {
      throw new RuntimeValidationError(
        "invalid_connector_auth",
        "Basic connector auth requires username/user and password.",
        { mode },
      );
    }
    const token = Buffer.from(`${username}:${password}`, "utf8").toString("base64");
    if (headers.Authorization === undefined) {
      headers.Authorization = `Basic ${token}`;
    }
  } else if (mode === "api_key") {
    const apiKey = flattened.api_key ?? flattened.token;
    const headerName = flattened.api_key_header ?? flattened.header;
    delete flattened.header;
    delete flattened.token;
    if (typeof apiKey !== "string" || !apiKey.trim()) {
      throw new RuntimeValidationError(
        "invalid_connector_auth",
        "API key connector auth requires api_key or token credentials.",
        { mode },
      );
    }
    const normalizedHeaderName =
      typeof headerName === "string" && headerName.trim() ? headerName.trim() : "X-API-Key";
    if (headers[normalizedHeaderName] === undefined) {
      headers[normalizedHeaderName] = apiKey.trim();
    }
  } else {
    throw new RuntimeValidationError(
      "invalid_connector_auth",
      `Unsupported connector auth mode '${mode}'.`,
      { mode },
    );
  }

  flattened.headers = headers;
}

function flattenConnectorEnvelope(source: Record<string, unknown>): Record<string, unknown> {
  const rawType = source.type;
  if (typeof rawType !== "string" || !rawType.trim()) {
    throw new RuntimeValidationError(
      "invalid_connector",
      "Canonical connectors require a non-empty type.",
      { field: "type" },
    );
  }

  const flattened = stripUndefined(
    Object.fromEntries(
      Object.entries(source).filter(([key]) => key !== "location" && key !== "auth" && key !== "options"),
    ),
  );
  flattened.type = rawType.trim().toLowerCase().replace(/-/g, "_");

  mergeConnectorSection(flattened, source.location, "location");
  if (source.auth !== undefined) {
    if (!source.auth || typeof source.auth !== "object" || Array.isArray(source.auth)) {
      throw new RuntimeValidationError(
        "invalid_connector",
        "Canonical connector auth must be an object.",
        { field: "auth" },
      );
    }
    const auth = source.auth as Record<string, unknown>;
    if (auth.mode !== undefined) {
      flattened.auth_mode = String(auth.mode).trim().toLowerCase();
    }
    mergeConnectorSection(flattened, auth.credentials, "auth.credentials");
    mergeConnectorSection(flattened, auth.headers, "auth.headers");
  }
  mergeConnectorSection(flattened, source.options, "options");

  if (CANONICAL_API_TYPES.has(String(flattened.type))) {
    normalizeConnectorAuth(flattened);
  }
  return stripUndefined(flattened);
}

function fileConnectorType(source: Record<string, unknown>): string {
  const rawType = String(source.type ?? source.provider ?? "").trim().toLowerCase();
  return rawType === "xlsx" || rawType === "xls" ? "excel" : rawType;
}

function normalizeLocalRuntimeSource(source: Record<string, unknown>): Record<string, unknown> {
  const normalized = isCanonicalConnectorEnvelope(source) ? flattenConnectorEnvelope(source) : stripUndefined({ ...source });
  const rawType = String(normalized.type ?? normalized.provider ?? normalized.connection_type ?? "").trim().toLowerCase();
  if (CANONICAL_FILE_TYPES.has(rawType)) {
    const filePath = normalized.file_path ?? normalized.path;
    if (typeof filePath === "string" && filePath.trim()) {
      return { path: filePath.trim() };
    }
    if (Array.isArray(normalized.records)) {
      return { records: normalized.records };
    }
    if ((rawType === "csv" || rawType === "tsv") && typeof normalized.csv === "string") {
      return { csv: normalized.csv };
    }
    if (rawType === "json" && typeof normalized.json_str === "string") {
      return { json_str: normalized.json_str };
    }
    throw new RuntimeValidationError(
      "unsupported_local_connector",
      "Local Runtime.connect() supports canonical file connectors only with a local path or inline data.",
      { type: rawType },
    );
  }
  if (rawType && !LOCAL_RUNTIME_CONNECTOR_TYPES.has(rawType)) {
    throw new RuntimeValidationError(
      "unsupported_local_connector",
      "Local Runtime.connect() supports local files and SQLite descriptors. Use Runtime({ mode: 'api', apiKey: '...' }) or Runtime({ mode: 'self_hosted', baseUrl: '...' }) for remote connectors.",
      { type: rawType },
    );
  }
  return normalized;
}

function runtimeApiSourceName(source: Record<string, unknown>, explicitName?: string): string {
  if (explicitName && explicitName.trim()) {
    return explicitName.trim();
  }
  const nameCandidate = source.name;
  if (typeof nameCandidate === "string" && nameCandidate.trim()) {
    return nameCandidate.trim();
  }
  return localSourceName(source, 0);
}

function sqlIdentifier(value: unknown, fieldName: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new RuntimeValidationError(
      "invalid_sql_descriptor",
      `API and self_hosted SQL descriptors require a non-empty ${fieldName}.`,
      { field: fieldName },
    );
  }
  const normalized = value.trim();
  if (!SQL_IDENTIFIER_RE.test(normalized)) {
    throw new RuntimeValidationError(
      "invalid_sql_identifier",
      "API and self_hosted SQL descriptors only auto-build queries for simple schema/table identifiers. Provide an explicit query for advanced SQL.",
      { field: fieldName, value: normalized },
    );
  }
  return normalized;
}

function runtimeSqlConnectionString(provider: string, source: Record<string, unknown>): string {
  const connectionString = source.connection_string;
  if (typeof connectionString === "string" && connectionString.trim()) {
    return connectionString.trim();
  }
  if (provider in SQL_DSN_SCHEMES) {
    const hostValue = source.host;
    const databaseValue = source.database;
    if (
      typeof hostValue === "string" &&
      hostValue.trim() &&
      typeof databaseValue === "string" &&
      databaseValue.trim()
    ) {
      const usernameValue = source.user ?? source.username;
      const passwordValue = source.password;
      if (passwordValue !== undefined && typeof passwordValue !== "string") {
        throw new RuntimeValidationError(
          "invalid_sql_descriptor",
          "Database connector password must be a string when provided.",
          { field: "password", provider },
        );
      }
      if (usernameValue !== undefined && typeof usernameValue !== "string") {
        throw new RuntimeValidationError(
          "invalid_sql_descriptor",
          "Database connector user must be a string when provided.",
          { field: "user", provider },
        );
      }
      if (passwordValue !== undefined && (!usernameValue || !String(usernameValue).trim())) {
        throw new RuntimeValidationError(
          "invalid_sql_descriptor",
          "Database connector password requires user/username when building a connection_string.",
          { field: "password", provider },
        );
      }
      const portValue = source.port;
      let port = SQL_DEFAULT_PORTS[provider];
      if (portValue !== undefined) {
        const parsed = typeof portValue === "number" ? portValue : Number(String(portValue));
        if (!Number.isInteger(parsed)) {
          throw new RuntimeValidationError(
            "invalid_sql_descriptor",
            "Database connector port must be an integer when provided.",
            { field: "port", provider },
          );
        }
        port = parsed;
      }
      let credentials = "";
      if (typeof usernameValue === "string" && usernameValue.trim()) {
        credentials = encodeURIComponent(usernameValue.trim());
        if (typeof passwordValue === "string") {
          credentials = `${credentials}:${encodeURIComponent(passwordValue)}`;
        }
        credentials = `${credentials}@`;
      }
      return `${SQL_DSN_SCHEMES[provider]}://${credentials}${hostValue.trim()}:${port}/${encodeURIComponent(databaseValue.trim())}`;
    }
  }
  if (provider !== "sqlite") {
    throw new RuntimeValidationError(
      "missing_connection_string",
      "API and self_hosted database descriptors require connection_string or a structured host/database descriptor.",
      { provider },
    );
  }
  const pathValue = source.path;
  if (typeof pathValue !== "string" || !pathValue.trim()) {
    throw new RuntimeValidationError(
      "missing_connection_string",
      "SQLite API descriptors require path or connection_string.",
      { provider },
    );
  }
  return `sqlite+pysqlite:///${resolvePath(pathValue.trim())}`;
}

function runtimeSqlQuery(source: Record<string, unknown>): string {
  const query = source.query;
  if (typeof query === "string" && query.trim()) {
    return query.trim();
  }
  const table = sqlIdentifier(source.table, "table");
  if (source.schema === undefined || source.schema === null) {
    return `SELECT * FROM ${table}`;
  }
  const schema = sqlIdentifier(source.schema, "schema");
  return `SELECT * FROM ${schema}.${table}`;
}

function runtimeRestUrl(source: Record<string, unknown>): string {
  const url = source.url;
  if (typeof url === "string" && url.trim()) {
    return url.trim();
  }
  const baseUrl = source.base_url;
  if (typeof baseUrl !== "string" || !baseUrl.trim()) {
    throw new RuntimeValidationError(
      "missing_rest_url",
      "API and self_hosted REST descriptors require url or base_url.",
    );
  }
  const path = source.path;
  if (typeof path !== "string" || !path.trim()) {
    return baseUrl.replace(/\/+$/, "");
  }
  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function normalizeRuntimeConnection(source: Record<string, unknown>): Record<string, unknown> {
  const normalized = isCanonicalConnectorEnvelope(source)
    ? flattenConnectorEnvelope(source)
    : stripUndefined({ ...source });
  const rawType = String(normalized.type ?? normalized.provider ?? normalized.connection_type ?? "").trim().toLowerCase();
  if (CANONICAL_FILE_TYPES.has(rawType)) {
    const fileType = fileConnectorType(normalized);
    const connection: Record<string, unknown> = stripUndefined({
      type: "file",
      file_type: fileType,
      file_path: normalized.file_path ?? normalized.path,
      delimiter: normalized.delimiter,
      json_path: normalized.json_path,
      sheet: normalized.sheet,
    });
    if (connection.file_path) {
      return connection;
    }
    if ((fileType === "csv" || fileType === "tsv") && normalized.csv !== undefined) {
      connection.content = normalized.csv;
      return stripUndefined(connection);
    }
    if (fileType === "json" && normalized.json_str !== undefined) {
      connection.content = normalized.json_str;
      return stripUndefined(connection);
    }
    if (fileType === "excel" && normalized.excel_b64 !== undefined) {
      connection.content = normalized.excel_b64;
      return stripUndefined(connection);
    }
    if (fileType === "parquet" && normalized.parquet_b64 !== undefined) {
      connection.content = normalized.parquet_b64;
      return stripUndefined(connection);
    }
    throw new RuntimeValidationError(
      "invalid_file_connector",
      "File connectors require a local path or inline content matching their declared type.",
      { type: fileType },
    );
  }
  if (rawType === "rest" || rawType === "api") {
    normalized.type = "rest_api";
    normalized.url = runtimeRestUrl(normalized);
    delete normalized.base_url;
    return stripUndefined(normalized);
  }
  if (OBJECT_STORAGE_TYPES.has(rawType)) {
    normalized.type = rawType;
    if (normalized.format !== undefined && normalized.file_type === undefined) {
      normalized.file_type = normalized.format;
      delete normalized.format;
    }
    return stripUndefined(normalized);
  }
  if (SQL_PROVIDER_TYPES.has(rawType)) {
    const provider = rawType !== "sql" ? rawType : String(normalized.provider ?? "").trim().toLowerCase();
    normalized.type = "sql";
    if (provider && provider !== "sql") {
      normalized.provider = provider;
    }
    normalized.connection_string = runtimeSqlConnectionString(provider || "sql", normalized);
    delete normalized.host;
    delete normalized.port;
    delete normalized.database;
    delete normalized.user;
    delete normalized.username;
    delete normalized.password;
    normalized.query = runtimeSqlQuery(normalized);
    return stripUndefined(normalized);
  }
  if (!rawType) {
    throw new RuntimeValidationError(
      "missing_connection_type",
      "API and self_hosted source descriptors require an explicit connector type or a direct source payload.",
    );
  }
  return stripUndefined(normalized);
}

function normalizeApiSourcePayload(
  source: Record<string, unknown>,
  explicitName?: string,
): Record<string, unknown> {
  const rawSource = isCanonicalConnectorEnvelope(source)
    ? flattenConnectorEnvelope(source)
    : stripUndefined({ ...source });
  const payload = { ...rawSource };
  const hasDirectSourceKeys = Object.keys(payload).some(key => DIRECT_API_SOURCE_KEYS.has(key));
  payload.name = runtimeApiSourceName(payload, explicitName);
  if (payload.connection && typeof payload.connection === "object" && !Array.isArray(payload.connection)) {
    payload.connection = normalizeRuntimeConnection(payload.connection as Record<string, unknown>);
    return payload;
  }
  if (hasDirectSourceKeys) {
    return payload;
  }
  return {
    name: payload.name,
    connection: normalizeRuntimeConnection(rawSource),
  };
}

function canonicalizeCsvHeaders(headers: string[]): string[] {
  const counts = new Map<string, number>();
  return headers.map(header => {
    const baseName = header.trim() || "Unnamed_Column";
    const nextCount = (counts.get(baseName) ?? 0) + 1;
    counts.set(baseName, nextCount);
    return nextCount === 1 ? baseName : `${baseName}__${nextCount}`;
  });
}

function baseHeaderName(field: string): string {
  return field.split("__", 1)[0];
}

function csvFieldTokens(field: string): Set<string> {
  return new Set(field.toLowerCase().match(CSV_TOKEN_RE) ?? []);
}

function csvIsIdentifierField(field: string): boolean {
  const tokens = csvFieldTokens(field);
  if (tokens.size === 0) return false;
  if (["zip", "postal"].some(token => tokens.has(token))) return true;
  if (["uuid", "guid", "serial", "sku", "cage"].some(token => tokens.has(token))) return true;
  if (["id", "key", "ref"].some(token => tokens.has(token))) return true;
  if (tokens.has("part") && ["number", "num", "nbr", "code"].some(token => tokens.has(token))) return true;
  if ((tokens.has("invoice") || tokens.has("account")) && ![...MEASURE_TOKENS].some(token => tokens.has(token))) {
    return true;
  }
  if (tokens.has("order") && ![...MEASURE_TOKENS].some(token => tokens.has(token))) return true;
  if (tokens.has("code") && ![...MEASURE_TOKENS].some(token => tokens.has(token))) return true;
  if (tokens.has("number") && ![...MEASURE_TOKENS].some(token => tokens.has(token))) return true;
  if (tokens.has("item") && ![...MEASURE_TOKENS].some(token => tokens.has(token))) return true;
  return false;
}

function coerceCsvScalar(field: string, value: unknown): unknown {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value;

  const raw = String(value).trim();
  if (!raw) return "";
  if (raw.length >= 16 && CSV_INT_RE.test(raw)) return raw;
  if (CSV_LEADING_ZERO_INT_RE.test(raw)) return raw;
  if (csvIsIdentifierField(field) && !raw.includes("%")) return raw;

  let normalized = raw.replace(/,/g, "");
  const negative = normalized.startsWith("(") && normalized.endsWith(")");
  if (negative) {
    normalized = normalized.slice(1, -1).trim();
  }
  normalized = normalized.replace(CSV_CURRENCY_PREFIX_RE, "");

  if (CSV_INT_RE.test(normalized)) {
    const parsed = Number.parseInt(normalized, 10);
    return negative ? -parsed : parsed;
  }
  if (normalized.endsWith("%")) {
    return raw;
  }
  if (CSV_FLOAT_RE.test(normalized)) {
    const parsed = Number.parseFloat(normalized);
    return negative ? -parsed : parsed;
  }
  return raw;
}

function looksLikeHeaderAliasRow(fieldNames: string[], values: unknown[]): boolean {
  const comparableThreshold = Math.min(
    HEADER_ALIAS_MAX_COLUMNS,
    Math.max(HEADER_ALIAS_MIN_COLUMNS, fieldNames.length),
  );
  if (fieldNames.length < HEADER_ALIAS_MIN_COLUMNS) {
    return false;
  }

  const scores: number[] = [];
  for (const [index, fieldName] of fieldNames.entries()) {
    const raw = String(values[index] ?? "").trim();
    if (!raw) continue;
    const valueTokens = csvFieldTokens(raw);
    if (valueTokens.size === 0) continue;
    const headerTokens = csvFieldTokens(baseHeaderName(fieldName));
    if (headerTokens.size === 0) continue;
    if (csvIsIdentifierField(fieldName)) {
      const unmatchedTokens = [...valueTokens].filter(token => !headerTokens.has(token));
      if (unmatchedTokens.some(token => /\d/.test(token))) {
        return false;
      }
    }
    const overlap = [...headerTokens].filter(token => valueTokens.has(token)).length / valueTokens.size;
    scores.push(overlap);
  }

  if (scores.length < comparableThreshold) {
    return false;
  }

  const matching = scores.filter(score => score >= HEADER_ALIAS_MATCH_SCORE).length;
  return (
    matching / scores.length >= HEADER_ALIAS_MIN_MATCH_RATIO &&
    scores.reduce((sum, score) => sum + score, 0) / scores.length >= HEADER_ALIAS_AVG_SCORE
  );
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;
  let index = 0;
  const normalizedText = text.replace(/^\ufeff/, "");

  const pushCell = (): void => {
    currentRow.push(currentCell);
    currentCell = "";
  };

  const pushRow = (): void => {
    pushCell();
    if (currentRow.length > 1 || currentRow.some(value => value.length > 0)) {
      rows.push(currentRow);
    }
    currentRow = [];
  };

  while (index < normalizedText.length) {
    const char = normalizedText[index];
    if (inQuotes) {
      if (char === "\"") {
        if (normalizedText[index + 1] === "\"") {
          currentCell += "\"";
          index += 2;
          continue;
        }
        inQuotes = false;
        index += 1;
        continue;
      }
      currentCell += char;
      index += 1;
      continue;
    }

    if (char === "\"") {
      inQuotes = true;
      index += 1;
      continue;
    }
    if (char === ",") {
      pushCell();
      index += 1;
      continue;
    }
    if (char === "\r") {
      if (normalizedText[index + 1] === "\n") {
        index += 1;
      }
      pushRow();
      index += 1;
      continue;
    }
    if (char === "\n") {
      pushRow();
      index += 1;
      continue;
    }
    currentCell += char;
    index += 1;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    pushRow();
  }
  return rows;
}

function parseCsvText(text: string): LocalRecord[] {
  if (!text.trim()) {
    return [];
  }
  const rows = parseCsvRows(text);
  if (rows.length === 0) {
    return [];
  }
  const headers = canonicalizeCsvHeaders(rows[0]);
  const dataRows = rows.slice(1);
  if (dataRows.length === 0) {
    return [];
  }
  const actualRows = looksLikeHeaderAliasRow(headers, dataRows[0]) ? dataRows.slice(1) : dataRows;
  return actualRows.map(values => {
    const record: LocalRecord = {};
    headers.forEach((header, index) => {
      record[header] = coerceCsvScalar(header, values[index] ?? "");
    });
    return record;
  });
}

function parseJsonText(text: string): LocalRecord[] {
  const parsed = JSON.parse(text) as unknown;
  if (Array.isArray(parsed)) {
    return parsed.filter((value): value is LocalRecord => Boolean(value) && typeof value === "object");
  }
  if (parsed && typeof parsed === "object") {
    return [parsed as LocalRecord];
  }
  throw new RuntimeValidationError("unsupported_json_source", "JSON local sources must contain an object or array of objects.");
}

async function readSqliteSource(source: Record<string, unknown>): Promise<LocalRecord[]> {
  const descriptorPath = sourceDescriptorPath(source);
  if (!descriptorPath) {
    throw new RuntimeValidationError(
      "invalid_local_source",
      "Local SQLite descriptors require a path or sqlite connection_string.",
    );
  }
  const tableCandidate = source.table;
  const queryCandidate = source.query;
  const hasTable = typeof tableCandidate === "string" && tableCandidate.trim().length > 0;
  const hasQuery = typeof queryCandidate === "string" && queryCandidate.trim().length > 0;
  if (hasTable === hasQuery) {
    throw new RuntimeValidationError(
      "invalid_local_source",
      "Local SQLite descriptors must include exactly one of table or query.",
    );
  }
  if (
    hasQuery &&
    !String(queryCandidate).trim().toLowerCase().startsWith("select") &&
    !String(queryCandidate).trim().toLowerCase().startsWith("with")
  ) {
    throw new RuntimeValidationError(
      "invalid_local_source",
      "Local SQLite query descriptors must use a read-only SELECT or WITH statement.",
    );
  }

  let DatabaseSyncCtor: new (path: string) => {
    prepare(sql: string): { all(): Array<Record<string, unknown>> };
    close(): void;
  };
  try {
    const sqliteModule = await import("node:sqlite");
    DatabaseSyncCtor = sqliteModule.DatabaseSync as typeof DatabaseSyncCtor;
  } catch (error) {
    throw new RuntimeValidationError(
      "unsupported_local_source",
      "Local SQLite descriptors require a Node runtime with node:sqlite support.",
      { error: error instanceof Error ? error.message : String(error) },
    );
  }

  const sql = hasQuery
    ? String(queryCandidate).trim()
    : `SELECT * FROM "${String(tableCandidate).replace(/"/g, "\"\"")}"`;
  const database = new DatabaseSyncCtor(resolvePath(descriptorPath));
  try {
    return database.prepare(sql).all().map(row => ({ ...row }));
  } catch (error) {
    throw new RuntimeValidationError(
      "invalid_local_source",
      "Unable to read the requested local SQLite source.",
      { error: error instanceof Error ? error.message : String(error), path: descriptorPath },
    );
  } finally {
    database.close();
  }
}

function readLocalSource(source: string): LocalRecord[] {
  const absolutePath = resolvePath(source);
  let text: string;
  try {
    text = readFileSync(absolutePath, "utf8");
  } catch (error) {
    throw new RuntimeValidationError(
      "local_source_not_found",
      "Local Runtime.connect() could not read the requested source path.",
      {
        source,
        error: error instanceof Error ? error.message : String(error),
      },
    );
  }
  const suffix = extname(absolutePath).toLowerCase();
  if (suffix === ".csv") {
    return parseCsvText(text);
  }
  if (suffix === ".json") {
    return parseJsonText(text);
  }
  throw new RuntimeValidationError(
    "unsupported_local_source",
    "Local Runtime.connect() currently supports only CSV and JSON file paths.",
    { source, suffix },
  );
}

function localSourceName(
  source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
  index: number,
): string {
  if (typeof source === "string") {
    return source.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, "") || `source_${index}`;
  }
  if (Array.isArray(source)) {
    return `source_${index}`;
  }
  const sourceRecord = isCanonicalConnectorEnvelope(source as Record<string, unknown>)
    ? flattenConnectorEnvelope(source as Record<string, unknown>)
    : (source as Record<string, unknown>);
  const explicitName = sourceRecord.name;
  if (typeof explicitName === "string" && explicitName.trim()) {
    return explicitName.trim();
  }
  const descriptorPath = sourceDescriptorPath(sourceRecord);
  if (descriptorPath) {
    const baseName =
      descriptorPath.split(/[\\/]/).pop()?.replace(/\.[^.]+$/, "") || `source_${index}`;
    const tableCandidate = sourceRecord.table;
    if (typeof tableCandidate === "string" && tableCandidate.trim()) {
      return `${baseName}_${tableCandidate.trim()}`;
    }
    if (typeof sourceRecord.query === "string") {
      return `${baseName}_query`;
    }
    return baseName;
  }
  if (Array.isArray(sourceRecord.records)) {
    return `source_${index}`;
  }
  return `source_${index}`;
}

export function renderSourceImportPreview(
  registration: SourceRegistrationResponse,
  options: {
    sourceRef?: string;
    mode?: RuntimeMode;
    color?: boolean;
  } = {},
): string {
  const fields = registrationFields(registration);
  const preview =
    fields.length === 0
      ? "(no schema fields detected)"
      : fields.length > 3
        ? `${fields.slice(0, 3).join(", ")}, +${fields.length - 3} more`
        : fields.join(", ");
  const sourceName = registration.name ?? registration.dataset_name ?? "source";
  const status = registration.status ?? "ready";
  const schemaRevision = registration.planner_schema_revision ?? "n/a";
  const latency = typeof registration.latency_ms === "number" ? `${registration.latency_ms.toFixed(3)}ms` : "n/a";
  const rowCount = typeof registration.row_count === "number" ? String(registration.row_count) : "unknown";
  return runtimeBanner(
    "Algenta Source Import",
    [
      `Mode: ${options.mode ?? "local"} | Status: ${status}`,
      `Source: ${sourceName}`,
      `Origin: ${options.sourceRef ?? "source"}`,
      `Rows: ${rowCount} | Fields: ${fields.length}`,
      `Preview: ${preview}`,
      `Schema: ${schemaRevision.slice(0, 12)} | Latency: ${latency}`,
    ],
    options.color,
  );
}

export function renderSourceBundlePreview(
  registrations: SourceRegistrationResponse[],
  failures: ImportFailureResult[],
  options: { mode?: RuntimeMode; color?: boolean } = {},
): string {
  const lines = [
    `Mode: ${options.mode ?? "local"} | Imported: ${registrations.length} | Failures: ${failures.length}`,
    `Rows: ${registrations.reduce((sum, registration) => sum + (registration.row_count ?? 0), 0)}`,
    "Sources:",
    ...(
      registrations.length > 0
        ? registrations.map(registration => `- ${registration.name ?? registration.dataset_name ?? "source"}`)
        : ["- (no sources imported)"]
    ),
    "Shared fields:",
    ...(
      bundleOverlapLines(registrations).length > 0
        ? bundleOverlapLines(registrations).map(line => `- ${line}`)
        : ["- No deterministic shared-field overlaps detected."]
    ),
    "Failures:",
    ...(
      failures.length > 0
        ? failures.slice(0, 3).map(failure => `- ${(failure.name ?? failure.sourceRef)}: ${failure.code}`)
        : ["- None"]
    ),
  ];
  return runtimeBanner("Algenta Source Bundle", lines, options.color);
}

function exactPlanHash(plan: ResolvedPlan): string {
  return stableHash(plan);
}

function looksLikeResolvedPlan(value: unknown): value is ResolvedPlan {
  if (!value || typeof value !== "object") {
    return false;
  }
  const plan = value as Record<string, unknown>;
  return (
    typeof plan.source_name === "string" &&
    typeof plan.metric_column === "string" &&
    typeof plan.schema_revision === "string"
  );
}

function intentSignature(
  sourceName: string,
  request: Record<string, unknown>,
  schemaRevision: string,
): string {
  return stableHash({
    source_name: sourceName,
    schema_revision: schemaRevision,
    metric: normalizeText(String(request.metric ?? "")),
    group_by: normalizeText(String(request.group_by ?? "")),
    aggregation: resolveAggregation(request),
    limit: request.limit ?? null,
    order: String(request.order ?? "desc").toLowerCase(),
    constraints: request.constraints ?? {},
    filter: request.filter ?? {},
  });
}

async function coerceRecords(
  source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
): Promise<LocalRecord[]> {
  if (typeof source === "string") {
    return readLocalSource(source);
  }
  if (Array.isArray(source)) {
    return source.map(record => ({ ...record }));
  }
  const sourceRecord = normalizeLocalRuntimeSource(source as Record<string, unknown>);
  if (Array.isArray(sourceRecord.records)) {
    return sourceRecord.records
      .filter((record): record is LocalRecord => Boolean(record) && typeof record === "object")
      .map(record => ({ ...record }));
  }
  const provider = String(sourceRecord.provider ?? sourceRecord.type ?? "").trim().toLowerCase();
  if (provider === "sqlite" || provider === "sqlite3" || typeof sourceRecord.connection_string === "string") {
    return readSqliteSource(sourceRecord);
  }
  const descriptorPath = sourceDescriptorPath(sourceRecord);
  if (descriptorPath) {
    return readLocalSource(descriptorPath);
  }
  return [{ ...source }];
}

function aggregateValues(values: number[], aggregation: string): number {
  switch (aggregation) {
    case "count":
      return values.length;
    case "avg":
      return values.length === 0 ? 0 : values.reduce((sum, value) => sum + value, 0) / values.length;
    case "min":
      return values.length === 0 ? 0 : Math.min(...values);
    case "max":
      return values.length === 0 ? 0 : Math.max(...values);
    case "sum":
    default:
      return values.reduce((sum, value) => sum + value, 0);
  }
}

function executePlan(
  records: LocalRecord[],
  metricColumn: string,
  groupColumn: string | undefined | null,
  aggregation: string,
  limit: number,
): Array<Record<string, unknown>> {
  if (!groupColumn) {
    const values = records
      .map(record => numericValue(record[metricColumn]))
      .filter((value): value is number => value !== null);
    return [{ [metricColumn]: aggregateValues(values, aggregation) }];
  }

  const groups = new Map<string, { label: unknown; values: number[] }>();
  for (const record of records) {
    const label = record[groupColumn];
    const key = stableStringify(label);
    if (!groups.has(key)) {
      groups.set(key, { label, values: [] });
    }
    const parsed = numericValue(record[metricColumn]);
    if (parsed !== null) {
      groups.get(key)?.values.push(parsed);
    }
  }

  return [...groups.values()]
    .map(group => ({
      [groupColumn]: group.label,
      [metricColumn]: aggregateValues(group.values, aggregation),
    }))
    .sort((left, right) => Number(right[metricColumn] ?? 0) - Number(left[metricColumn] ?? 0))
    .slice(0, limit);
}

export class RuntimeError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "RuntimeError";
  }

  public get validationErrors(): Array<Record<string, unknown>> {
    const directErrors = extractRuntimeValidationErrors(this.details);
    if (directErrors.length > 0) {
      return directErrors;
    }
    const sourceDetails = this.details.source_error_details;
    return extractRuntimeValidationErrors(sourceDetails);
  }

  public get fieldErrors(): Array<Record<string, unknown>> {
    return this.validationErrors;
  }
}

export class RuntimeConfigurationError extends RuntimeError {
  constructor(code: string, message: string, details: Record<string, unknown> = {}) {
    super(message, code, details);
    this.name = "RuntimeConfigurationError";
  }
}

export class RuntimeValidationError extends RuntimeError {
  constructor(code: string, message: string, details: Record<string, unknown> = {}) {
    super(message, code, details);
    this.name = "RuntimeValidationError";
  }
}

function extractRuntimeValidationErrors(
  value: unknown,
): Array<Record<string, unknown>> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  const validationErrors = (value as { validation_errors?: unknown }).validation_errors;
  if (!Array.isArray(validationErrors)) {
    return [];
  }
  return validationErrors.filter(
    (item): item is Record<string, unknown> =>
      !!item && typeof item === "object" && !Array.isArray(item),
  );
}

export class Runtime {
  private readonly mode: RuntimeMode;
  private readonly apiKey?: string;
  private readonly enforceLimits: boolean;
  private readonly baseUrl?: string;
  private readonly clientInstance?: DecisionEngineClient;
  private readonly clientConfig: DecisionEngineClientConfig;
  private readonly localSources = new Map<string, LocalSource>();
  private readonly apiRegistrationsByName = new Map<string, SourceRegistrationResponse>();
  private readonly apiRegistrationsByDataset = new Map<string, SourceRegistrationResponse>();
  private readonly capabilityAdapters = new Map<string, CapabilityAdapter>();
  private readonly localCapabilityBindings = new Map<string, CapabilityBindingResponse>();
  private readonly localCapabilityCatalog = new Map<string, CapabilityCatalogEntry>();
  private readonly localCapabilityAuthSessions = new Map<
    string,
    {
      session_id: string;
      binding_id: string;
      provider_id: string;
      authorize_url: string;
      expires_at: string;
      requested_scopes: string[];
    }
  >();
  private readonly localCapabilityOutcomes: CapabilityOutcomeRecord[] = [];
  private lazyClient?: DecisionEngineClient;
  private localLicense?: LocalRuntimeLicense;
  private licensePromise?: Promise<LocalRuntimeLicense>;
  private creditRefreshPromise?: Promise<void>;

  constructor(config: RuntimeConfig = {}) {
    this.mode = config.mode ?? "local";
    if (!["local", "api", "self_hosted"].includes(this.mode)) {
      throw new RuntimeValidationError("invalid_mode", "Invalid mode. Expected 'local', 'api', or 'self_hosted'.", {
        mode: config.mode,
      });
    }
    if (deploymentMode() === "air_gapped" && (telemetryMode() === "control_plane_sync" || meteringMode() === "control_plane_sync")) {
      throw new RuntimeConfigurationError(
        "air_gapped_control_plane_sync_forbidden",
        "air_gapped deployments cannot use control_plane_sync telemetry or metering.",
      );
    }
    const controlPlaneSyncEnabled =
      telemetryMode() === "control_plane_sync" || meteringMode() === "control_plane_sync";
    const explicitControlPlaneUrl = (runtimeEnv().ALGENTA_CONTROL_PLANE_URL ?? "").trim();
    const resolvedControlPlaneUrl = resolveControlPlaneBaseUrl(config.baseUrl);
    if (controlPlaneSyncEnabled && !resolvedControlPlaneUrl) {
      throw new RuntimeConfigurationError(
        "control_plane_url_required",
        "control_plane_sync requires a non-empty ALGENTA_CONTROL_PLANE_URL or explicit baseUrl.",
      );
    }
    if ((controlPlaneSyncEnabled || explicitControlPlaneUrl) && resolvedControlPlaneUrl) {
      try {
        validatedControlPlaneBaseUrl(config.baseUrl, {
          surface: "runtime_control_plane_config",
          record: false,
        });
      } catch (error) {
        if (error instanceof RuntimeEgressPolicyDeniedError) {
          throw new RuntimeConfigurationError(
            "egress_policy_denied",
            `Control-plane egress is blocked by the active privacy policy. Reason: ${error.decision.reason}.`,
            {
              reason: error.decision.reason,
              surface: error.decision.surface,
              egress_class: error.decision.egressClass,
            },
          );
        }
        if (error instanceof Error) {
          throw new RuntimeConfigurationError("control_plane_url_invalid", error.message);
        }
        throw error;
      }
    }
    const envApiKey =
      typeof globalThis !== "undefined" &&
      "process" in globalThis &&
      (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
        ? (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
            ?.ALGENTA_API_KEY ??
          (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env
            ?.DE_API_KEY
        : undefined;
    const explicitApiKey = Object.prototype.hasOwnProperty.call(config, "apiKey");
    this.apiKey = config.apiKey ?? envApiKey;
    this.enforceLimits = config.enforceLimits ?? (this.mode === "local" && explicitApiKey);
    if (this.mode === "self_hosted") {
      if (typeof config.baseUrl !== "string" || !config.baseUrl.trim()) {
        throw new RuntimeConfigurationError(
          "self_hosted_base_url_required",
          "Runtime({ mode: 'self_hosted' }) requires an explicit baseUrl.",
        );
      }
      this.baseUrl = resolveClientBaseUrl(
        config.baseUrl.trim(),
        "Runtime({ mode: 'self_hosted' })",
      );
    } else if (this.mode === "api") {
      this.baseUrl = resolveClientBaseUrl(
        config.baseUrl,
        "Runtime({ mode: 'api' })",
      );
    } else {
      this.baseUrl = config.baseUrl;
    }
    this.clientInstance = config.client;
    this.clientConfig = {
      apiKey: this.apiKey,
      baseUrl: this.baseUrl,
      timeout: config.timeout,
      maxRetries: config.maxRetries,
      defaultHeaders: config.defaultHeaders,
    };
    for (const adapter of config.capabilityAdapters ?? []) {
      this.registerCapabilityAdapter(adapter);
    }
  }

  toString(): string {
    return `Runtime(mode=${JSON.stringify(this.mode)}, apiKey=${this.apiKey ? "set" : "not set"})`;
  }

  private usesApiTransport(): boolean {
    return this.mode === "api" || this.mode === "self_hosted";
  }

  private requireApiTransport(methodName: string): void {
    if (this.usesApiTransport()) {
      return;
    }
    throw new RuntimeConfigurationError(
      "local_mode_not_supported",
      `${methodName}() is not supported for Runtime({ mode: 'local' }). Use Runtime({ mode: 'api', apiKey: '...' }) or Runtime({ mode: 'self_hosted', baseUrl: '...' }).`,
    );
  }

  private nowIso(): string {
    return new Date().toISOString();
  }

  private dedupeCapabilityStrings(values: Array<string | undefined | null>): string[] {
    const ordered: string[] = [];
    const seen = new Set<string>();
    for (const value of values) {
      if (typeof value !== "string") continue;
      const normalized = value.trim();
      if (!normalized || seen.has(normalized)) continue;
      seen.add(normalized);
      ordered.push(normalized);
    }
    return ordered;
  }

  private inferLocalProviderType(
    kind: CapabilityCatalogEntry["kind"],
  ): CapabilityProviderResponse["provider_type"] {
    switch (kind) {
      case "dataset":
        return "data_connector";
      case "mcp_tool":
      case "mcp_resource":
      case "mcp_prompt":
        return "mcp_provider";
      case "skill":
        return "skill_pack";
      case "native_tool":
        return "native_tool_pack";
      case "runtime_library":
      default:
        return "runtime_library_pack";
    }
  }

  private localBindingIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string {
    if (descriptor.binding_id?.trim()) return descriptor.binding_id.trim();
    const seed = JSON.stringify({
      capability_id: descriptor.capability_id,
      provider_id: descriptor.provider_id,
      name: descriptor.name,
      kind: descriptor.kind,
    });
    return `local-binding-${sha256Hex(seed).slice(0, 24)}`;
  }

  private localProfileIdForDescriptor(descriptor: CapabilityAdapterDescriptor): string {
    if (descriptor.profile_id?.trim()) return descriptor.profile_id.trim();
    const providerType = this.inferLocalProviderType(descriptor.kind);
    return `profile.${providerType}.local`;
  }

  private ensureLocalBindingFromAdapter(adapter: CapabilityAdapter): CapabilityBindingResponse {
    const descriptor = adapter.descriptor;
    const bindingId = this.localBindingIdForDescriptor(descriptor);
    const existing = this.localCapabilityBindings.get(bindingId);
    if (existing) {
      return existing;
    }
    const now = this.nowIso();
    const binding: CapabilityBindingResponse = {
      binding_id: bindingId,
      provider_id: descriptor.provider_id,
      profile_id: this.localProfileIdForDescriptor(descriptor),
      binding_name: descriptor.binding_name ?? descriptor.name,
      scope: "workspace",
      scope_ref: "local",
      status: "ready",
      execution_owner: descriptor.execution_owner ?? "client_managed",
      config: null,
      customer_metadata: descriptor.customer_metadata ?? null,
      system_managed: false,
      last_tested_at: now,
      last_discovered_at: now,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
      created_at: now,
      updated_at: now,
    };
    this.localCapabilityBindings.set(binding.binding_id, binding);
    return binding;
  }

  private capabilityEntryFromAdapter(adapter: CapabilityAdapter): CapabilityCatalogEntry {
    const descriptor = adapter.descriptor;
    const binding = this.ensureLocalBindingFromAdapter(adapter);
    const manifestHash = sha256Hex(JSON.stringify(descriptor));
    return {
      capability_id: descriptor.capability_id,
      provider_id: descriptor.provider_id,
      profile_id: binding.profile_id,
      binding_id: binding.binding_id,
      kind: descriptor.kind,
      name: descriptor.name,
      description: descriptor.description ?? null,
      implementation_kind: descriptor.implementation_kind ?? "callable",
      execution_owner: descriptor.execution_owner ?? "client_managed",
      input_schema_ref:
        descriptor.input_schema_ref ?? `capability://${descriptor.capability_id}/input`,
      output_schema_ref:
        descriptor.output_schema_ref ?? `capability://${descriptor.capability_id}/output`,
      side_effect_class: descriptor.side_effect_class ?? "read_only",
      risk_level: descriptor.risk_level ?? "low",
      required_policy: descriptor.required_policy ?? "policy.capability.execute",
      replayability: descriptor.replayability ?? "deterministic",
      approval_required: descriptor.approval_required ?? false,
      trust_tier: descriptor.trust_tier ?? "customer_managed",
      manifest_hash: manifestHash,
      artifact_affinities: this.dedupeCapabilityStrings(descriptor.artifact_affinities ?? []),
      tags: this.dedupeCapabilityStrings(descriptor.tags ?? []),
      required_binding_ids: [binding.binding_id],
      selected_tool_name: descriptor.selected_tool_name ?? null,
      instruction_artifact_ref: descriptor.instruction_artifact_ref ?? null,
      binding_status: binding.status,
      discovered_at: binding.last_discovered_at ?? binding.created_at,
      customer_metadata: descriptor.customer_metadata ?? null,
      instruction_text: descriptor.instruction_text ?? null,
    };
  }

  registerCapabilityAdapter(adapter: CapabilityAdapter): void {
    const entry = this.capabilityEntryFromAdapter(adapter);
    this.capabilityAdapters.set(entry.capability_id, adapter);
    this.localCapabilityCatalog.set(entry.capability_id, entry);
  }

  private localBindingsArray(): CapabilityBindingResponse[] {
    return Array.from(this.localCapabilityBindings.values()).sort((left, right) =>
      left.binding_name.localeCompare(right.binding_name),
    );
  }

  private localCapabilitiesArray(): CapabilityCatalogEntry[] {
    return Array.from(this.localCapabilityCatalog.values()).sort((left, right) =>
      left.name.localeCompare(right.name),
    );
  }

  private localCapabilityEntryFromManifest(
    payload: Record<string, unknown>,
    binding: CapabilityBindingResponse,
  ): CapabilityCatalogEntry {
    const capabilityId = String(payload.capability_id ?? "").trim();
    if (!capabilityId) {
      throw new RuntimeValidationError(
        "invalid_capability_manifest",
        "Local capability manifests require capability_id.",
      );
    }
    const kind = String(payload.kind ?? "").trim() as CapabilityCatalogEntry["kind"];
    if (!kind) {
      throw new RuntimeValidationError(
        "invalid_capability_manifest",
        "Local capability manifests require kind.",
      );
    }
    const manifestHash = sha256Hex(JSON.stringify(payload));
    const instructionText =
      typeof payload.instruction === "string" && payload.instruction.trim()
        ? payload.instruction
        : null;
    return {
      capability_id: capabilityId,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      binding_id: binding.binding_id,
      kind,
      name: String(payload.name ?? capabilityId),
      description: typeof payload.description === "string" ? payload.description : null,
      implementation_kind:
        (String(payload.implementation_kind ?? "callable") as CapabilityCatalogEntry["implementation_kind"]),
      execution_owner:
        (String(payload.execution_owner ?? binding.execution_owner) as CapabilityCatalogEntry["execution_owner"]),
      input_schema_ref: String(
        payload.input_schema_ref ?? `capability://${capabilityId}/input`,
      ),
      output_schema_ref: String(
        payload.output_schema_ref ?? `capability://${capabilityId}/output`,
      ),
      side_effect_class:
        (String(payload.side_effect_class ?? "read_only") as CapabilityCatalogEntry["side_effect_class"]),
      risk_level: (String(payload.risk_level ?? "low") as CapabilityCatalogEntry["risk_level"]),
      required_policy: String(payload.required_policy ?? "policy.capability.execute"),
      replayability:
        (String(payload.replayability ?? "deterministic") as CapabilityCatalogEntry["replayability"]),
      approval_required: Boolean(payload.approval_required ?? false),
      trust_tier: String(payload.trust_tier ?? "customer_managed"),
      manifest_hash: manifestHash,
      artifact_affinities: this.dedupeCapabilityStrings(
        Array.isArray(payload.artifact_affinities)
          ? (payload.artifact_affinities as Array<string | undefined | null>)
          : [],
      ),
      tags: this.dedupeCapabilityStrings(
        Array.isArray(payload.tags) ? (payload.tags as Array<string | undefined | null>) : [],
      ),
      required_binding_ids: [binding.binding_id],
      selected_tool_name:
        typeof payload.selected_tool_name === "string" ? payload.selected_tool_name : null,
      instruction_artifact_ref:
        typeof payload.instruction_artifact_ref === "string"
          ? payload.instruction_artifact_ref
          : instructionText
            ? `artifact://local-capability/${manifestHash}/${capabilityId}`
            : null,
      binding_status: binding.status,
      discovered_at: this.nowIso(),
      customer_metadata:
        payload.customer_metadata && typeof payload.customer_metadata === "object" && !Array.isArray(payload.customer_metadata)
          ? (payload.customer_metadata as Record<string, unknown>)
          : null,
      instruction_text: instructionText,
    };
  }

  private discoverLocalBinding(
    binding:
      | CapabilityBindingResponse
      | (CapabilityBindingPreviewRequest & {
          binding_id?: string;
          binding_name?: string;
          status?: BindingStatus;
        }),
  ): CapabilityDiscoverResponse {
    const manifest =
      binding.config && typeof binding.config === "object" && !Array.isArray(binding.config)
        ? (binding.config as Record<string, unknown>).manifest
        : null;
    const bindingId =
      "binding_id" in binding && typeof binding.binding_id === "string"
        ? binding.binding_id
        : null;
    const bindingName =
      "binding_name" in binding && typeof binding.binding_name === "string"
        ? binding.binding_name
        : "preview";
    const bindingStatus =
      "status" in binding && binding.status ? binding.status : ("ready" as BindingStatus);
    const discoveredAt = this.nowIso();

    if (manifest && typeof manifest === "object" && !Array.isArray(manifest)) {
      const rawCapabilities = Array.isArray((manifest as { capabilities?: unknown }).capabilities)
        ? ((manifest as { capabilities: unknown[] }).capabilities as unknown[])
        : [];
      const normalizedBinding: CapabilityBindingResponse = {
        binding_id: bindingId ?? `preview-${sha256Hex(JSON.stringify(binding)).slice(0, 12)}`,
        provider_id: binding.provider_id,
        profile_id: binding.profile_id,
        binding_name: bindingName,
        scope: ("scope" in binding && binding.scope ? binding.scope : "workspace") as BindingScope,
        scope_ref:
          ("scope_ref" in binding && typeof binding.scope_ref === "string"
            ? binding.scope_ref
            : "local"),
        status: bindingStatus,
        execution_owner:
          ("execution_owner" in binding && binding.execution_owner
            ? binding.execution_owner
            : "client_managed") as ExecutionOwner,
        config: binding.config ?? null,
        customer_metadata:
          ("customer_metadata" in binding ? binding.customer_metadata ?? null : null) as
            | Record<string, unknown>
            | null,
        system_managed: false,
        last_tested_at: discoveredAt,
        last_discovered_at: discoveredAt,
        authorized_at: null,
        quarantine_reason: null,
        discovery_error_message: null,
        test_error_message: null,
        created_at: discoveredAt,
        updated_at: discoveredAt,
      };
      const capabilities = rawCapabilities
        .filter(item => item && typeof item === "object" && !Array.isArray(item))
        .map(item =>
          this.localCapabilityEntryFromManifest(item as Record<string, unknown>, normalizedBinding),
        );
      const manifestHash = sha256Hex(JSON.stringify(rawCapabilities));
      return {
        binding_id: bindingId,
        provider_id: binding.provider_id,
        profile_id: binding.profile_id,
        snapshot_id: null,
        binding_status: capabilities.length > 0 ? "ready" : "degraded",
        manifest_hash: manifestHash,
        capability_count: capabilities.length,
        discovered_at: discoveredAt,
        message: `Discovered ${capabilities.length} local manifest-backed capabilities.`,
        capabilities,
      };
    }

    const capabilities = this.localCapabilitiesArray().filter(
      entry =>
        entry.binding_id === bindingId ||
        (!bindingId &&
          entry.provider_id === binding.provider_id &&
          entry.profile_id === binding.profile_id),
    );
    const manifestHash = sha256Hex(
      JSON.stringify(capabilities.map(item => item.capability_id)),
    );
    return {
      binding_id: bindingId,
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      snapshot_id: null,
      binding_status: capabilities.length > 0 ? "ready" : "degraded",
      manifest_hash: manifestHash,
      capability_count: capabilities.length,
      discovered_at: discoveredAt,
      message: `Discovered ${capabilities.length} local adapter-backed capabilities.`,
      capabilities,
    };
  }

  private localProviderResponses(): CapabilityProviderResponse[] {
    const providers = new Map<string, CapabilityProviderResponse>();
    for (const binding of this.localBindingsArray()) {
      const sampleCapability = this.localCapabilitiesArray().find(
        entry => entry.binding_id === binding.binding_id,
      );
      const providerType = sampleCapability
        ? this.inferLocalProviderType(sampleCapability.kind)
        : "native_tool_pack";
      const existing = providers.get(binding.provider_id);
      const profile = {
        profile_id: binding.profile_id,
        provider_id: binding.provider_id,
        name: binding.binding_name,
        description: null,
        auth_kind: "none",
        default_execution_owner: binding.execution_owner,
        binding_scope_default: binding.scope,
        supported_binding_scopes: [binding.scope],
        profile_metadata: null,
      };
      if (existing) {
        if (!existing.profiles.some(item => item.profile_id === profile.profile_id)) {
          existing.profiles.push(profile);
        }
        continue;
      }
      providers.set(binding.provider_id, {
        provider_id: binding.provider_id,
        provider_type: providerType,
        name: binding.provider_id,
        description: "Local capability-plane provider",
        docs_url: null,
        auth_schema: { type: "none", fields: [] },
        certification_summary: { owner: "customer", certified: false },
        policy_summary: { route_authority: "capability_plane", execution_owner: "client_managed" },
        supported_execution_owners: [binding.execution_owner],
        install_metadata: { discovery_mode: "local_adapter" },
        customer_metadata: null,
        active: true,
        profiles: [profile],
      });
    }
    return Array.from(providers.values()).sort((left, right) =>
      left.provider_id.localeCompare(right.provider_id),
    );
  }

  private sourceRegistrationFromDatasetConnect(
    registration: DatasetConnectResult,
    datasetName: string,
  ): SourceRegistrationResponse {
    return {
      status: registration.status,
      source_id:
        typeof registration.source_id === "string" && registration.source_id.trim()
          ? registration.source_id.trim()
          : typeof registration.dataset_id === "string" && registration.dataset_id.trim()
            ? registration.dataset_id.trim()
            : null,
      dataset_id:
        typeof registration.dataset_id === "string" && registration.dataset_id.trim()
          ? registration.dataset_id.trim()
          : typeof registration.source_id === "string" && registration.source_id.trim()
            ? registration.source_id.trim()
            : null,
      name:
        typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name.trim()
          : datasetName,
      dataset_name:
        typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name.trim()
          : datasetName,
      schema: registration.schema ?? null,
      source_schema: registration.schema ?? null,
      latency_ms: registration.latency_ms ?? null,
      connection_id: registration.connection_id ?? null,
      connection_type: registration.connection_type ?? null,
      provider: registration.provider ?? null,
      selection: registration.selection ?? null,
      visibility: registration.visibility ?? null,
      row_count: null,
    };
  }

  private async connectWithManagedConnector(
    options: RuntimeConnectOptions,
  ): Promise<SourceRegistrationResponse> {
    this.requireApiTransport("connect");
    const hasInlineConnector = Boolean(options.connector);
    if (hasInlineConnector && !options.persist) {
      throw new RuntimeValidationError(
        "connector_persistence_required",
        "connect(connector=...) requires persist=true. Use testConnector() or browseConnector() for inline preview flows.",
      );
    }
    const datasetName = (options.datasetName ?? options.name ?? "").trim();
    if (!datasetName) {
      throw new RuntimeValidationError(
        "missing_dataset_name",
        "connect() requires datasetName or name when onboarding a connector-backed dataset.",
      );
    }
    const result = await this.client().connectData({
      dataset_name: datasetName,
      description: options.description,
      selection: options.selection,
      visibility: options.visibility,
      connection_name: options.connectionName,
      ...(options.connectorId ? { connection_id: options.connectorId } : {}),
      ...(options.connector ? { connector: options.connector } : {}),
    });
    if (result.status !== "ready") {
      const errorCode = result.status === "needs_selection" ? "selection_required" : `connect_${result.status}`;
      throw new RuntimeValidationError(
        errorCode,
        result.message ?? "Connector-backed dataset connection did not complete.",
        {
          status: result.status,
          choices: result.choices ?? [],
          labels: result.labels ?? {},
          discovery: result.discovery ?? {},
          connection_id: result.connection_id ?? null,
        },
      );
    }
    const registration = this.sourceRegistrationFromDatasetConnect(result, datasetName);
    const hydrated = await this.hydrateApiRegistration(registration);
    this.rememberApiRegistration(hydrated);
    return hydrated;
  }

  private normalizePreviewConnectorPayload(
    connector: Record<string, unknown>,
  ): { connector_type: string; config?: Record<string, unknown> } {
    const normalized = isCanonicalConnectorEnvelope(connector)
      ? flattenConnectorEnvelope(connector)
      : stripUndefined({ ...connector });
    const connectorType = String(
      normalized.type ?? normalized.connector_type ?? normalized.provider ?? "",
    )
      .trim()
      .toLowerCase()
      .replace(/-/g, "_");
    if (!connectorType) {
      throw new RuntimeValidationError(
        "invalid_connector",
        "Connector previews require an explicit connector type.",
        { field: "type" },
      );
    }
    const config = stripUndefined(
      Object.fromEntries(
        Object.entries(normalized).filter(([key]) => !["type", "connector_type", "provider"].includes(key)),
      ),
    );
    return Object.keys(config).length > 0
      ? { connector_type: connectorType, config }
      : { connector_type: connectorType };
  }

  async connect(
    source?: string | LocalRecord[] | LocalRecord | Record<string, unknown> | null,
    options: RuntimeConnectOptions = {},
  ): Promise<SourceRegistrationResponse> {
    const startMs = Date.now();
    if (options.connectorId || options.connector) {
      return this.connectWithManagedConnector(options);
    }
    if (this.usesApiTransport()) {
      if (!source || typeof source !== "object" || Array.isArray(source)) {
        throw new RuntimeValidationError(
          "api_connect_requires_source_descriptor",
          "API and self_hosted mode connect() expect a structured source descriptor.",
          { expected: "object", received: source === null ? "null" : Array.isArray(source) ? "array" : typeof source },
        );
      }
      const registration = await this.client().registerSource(normalizeApiSourcePayload(source, options.name), {
        description: options.description,
      });
      const hydrated = await this.hydrateApiRegistration(registration);
      this.rememberApiRegistration(hydrated);
      return hydrated;
    }

    if (source === null || source === undefined) {
      throw new RuntimeValidationError(
        "source_required",
        "Local Runtime.connect() requires a local source path, records array, or structured local descriptor.",
      );
    }

    const records = await coerceRecords(source);
    if (records.length === 0) {
      throw new RuntimeValidationError("empty_source", "Connected source is empty and cannot be queried.", {
        name: options.name ?? localSourceName(source, this.localSources.size),
      });
    }

    const name = options.name ?? localSourceName(source, this.localSources.size);
    const fields = orderedFields(records);
    const datasetId = stableHash({ name, fields }).slice(0, 24);
    const schemaRevision = stableHash({ datasetId, fields });
    this.localSources.set(name, {
      name,
      records,
      fields,
      schemaRevision,
      datasetId,
    });

    return {
      source_id: datasetId,
      dataset_id: datasetId,
      name,
      status: "ready",
      ingest_mode: "local",
      schema: { fields },
      source_schema: { fields },
      planner_cache_hit: false,
      planner_schema_revision: schemaRevision,
      planner_prewarm_ms: 0,
      latency_ms: roundLatency(startMs),
      row_count: records.length,
    };
  }

  registerSource(
    source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
    options: { name?: string; description?: string } = {},
  ): Promise<SourceRegistrationResponse> {
    return this.connect(source, options);
  }

  async connectMany(
    sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
    options: { names?: Array<string | undefined>; description?: string } = {},
  ): Promise<SourceRegistrationResponse[]> {
    if (options.names && options.names.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_names_length",
        "connectMany() names must match the number of sources.",
        { sources: sources.length, names: options.names.length },
      );
    }
    const registrations: SourceRegistrationResponse[] = [];
    for (const [index, source] of sources.entries()) {
      registrations.push(
        await this.connect(source, {
          name: options.names?.[index],
          description: options.description,
        }),
      );
    }
    return registrations;
  }

  async createConnector(request: {
    name: string;
    connectorType: string;
    config?: Record<string, unknown>;
    description?: string;
    visibility?: string;
  }): Promise<ConnectorInfo> {
    this.requireApiTransport("createConnector");
    return this.client().createConnector({
      name: request.name,
      connector_type: request.connectorType,
      config: request.config,
      description: request.description,
      visibility: request.visibility,
    });
  }

  async listConnectors(options: { page?: number; limit?: number } = {}): Promise<ConnectorListResult> {
    this.requireApiTransport("listConnectors");
    return this.client().listConnectors(options);
  }

  async getConnector(connectorId: string): Promise<ConnectorInfo> {
    this.requireApiTransport("getConnector");
    return this.client().getConnector(connectorId);
  }

  async updateConnector(
    connectorId: string,
    request: {
      name?: string;
      description?: string;
      visibility?: string;
      config?: Record<string, unknown>;
    },
  ): Promise<ConnectorInfo> {
    this.requireApiTransport("updateConnector");
    return this.client().updateConnector(connectorId, {
      name: request.name,
      description: request.description,
      visibility: request.visibility,
      config: request.config,
    });
  }

  async testConnector(connectorIdOrConnector: string | Record<string, unknown>): Promise<ConnectorTestInfo> {
    this.requireApiTransport("testConnector");
    if (typeof connectorIdOrConnector === "string") {
      return this.client().testConnector(connectorIdOrConnector);
    }
    return this.client().previewTestConnector(this.normalizePreviewConnectorPayload(connectorIdOrConnector));
  }

  async browseConnector(connectorIdOrConnector: string | Record<string, unknown>): Promise<ConnectorBrowseResult> {
    this.requireApiTransport("browseConnector");
    if (typeof connectorIdOrConnector === "string") {
      return this.client().browseConnector(connectorIdOrConnector);
    }
    return this.client().previewBrowseConnector(this.normalizePreviewConnectorPayload(connectorIdOrConnector));
  }

  async deleteConnector(connectorId: string): Promise<void> {
    this.requireApiTransport("deleteConnector");
    await this.client().deleteConnector(connectorId);
  }

  async createRepositorySnapshot(
    repositoryId: string,
    request: RepositorySnapshotCreateRequest,
  ): Promise<RepositorySnapshotResponse> {
    this.requireApiTransport("createRepositorySnapshot");
    return this.client().createRepositorySnapshot(repositoryId, request);
  }

  async getRepositoryIntelligenceCapabilities(): Promise<RepositoryIntelligenceCapabilitiesResponse> {
    this.requireApiTransport("getRepositoryIntelligenceCapabilities");
    return this.client().getRepositoryIntelligenceCapabilities();
  }

  async getRepositorySnapshot(
    repositoryId: string,
    snapshotId: string,
  ): Promise<RepositorySnapshotResponse> {
    this.requireApiTransport("getRepositorySnapshot");
    return this.client().getRepositorySnapshot(repositoryId, snapshotId);
  }

  async triageRepository(
    repositoryId: string,
    request: RepositoryTriageRequest,
  ): Promise<RepositoryTriageResponse> {
    this.requireApiTransport("triageRepository");
    return this.client().triageRepository(repositoryId, request);
  }

  async createRepositoryDecisionPlan(
    repositoryId: string,
    request: RepositoryDecisionPlanCreateRequest,
  ): Promise<RepositoryDecisionPlanRevisionResponse> {
    this.requireApiTransport("createRepositoryDecisionPlan");
    return this.client().createRepositoryDecisionPlan(repositoryId, request);
  }

  async queryRepositoryGraph(
    repositoryId: string,
    request: RepositoryGraphQueryRequest,
  ): Promise<RepositoryGraphQueryResponse> {
    this.requireApiTransport("queryRepositoryGraph");
    return this.client().queryRepositoryGraph(repositoryId, request);
  }

  async simulateRepository(
    repositoryId: string,
    request: RepositorySimulationRequest,
  ): Promise<DecisionEnvelope> {
    this.requireApiTransport("simulateRepository");
    return this.client().simulateRepository(repositoryId, request);
  }

  async applyRepository(
    repositoryId: string,
    request: RepositoryApplyRequest,
  ): Promise<RepositoryApplyResponse> {
    this.requireApiTransport("applyRepository");
    return this.client().applyRepository(repositoryId, request);
  }

  async listDatasets(options: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    sourceName?: string;
    compact?: boolean;
  } = {}): Promise<DatasetListResult> {
    this.requireApiTransport("listDatasets");
    return this.client().listDatasets(options);
  }

  async getDataset(datasetId: string): Promise<DatasetDetailResult> {
    this.requireApiTransport("getDataset");
    return this.client().getDataset(datasetId);
  }

  async getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult> {
    this.requireApiTransport("getDatasetSummary");
    return this.client().getDatasetSummary(datasetId);
  }

  async getContract(): Promise<PlatformContractResponse> {
    this.requireApiTransport("getContract");
    return this.requestValidatedContractPayload(
      "getContract",
      () => this.client().getContract(),
      assertPlatformContractResponse,
    );
  }

  async listCapabilityProviders(): Promise<CapabilityProviderResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilityProviders();
    }
    return this.localProviderResponses();
  }

  async getCapabilityProvider(providerId: string): Promise<CapabilityProviderResponse> {
    if (this.usesApiTransport()) {
      return this.client().getCapabilityProvider(providerId);
    }
    const provider = this.localProviderResponses().find(item => item.provider_id === providerId);
    if (!provider) {
      throw new RuntimeValidationError(
        "provider_not_found",
        `Capability provider '${providerId}' was not found in local mode.`,
      );
    }
    return provider;
  }

  async listCapabilityBindings(
    options: { providerId?: string; scope?: string } = {},
  ): Promise<CapabilityBindingResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilityBindings(options);
    }
    return this.localBindingsArray().filter(binding => {
      if (options.providerId && binding.provider_id !== options.providerId) return false;
      if (options.scope && binding.scope !== options.scope) return false;
      return true;
    });
  }

  async createCapabilityBinding(
    request: CapabilityBindingCreateRequest,
  ): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().createCapabilityBinding(request);
    }
    const now = this.nowIso();
    const bindingId = `local-binding-${sha256Hex(
      JSON.stringify({ request, now }).slice(0, 2048),
    ).slice(0, 24)}`;
    const binding: CapabilityBindingResponse = {
      binding_id: bindingId,
      provider_id: request.provider_id,
      profile_id: request.profile_id,
      binding_name: request.binding_name,
      scope: request.scope ?? "workspace",
      scope_ref: request.scope_ref ?? "local",
      status: "unconfigured",
      execution_owner: request.execution_owner ?? "client_managed",
      config: request.config ?? null,
      customer_metadata: request.customer_metadata ?? null,
      system_managed: false,
      last_tested_at: null,
      last_discovered_at: null,
      authorized_at: null,
      quarantine_reason: null,
      discovery_error_message: null,
      test_error_message: null,
      created_at: now,
      updated_at: now,
    };
    this.localCapabilityBindings.set(bindingId, binding);
    return binding;
  }

  async getCapabilityBinding(bindingId: string): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().getCapabilityBinding(bindingId);
    }
    const binding = this.localCapabilityBindings.get(bindingId);
    if (!binding) {
      throw new RuntimeValidationError(
        "binding_not_found",
        `Capability binding '${bindingId}' was not found in local mode.`,
      );
    }
    return binding;
  }

  async updateCapabilityBinding(
    bindingId: string,
    request: CapabilityBindingUpdateRequest,
  ): Promise<CapabilityBindingResponse> {
    if (this.usesApiTransport()) {
      return this.client().updateCapabilityBinding(bindingId, request);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const updated: CapabilityBindingResponse = {
      ...binding,
      binding_name: request.binding_name ?? binding.binding_name,
      scope: request.scope ?? binding.scope,
      scope_ref: request.scope_ref ?? binding.scope_ref,
      status: request.status ?? binding.status,
      execution_owner: request.execution_owner ?? binding.execution_owner,
      config: request.config ?? binding.config,
      customer_metadata: request.customer_metadata ?? binding.customer_metadata,
      updated_at: this.nowIso(),
    };
    this.localCapabilityBindings.set(bindingId, updated);
    return updated;
  }

  async deleteCapabilityBinding(bindingId: string): Promise<void> {
    if (this.usesApiTransport()) {
      await this.client().deleteCapabilityBinding(bindingId);
      return;
    }
    this.localCapabilityBindings.delete(bindingId);
    Array.from(this.localCapabilityCatalog.values())
      .filter(entry => entry.binding_id === bindingId)
      .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
  }

  async previewTestCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityBindingTestResult> {
    if (this.usesApiTransport()) {
      return this.client().previewTestCapabilityBinding(request);
    }
    const manifest =
      request.config && typeof request.config === "object" && !Array.isArray(request.config)
        ? (request.config as Record<string, unknown>).manifest
        : null;
    if (
      manifest &&
      typeof manifest === "object" &&
      !Array.isArray(manifest) &&
      Array.isArray((manifest as { capabilities?: unknown }).capabilities)
    ) {
      return {
        success: true,
        binding_status: "ready",
        message: "Local manifest-backed capability binding is valid.",
        latency_ms: null,
        details: {
          capability_count: ((manifest as { capabilities: unknown[] }).capabilities ?? []).length,
        },
      };
    }
    const adapterMatch = this.localCapabilitiesArray().some(
      entry => entry.provider_id === request.provider_id && entry.profile_id === request.profile_id,
    );
    return adapterMatch
      ? {
          success: true,
          binding_status: "ready",
          message: "Local adapter-backed capability binding is available.",
          latency_ms: null,
          details: { adapter_backed: true },
        }
      : {
          success: false,
          binding_status: "unconfigured",
          message: "Local capability binding requires config.manifest.capabilities or a matching registered adapter.",
          latency_ms: null,
          details: { required_field: "config.manifest.capabilities" },
        };
  }

  async testCapabilityBinding(bindingId: string): Promise<CapabilityBindingTestResult> {
    if (this.usesApiTransport()) {
      return this.client().testCapabilityBinding(bindingId);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const result = await this.previewTestCapabilityBinding({
      provider_id: binding.provider_id,
      profile_id: binding.profile_id,
      scope: binding.scope,
      scope_ref: binding.scope_ref,
      execution_owner: binding.execution_owner,
      config: binding.config ?? undefined,
      customer_metadata: binding.customer_metadata ?? undefined,
    });
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: result.binding_status,
      last_tested_at: this.nowIso(),
      test_error_message: result.success ? null : result.message,
      updated_at: this.nowIso(),
    });
    return result;
  }

  async previewDiscoverCapabilityBinding(
    request: CapabilityBindingPreviewRequest,
  ): Promise<CapabilityDiscoverResponse> {
    if (this.usesApiTransport()) {
      return this.client().previewDiscoverCapabilityBinding(request);
    }
    return this.discoverLocalBinding(request);
  }

  async discoverCapabilityBinding(bindingId: string): Promise<CapabilityDiscoverResponse> {
    if (this.usesApiTransport()) {
      return this.client().discoverCapabilityBinding(bindingId);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const response = this.discoverLocalBinding(binding);
    Array.from(this.localCapabilityCatalog.values())
      .filter(entry => entry.binding_id === bindingId)
      .forEach(entry => this.localCapabilityCatalog.delete(entry.capability_id));
    response.capabilities.forEach(entry => this.localCapabilityCatalog.set(entry.capability_id, entry));
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: response.binding_status,
      last_discovered_at: response.discovered_at,
      discovery_error_message: response.capabilities.length > 0 ? null : response.message,
      updated_at: this.nowIso(),
    });
    return response;
  }

  async startCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationStartRequest,
  ): Promise<CapabilityAuthorizationStartResponse> {
    if (this.usesApiTransport()) {
      return this.client().startCapabilityAuthorization(bindingId, request);
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const authorizeUrl =
      binding.config &&
      typeof binding.config === "object" &&
      !Array.isArray(binding.config) &&
      typeof (binding.config as { authorization_url?: unknown }).authorization_url === "string"
        ? String((binding.config as { authorization_url?: unknown }).authorization_url)
        : null;
    if (!authorizeUrl) {
      throw new RuntimeValidationError(
        "authorization_not_supported",
        "This local capability binding does not expose authorization_url.",
      );
    }
    const sessionId = `local-auth-${sha256Hex(
      JSON.stringify({ bindingId, request, now: this.nowIso() }),
    ).slice(0, 24)}`;
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000).toISOString();
    const requestedScopes = request.requested_scopes ?? [];
    const response: CapabilityAuthorizationStartResponse = {
      session_id: sessionId,
      binding_id: bindingId,
      provider_id: binding.provider_id,
      authorize_url: authorizeUrl,
      expires_at: expiresAt,
      requested_scopes: requestedScopes,
    };
    this.localCapabilityAuthSessions.set(sessionId, response);
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: "authorizing",
      updated_at: this.nowIso(),
    });
    return response;
  }

  async completeCapabilityAuthorization(
    bindingId: string,
    request: CapabilityAuthorizationCompleteRequest,
  ): Promise<CapabilityAuthorizationCompleteResponse> {
    if (this.usesApiTransport()) {
      return this.client().completeCapabilityAuthorization(bindingId, request);
    }
    const session = this.localCapabilityAuthSessions.get(request.session_id);
    if (!session || session.binding_id !== bindingId) {
      throw new RuntimeValidationError(
        "authorization_session_not_found",
        "Local capability authorization session was not found.",
      );
    }
    const binding = await this.getCapabilityBinding(bindingId);
    const authorizedAt = this.nowIso();
    this.localCapabilityBindings.set(bindingId, {
      ...binding,
      status: "ready",
      authorized_at: authorizedAt,
      updated_at: authorizedAt,
    });
    return {
      session_id: session.session_id,
      binding_id: bindingId,
      provider_id: binding.provider_id,
      status: "completed",
      authorized_at: authorizedAt,
    };
  }

  async listCapabilities(
    options: {
      kinds?: string[];
      providerIds?: string[];
      bindingIds?: string[];
    } = {},
  ): Promise<CapabilityCatalogEntry[]> {
    if (this.usesApiTransport()) {
      return this.client().listCapabilities(options);
    }
    return this.localCapabilitiesArray().filter(entry => {
      if (options.kinds?.length && !options.kinds.includes(entry.kind)) return false;
      if (options.providerIds?.length && !options.providerIds.includes(entry.provider_id)) return false;
      if (options.bindingIds?.length && !options.bindingIds.includes(entry.binding_id)) return false;
      return true;
    });
  }

  async getCapability(
    capabilityId: string,
    options: { includeInstruction?: boolean } = {},
  ): Promise<CapabilityCatalogEntry> {
    if (this.usesApiTransport()) {
      return this.client().getCapability(capabilityId, options);
    }
    const capability = this.localCapabilityCatalog.get(capabilityId);
    if (!capability) {
      throw new RuntimeValidationError(
        "capability_not_found",
        `Capability '${capabilityId}' was not found in local mode.`,
      );
    }
    if (options.includeInstruction) return capability;
    const { instruction_text, ...rest } = capability;
    return { ...rest, instruction_text: null };
  }

  async routeCapabilities(request: CapabilityRouteRequest): Promise<CapabilityRoutePlan> {
    if (this.usesApiTransport()) {
      return this.client().routeCapabilities(request);
    }
    const tokenize = (value: string): string[] =>
      value
        .toLowerCase()
        .split(/[^a-z0-9_.-]+/g)
        .filter(Boolean);
    const objectiveTokens = new Set(tokenize(request.objective));
    const entries = await this.listCapabilities({
      kinds: request.kinds,
      providerIds: request.provider_ids,
      bindingIds: request.binding_ids,
    });
    const filtered = entries.filter(entry => {
      if (request.execution_owners?.length && !request.execution_owners.includes(entry.execution_owner)) {
        return false;
      }
      return entry.binding_status !== "quarantined";
    });
    if (filtered.length === 0) {
      throw new RuntimeValidationError(
        "capability_route_not_found",
        "No capabilities matched the requested local route filters.",
      );
    }
    const scored = filtered
      .map(entry => {
        const overlap = new Set(
          [
            ...tokenize(entry.name),
            ...tokenize(entry.description ?? ""),
            ...(entry.tags ?? []).flatMap(tokenize),
            ...(entry.artifact_affinities ?? []).flatMap(tokenize),
          ].filter(token => objectiveTokens.has(token)),
        );
        let score = overlap.size * 10 + (entry.binding_status === "ready" ? 15 : 0);
        if ((request.tags ?? []).some(tag => entry.tags.includes(tag))) score += 8;
        if ((request.artifact_affinities ?? []).some(tag => entry.artifact_affinities.includes(tag))) {
          score += 8;
        }
        const confidence = Math.max(0.05, Math.min(0.99, score / 100));
        return {
          entry,
          confidence,
          reason:
            overlap.size > 0
              ? `token overlap: ${Array.from(overlap).sort().join(", ")}`
              : "default local catalog ranking",
        };
      })
      .sort((left, right) => {
        if (right.confidence !== left.confidence) return right.confidence - left.confidence;
        return left.entry.name.localeCompare(right.entry.name);
      });
    const selected = scored[0];
    return {
      selected_capability_id: selected.entry.capability_id,
      selected_provider_id: selected.entry.provider_id,
      selected_binding_id: selected.entry.binding_id,
      kind: selected.entry.kind,
      execution_owner: selected.entry.execution_owner,
      requires_approval: selected.entry.approval_required,
      confidence: Number(selected.confidence.toFixed(4)),
      reason: selected.reason,
      fallbacks: scored.slice(1, 1 + (request.max_fallbacks ?? 3)).map(item => ({
        capability_id: item.entry.capability_id,
        provider_id: item.entry.provider_id,
        binding_id: item.entry.binding_id,
        kind: item.entry.kind,
        execution_owner: item.entry.execution_owner,
        confidence: Number(item.confidence.toFixed(4)),
        reason: item.reason,
        selected_tool_name: item.entry.selected_tool_name ?? null,
        instruction_artifact_ref: item.entry.instruction_artifact_ref ?? null,
      })),
      policy_snapshot_id: "capability-plane-policy-v1",
      selected_tool_name: selected.entry.selected_tool_name ?? null,
      instruction_artifact_ref: selected.entry.instruction_artifact_ref ?? null,
    };
  }

  async executeCapability(
    request: CapabilityExecutionRequest,
  ): Promise<CapabilityExecutionResponse> {
    if (this.usesApiTransport()) {
      return this.client().executeCapability(request);
    }
    const capability = await this.getCapability(request.capability_id, {
      includeInstruction: true,
    });
    if (request.binding_id && request.binding_id !== capability.binding_id) {
      throw new RuntimeValidationError(
        "binding_mismatch",
        "binding_id does not match the selected capability binding.",
      );
    }
    if (capability.execution_owner !== "client_managed") {
      throw new RuntimeValidationError(
        "capability_execution_owner_unsupported",
        "Local runtime execution only supports client_managed capabilities.",
        {
          capability_id: capability.capability_id,
          execution_owner: capability.execution_owner,
        },
      );
    }
    const executionSessionId = `local-exec-${sha256Hex(
      JSON.stringify({ request, ts: this.nowIso() }),
    ).slice(0, 24)}`;
    const startedAt = this.nowIso();
    if (capability.implementation_kind === "instruction_only") {
      return {
        execution_session_id: executionSessionId,
        capability_id: capability.capability_id,
        provider_id: capability.provider_id,
        binding_id: capability.binding_id,
        execution_owner: capability.execution_owner,
        status: "succeeded",
        output: {
          instruction_artifact_ref: capability.instruction_artifact_ref ?? null,
          instruction_text: capability.instruction_text ?? null,
          capability_id: capability.capability_id,
        },
        error: null,
        started_at: startedAt,
        completed_at: this.nowIso(),
      };
    }
    const adapter = this.capabilityAdapters.get(capability.capability_id);
    if (!adapter) {
      throw new RuntimeValidationError(
        "capability_adapter_missing",
        "Local capability execution requires a registered adapter.",
        { capability_id: capability.capability_id },
      );
    }
    const output = (await adapter.execute(request, capability)) ?? null;
    return {
      execution_session_id: executionSessionId,
      capability_id: capability.capability_id,
      provider_id: capability.provider_id,
      binding_id: capability.binding_id,
      execution_owner: capability.execution_owner,
      status: "succeeded",
      output,
      error: null,
      started_at: startedAt,
      completed_at: this.nowIso(),
    };
  }

  async recordCapabilityOutcome(
    request: CapabilityOutcomeRecordRequest,
  ): Promise<CapabilityOutcomeRecord> {
    if (this.usesApiTransport()) {
      return this.client().recordCapabilityOutcome(request);
    }
    const outcome: CapabilityOutcomeRecord = {
      outcome_id: `local-outcome-${sha256Hex(
        JSON.stringify({ request, ts: this.nowIso() }),
      ).slice(0, 24)}`,
      capability_id: request.capability_id,
      provider_id: request.provider_id,
      binding_id: request.binding_id ?? null,
      success: request.success ?? null,
      result_status: request.result_status ?? "reported",
      confidence: request.confidence ?? null,
      latency_ms: request.latency_ms ?? null,
      error_code: request.error_code ?? null,
      details: request.details ?? null,
      created_at: this.nowIso(),
    };
    this.localCapabilityOutcomes.push(outcome);
    return outcome;
  }

  async listSkills(): Promise<CapabilityCatalogEntry[]> {
    if (this.usesApiTransport()) {
      return this.client().listSkills();
    }
    return this.listCapabilities({ kinds: ["skill"] });
  }

  async enableSkill(
    request: {
      skill_name: string;
      instruction: string;
      description?: string;
      tags?: string[];
      artifact_affinities?: string[];
      execution_owner?: "algenta_managed" | "client_managed";
    },
  ): Promise<CapabilityDiscoverResponse> {
    if (this.usesApiTransport()) {
      return this.client().enableSkill(request);
    }
    const binding = await this.createCapabilityBinding({
      provider_id: "provider.skill_pack.algenta",
      profile_id: "profile.skill_pack.user",
      binding_name: request.skill_name,
      scope: "user",
      execution_owner: request.execution_owner ?? "client_managed",
      config: {
        manifest: {
          capabilities: [
            {
              capability_id: `cap.skill.${request.skill_name.toLowerCase().replace(/\s+/g, "_")}`,
              name: request.skill_name,
              description: request.description,
              kind: "skill",
              implementation_kind: "instruction_only",
              execution_owner: request.execution_owner ?? "client_managed",
              instruction: request.instruction,
              artifact_affinities: request.artifact_affinities ?? [],
              tags: request.tags ?? [],
              replayability: "deterministic",
            },
          ],
        },
      },
    });
    return this.discoverCapabilityBinding(binding.binding_id);
  }

  async disableSkill(bindingId: string): Promise<void> {
    if (this.usesApiTransport()) {
      await this.client().disableSkill(bindingId);
      return;
    }
    await this.deleteCapabilityBinding(bindingId);
  }

  async listMcpProviders(): Promise<CapabilityProviderResponse[]> {
    if (this.usesApiTransport()) {
      return this.client().listMcpProviders();
    }
    return (await this.listCapabilityProviders()).filter(
      provider => provider.provider_type === "mcp_provider",
    );
  }

  private buildNormalizedContractErrorDetails(error: DecisionEngineError): Record<string, unknown> {
    const details: Record<string, unknown> = {
      cause: error.message,
      source_error_code: error.errorCode,
      source_status_code: error.statusCode,
    };
    if (error.details && typeof error.details === "object" && !Array.isArray(error.details)) {
      details.source_error_details = error.details;
    }
    return details;
  }

  private rethrowNormalizedContractError(
    error: unknown,
    runtimeCode: string,
    message: string,
    upstreamErrorCodes: ReadonlyArray<string>,
  ): never {
    if (
      error instanceof DecisionEngineError &&
      upstreamErrorCodes.includes(error.errorCode)
    ) {
      throw new RuntimeValidationError(
        runtimeCode,
        message,
        this.buildNormalizedContractErrorDetails(error),
      );
    }
    throw error;
  }

  private async requestValidatedContractPayload<T>(
    methodName: string,
    requester: () => Promise<unknown>,
    validator: (value: unknown) => T,
  ): Promise<T> {
    let payload: unknown;
    try {
      payload = await requester();
    } catch (error) {
      this.rethrowNormalizedContractError(
        error,
        "invalid_contract_payload",
        `${methodName}() returned an invalid payload.`,
        ["invalid_contract_payload", "contract_extension_missing"],
      );
    }
    return this.validateContractPayload(methodName, payload, validator);
  }

  private validateContractPayload<T>(
    methodName: string,
    payload: unknown,
    validator: (value: unknown) => T,
  ): T {
    try {
      return validator(payload);
    } catch (error) {
      if (error instanceof DecisionEngineError) {
        throw new RuntimeValidationError(
          "invalid_contract_payload",
          `${methodName}() returned an invalid payload.`,
          this.buildNormalizedContractErrorDetails(error),
        );
      }
      throw error;
    }
  }

  private validateRuntimeProofPayload<T>(
    methodName: string,
    payload: unknown,
    validator: (value: unknown) => T,
  ): T {
    try {
      return validator(payload);
    } catch (error) {
      if (error instanceof DecisionEngineError) {
        throw new RuntimeValidationError(
          "invalid_runtime_contract_payload",
          `${methodName}() returned an invalid signed payload.`,
          this.buildNormalizedContractErrorDetails(error),
        );
      }
      throw error;
    }
  }

  private async requestValidatedRuntimeProofPayload<T>(
    methodName: string,
    requester: () => Promise<unknown>,
    validator: (value: unknown) => T,
  ): Promise<T> {
    let payload: unknown;
    try {
      payload = await requester();
    } catch (error) {
      this.rethrowNormalizedContractError(
        error,
        "invalid_runtime_contract_payload",
        `${methodName}() returned an invalid signed payload.`,
        ["invalid_runtime_contract_payload"],
      );
    }
    return this.validateRuntimeProofPayload(methodName, payload, validator);
  }

  async getRuntimeManifest(): Promise<RuntimeManifestResponse> {
    this.requireApiTransport("getRuntimeManifest");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeManifest",
      () => this.client().getRuntimeManifest(),
      assertRuntimeManifestResponse,
    );
  }

  async getRuntimeModules(): Promise<RuntimeAdminModulesResponse> {
    this.requireApiTransport("getRuntimeModules");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeModules",
      () => this.client().getRuntimeModules(),
      assertRuntimeAdminModulesResponse,
    );
  }

  async getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse> {
    this.requireApiTransport("getRuntimeBenchmarks");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeBenchmarks",
      () => this.client().getRuntimeBenchmarks(),
      assertRuntimeAdminBenchmarksResponse,
    );
  }

  async getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse> {
    this.requireApiTransport("getRuntimeReleaseValidation");
    return this.requestValidatedRuntimeProofPayload(
      "getRuntimeReleaseValidation",
      () => this.client().getRuntimeReleaseValidation(),
      assertRuntimeReleaseValidationResponse,
    );
  }

  async listModels(): Promise<LLMModelListResponse> {
    this.requireApiTransport("listModels");
    return this.client().listModels();
  }

  async resolveArtifactBridge(
    request: ArtifactBridgeResolveRequest,
  ): Promise<ArtifactBridgeResolveResponse> {
    this.requireApiTransport("resolveArtifactBridge");
    return this.client().resolveArtifactBridge(request);
  }

  async tokenize(request: TokenizeRequest): Promise<TokenizeResponse> {
    this.requireApiTransport("tokenize");
    return this.client().tokenize(request);
  }

  async countTokens(request: CountTokensRequest): Promise<CountTokensResponse> {
    this.requireApiTransport("countTokens");
    return this.client().countTokens(request);
  }

  async chatCompletions(request: ChatCompletionsRequest): Promise<ChatCompletionsResponse> {
    this.requireApiTransport("chatCompletions");
    return this.client().chatCompletions(request);
  }

  async *streamChatCompletions(
    request: ChatCompletionsRequest,
  ): AsyncGenerator<ChatCompletionsStreamChunkResponse> {
    this.requireApiTransport("streamChatCompletions");
    yield* this.client().streamChatCompletions(request);
  }

  async responses(request: ResponsesRequest): Promise<ResponsesResponse> {
    this.requireApiTransport("responses");
    return this.client().responses(request);
  }

  async *streamResponses(
    request: ResponsesRequest,
  ): AsyncGenerator<ResponseStreamEventResponse> {
    this.requireApiTransport("streamResponses");
    yield* this.client().streamResponses(request);
  }

  async embeddings(request: EmbeddingsRequest): Promise<EmbeddingsResponse> {
    this.requireApiTransport("embeddings");
    return this.client().embeddings(request);
  }

  async embeddingSimilarity(
    request: EmbeddingSimilarityRequest,
  ): Promise<EmbeddingSimilarityResponse> {
    this.requireApiTransport("embeddingSimilarity");
    return this.client().embeddingSimilarity(request);
  }

  async rerank(request: RerankRequest): Promise<RerankResponse> {
    this.requireApiTransport("rerank");
    return this.client().rerank(request);
  }

  async planDecision(request: SimulateRequest): Promise<DecisionPlanResponse> {
    this.requireApiTransport("planDecision");
    return this.client().planDecision(request);
  }

  async productDecision(request: ProductDecisionRequest): Promise<ProductDecisionResponse> {
    this.requireApiTransport("productDecision");
    return this.client().productDecision(request);
  }

  async productAgentRun(request: ProductAgentRunRequest): Promise<ProductAgentRunResponse> {
    this.requireApiTransport("productAgentRun");
    return this.client().productAgentRun(request);
  }

  async productOptimize(request: ProductOptimizeRequest): Promise<ProductOptimizeResponse> {
    this.requireApiTransport("productOptimize");
    return this.client().productOptimize(request);
  }

  async productRetrieve(request: ProductRetrieveRequest): Promise<ProductRetrieveResponse> {
    this.requireApiTransport("productRetrieve");
    return this.client().productRetrieve(request);
  }

  async productForecast(request: ProductForecastRequest): Promise<ProductForecastResponse> {
    this.requireApiTransport("productForecast");
    return this.client().productForecast(request);
  }

  async logDecision(request: LogDecisionRequest): Promise<DecisionLogResponse> {
    this.requireApiTransport("logDecision");
    return this.client().logDecision(request);
  }

  async listDecisions(options: {
    page?: number;
    limit?: number;
    page_size?: number;
    with_outcome_only?: boolean;
  } = {}): Promise<DecisionListResponse> {
    this.requireApiTransport("listDecisions");
    return this.client().listDecisions(options);
  }

  async getDecision(decisionId: string): Promise<DecisionLogResponse> {
    this.requireApiTransport("getDecision");
    return this.client().getDecision(decisionId);
  }

  async recordOutcome(
    decisionId: string,
    request: RecordOutcomeRequest,
  ): Promise<DecisionLogResponse> {
    this.requireApiTransport("recordOutcome");
    return this.client().recordOutcome(decisionId, request);
  }

  async executeDecision(
    decisionId: string,
    request: ExecuteDecisionRequest,
  ): Promise<ExecutionReceiptResponse> {
    this.requireApiTransport("executeDecision");
    return this.client().executeDecision(decisionId, request);
  }

  async deleteDecision(decisionId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("deleteDecision");
    return this.client().deleteDecision(decisionId);
  }

  async createAgentRun(request: AgentRunCreateRequest): Promise<AgentRunResponse> {
    this.requireApiTransport("createAgentRun");
    return this.client().createAgentRun(request);
  }

  async getAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("getAgentRun");
    return this.client().getAgentRun(runId);
  }

  async listAgentRuns(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
    } = {},
  ): Promise<AgentRunListResponse> {
    this.requireApiTransport("listAgentRuns");
    return this.client().listAgentRuns(options);
  }

  async getAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunEventsResponse> {
    this.requireApiTransport("getAgentRunEvents");
    return this.client().getAgentRunEvents(runId, options);
  }

  async *streamAgentRunEvents(
    runId: string,
    options: { limit?: number } = {},
  ): AsyncGenerator<AgentRunStreamEventResponse> {
    this.requireApiTransport("streamAgentRunEvents");
    yield* this.client().streamAgentRunEvents(runId, options);
  }

  async listAgentRunCheckpoints(runId: string): Promise<AgentRunCheckpointsResponse> {
    this.requireApiTransport("listAgentRunCheckpoints");
    return this.client().listAgentRunCheckpoints(runId);
  }

  async queryAgentRunCheckpoints(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      checkpoint_id?: string;
    } = {},
  ): Promise<AgentRunCheckpointListResponse> {
    this.requireApiTransport("queryAgentRunCheckpoints");
    return this.client().queryAgentRunCheckpoints(options);
  }

  async listAgentRunMissionEvents(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunMissionEventsResponse> {
    this.requireApiTransport("listAgentRunMissionEvents");
    return this.client().listAgentRunMissionEvents(runId, options);
  }

  async queryAgentRunMissionEvents(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      event_type?: string;
    } = {},
  ): Promise<AgentRunMissionEventListResponse> {
    this.requireApiTransport("queryAgentRunMissionEvents");
    return this.client().queryAgentRunMissionEvents(options);
  }

  async replayAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunReplayResponse> {
    this.requireApiTransport("replayAgentRun");
    return this.client().replayAgentRun(runId, options);
  }

  async forkAgentRun(
    runId: string,
    options: { checkpoint_id?: string | null } = {},
  ): Promise<AgentRunResponse> {
    this.requireApiTransport("forkAgentRun");
    return this.client().forkAgentRun(runId, options);
  }

  async resumeAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("resumeAgentRun");
    return this.client().resumeAgentRun(runId);
  }

  async cancelAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("cancelAgentRun");
    return this.client().cancelAgentRun(runId);
  }

  async approveAgentRun(runId: string): Promise<AgentRunResponse> {
    this.requireApiTransport("approveAgentRun");
    return this.client().approveAgentRun(runId);
  }

  async listAgentRunTelemetry(
    runId: string,
    options: { limit?: number } = {},
  ): Promise<AgentRunTelemetryResponse> {
    this.requireApiTransport("listAgentRunTelemetry");
    return this.client().listAgentRunTelemetry(runId, options);
  }

  async queryAgentRunTelemetry(
    options: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      telemetry_kind?: string;
      module_name?: string;
    } = {},
  ): Promise<AgentRunTelemetryListResponse> {
    this.requireApiTransport("queryAgentRunTelemetry");
    return this.client().queryAgentRunTelemetry(options);
  }

  async recommend(
    actions: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<RecommendResponse> {
    this.requireApiTransport("recommend");
    return this.client().recommend(actions, options);
  }

  async score(
    request: SimulateRequest,
    scoringWeights?: Record<string, number>,
  ): Promise<ScoreResponse> {
    this.requireApiTransport("score");
    return this.client().score(request, scoringWeights);
  }

  async batch(items: SimulateRequest[]): Promise<BatchResult> {
    this.requireApiTransport("batch");
    return this.client().batch(items);
  }

  async compare(
    scenarios: Array<{ name: string; request: SimulateRequest }>,
    options?: { runs?: number; seed?: number },
  ): Promise<CompareResponse> {
    this.requireApiTransport("compare");
    return this.client().compare(scenarios, options);
  }

  async listJobs(options: { page?: number; limit?: number; status?: string } = {}): Promise<JobListResponse> {
    this.requireApiTransport("listJobs");
    return this.client().listJobs(options);
  }

  async submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse> {
    this.requireApiTransport("submitJob");
    return this.client().submitJob(request, callbackUrl);
  }

  async getJob(jobId: string): Promise<JobStatusResponse> {
    this.requireApiTransport("getJob");
    return this.client().getJob(jobId);
  }

  async getJobResult(jobId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("getJobResult");
    return this.client().getJobResult(jobId);
  }

  async cancelJob(jobId: string): Promise<JobStatusResponse> {
    this.requireApiTransport("cancelJob");
    return this.client().cancelJob(jobId);
  }

  async testWebhookDelivery(callbackUrl: string): Promise<WebhookTestResponse> {
    this.requireApiTransport("testWebhookDelivery");
    return this.client().testWebhookDelivery(callbackUrl);
  }

  async registerTrigger(request: RegisterTriggerRequest): Promise<TriggerResponse> {
    this.requireApiTransport("registerTrigger");
    return this.client().registerTrigger(request);
  }

  async listTriggers(options: { status?: "active" | "paused" | "all"; page?: number; limit?: number } = {}): Promise<TriggerListResponse> {
    this.requireApiTransport("listTriggers");
    return this.client().listTriggers(options);
  }

  async fireTrigger(triggerId: string, options: { force?: boolean } = {}): Promise<TriggerFireResponse> {
    this.requireApiTransport("fireTrigger");
    return this.client().fireTrigger(triggerId, options);
  }

  async pauseTrigger(triggerId: string, options: { paused?: boolean } = {}): Promise<TriggerPauseResponse> {
    this.requireApiTransport("pauseTrigger");
    return this.client().pauseTrigger(triggerId, options);
  }

  async deleteTrigger(triggerId: string): Promise<TriggerDeleteResponse> {
    this.requireApiTransport("deleteTrigger");
    return this.client().deleteTrigger(triggerId);
  }

  async pollJob(
    jobId: string,
    options: { timeoutMs?: number; pollIntervalMs?: number } = {},
  ): Promise<Record<string, unknown>> {
    this.requireApiTransport("pollJob");
    return this.client().pollJob(jobId, options);
  }

  async listDeploymentRegions(): Promise<DeploymentRegionsResponse> {
    this.requireApiTransport("listDeploymentRegions");
    return this.client().listDeploymentRegions();
  }

  async getDeployment(): Promise<DeploymentResponse | null> {
    this.requireApiTransport("getDeployment");
    return this.client().getDeployment();
  }

  async createDeployment(request: {
    provider?: string;
    region?: string;
    config?: Record<string, unknown> | null;
    billing_markup_pct?: number;
  } = {}): Promise<DeploymentResponse> {
    this.requireApiTransport("createDeployment");
    return this.client().createDeployment(request);
  }

  async deleteDeployment(deploymentId: string): Promise<DeploymentDeleteResponse> {
    this.requireApiTransport("deleteDeployment");
    return this.client().deleteDeployment(deploymentId);
  }

  async getDeploymentCost(deploymentId: string): Promise<DeploymentCostResponse> {
    this.requireApiTransport("getDeploymentCost");
    return this.client().getDeploymentCost(deploymentId);
  }

  async me(): Promise<MeResponse> {
    this.requireApiTransport("me");
    return this.client().me();
  }

  async updateMe(request: UpdateMeRequest): Promise<MeResponse> {
    this.requireApiTransport("updateMe");
    return this.client().updateMe(request);
  }

  async usage(): Promise<UsageInfo> {
    this.requireApiTransport("usage");
    return this.client().usage();
  }

  async limits(): Promise<LimitsInfo> {
    this.requireApiTransport("limits");
    return this.client().limits();
  }

  async distributions(): Promise<DistributionListResponse> {
    this.requireApiTransport("distributions");
    return this.client().distributions();
  }

  async templates(): Promise<TemplateListResponse> {
    this.requireApiTransport("templates");
    return this.client().templates();
  }

  async getBillingInfo(): Promise<BillingInfoResponse> {
    this.requireApiTransport("getBillingInfo");
    return this.client().getBillingInfo();
  }

  async createBillingCheckout(
    options: { plan?: "developer" | "pro" } = {},
  ): Promise<BillingSessionResponse> {
    this.requireApiTransport("createBillingCheckout");
    return this.client().createBillingCheckout(options);
  }

  async createBillingPortal(): Promise<BillingSessionResponse> {
    this.requireApiTransport("createBillingPortal");
    return this.client().createBillingPortal();
  }

  async refreshCredits(request: CreditRefreshRequest): Promise<CreditRefreshResponse> {
    this.requireApiTransport("refreshCredits");
    return this.client().refreshCredits(request);
  }

  async ingestMeteringEvents(request: MeteringBatchRequest): Promise<MeteringBatchResponse> {
    this.requireApiTransport("ingestMeteringEvents");
    return this.client().ingestMeteringEvents(request);
  }

  async listApiKeys(): Promise<APIKeyInfo[]> {
    this.requireApiTransport("listApiKeys");
    return this.client().listApiKeys();
  }

  async createApiKey(request: CreateAPIKeyRequest): Promise<APIKeyCreated> {
    this.requireApiTransport("createApiKey");
    return this.client().createApiKey(request);
  }

  async revokeApiKey(keyId: string): Promise<Record<string, unknown>> {
    this.requireApiTransport("revokeApiKey");
    return this.client().revokeApiKey(keyId);
  }

  async listTeamMembers(options: { page?: number; limit?: number } = {}): Promise<TeamListResponse> {
    this.requireApiTransport("listTeamMembers");
    return this.client().listTeamMembers(options);
  }

  async inviteTeamMember(request: TeamInviteRequest): Promise<TeamInviteResponse> {
    this.requireApiTransport("inviteTeamMember");
    return this.client().inviteTeamMember(request);
  }

  async updateTeamMemberRole(
    userId: string,
    role: "owner" | "admin" | "member" | "viewer",
  ): Promise<TeamRoleUpdateResponse> {
    this.requireApiTransport("updateTeamMemberRole");
    return this.client().updateTeamMemberRole(userId, role);
  }

  async removeTeamMember(userId: string): Promise<TeamRemoveResponse> {
    this.requireApiTransport("removeTeamMember");
    return this.client().removeTeamMember(userId);
  }

  async listDevices(options: { page?: number; limit?: number } = {}): Promise<DeviceListResponse> {
    this.requireApiTransport("listDevices");
    return this.client().listDevices(options);
  }

  async revokeDevice(registrationId: string): Promise<DeviceRevokeResponse> {
    this.requireApiTransport("revokeDevice");
    return this.client().revokeDevice(registrationId);
  }

  async getAuditLogs(
    options: {
      page?: number;
      limit?: number;
      actor_email?: string;
      action?: string;
      resource_type?: string;
      result?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      manifest_version?: string;
      request_hash?: string;
    } = {},
  ): Promise<AuditLogResponse> {
    this.requireApiTransport("getAuditLogs");
    return this.client().getAuditLogs(options);
  }

  async getAuditLogArtifacts(
    options: {
      page?: number;
      limit?: number;
      actor_email?: string;
      action?: string;
      resource_type?: string;
      result?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      manifest_version?: string;
      request_hash?: string;
      content_hash?: string;
    } = {},
  ): Promise<AuditLogResponse> {
    this.requireApiTransport("getAuditLogArtifacts");
    return this.client().getAuditLogArtifacts(options);
  }

  async getExecutionPolicy(): Promise<ExecutionPolicyResponse> {
    this.requireApiTransport("getExecutionPolicy");
    return this.client().getExecutionPolicy();
  }

  async listExecutionPolicySnapshots(): Promise<ExecutionPolicySnapshotListResponse> {
    this.requireApiTransport("listExecutionPolicySnapshots");
    return this.client().listExecutionPolicySnapshots();
  }

  async updateExecutionPolicy(
    request: UpdateExecutionPolicyRequest,
  ): Promise<ExecutionPolicyResponse> {
    this.requireApiTransport("updateExecutionPolicy");
    return this.client().updateExecutionPolicy(request);
  }

  async refreshDataset(datasetId: string): Promise<DatasetConnectResult> {
    this.requireApiTransport("refreshDataset");
    return this.client().refreshDataset(datasetId);
  }

  async deleteDataset(datasetId: string): Promise<DatasetDeleteResult> {
    this.requireApiTransport("deleteDataset");
    return this.client().deleteDataset(datasetId);
  }

  async importPreview(
    source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
    options: ImportPreviewOptions = {},
  ): Promise<ImportPreviewResult> {
    const registration = await this.connect(source, options);
    return {
      registration,
      preview: renderSourceImportPreview(registration, {
        sourceRef: sourceReference(source, options.sourceRef),
        mode: this.mode,
        color: options.color,
      }),
    };
  }

  async importBundlePreview(
    sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
    options: ImportBundlePreviewOptions = {},
  ): Promise<ImportBundlePreviewResult> {
    if (options.names && options.names.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_names_length",
        "importBundlePreview() names must match the number of sources.",
        { sources: sources.length, names: options.names.length },
      );
    }
    if (options.sourceRefs && options.sourceRefs.length !== sources.length) {
      throw new RuntimeValidationError(
        "invalid_source_refs_length",
        "importBundlePreview() sourceRefs must match the number of sources.",
        { sources: sources.length, sourceRefs: options.sourceRefs.length },
      );
    }

    const registrations: SourceRegistrationResponse[] = [];
    const failures: ImportFailureResult[] = [];
    for (const [index, source] of sources.entries()) {
      try {
        registrations.push(
          await this.connect(source, {
            name: options.names?.[index],
            description: options.description,
          }),
        );
      } catch (error) {
        if (!(error instanceof RuntimeError)) {
          throw error;
        }
        failures.push({
          sourceRef: options.sourceRefs?.[index] ?? sourceReference(source),
          code: error.code,
          message: error.message,
          name: options.names?.[index],
        });
      }
    }

    return {
      registrations,
      failures,
      preview: renderSourceBundlePreview(registrations, failures, {
        mode: this.mode,
        color: options.color,
      }),
    };
  }

  async resolve(
    request: Record<string, unknown> = {},
    overrides: Record<string, unknown> = {},
  ): Promise<ResolveResponse> {
    const merged = mergeRequest(request, overrides);
    if (this.usesApiTransport()) {
      const exact = await this.tryExactApiResolve(merged);
      if (exact) {
        return exact;
      }
      return this.client().resolve(this.coerceApiResolvePayload(merged));
    }
    return this.resolveLocal(merged);
  }

  async query(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<QueryResponse> {
    if (this.usesApiTransport()) {
      return this.client().query(this.coerceApiQueryPayload(request, overrides));
    }
    return this.queryLocal(request, overrides);
  }

  async queryWithMetadata(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<QueryWithMetadataResponse> {
    if (this.usesApiTransport()) {
      return this.client().queryWithMetadata(this.coerceApiQueryPayload(request, overrides));
    }
    const data = await this.queryLocal(request, overrides);
    return {
      data,
      metadata: {
        request_id: data.request_id ?? undefined,
        latency_ms: data.latency_ms,
      },
    };
  }

  async verify(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<VerifyResponse> {
    if (this.usesApiTransport()) {
      return this.client().verify(this.coerceApiQueryPayload(request, overrides));
    }
    return this.verifyLocal(request, overrides);
  }

  async queryBatch(request: {
    defaults?: {
      dataset_id?: string | null;
      filter?: Record<string, unknown> | null;
      limit?: number | null;
      order?: "asc" | "desc" | null;
    } | null;
    queries: Array<{ key: string; request: Record<string, unknown> }>;
  }): Promise<QueryBatchResponse> {
    this.requireApiTransport("queryBatch");
    return this.client().queryBatch(request);
  }

  async querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse> {
    this.requireApiTransport("querySqlReport");
    return this.client().querySqlReport(request);
  }

  private client(): DecisionEngineClient {
    if (this.clientInstance) {
      return this.clientInstance;
    }
    if (this.lazyClient) {
      return this.lazyClient;
    }
    if (!this.apiKey) {
      throw new RuntimeConfigurationError(
        "api_key_required",
        "API and self_hosted mode require an API key. Set ALGENTA_API_KEY / DE_API_KEY or pass apiKey.",
      );
    }
    this.lazyClient = new DecisionEngineClient(this.clientConfig);
    return this.lazyClient;
  }

  private rememberApiRegistration(registration: SourceRegistrationResponse): void {
    if (typeof registration.name === "string" && registration.name.trim()) {
      this.apiRegistrationsByName.set(registration.name.trim(), registration);
    }
    const datasetId = registrationDatasetId(registration);
    if (datasetId) {
      this.apiRegistrationsByDataset.set(datasetId, registration);
    }
  }

  private async hydrateApiRegistration(
    registration: SourceRegistrationResponse,
  ): Promise<SourceRegistrationResponse> {
    const datasetId = registrationDatasetId(registration);
    if (!datasetId) {
      return registration;
    }
    const needsHydration =
      registration.row_count == null ||
      typeof registration.name !== "string" ||
      !registration.name.trim() ||
      typeof registration.dataset_name !== "string" ||
      !registration.dataset_name.trim() ||
      registration.schema == null ||
      registration.source_schema == null;
    if (!needsHydration) {
      return registration;
    }
    const clientWithGetDataset = this.client() as unknown as {
      getDataset?: (datasetId: string) => Promise<DatasetDetailResult>;
    };
    if (typeof clientWithGetDataset.getDataset !== "function") {
      return registration;
    }
    try {
      const detail = await clientWithGetDataset.getDataset(datasetId);
      const dataset = detail?.dataset;
      const schema =
        detail?.schema && typeof detail.schema === "object"
          ? detail.schema
          : null;
      return {
        ...registration,
        name:
          typeof registration.name === "string" && registration.name.trim()
            ? registration.name
            : typeof dataset?.name === "string" && dataset.name.trim()
              ? dataset.name
              : registration.name ?? null,
        dataset_name:
          typeof registration.dataset_name === "string" && registration.dataset_name.trim()
            ? registration.dataset_name
            : typeof dataset?.name === "string" && dataset.name.trim()
              ? dataset.name
              : registration.dataset_name ?? null,
        row_count:
          typeof registration.row_count === "number"
            ? registration.row_count
            : typeof dataset?.row_count === "number"
              ? dataset.row_count
              : registration.row_count ?? null,
        schema: registration.schema ?? schema,
        source_schema: registration.source_schema ?? schema,
      };
    } catch {
      return registration;
    }
  }

  private lookupApiRegistration(request: Record<string, unknown>): SourceRegistrationResponse | null {
    const datasetId = request.dataset_id;
    if (typeof datasetId === "string" && datasetId.trim()) {
      const registration = this.apiRegistrationsByDataset.get(datasetId.trim());
      if (registration) {
        return registration;
      }
    }
    const sourceName = request.source_name;
    if (typeof sourceName === "string" && sourceName.trim()) {
      return this.apiRegistrationsByName.get(sourceName.trim()) ?? null;
    }
    return null;
  }

  private async fetchApiSourceSchemaRevision(
    registration: SourceRegistrationResponse,
  ): Promise<string | null> {
    const sourceId = registrationDatasetId(registration);
    if (!sourceId) {
      return null;
    }
    const clientWithRequest = this.client() as unknown as {
      request?: (method: string, path: string, body?: unknown) => Promise<unknown>;
    };
    if (typeof clientWithRequest.request !== "function") {
      return null;
    }
    try {
      const payload = await clientWithRequest.request("GET", `/v1/sources/${sourceId}`);
      if (!payload || typeof payload !== "object") {
        return null;
      }
      const body = payload as Record<string, unknown>;
      const entry = body.entry;
      if (entry && typeof entry === "object") {
        const entryRecord = entry as Record<string, unknown>;
        const entryRevision = entryRecord.source_schema_revision ?? entryRecord.schema_revision;
        if (typeof entryRevision === "string" && entryRevision.trim()) {
          return entryRevision.trim();
        }
      }
      const schema = body.schema;
      if (schema && typeof schema === "object") {
        const schemaRevision = (schema as Record<string, unknown>).schema_revision;
        if (typeof schemaRevision === "string" && schemaRevision.trim()) {
          return schemaRevision.trim();
        }
      }
      return null;
    } catch {
      return null;
    }
  }

  private async tryExactApiResolve(request: Record<string, unknown>): Promise<ResolveResponse | null> {
    const registration = this.lookupApiRegistration(request);
    if (!registration) {
      return null;
    }
    const resolvedSourceName = registrationResolvedSourceName(registration);
    if (!resolvedSourceName) {
      return null;
    }
    const schemaRevision =
      (await this.fetchApiSourceSchemaRevision(registration)) ??
      (typeof registration.planner_schema_revision === "string" &&
      registration.planner_schema_revision.trim()
        ? registration.planner_schema_revision.trim()
        : typeof registration.schema_revision === "string" && registration.schema_revision.trim()
          ? registration.schema_revision.trim()
          : null);
    if (!schemaRevision) {
      return null;
    }
    const fields = new Set(registrationFields(registration));
    if (fields.size === 0) {
      return null;
    }

    const metricColumn = this.exactResolveMetricField(request, fields);
    if (!metricColumn) {
      return null;
    }
    const groupColumn = this.exactResolveGroupField(request, fields);
    if (groupColumn === undefined) {
      return null;
    }

    const startMs = Date.now();
    const constraints =
      request.constraints && typeof request.constraints === "object"
        ? { ...(request.constraints as Record<string, unknown>) }
        : {};
    const datasetScope = registrationDatasetId(registration);
    if (datasetScope && constraints[RUNTIME_DATASET_SCOPE_KEY] === undefined) {
      constraints[RUNTIME_DATASET_SCOPE_KEY] = datasetScope;
    }
    const resolvedPlan: ResolvedPlan = {
      source_name: resolvedSourceName,
      metric_column: metricColumn,
      aggregation: resolveAggregation(request),
      ...(groupColumn ? { group_column: groupColumn } : {}),
      ...(request.join_path && typeof request.join_path === "object" ? { join_path: request.join_path as Record<string, unknown> } : {}),
      ...(request.filter && typeof request.filter === "object" ? { filter: request.filter as Record<string, unknown> } : {}),
      ...(typeof request.limit === "number" ? { limit: request.limit } : {}),
      order: typeof request.order === "string" ? request.order : "desc",
      constraints,
      schema_revision: schemaRevision,
    };
    const planHash = exactPlanHash(resolvedPlan);
    const signature = intentSignature(resolvedSourceName, request, schemaRevision);

    return {
      resolved_plan: resolvedPlan,
      confidence: 1,
      plan: [
        `Use exact source '${resolvedSourceName}'.`,
        `Use exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Group by exact column '${groupColumn}'.`] : []),
      ],
      explanation: [
        `Using registered source '${resolvedSourceName}' as an exact source.`,
        `Using exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Using exact group column '${groupColumn}'.`] : []),
      ],
      resolved_column: metricColumn,
      resolved_role: "measure",
      resolved_source: resolvedSourceName,
      candidates: [],
      source_scores: { [resolvedSourceName]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "exact_spec",
      plan_hash: planHash,
      schema_revision: schemaRevision,
      validated: true,
      deterministic_scope: "api_registered_source",
      confidence_source: "runtime_exact_spec",
      clarification_required: false,
      rejection_reason: null,
      request_id: `runtime_exact_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [resolvedSourceName],
      join_path: [],
      planner_mode: "runtime_exact_spec",
    };
  }

  private exactResolveMetricField(
    request: Record<string, unknown>,
    fields: Set<string>,
  ): string | null {
    const metricColumn = request.metric_column;
    if (typeof metricColumn === "string" && fields.has(metricColumn)) {
      return metricColumn;
    }
    const metric = request.metric;
    if (typeof metric === "string" && fields.has(metric)) {
      return metric;
    }
    return null;
  }

  private exactResolveGroupField(
    request: Record<string, unknown>,
    fields: Set<string>,
  ): string | null | undefined {
    const groupColumn = request.group_column;
    if (typeof groupColumn === "string") {
      return fields.has(groupColumn) ? groupColumn : undefined;
    }
    const groupBy = request.group_by;
    if (typeof groupBy === "string") {
      return fields.has(groupBy) ? groupBy : undefined;
    }
    if (Array.isArray(groupBy)) {
      const candidates = groupBy.filter(
        (value): value is string => typeof value === "string" && value.trim().length > 0,
      );
      if (candidates.length > 1) {
        return undefined;
      }
      if (candidates.length === 1) {
        return fields.has(candidates[0]) ? candidates[0] : undefined;
      }
    }
    return null;
  }

  private usesHostedLocalLimits(): boolean {
    return this.mode === "local" && this.enforceLimits && !privateProfile();
  }

  private async ensureLocalExecutionEntitlement(): Promise<void> {
    if (!this.usesHostedLocalLimits() && !requireLocalLicense()) {
      return;
    }
    if (this.usesHostedLocalLimits() && !this.apiKey) {
      throw new RuntimeConfigurationError(
        "api_key_required",
        "Hosted local mode requires an API key. Pass apiKey explicitly when constructing Runtime.",
      );
    }
    if (!this.licensePromise) {
      this.licensePromise = loadLocalLicense(this.apiKey ?? "", this.baseUrl)
        .finally(() => {
          this.licensePromise = undefined;
        });
    }
    this.localLicense = await this.licensePromise;
    if (!this.localLicense.valid) {
      throw new RuntimeConfigurationError(
        "license_required",
        this.localLicense.message || "A valid local device license is required.",
        {
          plan: this.localLicense.plan,
          source: this.localLicense.source,
        },
      );
    }
  }

  private consumeLocalCredit(): void {
    if (!this.usesHostedLocalLimits()) {
      return;
    }
    if (hasOfflineExecutionEntitlement(this.localLicense)) {
      return;
    }
    const outcome = decrementCredit();
    if (!outcome.permitted) {
      throw new RuntimeConfigurationError(
        "quota_exhausted",
        "Local execution credits are exhausted. Refresh credits or renew the device license before continuing.",
      );
    }
    if (outcome.state && stateNeedsRefresh(outcome.state) && !this.creditRefreshPromise) {
      this.creditRefreshPromise = this.refreshLocalCredits(outcome.state)
        .finally(() => {
          this.creditRefreshPromise = undefined;
        });
    }
  }

  private async refreshLocalCredits(state: LocalCreditState): Promise<void> {
    if (!this.apiKey) {
      return;
    }
    let controlPlaneUrl = "";
    try {
      controlPlaneUrl = validatedControlPlaneBaseUrl(this.baseUrl, {
        surface: "credits_refresh",
      });
    } catch {
      return;
    }
    try {
      const response = await fetch(`${controlPlaneUrl}/v1/credits/refresh`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          device_id: deviceInfo().device_id,
          billing_period: state.billing_period,
          credits_used: state.credits_total - state.credits_remaining,
        }),
      });
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as LicenseExchangeResponse;
      observeTrustedTime(
        data.server_time ?? Math.floor(Date.now() / 1000),
        "control-plane-credit-refresh",
      );
      const granted = data.credits_granted ?? 0;
      if (granted <= 0) {
        return;
      }
      const now = trustedNowEpoch();
      const expiresAt = data.credits_expires_at ?? now + CREDIT_TTL_SECONDS;
      const ttlSeconds = Math.max(1, expiresAt - now);
      const existing = readCreditState();
      const carry = existing?.credits_remaining ?? 0;
      writeCreditState({
        credits_remaining: carry + granted,
        credits_total: granted,
        issued_at: now,
        expires_at: now + ttlSeconds,
        billing_period: data.credits_billing_period ?? state.billing_period,
        refresh_after: now + ttlSeconds * 0.9,
      });
    } catch {
      return;
    }
  }

  private selectLocalSource(request: Record<string, unknown>): LocalSource {
    const requested = typeof request.source_name === "string"
      ? request.source_name
      : typeof request.dataset_id === "string"
        ? request.dataset_id
        : null;

    if (requested) {
      if (this.localSources.has(requested)) {
        return this.localSources.get(requested)!;
      }
      for (const source of this.localSources.values()) {
        if (source.datasetId === requested) return source;
      }
      throw new RuntimeValidationError("unknown_source", "Requested source is not connected to this runtime.", {
        requested,
        available: [...this.localSources.keys()].sort(),
      });
    }

    if (this.localSources.size === 1) {
      return [...this.localSources.values()][0];
    }
    if (this.localSources.size === 0) {
      throw new RuntimeConfigurationError(
        "source_required",
        "No local sources are connected. Call Runtime.connect(...) before resolve/query.",
      );
    }
    throw new RuntimeValidationError("source_required", "Multiple local sources are connected. Provide source_name or dataset_id.", {
      available: [...this.localSources.keys()].sort(),
    });
  }

  private rankFields(source: LocalSource, hint: string, numericOnly: boolean): RankedField[] {
    const hintTerms = metricSynonymSet(hint);
    return source.fields
      .filter(field => !numericOnly || isNumericField(field, source.records))
      .map(field => {
        const base = semanticScore(field, hint);
        let score = base.score;
        const reasons = [...base.reasons];
        const normalizedField = normalizeText(field);
        if (hintTerms.has(normalizedField)) {
          score = Math.max(score, 1);
          reasons.push("canonical synonym match");
        }
        if (isExactFieldMatch(field, hint)) {
          score = 1;
        }
        return {
          field,
          score: Number(score.toFixed(4)),
          reasons: reasons.length > 0 ? reasons : ["schema similarity"],
        };
      })
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        return left.field.localeCompare(right.field);
      });
  }

  private buildCandidates(source: LocalSource, ranked: RankedField[], role: string): QueryCandidate[] {
    return ranked.slice(0, 5).map(item => ({
      source: source.name,
      column: item.field,
      role,
      confidence: item.score,
      notes: item.reasons,
      score_components: { schema_similarity: item.score },
    }));
  }

  private resolveLocal(request: Record<string, unknown>): ResolveResponse {
    const startMs = Date.now();
    const source = this.selectLocalSource(request);
    const metricHint = typeof request.metric === "string" ? request.metric : null;
    if (!metricHint) {
      throw new RuntimeValidationError(
        "metric_required",
        "Local Runtime.resolve() requires a structured metric field.",
        { request },
      );
    }

    const aggregation = resolveAggregation(request);
    const metricRanked = this.rankFields(source, metricHint, true);
    if (metricRanked.length === 0) {
      return this.rejectedResolve(source, request, "schema_unresolved", [`No numeric field matched metric '${metricHint}'.`], startMs);
    }

    const metricChoice = metricRanked[0];
    const metricCandidates = this.buildCandidates(source, metricRanked, "measure");
    const metricSecond = metricRanked[1]?.score ?? 0;
    const metricGap = Number((metricChoice.score - metricSecond).toFixed(4));

    if (metricChoice.score < 0.7) {
      return this.rejectedResolve(
        source,
        request,
        "schema_unresolved",
        [`Top metric match '${metricChoice.field}' scored below the 0.70 threshold.`],
        startMs,
        metricCandidates,
      );
    }
    if (metricChoice.score < 0.85 || metricGap < 0.1) {
      return this.clarifyResolve(
        source,
        request,
        [`Metric mapping for '${metricHint}' is not decisive enough for execution.`],
        startMs,
        metricCandidates,
      );
    }

    let resolvedGroup: string | null = null;
    let groupCandidates: QueryCandidate[] = [];
    if (typeof request.group_by === "string" && request.group_by.trim()) {
      const groupRanked = this.rankFields(source, request.group_by, false);
      groupCandidates = this.buildCandidates(source, groupRanked, "dimension");
      if (groupRanked.length === 0) {
        return this.rejectedResolve(
          source,
          request,
          "schema_unresolved",
          [`No field matched group_by '${request.group_by}'.`],
          startMs,
          metricCandidates,
        );
      }
      const groupChoice = groupRanked[0];
      const groupSecond = groupRanked[1]?.score ?? 0;
      const groupGap = Number((groupChoice.score - groupSecond).toFixed(4));
      if (groupChoice.score < 0.7) {
        return this.rejectedResolve(
          source,
          request,
          "schema_unresolved",
          [`Top group_by match '${groupChoice.field}' scored below the 0.70 threshold.`],
          startMs,
          [...metricCandidates, ...groupCandidates],
        );
      }
      if (groupChoice.score < 0.85 || groupGap < 0.1) {
        return this.clarifyResolve(
          source,
          request,
          [`Group_by mapping for '${request.group_by}' is not decisive enough for execution.`],
          startMs,
          [...metricCandidates, ...groupCandidates],
        );
      }
      resolvedGroup = groupChoice.field;
    }

    const resolvedPlan: ResolvedPlan = {
      source_name: source.name,
      metric_column: metricChoice.field,
      aggregation,
      group_column: resolvedGroup,
      join_path: null,
      filter: (request.filter as Record<string, unknown> | undefined) ?? null,
      limit: typeof request.limit === "number" ? request.limit : null,
      order: typeof request.order === "string" ? request.order : "desc",
      constraints: (request.constraints as Record<string, unknown> | undefined) ?? {},
      schema_revision: source.schemaRevision,
    };
    const planHash = exactPlanHash(resolvedPlan);
    const signature = intentSignature(source.name, request, source.schemaRevision);
    const decisionPath =
      isExactFieldMatch(metricChoice.field, metricHint) &&
      (!resolvedGroup || isExactFieldMatch(resolvedGroup, String(request.group_by ?? "")))
        ? "exact_spec"
        : "planner_hint";

    return {
      resolved_plan: resolvedPlan,
      confidence: 1,
      plan: [
        `Use source '${source.name}'.`,
        `Aggregate '${metricChoice.field}' with '${aggregation}'.`,
        ...(resolvedGroup ? [`Group by '${resolvedGroup}'.`] : []),
      ],
      explanation: [
        `Resolved metric '${metricHint}' to '${metricChoice.field}'.`,
        ...(resolvedGroup ? [`Resolved group_by '${request.group_by}' to '${resolvedGroup}'.`] : []),
      ],
      resolved_column: metricChoice.field,
      resolved_role: "measure",
      resolved_source: source.name,
      candidates: [...metricCandidates, ...groupCandidates],
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: decisionPath,
      plan_hash: planHash,
      schema_revision: source.schemaRevision,
      validated: true,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: false,
      rejection_reason: null,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private rejectedResolve(
    source: LocalSource,
    request: Record<string, unknown>,
    reason: string,
    explanation: string[],
    startMs: number,
    candidates: QueryCandidate[] = [],
  ): ResolveResponse {
    const signature = intentSignature(source.name, request, source.schemaRevision);
    return {
      resolved_plan: null,
      confidence: 0,
      plan: [],
      explanation,
      resolved_column: "",
      resolved_role: "",
      resolved_source: source.name,
      candidates,
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "planner_hint",
      plan_hash: null,
      schema_revision: source.schemaRevision,
      validated: false,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: false,
      rejection_reason: reason,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private clarifyResolve(
    source: LocalSource,
    request: Record<string, unknown>,
    explanation: string[],
    startMs: number,
    candidates: QueryCandidate[],
  ): ResolveResponse {
    const signature = intentSignature(source.name, request, source.schemaRevision);
    return {
      resolved_plan: null,
      confidence: 0.75,
      plan: [],
      explanation,
      resolved_column: "",
      resolved_role: "",
      resolved_source: source.name,
      candidates,
      source_scores: { [source.name]: 1 },
      latency_ms: roundLatency(startMs),
      decision_path: "planner_hint",
      plan_hash: null,
      schema_revision: source.schemaRevision,
      validated: false,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_schema_match",
      clarification_required: true,
      rejection_reason: null,
      request_id: `local_${signature.slice(0, 12)}`,
      intent_signature: signature,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private coercePlan(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): ResolvedPlan {
    const payload =
      Object.keys(overrides).length > 0
        ? overrides
        : "resolved_plan" in request
          ? (request.resolved_plan as ResolvedPlan | null)
          : request;
    if (!payload) {
      throw new RuntimeValidationError(
        "query_requires_executable_plan",
        "Runtime.query() requires an executable plan.",
      );
    }
    return payload as ResolvedPlan;
  }

  private async queryLocal(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): Promise<QueryResponse> {
    const startMs = Date.now();
    const plan = this.coercePlan(request, overrides);
    const source = this.localSources.get(plan.source_name);
    if (!source) {
      throw new RuntimeValidationError(
        "unknown_source",
        "Query plan references a source that is not connected to this runtime.",
        { source_name: plan.source_name },
      );
    }
    if (plan.schema_revision !== source.schemaRevision) {
      throw new RuntimeValidationError(
        "schema_revision_mismatch",
        "Query plan schema_revision does not match the connected source.",
        { expected: source.schemaRevision, received: plan.schema_revision },
      );
    }

    await this.ensureLocalExecutionEntitlement();
    this.consumeLocalCredit();

    let executionRecords = source.records;
    const localPlanSteps: string[] = [];
    const filterValue =
      plan.filter && typeof plan.filter === "object" ? (plan.filter as Record<string, unknown>) : {};
    const timeFilter = typeof filterValue.time_filter === "string" ? filterValue.time_filter.trim() : "";
    if (timeFilter) {
      const localTimeField = findLocalTimeField(source);
      const localTimeRange = timeRange(timeFilter);
      if (localTimeField && localTimeRange) {
        const before = executionRecords.length;
        executionRecords = executionRecords.filter(record => {
          const parsed = parseDateValue(record[localTimeField]);
          return (
            parsed !== null &&
            parsed.getTime() >= localTimeRange.start.getTime() &&
            parsed.getTime() <= localTimeRange.end.getTime()
          );
        });
        localPlanSteps.push(
          `Time filter '${timeFilter}' on '${localTimeField}': ${before}->${executionRecords.length} rows.`,
        );
      } else {
        localPlanSteps.push("No time-like field found. time_filter skipped.");
      }
    }

    const resolvedFilterConditions = resolveLocalFilterConditions(source, filterValue);
    const filteredLocalRecords = applyLocalFilterConditions(executionRecords, resolvedFilterConditions);
    executionRecords = filteredLocalRecords.records;
    localPlanSteps.push(...filteredLocalRecords.planSteps);

    const rows = executePlan(
      executionRecords,
      plan.metric_column,
      plan.group_column,
      plan.aggregation,
      plan.limit ?? 100,
    );
    const result = plan.group_column ? rows : rows[0]?.[plan.metric_column] ?? null;

    return {
      query_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
      result,
      result_type: plan.group_column ? "table" : "scalar",
      confidence: 1,
      plan: [
        `Use source '${source.name}'.`,
        `Aggregate '${plan.metric_column}' with '${plan.aggregation}'.`,
        ...(plan.group_column ? [`Group by '${plan.group_column}'.`] : []),
        ...localPlanSteps,
      ],
      resolved_column: plan.metric_column,
      resolved_role: "measure",
      resolved_source: source.name,
      row_count: plan.group_column ? rows.length : result === null ? 0 : 1,
      candidates: [],
      source_scores: { [source.name]: 1 },
      ambiguous: false,
      exact_spec: true,
      explanation: ["Executed deterministic local plan."],
      latency_ms: roundLatency(startMs),
      decision_path: "exact_spec",
      plan_hash: exactPlanHash(plan),
      schema_revision: source.schemaRevision,
      validated: true,
      deterministic_scope: "local_registered_source",
      confidence_source: "local_exact_execution",
      clarification_required: false,
      rejection_reason: null,
      request_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
      source_set: [source.name],
      join_path: [],
      planner_mode: "local_structured_intent",
    };
  }

  private verifyLocal(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): VerifyResponse {
    const startMs = Date.now();
    try {
      const plan = this.coercePlan(request, overrides);
      const source = this.localSources.get(plan.source_name);
      const errors: string[] = [];
      if (!source) {
        errors.push(`Source '${plan.source_name}' is not connected.`);
      } else {
        if (plan.schema_revision !== source.schemaRevision) {
          errors.push("schema_revision mismatch");
        }
        if (!source.fields.includes(plan.metric_column)) {
          errors.push(`Metric column '${plan.metric_column}' is missing.`);
        }
        if (plan.group_column && !source.fields.includes(plan.group_column)) {
          errors.push(`Group column '${plan.group_column}' is missing.`);
        }
        try {
          resolveLocalFilterConditions(
            source,
            plan.filter && typeof plan.filter === "object" ? (plan.filter as Record<string, unknown>) : {},
          );
        } catch (error) {
          if (error instanceof RuntimeValidationError) {
            errors.push(error.message);
          } else {
            throw error;
          }
        }
      }
      const valid = errors.length === 0;
      return {
        valid,
        errors,
        suggestions: valid ? [] : ["Reconnect the source or rerun resolve against the current schema."],
        resolved: {
          source_name: plan.source_name,
          metric_column: plan.metric_column,
          group_column: plan.group_column ?? "",
        },
        valid_dimensions: plan.group_column ? [plan.group_column] : [],
        valid_measures: [plan.metric_column],
        source_behavior: "local_registered_source",
        latency_ms: roundLatency(startMs),
        verified: valid,
        request_id: `local_verify_${exactPlanHash(plan).slice(0, 12)}`,
        schema_revision: plan.schema_revision,
        plan_hash: exactPlanHash(plan),
        verification_mode: "local",
        rejection_reason: valid ? null : "plan_verification_failed",
      };
    } catch (error) {
      if (error instanceof RuntimeError) {
        return {
          valid: false,
          errors: [error.message],
          suggestions: ["Run Runtime.resolve(...) again with a more explicit metric or source."],
          resolved: {},
          latency_ms: roundLatency(startMs),
          verified: false,
          verification_mode: "local",
          rejection_reason: error.code,
        };
      }
      throw error;
    }
  }

  private coerceApiQueryPayload(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown>,
  ): Record<string, unknown> {
    if (Object.keys(overrides).length > 0) {
      return this.extractRuntimeDatasetScope({ ...overrides });
    }
    if ("resolved_plan" in request) {
      if (!request.resolved_plan) {
        throw new RuntimeValidationError(
          "query_requires_executable_plan",
          "Runtime.query() requires an executable plan.",
        );
      }
      return this.extractRuntimeDatasetScope({
        resolved_plan: { ...(request.resolved_plan as Record<string, unknown>) },
      });
    }
    if (looksLikeResolvedPlan(request)) {
      return this.extractRuntimeDatasetScope({
        resolved_plan: { ...(request as unknown as Record<string, unknown>) },
      });
    }
    return this.extractRuntimeDatasetScope({ ...(request as Record<string, unknown>) });
  }

  private extractRuntimeDatasetScope(payload: Record<string, unknown>): Record<string, unknown> {
    const resolvedPlan = payload.resolved_plan;
    if (!resolvedPlan || typeof resolvedPlan !== "object" || Array.isArray(resolvedPlan)) {
      return payload;
    }
    const resolvedPlanPayload = { ...(resolvedPlan as Record<string, unknown>) };
    const rawConstraints = resolvedPlanPayload.constraints;
    if (!rawConstraints || typeof rawConstraints !== "object" || Array.isArray(rawConstraints)) {
      payload.resolved_plan = resolvedPlanPayload;
      return payload;
    }
    const constraints = { ...(rawConstraints as Record<string, unknown>) };
    const datasetId = constraints[RUNTIME_DATASET_SCOPE_KEY];
    delete constraints[RUNTIME_DATASET_SCOPE_KEY];
    if (
      payload.dataset_id === undefined &&
      typeof datasetId === "string" &&
      datasetId.trim()
    ) {
      payload.dataset_id = datasetId.trim();
    }
    resolvedPlanPayload.constraints = constraints;
    payload.resolved_plan = resolvedPlanPayload;
    return payload;
  }

  private coerceApiResolvePayload(request: Record<string, unknown>): Record<string, unknown> {
    const payload: Record<string, unknown> = { ...request };
    const sourceName = payload.source_name;
    if (typeof sourceName === "string" && sourceName.trim()) {
      if (payload.preferred_source === undefined) {
        payload.preferred_source = sourceName.trim();
      }
      if (payload.allow_org_scope === undefined) {
        payload.allow_org_scope = true;
      }
    }
    delete payload.source_name;

    const metric = payload.metric;
    if (typeof metric === "string") {
      payload.metric = {
        role: "metric",
        hint: metric.trim(),
      };
    }

    const groupBy = payload.group_by;
    if (typeof groupBy === "string") {
      payload.group_by = [groupBy];
    } else if (groupBy == null) {
      const groupColumn = payload.group_column;
      if (typeof groupColumn === "string" && groupColumn.trim()) {
        payload.group_by = [groupColumn.trim()];
      }
    }
    delete payload.group_column;
    delete payload.metric_column;
    delete payload.resolved_plan;
    return payload;
  }
}
