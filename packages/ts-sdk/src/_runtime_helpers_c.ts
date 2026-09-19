// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — internal helpers (part C). */

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


import { Runtime } from "./_runtime_class.js";
import {
  CSV_CURRENCY_PREFIX_RE,
  CSV_FLOAT_RE,
  CSV_INT_RE,
  CSV_LEADING_ZERO_INT_RE,
  CSV_TOKEN_RE,
  HEADER_ALIAS_AVG_SCORE,
  HEADER_ALIAS_MATCH_SCORE,
  HEADER_ALIAS_MAX_COLUMNS,
  HEADER_ALIAS_MIN_COLUMNS,
  HEADER_ALIAS_MIN_MATCH_RATIO,
  LocalRecord,
  MEASURE_TOKENS,
  SQLITE_DSN_RE,
  SQL_DEFAULT_PORTS,
  SQL_DSN_SCHEMES,
  SQL_IDENTIFIER_RE,
} from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import {
  CANONICAL_API_TYPES,
  CANONICAL_FILE_TYPES,
  DIRECT_API_SOURCE_KEYS,
  LOCAL_RUNTIME_CONNECTOR_TYPES,
  OBJECT_STORAGE_TYPES,
  SQL_PROVIDER_TYPES,
} from "./_runtime_helpers_a.js";
import { fieldOverlapScore, registrationFields } from "./_runtime_helpers_b.js";
import { localSourceName } from "./_runtime_helpers_d.js";

export function bundleOverlapLines(registrations: SourceRegistrationResponse[]): string[] {
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

export function sourceReference(
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

export function sourceDescriptorPath(source: Record<string, unknown>): string | null {
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

export function stripUndefined(record: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(record).filter(([, value]) => value !== undefined && value !== null));
}

export function isCanonicalConnectorEnvelope(source: Record<string, unknown>): boolean {
  return "location" in source || "auth" in source || "options" in source;
}

export function mergeConnectorSection(
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

export function normalizeConnectorAuth(flattened: Record<string, unknown>): void {
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

export function flattenConnectorEnvelope(source: Record<string, unknown>): Record<string, unknown> {
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

export function fileConnectorType(source: Record<string, unknown>): string {
  const rawType = String(source.type ?? source.provider ?? "").trim().toLowerCase();
  return rawType === "xlsx" || rawType === "xls" ? "excel" : rawType;
}

export function normalizeLocalRuntimeSource(source: Record<string, unknown>): Record<string, unknown> {
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

export function runtimeApiSourceName(source: Record<string, unknown>, explicitName?: string): string {
  if (explicitName && explicitName.trim()) {
    return explicitName.trim();
  }
  const nameCandidate = source.name;
  if (typeof nameCandidate === "string" && nameCandidate.trim()) {
    return nameCandidate.trim();
  }
  return localSourceName(source, 0);
}

export function sqlIdentifier(value: unknown, fieldName: string): string {
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

export function runtimeSqlConnectionString(provider: string, source: Record<string, unknown>): string {
  const connectionString = source.connection_string;
  if (typeof connectionString === "string" && connectionString.trim()) {
    return connectionString.trim();
  }
  // Own-key check, never `in`: `provider` is caller-supplied text and `in` also matches what a
  // plain object inherits from Object.prototype, so "constructor" et al. built a garbage DSN
  // instead of reaching the missing_connection_string rejection below. Python: dict membership.
  if (Object.prototype.hasOwnProperty.call(SQL_DSN_SCHEMES, provider)) {
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

export function runtimeSqlQuery(source: Record<string, unknown>): string {
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

export function runtimeRestUrl(source: Record<string, unknown>): string {
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

export function normalizeRuntimeConnection(source: Record<string, unknown>): Record<string, unknown> {
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

export function normalizeApiSourcePayload(
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

export function canonicalizeCsvHeaders(headers: string[]): string[] {
  const counts = new Map<string, number>();
  return headers.map(header => {
    const baseName = header.trim() || "Unnamed_Column";
    const nextCount = (counts.get(baseName) ?? 0) + 1;
    counts.set(baseName, nextCount);
    return nextCount === 1 ? baseName : `${baseName}__${nextCount}`;
  });
}

export function baseHeaderName(field: string): string {
  return field.split("__", 1)[0];
}

export function csvFieldTokens(field: string): Set<string> {
  return new Set(field.toLowerCase().match(CSV_TOKEN_RE) ?? []);
}

export function csvIsIdentifierField(field: string): boolean {
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

export function coerceCsvScalar(field: string, value: unknown): unknown {
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

export function looksLikeHeaderAliasRow(fieldNames: string[], values: unknown[]): boolean {
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

