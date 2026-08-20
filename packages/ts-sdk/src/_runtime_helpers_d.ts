/** Auto-split sub-module of runtime.ts — intent signature, execute plan, validation. */

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
import { ImportFailureResult, LocalRecord, RuntimeMode } from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { normalizeText, runtimeBanner, stableHash, stableStringify, stripNullEntries } from "./_runtime_helpers_a.js";
import { canonicalizeAggregation, numericValue, registrationFields, resolveAggregation } from "./_runtime_helpers_b.js";
import {
  bundleOverlapLines,
  canonicalizeCsvHeaders,
  coerceCsvScalar,
  flattenConnectorEnvelope,
  isCanonicalConnectorEnvelope,
  looksLikeHeaderAliasRow,
  normalizeLocalRuntimeSource,
  sourceDescriptorPath,
} from "./_runtime_helpers_c.js";

export function parseCsvRows(text: string): string[][] {
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

export function parseCsvText(text: string): LocalRecord[] {
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

export function parseJsonText(text: string): LocalRecord[] {
  const parsed = JSON.parse(text) as unknown;
  if (Array.isArray(parsed)) {
    return parsed.filter((value): value is LocalRecord => Boolean(value) && typeof value === "object");
  }
  if (parsed && typeof parsed === "object") {
    return [parsed as LocalRecord];
  }
  throw new RuntimeValidationError("unsupported_json_source", "JSON local sources must contain an object or array of objects.");
}

export async function readSqliteSource(source: Record<string, unknown>): Promise<LocalRecord[]> {
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

export function readLocalSource(source: string): LocalRecord[] {
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

export function localSourceName(
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

export function exactPlanHash(plan: ResolvedPlan): string {
  // sha256 over the null-stripped plan — mirrors the Python SDK's plan_hash
  // (stable_hash) so both SDKs stamp byte-identical hashes on the same plan.
  return createHash("sha256")
    .update(stableStringify(stripNullEntries(plan)), "utf-8")
    .digest("hex");
}

export function looksLikeResolvedPlan(value: unknown): value is ResolvedPlan {
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

export function intentSignature(
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

export async function coerceRecords(
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

/** Aggregate admitted values. Canonical names only; empty avg/min/max is null
 * (never 0), empty sum is 0, count counts admitted values. Unknown aggregations
 * throw — silent sum fallback is forbidden. Semantics mirror the Python SDK's
 * `_agg` exactly (conformance-tested cross-language). */
export function aggregateValues(values: number[], aggregation: string): number | null {
  const canonical = canonicalizeAggregation(aggregation);
  switch (canonical) {
    case "count":
      return values.length;
    case "sum":
      return values.reduce((sum, value) => sum + value, 0);
    case "avg":
      return values.length === 0
        ? null
        : values.reduce((sum, value) => sum + value, 0) / values.length;
    case "min":
      return values.length === 0 ? null : Math.min(...values);
    default:
      return values.length === 0 ? null : Math.max(...values);
  }
}

/** Descending metric sort with null-metric rows last, identical to the Python SDK. */
function metricSortRank(row: Record<string, unknown>, metricColumn: string): [number, number] {
  const value = row[metricColumn];
  if (typeof value === "number" && Number.isFinite(value)) {
    return [0, -value];
  }
  return [1, 0];
}

export function executePlan(
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
    return [{ [metricColumn]: aggregateValues(values, aggregation), count: values.length }];
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
      count: group.values.length,
    }))
    .sort((left, right) => {
      const [leftNullRank, leftValue] = metricSortRank(left, metricColumn);
      const [rightNullRank, rightValue] = metricSortRank(right, metricColumn);
      return leftNullRank - rightNullRank || leftValue - rightValue;
    })
    .slice(0, limit);
}

