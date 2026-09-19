// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — internal helpers (part B). */

import type {
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
  APIKeyCreated,
  APIKeyInfo,
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  AuditLogResponse,
  BatchResult,
  BillingInfoResponse,
  BillingSessionResponse,
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
  CreateAPIKeyRequest,
  CreditRefreshRequest,
  CreditRefreshResponse,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetListResult,
  DatasetSummaryResult,
  DecisionEngineClientConfig,
  DecisionEnvelope,
  DecisionListResponse,
  DecisionLogResponse,
  DecisionPlanResponse,
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
  DeviceListResponse,
  DeviceRevokeResponse,
  DistributionListResponse,
  EmbeddingSimilarityRequest,
  EmbeddingSimilarityResponse,
  EmbeddingsRequest,
  EmbeddingsResponse,
  ExecuteDecisionRequest,
  ExecutionOwner,
  ExecutionPolicyResponse,
  ExecutionPolicySnapshotListResponse,
  ExecutionReceiptResponse,
  ExecutionSessionStatus,
  JobListResponse,
  JobStatusResponse,
  JobSubmitResponse,
  LimitsInfo,
  LLMModelListResponse,
  LogDecisionRequest,
  MeResponse,
  MeteringBatchRequest,
  MeteringBatchResponse,
  PlatformContractResponse,
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
  QueryBatchResponse,
  QueryCandidate,
  QueryResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryWithMetadataResponse,
  RecommendResponse,
  RecordOutcomeRequest,
  RegisterTriggerRequest,
  RepositoryApplyRequest,
  RepositoryApplyResponse,
  RepositoryDecisionPlanCreateRequest,
  RepositoryDecisionPlanRevisionResponse,
  RepositoryGraphQueryRequest,
  RepositoryGraphQueryResponse,
  RepositoryIntelligenceCapabilitiesResponse,
  RepositorySimulationRequest,
  RepositorySnapshotCreateRequest,
  RepositorySnapshotResponse,
  RepositoryTriageRequest,
  RepositoryTriageResponse,
  RerankRequest,
  RerankResponse,
  ResolvedPlan,
  ResolveResponse,
  ResponsesRequest,
  ResponsesResponse,
  ResponseStreamEventResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeManifestResponse,
  RuntimeReleaseValidationResponse,
  ScoreResponse,
  SimulateRequest,
  SourceRegistrationResponse,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamListResponse,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  TemplateListResponse,
  TokenizeRequest,
  TokenizeResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  TypedField,
  TypedFieldType,
  UpdateExecutionPolicyRequest,
  UpdateMeRequest,
  UsageInfo,
  VerifyResponse,
  WebhookTestResponse,
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


import {
  AGGREGATION_KEYWORDS,
  FILTER_FALSE_VALUES,
  FILTER_NULL_OPS,
  FILTER_NUMERIC_OPS,
  FILTER_SUPPORTED_OPS,
  FILTER_TRUE_VALUES,
  LOCAL_TIME_FIELD_CUES,
  LocalRecord,
  LocalResolvedFilterCondition,
  LocalSource,
  METRIC_SYNONYMS,
} from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { normalizeText } from "./_runtime_helpers_a.js";
import { baseHeaderName } from "./_runtime_helpers_c.js";

export function isExactFieldMatch(field: string, hint: string): boolean {
  return normalizeText(field) === normalizeText(hint);
}

export function metricSynonymSet(hint: string): Set<string> {
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

export function parseRawText(rawText: string): Record<string, unknown> {
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

export function mergeRequest(
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

// Canonical aggregation names shared verbatim with the Python SDK (`avg`, never `mean`) —
// the canonical string is embedded in resolved plans and therefore in plan_hash, so both
// SDKs must canonicalize identically for cross-language hash parity.
export const CANONICAL_AGGREGATIONS = ["sum", "avg", "count", "min", "max"] as const;

// A Map, not a plain object: the key is caller-supplied text, and a plain object also answers
// for everything it inherits from Object.prototype ("constructor", "toString", "__proto__", ...),
// so those spellings resolved to an inherited function instead of throwing. Map.get is own-keys
// only, exactly like the Python SDK's dict.get in map_query.canonicalize_aggregation.
const AGGREGATION_ALIASES: ReadonlyMap<string, string> = new Map([
  ["sum", "sum"],
  ["total", "sum"],
  ["avg", "avg"],
  ["average", "avg"],
  ["mean", "avg"],
  ["count", "count"],
  ["min", "min"],
  ["minimum", "min"],
  ["max", "max"],
  ["maximum", "max"],
]);

/** Map an aggregation spelling to its canonical name; throw on unknown.
 * Unknown aggregations must never silently fall back to sum. */
export function canonicalizeAggregation(value: string): string {
  const canonical = AGGREGATION_ALIASES.get(value.trim().toLowerCase());
  if (canonical === undefined) {
    throw new RuntimeValidationError(
      "invalid_aggregation",
      `Unknown aggregation '${value}'. Supported: ${[...CANONICAL_AGGREGATIONS].sort().join(", ")}.`,
      { aggregation: value, supported: [...CANONICAL_AGGREGATIONS].sort() },
    );
  }
  return canonical;
}

export function resolveAggregation(request: Record<string, unknown>): string {
  if (typeof request.aggregation === "string" && request.aggregation.trim()) {
    return canonicalizeAggregation(request.aggregation);
  }
  if (typeof request.raw_text === "string") {
    const parsed = parseRawText(request.raw_text);
    if (typeof parsed.aggregation === "string") {
      return parsed.aggregation;
    }
  }
  return "sum";
}

export function orderedFields(records: LocalRecord[]): string[] {
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

export function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

// ISO-date-like strings vote "date" during typed-field inference. Shared
// verbatim with the Python SDK's _ISO_DATE_LIKE_RE.
const ISO_DATE_LIKE_RE = /^\d{4}-\d{2}-\d{2}([T ].*)?$/;

// Tie-break precedence for typed-field majority votes. Shared verbatim with the
// Python SDK's _TYPED_FIELD_PRECEDENCE (conformance-tested cross-language).
const TYPED_FIELD_PRECEDENCE: TypedFieldType[] = [
  "number",
  "date",
  "string",
  "boolean",
  "unknown",
];

const TYPED_FIELD_SAMPLE_SIZE = 50;

function typedFieldVote(value: unknown): TypedFieldType {
  if (numericValue(value) !== null) return "number";
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "string") {
    return ISO_DATE_LIKE_RE.test(value) ? "date" : "string";
  }
  return "unknown";
}

/** Infer a coarse type per field from up to the first 50 records.
 *
 * Semantics mirror the Python SDK's infer_typed_fields exactly (conformance-
 * tested): non-null sampled values vote number / boolean / date / string /
 * unknown, the majority wins, ties break by precedence number > date > string >
 * boolean > unknown, and fields with no non-null sampled values are "unknown". */
export function inferTypedFields(records: LocalRecord[], fields: string[]): TypedField[] {
  const sample = records.slice(0, TYPED_FIELD_SAMPLE_SIZE);
  return fields.map(fieldName => {
    const votes = new Map<TypedFieldType, number>(
      TYPED_FIELD_PRECEDENCE.map(typeName => [typeName, 0]),
    );
    for (const record of sample) {
      const value = record[fieldName];
      if (value === null || value === undefined) continue;
      const vote = typedFieldVote(value);
      votes.set(vote, (votes.get(vote) ?? 0) + 1);
    }
    let inferred: TypedFieldType = "unknown";
    let bestCount = 0;
    for (const typeName of TYPED_FIELD_PRECEDENCE) {
      const count = votes.get(typeName) ?? 0;
      if (count > bestCount) {
        inferred = typeName;
        bestCount = count;
      }
    }
    return { name: fieldName, type: inferred };
  });
}

export function booleanValue(value: unknown): boolean | null {
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

export function isNullishFilterValue(value: unknown): boolean {
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

export function valuesEqual(rowValue: unknown, expected: unknown): boolean {
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

export function parseDateValue(value: unknown): Date | null {
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

export function timeRange(filterName: string): { start: Date; end: Date } | null {
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

export function sampleBooleanField(records: LocalRecord[], fieldName: string): boolean {
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

export function fieldMatchScore(fieldName: string, hint: string): { score: number; exact: boolean } {
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

export function preferredFilterValueType(condition: Record<string, unknown>): "numeric" | "boolean" | null {
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

export function resolveLocalFilterColumn(source: LocalSource, condition: Record<string, unknown>): string {
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

export function resolveLocalFilterConditions(
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

export function rowMatchesFilterCondition(
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

export function applyLocalFilterConditions(
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

export function findLocalTimeField(source: LocalSource): string | null {
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

export function isNumericField(field: string, records: LocalRecord[]): boolean {
  let seen = false;
  for (const record of records) {
    if (!(field in record)) continue;
    const parsed = numericValue(record[field]);
    if (parsed === null) return false;
    seen = true;
  }
  return seen;
}

export function semanticScore(field: string, hint: string): { score: number; reasons: string[] } {
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

export function dedupeStrings(values: string[]): string[] {
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

export function sourceSetFromRequest(request: Record<string, unknown>): string[] {
  const values: string[] = [];
  if (typeof request.source_name === "string") values.push(request.source_name);
  if (typeof request.join_source_name === "string") values.push(request.join_source_name);
  return dedupeStrings(values);
}

export function buildExplainJoinPath(sourceSet: string[]): Array<Record<string, unknown>> {
  if (sourceSet.length < 2) return [];
  return sourceSet.slice(0, -1).map((source, index) => ({
    left_source: source,
    right_source: sourceSet[index + 1],
  }));
}

export function roundLatency(startMs: number): number {
  return Number((Date.now() - startMs).toFixed(3));
}

export function registrationFields(registration: SourceRegistrationResponse): string[] {
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

export function registrationResolvedSourceName(
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

export function registrationDatasetId(
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

export function bundleFieldTokens(field: string): Set<string> {
  return new Set(normalizeText(baseHeaderName(field)).match(/[a-z0-9]+/g) ?? []);
}

export function fieldOverlapScore(left: string, right: string): number {
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

