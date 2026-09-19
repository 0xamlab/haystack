// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — imports, types, module-level constants. */

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

export const RUNTIME_DATASET_SCOPE_KEY = "__runtime_dataset_id__";

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

export type LocalRecord = Record<string, unknown>;

export interface LocalSource {
  name: string;
  records: LocalRecord[];
  fields: string[];
  schemaRevision: string;
  datasetId: string;
}

export interface LocalResolvedFilterCondition {
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

export interface RankedField {
  field: string;
  score: number;
  reasons: string[];
}

export interface LocalRuntimeLicense {
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

export interface LicenseExchangeResponse {
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

export interface TrustedTimeState {
  version: number;
  trusted_epoch: number;
  source: string;
}

export const AGGREGATION_KEYWORDS: Array<[string, string]> = [
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

export const METRIC_SYNONYMS: Record<string, string[]> = {
  revenue: ["sales", "net sales", "income", "gmv"],
  profit: ["margin", "net profit"],
  cost: ["expense", "spend"],
  quantity: ["qty", "units", "count"],
};

export const TITLE_ART = [
  " █████╗ ██╗      ██████╗ ███████╗███╗   ██╗████████╗ █████╗ ",
  "██╔══██╗██║     ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔══██╗",
  "███████║██║     ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████║",
  "██╔══██║██║     ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██╔══██║",
  "██║  ██║███████╗╚██████╔╝███████╗██║ ╚████║   ██║   ██║  ██║",
  "╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝",
];

export const TITLE_COLORS = [
  "\u001b[38;5;75m",
  "\u001b[38;5;81m",
  "\u001b[38;5;111m",
  "\u001b[38;5;141m",
  "\u001b[38;5;176m",
  "\u001b[38;5;204m",
];

export const MUTED = "\u001b[38;5;245m";
export const ACCENT = "\u001b[38;5;183m";
export const RESET = "\u001b[0m";
export const MEASURE_TOKENS = new Set([
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
export const CSV_INT_RE = /^[+-]?\d+$/;
export const CSV_FLOAT_RE = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;
export const CSV_LEADING_ZERO_INT_RE = /^[+-]?0\d+$/;
export const CSV_CURRENCY_PREFIX_RE = /^[\$£€¥]+/;
export const CSV_TOKEN_RE = /[a-z0-9]+/g;
export const FILTER_SUPPORTED_OPS = new Set(["eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"]);
export const FILTER_NUMERIC_OPS = new Set(["gt", "gte", "lt", "lte"]);
export const FILTER_NULL_OPS = new Set(["is_null", "is_not_null"]);
export const FILTER_TRUE_VALUES = new Set(["1", "true", "t", "yes", "y"]);
export const FILTER_FALSE_VALUES = new Set(["0", "false", "f", "no", "n"]);
export const LOCAL_TIME_FIELD_CUES = ["date", "time", "timestamp", "month", "day", "year"];
export const SQLITE_DSN_RE = /^sqlite(?:\+pysqlite)?:\/\/\/(.+)$/i;
export const SQL_IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_$]*$/;
export const SQL_DSN_SCHEMES: Record<string, string> = {
  postgres: "postgresql",
  postgresql: "postgresql",
  mysql: "mysql",
  mssql: "mssql",
  redshift: "redshift",
};
export const SQL_DEFAULT_PORTS: Record<string, number> = {
  postgres: 5432,
  postgresql: 5432,
  mysql: 3306,
  mssql: 1433,
  redshift: 5439,
};
export const HEADER_ALIAS_MIN_COLUMNS = 3;
export const HEADER_ALIAS_MAX_COLUMNS = 8;
export const HEADER_ALIAS_MIN_MATCH_RATIO = 0.6;
export const HEADER_ALIAS_MATCH_SCORE = 0.34;
export const HEADER_ALIAS_AVG_SCORE = 0.45;
export const LICENSE_VERSION = 1;
export const DEFAULT_GRACE_DAYS = 14;
export const TRUSTED_TIME_VERSION = 1;
export const TRUSTED_TIME_PERSIST_INTERVAL_SECONDS = 60;
