/** Auto-split sub-module of client.ts — compatibility + capability plane internal validators. */

/**
 * Algenta TypeScript SDK — fetch-based client.
 * Works in Node.js 18+ and modern browsers.
 *
 * @example
 * import { AlgentaClient } from 'algenta-sdk';
 *
 * const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
 * if (!apiKey) {
 *   throw new Error('Set ALGENTA_API_KEY or DE_API_KEY before running this example.');
 * }
 * const client = new AlgentaClient({ apiKey });
 * const result = await client.simulate({
 *   mode: 'auto',
 *   scenario: {
 *     variables: { revenue: { low: 80000, high: 200000 } },
 *     objective: 'maximize_net_value',
 *   },
 * });
 * console.log(result.recommended_action, result.confidence);
 *
 * This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
 * pass an explicit self-hosted `baseUrl` and use the API key provisioned by
 * your self-hosted operator deployment instead. Private profiles fail closed
 * and do not silently fall back to Algenta cloud.
 */

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
  AuditLogEntry,
  AuditLogResponse,
  BillingInfoResponse,
  BillingSessionResponse,
  BatchResult,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
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
  CapabilityPlaneContract,
  CapabilityProviderResponse,
  CapabilityRoutePlan,
  CapabilityRouteRequest,
  CompatibilityContract,
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
  CreateDeploymentRequest,
  CreateConnectorRequest,
  DecisionListResponse,
  DecisionLogResponse,
  DistributionInfoResponse,
  DistributionListResponse,
  DeviceListEntryResponse,
  DeviceListResponse,
  DeviceRegistrationResponse,
  DeviceRevokeResponse,
  DefaultsContract,
  DecisionEnvelope,
  DecisionEngineClientConfig,
  DecisionPlanResponse,
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
  DeploymentCostResponse,
  DeploymentDeleteResponse,
  DeploymentProviderResponse,
  DeploymentRegionResponse,
  DeploymentRegionsResponse,
  DeploymentResponse,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetInfo,
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
  ExplainResponse,
  JobListResponse,
  JobStatusResponse,
  JobSubmitResponse,
  WebhookTestResponse,
  LLMModelListResponse,
  LogDecisionRequest,
  MeteringBatchRequest,
  MeteringBatchResponse,
  MeResponse,
  PlatformContractResponse,
  PrivacyRegistryContract,
  PrimaryDataQueryContract,
  PreviewConnectorRequest,
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
  QueryBatchResponse,
  QueryExecutionMetadata,
  QueryFilterSpec,
  QueryResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryWithMetadataResponse,
  RecordOutcomeRequest,
  ResponseStreamEventResponse,
  RecommendResponse,
  ResolveResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeBenchmarkClassCode,
  RuntimeCompiledEngine,
  RuntimeLayer,
  RuntimeManifestResponse,
  RuntimeMaturity,
  RuntimeModuleId,
  RuntimeReleaseValidationResponse,
  ScoreResponse,
  SimulateRequest,
  SourceRegistrationRequest,
  SourceRegistrationResponse,
  ResponsesRequest,
  ResponsesResponse,
  RerankRequest,
  RerankResponse,
  TokenizeRequest,
  TokenizeResponse,
  TeamListResponse,
  TeamInviteRequest,
  TeamInviteResponse,
  TeamMemberInfo,
  TemplateInfoResponse,
  TemplateListResponse,
  TriggerDeleteResponse,
  TriggerFireResponse,
  TriggerListResponse,
  TriggerPauseResponse,
  TriggerResponse,
  RegisterTriggerRequest,
  TeamRemoveResponse,
  TeamRoleUpdateResponse,
  UpdateMeRequest,
  UpdateConnectorRequest,
  UpdateExecutionPolicyRequest,
  UsageInfo,
  VerifyResponse,
  LimitsInfo,
} from './types.js';
import {
  ALGENTA_OWNED_HOSTS,
  ALGENTA_OWNED_SUFFIXES,
  API_KEY_PREFIX_LIVE,
  API_KEY_PREFIX_TEST,
  AUTH_SCHEME,
  BRAND,
  CONTRACT_VERSION,
  DEFAULT_BASE_URL,
  DEPRECATION_WINDOW_DAYS,
  INTEGRATIONS,
  LEGACY_DOMAINS,
  LEGACY_ENV_VARS,
  LEGACY_HEADERS,
  MCP_ENDPOINT,
  MCP_LEGACY_SSE_ENDPOINT,
  MCP_PROTOCOL_VERSION,
  MCP_TRANSPORT,
  MCP_TOOLS_ENDPOINT,
  PLAN_LIMITS,
  PRIVATE_HOST_SUFFIXES,
  CAPABILITY_PLANE_CONTRACT,
  PRIMARY_DATA_QUERY_CONTRACT,
  READ_ONLY_DEFAULT,
  VENDOR_TELEMETRY_HOSTS,
  WRITE_CONFIRMATION_REQUIRED,
} from './contract.js';
import { DEVICE_ID_HEADER, resolveClientDeviceHeaders } from './client_device_headers.js';
import {
  DEVICE_BINDING_TOKEN_HEADER,
  loadHostedDeviceBindingToken,
  persistHostedDeviceBindingToken,
} from './client_device_binding.js';
import { apiKeyHelpText, resolveClientBaseUrl } from './privacy_profile.js';


import { cloneJsonValue, mergeContractSections, rebaseEndpoint } from "./_client_constants.js";
import { DecisionEngineError } from "./_client_errors.js";
import { assertStringArray } from "./_client_platform_validators_a1.js";
import { assertArray, assertBoolean, assertFiniteNumber, assertInteger, assertJsonObject, assertNonEmptyString } from "./_client_platform_validators_b2.js";

export function assertPrimaryDataQueryContractExtension(
  payload: unknown,
): PrimaryDataQueryContract {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback payload must be a JSON object.",
      0,
      "invalid_contract_payload",
    );
  }
  const extension = (payload as { ["x-primary-data-query-contract"]?: unknown })[
    "x-primary-data-query-contract"
  ];
  if (!extension || typeof extension !== "object" || Array.isArray(extension)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing x-primary-data-query-contract.",
      0,
      "contract_extension_missing",
    );
  }
  const apiContract = (extension as { api?: unknown }).api;
  if (!apiContract || typeof apiContract !== "object" || Array.isArray(apiContract)) {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing the api contract section.",
      0,
      "invalid_contract_payload",
    );
  }
  if (typeof (apiContract as { contract_endpoint?: unknown }).contract_endpoint !== "string") {
    throw new DecisionEngineError(
      "OpenAPI contract fallback is missing api.contract_endpoint.",
      0,
      "invalid_contract_payload",
    );
  }
  const merged = mergeContractSections(PRIMARY_DATA_QUERY_CONTRACT, extension);
  return merged;
}

export function buildPlatformContractFromOpenApi(
  baseUrl: string,
  payload: unknown,
): PlatformContractResponse {
  const apiBaseUrl = baseUrl.replace(/\/$/, "");
  const schema =
    payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as { ["x-capability-plane-contract"]?: unknown })
      : {};
  let capabilityPlane: CapabilityPlaneContract | null = null;
  const capabilityPlaneExtension = schema["x-capability-plane-contract"];
  if (capabilityPlaneExtension !== undefined) {
    if (
      !capabilityPlaneExtension ||
      typeof capabilityPlaneExtension !== "object" ||
      Array.isArray(capabilityPlaneExtension)
    ) {
      throw new DecisionEngineError(
        "OpenAPI contract fallback returned an invalid x-capability-plane-contract payload.",
        0,
        "invalid_contract_payload",
      );
    }
    capabilityPlane = mergeContractSections(
      CAPABILITY_PLANE_CONTRACT,
      capabilityPlaneExtension,
    ) as CapabilityPlaneContract;
  }
  return {
    contract_version: CONTRACT_VERSION,
    brand: BRAND,
    api_base_url: apiBaseUrl,
    mcp_endpoint: rebaseEndpoint(apiBaseUrl, MCP_ENDPOINT),
    mcp_transport: MCP_TRANSPORT,
    mcp_protocol_version: MCP_PROTOCOL_VERSION,
    mcp_legacy_sse_endpoint: rebaseEndpoint(apiBaseUrl, MCP_LEGACY_SSE_ENDPOINT),
    mcp_tools_endpoint: rebaseEndpoint(apiBaseUrl, MCP_TOOLS_ENDPOINT),
    auth_scheme: AUTH_SCHEME,
    api_key_prefixes: {
      live: API_KEY_PREFIX_LIVE,
      test: API_KEY_PREFIX_TEST,
    },
    compatibility: {
      legacy_headers: [...LEGACY_HEADERS],
      legacy_env_vars: [...LEGACY_ENV_VARS],
      legacy_domains: [...LEGACY_DOMAINS],
      deprecation_window_days: DEPRECATION_WINDOW_DAYS,
    } satisfies CompatibilityContract,
    privacy_registry: {
      algenta_owned_hosts: [...ALGENTA_OWNED_HOSTS],
      algenta_owned_suffixes: [...ALGENTA_OWNED_SUFFIXES],
      vendor_telemetry_hosts: [...VENDOR_TELEMETRY_HOSTS],
      private_host_suffixes: [...PRIVATE_HOST_SUFFIXES],
    } satisfies PrivacyRegistryContract,
    defaults: {
      read_only_default: READ_ONLY_DEFAULT,
      write_confirmation_required: WRITE_CONFIRMATION_REQUIRED,
      plan_limits: cloneJsonValue(PLAN_LIMITS),
    } satisfies DefaultsContract,
    primary_data_query_contract: cloneJsonValue(assertPrimaryDataQueryContractExtension(payload)),
    capability_plane: capabilityPlane,
    integrations: cloneJsonValue(INTEGRATIONS),
  };
}

export function assertApiKeyPrefixes(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.live, `${context}.live`);
  assertNonEmptyString(obj.test, `${context}.test`);
}

export function assertCompatibilityContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.legacy_headers, `${context}.legacy_headers`);
  assertStringArray(obj.legacy_env_vars, `${context}.legacy_env_vars`);
  assertStringArray(obj.legacy_domains, `${context}.legacy_domains`);
  assertInteger(obj.deprecation_window_days, `${context}.deprecation_window_days`);
}

export function assertPrivacyRegistryContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.algenta_owned_hosts, `${context}.algenta_owned_hosts`);
  assertStringArray(obj.algenta_owned_suffixes, `${context}.algenta_owned_suffixes`);
  assertStringArray(obj.vendor_telemetry_hosts, `${context}.vendor_telemetry_hosts`);
  assertStringArray(obj.private_host_suffixes, `${context}.private_host_suffixes`);
}

export function assertDefaultsContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertBoolean(obj.read_only_default, `${context}.read_only_default`);
  assertBoolean(obj.write_confirmation_required, `${context}.write_confirmation_required`);
  const planLimits = assertJsonObject(obj.plan_limits, `${context}.plan_limits`);
  for (const [planName, limitPayload] of Object.entries(planLimits)) {
    const limits = assertJsonObject(limitPayload, `${context}.plan_limits.${planName}`);
    for (const [limitName, limitValue] of Object.entries(limits)) {
      if (typeof limitValue === "string") {
        if (!limitValue.trim()) {
          throw new DecisionEngineError(
            `${context}.plan_limits.${planName}.${limitName} must be a non-empty string.`,
          );
        }
        continue;
      }
      assertFiniteNumber(limitValue, `${context}.plan_limits.${planName}.${limitName}`);
    }
  }
}

export function assertIntegrationContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.name, `${context}.name`);
  assertNonEmptyString(obj.description, `${context}.description`);
  assertNonEmptyString(obj.icon, `${context}.icon`);
  assertStringArray(obj.capabilities, `${context}.capabilities`);
  assertNonEmptyString(obj.auth_scheme, `${context}.auth_scheme`);
  assertStringArray(obj.required_scopes, `${context}.required_scopes`);
  assertBoolean(obj.read_only_default, `${context}.read_only_default`);
  assertStringArray(obj.write_actions, `${context}.write_actions`);
  assertStringArray(obj.admin_controls, `${context}.admin_controls`);
  assertNonEmptyString(obj.docs_url, `${context}.docs_url`);
  assertNonEmptyString(obj.privacy_url, `${context}.privacy_url`);
  assertNonEmptyString(obj.terms_url, `${context}.terms_url`);
  assertNonEmptyString(obj.support_url, `${context}.support_url`);
  assertStringArray(obj.regions, `${context}.regions`);
  assertNonEmptyString(obj.status, `${context}.status`);
}

export function assertPrimaryDataQueryApiPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_endpoint, `${context}.contract_endpoint`);
  assertNonEmptyString(obj.discovery_endpoint, `${context}.discovery_endpoint`);
  assertNonEmptyString(obj.summary_endpoint, `${context}.summary_endpoint`);
  assertNonEmptyString(obj.resolve_endpoint, `${context}.resolve_endpoint`);
  assertNonEmptyString(obj.verify_endpoint, `${context}.verify_endpoint`);
  assertNonEmptyString(obj.query_endpoint, `${context}.query_endpoint`);
  assertNonEmptyString(obj.query_batch_endpoint, `${context}.query_batch_endpoint`);
  assertNonEmptyString(obj.query_sql_report_endpoint, `${context}.query_sql_report_endpoint`);
}

export function assertGovernedFilterOperatorsPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.scalar, `${context}.scalar`);
  assertStringArray(obj.list, `${context}.list`);
  assertStringArray(obj.nullary, `${context}.nullary`);
}

export function assertGovernedFilterTypeBehaviorPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.boolean, `${context}.boolean`);
  assertStringArray(obj.string, `${context}.string`);
  assertStringArray(obj.numeric, `${context}.numeric`);
  assertStringArray(obj.null_checks, `${context}.null_checks`);
}

export function assertGovernedFilterValidationPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertBoolean(obj.requires_selector, `${context}.requires_selector`);
  assertStringArray(obj.scalar_ops_require_value, `${context}.scalar_ops_require_value`);
  assertStringArray(
    obj.list_ops_require_non_empty_values,
    `${context}.list_ops_require_non_empty_values`,
  );
  assertStringArray(
    obj.nullary_ops_forbid_value_and_values,
    `${context}.nullary_ops_forbid_value_and_values`,
  );
}

export function assertGovernedFilterContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.kind, `${context}.kind`);
  assertNonEmptyString(obj.time_filter_field, `${context}.time_filter_field`);
  assertNonEmptyString(obj.conditions_field, `${context}.conditions_field`);
  assertStringArray(obj.selector_fields, `${context}.selector_fields`);
  assertGovernedFilterOperatorsPayload(obj.operators, `${context}.operators`);
  assertGovernedFilterTypeBehaviorPayload(obj.type_behavior, `${context}.type_behavior`);
  assertGovernedFilterValidationPayload(obj.validation, `${context}.validation`);
  assertBoolean(obj.applies_before_aggregation, `${context}.applies_before_aggregation`);
  assertBoolean(obj.supports_non_sql_backends, `${context}.supports_non_sql_backends`);
  assertStringArray(obj.notes, `${context}.notes`);
}

export function assertDirectPythonSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_root, `${context}.import_root`);
  assertNonEmptyString(obj.preferred_client_class, `${context}.preferred_client_class`);
  assertNonEmptyString(
    obj.preferred_async_client_class,
    `${context}.preferred_async_client_class`,
  );
  assertNonEmptyString(obj.compatibility_client_class, `${context}.compatibility_client_class`);
  assertNonEmptyString(
    obj.compatibility_async_client_class,
    `${context}.compatibility_async_client_class`,
  );
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

export function assertDirectTypeScriptSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_package, `${context}.import_package`);
  assertNonEmptyString(obj.preferred_client_class, `${context}.preferred_client_class`);
  assertNonEmptyString(obj.compatibility_client_class, `${context}.compatibility_client_class`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

export function assertRuntimePythonSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_root, `${context}.import_root`);
  assertNonEmptyString(obj.runtime_class, `${context}.runtime_class`);
  assertNonEmptyString(obj.libraries_entrypoint, `${context}.libraries_entrypoint`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

export function assertRuntimeTypeScriptSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.import_package, `${context}.import_package`);
  assertNonEmptyString(obj.runtime_class, `${context}.runtime_class`);
  assertNonEmptyString(obj.libraries_entrypoint, `${context}.libraries_entrypoint`);
  assertNonEmptyString(obj.contract_method, `${context}.contract_method`);
  assertNonEmptyString(obj.discovery_method, `${context}.discovery_method`);
  assertNonEmptyString(obj.summary_method, `${context}.summary_method`);
  assertNonEmptyString(obj.query_with_metadata_method, `${context}.query_with_metadata_method`);
  assertNonEmptyString(obj.query_batch_method, `${context}.query_batch_method`);
  assertNonEmptyString(obj.query_sql_report_method, `${context}.query_sql_report_method`);
}

export function assertDirectSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertDirectPythonSdkContractPayload(obj.python, `${context}.python`);
  assertDirectTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

export function assertRuntimeSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertRuntimePythonSdkContractPayload(obj.python, `${context}.python`);
  assertRuntimeTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

export function assertCliContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_command, `${context}.contract_command`);
  assertNonEmptyString(obj.discovery_command, `${context}.discovery_command`);
  assertNonEmptyString(obj.summary_command, `${context}.summary_command`);
  assertNonEmptyString(obj.query_batch_command, `${context}.query_batch_command`);
  assertNonEmptyString(obj.query_sql_report_command, `${context}.query_sql_report_command`);
  assertNonEmptyString(obj.runtime_modules_command, `${context}.runtime_modules_command`);
  assertNonEmptyString(obj.runtime_functions_command, `${context}.runtime_functions_command`);
  assertNonEmptyString(obj.runtime_execute_command, `${context}.runtime_execute_command`);
}

export function assertMcpContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_tool, `${context}.contract_tool`);
  assertNonEmptyString(obj.discovery_tool, `${context}.discovery_tool`);
  assertNonEmptyString(obj.summary_tool, `${context}.summary_tool`);
  assertNonEmptyString(obj.query_tool, `${context}.query_tool`);
  assertNonEmptyString(obj.query_batch_tool, `${context}.query_batch_tool`);
  assertNonEmptyString(obj.query_sql_report_tool, `${context}.query_sql_report_tool`);
  assertNonEmptyString(obj.runtime_library_list_tool, `${context}.runtime_library_list_tool`);
  assertNonEmptyString(
    obj.runtime_library_execute_tool,
    `${context}.runtime_library_execute_tool`,
  );
}

export function assertRecommendedFlowsPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.machine_readable_contract, `${context}.machine_readable_contract`);
  assertStringArray(obj.governed_query, `${context}.governed_query`);
  assertStringArray(obj.multi_metric_query, `${context}.multi_metric_query`);
  assertStringArray(obj.wide_sql_report, `${context}.wide_sql_report`);
}

export function assertPrimaryDataQueryContractPayload(
  payload: unknown,
  context: string,
): PrimaryDataQueryContract {
  const obj = assertJsonObject(payload, context);
  assertPrimaryDataQueryApiPayload(obj.api, `${context}.api`);
  assertGovernedFilterContractPayload(
    obj.governed_filter_contract,
    `${context}.governed_filter_contract`,
  );
  assertDirectSdkContractPayload(obj.direct_sdk, `${context}.direct_sdk`);
  assertRuntimeSdkContractPayload(obj.runtime_sdk, `${context}.runtime_sdk`);
  assertCliContractPayload(obj.cli, `${context}.cli`);
  assertMcpContractPayload(obj.mcp, `${context}.mcp`);
  assertRecommendedFlowsPayload(obj.recommended_flows, `${context}.recommended_flows`);
  return cloneJsonValue(obj) as unknown as PrimaryDataQueryContract;
}

export function assertCapabilityPlaneApiContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  [
    "list_providers_endpoint",
    "get_provider_endpoint",
    "list_bindings_endpoint",
    "create_binding_endpoint",
    "get_binding_endpoint",
    "update_binding_endpoint",
    "delete_binding_endpoint",
    "preview_test_binding_endpoint",
    "test_binding_endpoint",
    "preview_discover_binding_endpoint",
    "discover_binding_endpoint",
    "start_authorization_endpoint",
    "complete_authorization_endpoint",
    "list_capabilities_endpoint",
    "get_capability_endpoint",
    "route_capabilities_endpoint",
    "execute_capability_endpoint",
    "record_outcome_endpoint",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

export function assertCapabilityPlaneEnumsContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertStringArray(obj.provider_types, `${context}.provider_types`);
  assertStringArray(obj.capability_kinds, `${context}.capability_kinds`);
  assertStringArray(obj.implementation_kinds, `${context}.implementation_kinds`);
  assertStringArray(obj.execution_owners, `${context}.execution_owners`);
  assertStringArray(obj.binding_scopes, `${context}.binding_scopes`);
  assertStringArray(obj.binding_statuses, `${context}.binding_statuses`);
}

export function assertCapabilityPlaneTypeScriptSdkContractPayload(
  payload: unknown,
  context: string,
): void {
  const obj = assertJsonObject(payload, context);
  [
    "import_package",
    "preferred_client_class",
    "compatibility_client_class",
    "list_providers_method",
    "get_provider_method",
    "list_bindings_method",
    "create_binding_method",
    "get_binding_method",
    "update_binding_method",
    "delete_binding_method",
    "preview_test_binding_method",
    "test_binding_method",
    "preview_discover_binding_method",
    "discover_binding_method",
    "start_authorization_method",
    "complete_authorization_method",
    "list_capabilities_method",
    "get_capability_method",
    "route_capabilities_method",
    "execute_capability_method",
    "record_outcome_method",
    "list_skills_method",
    "enable_skill_method",
    "disable_skill_method",
    "list_mcp_providers_method",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

export function assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload(
  payload: unknown,
  context: string,
): void {
  const obj = assertJsonObject(payload, context);
  [
    "import_package",
    "runtime_class",
    "list_providers_method",
    "list_bindings_method",
    "list_capabilities_method",
    "route_capabilities_method",
    "execute_capability_method",
    "register_adapter_method",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
}

export function assertCapabilityPlaneDirectSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneTypeScriptSdkContractPayload(obj.typescript, `${context}.typescript`);
}

export function assertCapabilityPlaneRuntimeSdkContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneRuntimeTypeScriptSdkContractPayload(
    obj.typescript,
    `${context}.typescript`,
  );
}

export function assertCapabilityPlaneMcpContractPayload(payload: unknown, context: string): void {
  const obj = assertJsonObject(payload, context);
  [
    "list_providers_tool",
    "list_bindings_tool",
    "create_binding_tool",
    "test_binding_tool",
    "discover_binding_tool",
    "list_capabilities_tool",
    "get_capability_tool",
    "route_capabilities_tool",
    "execute_capability_tool",
    "list_skills_tool",
    "enable_skill_tool",
    "disable_skill_tool",
  ].forEach(fieldName => assertNonEmptyString(obj[fieldName], `${context}.${fieldName}`));
  assertStringArray(obj.compatibility_aliases, `${context}.compatibility_aliases`);
}

export function assertCapabilityPlaneContractPayload(
  payload: unknown,
  context: string,
): CapabilityPlaneContract {
  const obj = assertJsonObject(payload, context);
  assertCapabilityPlaneApiContractPayload(obj.api, `${context}.api`);
  assertCapabilityPlaneEnumsContractPayload(obj.enums, `${context}.enums`);
  assertCapabilityPlaneDirectSdkContractPayload(obj.direct_sdk, `${context}.direct_sdk`);
  assertCapabilityPlaneRuntimeSdkContractPayload(obj.runtime_sdk, `${context}.runtime_sdk`);
  assertCapabilityPlaneMcpContractPayload(obj.mcp, `${context}.mcp`);
  return cloneJsonValue(obj) as unknown as CapabilityPlaneContract;
}

export function assertPlatformContractPayload(
  payload: unknown,
  context: string,
): PlatformContractResponse {
  const obj = assertJsonObject(payload, context);
  assertNonEmptyString(obj.contract_version, `${context}.contract_version`);
  assertNonEmptyString(obj.brand, `${context}.brand`);
  assertNonEmptyString(obj.api_base_url, `${context}.api_base_url`);
  assertNonEmptyString(obj.mcp_endpoint, `${context}.mcp_endpoint`);
  assertNonEmptyString(obj.mcp_transport, `${context}.mcp_transport`);
  assertNonEmptyString(obj.mcp_protocol_version, `${context}.mcp_protocol_version`);
  assertNonEmptyString(obj.mcp_legacy_sse_endpoint, `${context}.mcp_legacy_sse_endpoint`);
  assertNonEmptyString(obj.mcp_tools_endpoint, `${context}.mcp_tools_endpoint`);
  assertNonEmptyString(obj.auth_scheme, `${context}.auth_scheme`);
  assertApiKeyPrefixes(obj.api_key_prefixes, `${context}.api_key_prefixes`);
  assertCompatibilityContractPayload(obj.compatibility, `${context}.compatibility`);
  assertPrivacyRegistryContractPayload(obj.privacy_registry, `${context}.privacy_registry`);
  assertDefaultsContractPayload(obj.defaults, `${context}.defaults`);
  assertPrimaryDataQueryContractPayload(
    obj.primary_data_query_contract,
    `${context}.primary_data_query_contract`,
  );
  if (obj.capability_plane !== undefined && obj.capability_plane !== null) {
    assertCapabilityPlaneContractPayload(obj.capability_plane, `${context}.capability_plane`);
  }
  assertArray(obj.integrations, `${context}.integrations`).forEach((entry, index) =>
    assertIntegrationContractPayload(entry, `${context}.integrations[${index}]`),
  );
  return cloneJsonValue(obj) as unknown as PlatformContractResponse;
}

export function wrapContractValidation<T>(
  context: string,
  payload: unknown,
  validator: (value: unknown) => T,
): T {
  try {
    return validator(payload);
  } catch (error) {
    if (error instanceof DecisionEngineError) {
      const details =
        error.details && typeof error.details === "object" && !Array.isArray(error.details)
          ? error.details
          : { cause: error.message };
      throw new DecisionEngineError(
        `${context} returned an invalid payload: ${error.message}`,
        0,
        "invalid_contract_payload",
        {
          error: {
            code: "invalid_contract_payload",
            details,
          },
        },
      );
    }
    throw error;
  }
}
