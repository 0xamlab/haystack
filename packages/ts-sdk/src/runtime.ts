import type {
  DecisionEngineClientConfig,
  QueryCandidate,
  QueryResponse,
  ResolveResponse,
  ResolvedPlan,
  SourceRegistrationResponse,
  VerifyResponse,
} from "./types.js";
import { DecisionEngineClient } from "./client.js";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { homedir, hostname, platform, release } from "node:os";
import { extname, join, resolve as resolvePath } from "node:path";

import { DEFAULT_BASE_URL } from "./contract.js";

export type RuntimeMode = "local" | "api";

export interface RuntimeConfig {
  mode?: RuntimeMode;
  apiKey?: string;
  enforceLimits?: boolean;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  defaultHeaders?: Record<string, string>;
  client?: DecisionEngineClient;
}

type LocalRecord = Record<string, unknown>;

interface LocalSource {
  name: string;
  records: LocalRecord[];
  fields: string[];
  schemaRevision: string;
  datasetId: string;
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
  detail?: {
    message?: string;
  };
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

function controlPlaneBaseUrl(baseUrl?: string): string {
  const env = runtimeEnv();
  return (env.ALGENTA_CONTROL_PLANE_URL ?? env.ALGENTA_BASE_URL ?? env.DE_BASE_URL ?? baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
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
    sdk_version: "decision-engine-sdk/0.1.0",
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
  return Math.floor(Date.now() / 1000) > license.expiresAt + license.graceDays * 86_400;
}

function licenseInGrace(license: LocalRuntimeLicense): boolean {
  if (license.expiresAt === 0) {
    return false;
  }
  const now = Math.floor(Date.now() / 1000);
  return now > license.expiresAt && !licenseHardExpired(license);
}

function initializeCredits(granted: number, billingPeriod: string, ttlSeconds = CREDIT_TTL_SECONDS): void {
  const now = Date.now() / 1000;
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
  if (Date.now() / 1000 > state.expires_at) {
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

async function exchangeApiKeyForLicense(
  apiKey: string,
  baseUrl?: string,
): Promise<{ token: string | null; invalidMessage: string | null }> {
  try {
    const response = await fetch(`${controlPlaneBaseUrl(baseUrl)}/v1/device/register`, {
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
    if ((data.credits_granted ?? 0) > 0) {
      const expiresAt = data.credits_expires_at ?? Math.floor(Date.now() / 1000) + CREDIT_TTL_SECONDS;
      const ttlSeconds = Math.max(1, expiresAt - Math.floor(Date.now() / 1000));
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
      "Local Runtime.connect() supports local files and SQLite descriptors. Use Runtime({ mode: 'api', apiKey: '...' }) for remote connectors.",
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
      `API mode SQL descriptors require a non-empty ${fieldName}.`,
      { field: fieldName },
    );
  }
  const normalized = value.trim();
  if (!SQL_IDENTIFIER_RE.test(normalized)) {
    throw new RuntimeValidationError(
      "invalid_sql_identifier",
      "API mode SQL descriptors only auto-build queries for simple schema/table identifiers. Provide an explicit query for advanced SQL.",
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
      "API mode database descriptors require connection_string or a structured host/database descriptor.",
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
      "API mode REST descriptors require url or base_url.",
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
      "API mode source descriptors require an explicit connector type or a direct source payload.",
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
  private lazyClient?: DecisionEngineClient;
  private localLicense?: LocalRuntimeLicense;
  private licensePromise?: Promise<LocalRuntimeLicense>;
  private creditRefreshPromise?: Promise<void>;

  constructor(config: RuntimeConfig = {}) {
    this.mode = config.mode ?? "local";
    if (!["local", "api"].includes(this.mode)) {
      throw new RuntimeValidationError("invalid_mode", "Invalid mode. Expected 'local' or 'api'.", {
        mode: config.mode,
      });
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
    this.baseUrl = config.baseUrl;
    this.clientInstance = config.client;
    this.clientConfig = {
      apiKey: this.apiKey,
      baseUrl: this.baseUrl,
      timeout: config.timeout,
      maxRetries: config.maxRetries,
      defaultHeaders: config.defaultHeaders,
    };
  }

  toString(): string {
    return `Runtime(mode=${JSON.stringify(this.mode)}, apiKey=${this.apiKey ? "set" : "not set"})`;
  }

  async connect(
    source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
    options: { name?: string; description?: string } = {},
  ): Promise<SourceRegistrationResponse> {
    const startMs = Date.now();
    if (this.mode === "api") {
      if (typeof source === "string" || Array.isArray(source)) {
        throw new RuntimeValidationError(
          "api_connect_requires_source_descriptor",
          "API mode connect() expects a structured source descriptor.",
          { expected: "object", received: typeof source === "string" ? "string" : "array" },
        );
      }
      const registration = await this.client().registerSource(normalizeApiSourcePayload(source, options.name), {
        description: options.description,
      });
      this.rememberApiRegistration(registration);
      return registration;
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
    if (this.mode === "api") {
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
    if (this.mode === "api") {
      return this.client().query(this.coerceApiQueryPayload(request, overrides));
    }
    return this.queryLocal(request, overrides);
  }

  async verify(
    request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
    overrides: Record<string, unknown> = {},
  ): Promise<VerifyResponse> {
    if (this.mode === "api") {
      return this.client().verify(this.coerceApiQueryPayload(request, overrides));
    }
    return this.verifyLocal(request, overrides);
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
        "API mode requires an API key. Set ALGENTA_API_KEY or pass apiKey.",
      );
    }
    this.lazyClient = new DecisionEngineClient(this.clientConfig);
    return this.lazyClient;
  }

  private rememberApiRegistration(registration: SourceRegistrationResponse): void {
    if (typeof registration.name === "string" && registration.name.trim()) {
      this.apiRegistrationsByName.set(registration.name.trim(), registration);
    }
    const datasetId =
      typeof registration.dataset_id === "string" && registration.dataset_id.trim()
        ? registration.dataset_id.trim()
        : typeof registration.source_id === "string" && registration.source_id.trim()
          ? registration.source_id.trim()
          : null;
    if (datasetId) {
      this.apiRegistrationsByDataset.set(datasetId, registration);
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
    const sourceId =
      typeof registration.dataset_id === "string" && registration.dataset_id.trim()
        ? registration.dataset_id.trim()
        : typeof registration.source_id === "string" && registration.source_id.trim()
          ? registration.source_id.trim()
          : null;
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
    const sourceName =
      typeof registration.name === "string" && registration.name.trim()
        ? registration.name.trim()
        : typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name.trim()
          : null;
    if (!sourceName) {
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
    const resolvedPlan: ResolvedPlan = {
      source_name: sourceName,
      metric_column: metricColumn,
      aggregation: resolveAggregation(request),
      ...(groupColumn ? { group_column: groupColumn } : {}),
      ...(request.join_path && typeof request.join_path === "object" ? { join_path: request.join_path as Record<string, unknown> } : {}),
      ...(request.filter && typeof request.filter === "object" ? { filter: request.filter as Record<string, unknown> } : {}),
      ...(typeof request.limit === "number" ? { limit: request.limit } : {}),
      order: typeof request.order === "string" ? request.order : "desc",
      constraints:
        request.constraints && typeof request.constraints === "object"
          ? (request.constraints as Record<string, unknown>)
          : {},
      schema_revision: schemaRevision,
    };
    const planHash = exactPlanHash(resolvedPlan);
    const signature = intentSignature(sourceName, request, schemaRevision);

    return {
      resolved_plan: resolvedPlan,
      confidence: 1,
      plan: [
        `Use exact source '${sourceName}'.`,
        `Use exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Group by exact column '${groupColumn}'.`] : []),
      ],
      explanation: [
        `Using registered source '${sourceName}' as an exact source.`,
        `Using exact metric column '${metricColumn}'.`,
        ...(groupColumn ? [`Using exact group column '${groupColumn}'.`] : []),
      ],
      resolved_column: metricColumn,
      resolved_role: "measure",
      resolved_source: sourceName,
      candidates: [],
      source_scores: { [sourceName]: 1 },
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
      source_set: [sourceName],
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
    return this.mode === "local" && this.enforceLimits;
  }

  private async ensureLocalExecutionEntitlement(): Promise<void> {
    if (!this.usesHostedLocalLimits()) {
      return;
    }
    if (!this.apiKey) {
      throw new RuntimeConfigurationError(
        "api_key_required",
        "Hosted local mode requires an API key. Pass apiKey explicitly when constructing Runtime.",
      );
    }
    if (this.localLicense?.valid) {
      return;
    }
    if (!this.licensePromise) {
      this.licensePromise = loadLocalLicense(this.apiKey, this.baseUrl)
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
    try {
      const response = await fetch(`${controlPlaneBaseUrl(this.baseUrl)}/v1/credits/refresh`, {
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
      const granted = data.credits_granted ?? 0;
      if (granted <= 0) {
        return;
      }
      const expiresAt = data.credits_expires_at ?? Math.floor(Date.now() / 1000) + CREDIT_TTL_SECONDS;
      const ttlSeconds = Math.max(1, expiresAt - Math.floor(Date.now() / 1000));
      const existing = readCreditState();
      const carry = existing?.credits_remaining ?? 0;
      const now = Date.now() / 1000;
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

    const rows = executePlan(
      source.records,
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
      return { ...overrides };
    }
    if ("resolved_plan" in request) {
      if (!request.resolved_plan) {
        throw new RuntimeValidationError(
          "query_requires_executable_plan",
          "Runtime.query() requires an executable plan.",
        );
      }
      return { resolved_plan: { ...(request.resolved_plan as Record<string, unknown>) } };
    }
    if (looksLikeResolvedPlan(request)) {
      return { resolved_plan: { ...(request as unknown as Record<string, unknown>) } };
    }
    return { ...(request as Record<string, unknown>) };
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
