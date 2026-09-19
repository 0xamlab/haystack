// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — LLM, contract/runtime manifest,
 * source registration, connector, repository, and dataset methods for
 * DecisionEngineClient.
 *
 * This module augments the {@link DecisionEngineClient} class via TypeScript
 * declaration merging and prototype assignment. Importing this file (for its
 * side effects) is required so the prototype assignments execute and the
 * augmented methods are available on `DecisionEngineClient` instances.
 */

import type {
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
  ConnectDataRequest,
  ConnectorBrowseResult,
  ConnectorInfo,
  ConnectorListResult,
  ConnectorTestInfo,
  CountTokensRequest,
  CountTokensResponse,
  CreateConnectorRequest,
  DatasetConnectResult,
  DatasetDeleteResult,
  DatasetDetailResult,
  DatasetListResult,
  DatasetSummaryResult,
  DecisionEnvelope,
  EmbeddingsRequest,
  EmbeddingsResponse,
  EmbeddingSimilarityRequest,
  EmbeddingSimilarityResponse,
  LLMModelListResponse,
  PlatformContractResponse,
  PreviewConnectorRequest,
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
  ResponsesRequest,
  ResponsesResponse,
  ResponseStreamEventResponse,
  RuntimeAdminBenchmarksResponse,
  RuntimeAdminModulesResponse,
  RuntimeManifestResponse,
  RuntimeReleaseValidationResponse,
  SourceRegistrationRequest,
  SourceRegistrationResponse,
  TokenizeRequest,
  TokenizeResponse,
  UpdateConnectorRequest,
} from "./types.js";
import { DecisionEngineClient } from "./_client_class.js";
import {
  appendQueryParameters,
  normalizeSourceRegistrationRequest,
} from "./_client_constants.js";
import { buildPlatformContractFromOpenApi } from "./_client_contract_validators.js";
import { NotFoundError } from "./_client_errors.js";
import { assertPlatformContractResponse } from "./_client_platform_validators_a1.js";
import {
  assertConnectorListResponse,
  assertDatasetListResponse,
  assertDatasetSummaryResponse,
} from "./_client_platform_validators_b2.js";
import {
  assertRuntimeAdminBenchmarksResponse,
  assertRuntimeAdminModulesResponse,
} from "./_client_runtime_admin.js";
import { assertRuntimeManifestResponse } from "./_client_runtime_manifest.js";
import { assertRuntimeReleaseValidationResponse } from "./_client_runtime_release.js";

declare module "./_client_class.js" {
  interface DecisionEngineClient {
    listModels(): Promise<LLMModelListResponse>;
    resolveArtifactBridge(
      request: ArtifactBridgeResolveRequest,
    ): Promise<ArtifactBridgeResolveResponse>;
    chatCompletions(request: ChatCompletionsRequest): Promise<ChatCompletionsResponse>;
    streamChatCompletions(
      request: ChatCompletionsRequest,
    ): AsyncGenerator<ChatCompletionsStreamChunkResponse>;
    tokenize(request: TokenizeRequest): Promise<TokenizeResponse>;
    countTokens(request: CountTokensRequest): Promise<CountTokensResponse>;
    responses(request: ResponsesRequest): Promise<ResponsesResponse>;
    streamResponses(request: ResponsesRequest): AsyncGenerator<ResponseStreamEventResponse>;
    embeddings(request: EmbeddingsRequest): Promise<EmbeddingsResponse>;
    embeddingSimilarity(
      request: EmbeddingSimilarityRequest,
    ): Promise<EmbeddingSimilarityResponse>;
    rerank(request: RerankRequest): Promise<RerankResponse>;
    getContract(): Promise<PlatformContractResponse>;
    getRuntimeManifest(): Promise<RuntimeManifestResponse>;
    getRuntimeModules(): Promise<RuntimeAdminModulesResponse>;
    getRuntimeBenchmarks(): Promise<RuntimeAdminBenchmarksResponse>;
    getRuntimeReleaseValidation(): Promise<RuntimeReleaseValidationResponse>;
    registerSource(
      source: SourceRegistrationRequest | Record<string, unknown>,
      options?: { description?: string; name?: string },
    ): Promise<SourceRegistrationResponse>;
    refreshSource(datasetId: string): Promise<SourceRegistrationResponse>;
    createConnector(request: CreateConnectorRequest): Promise<ConnectorInfo>;
    listConnectors(options?: { page?: number; limit?: number }): Promise<ConnectorListResult>;
    getConnector(connectorId: string): Promise<ConnectorInfo>;
    updateConnector(
      connectorId: string,
      request: UpdateConnectorRequest,
    ): Promise<ConnectorInfo>;
    testConnector(connectorId: string): Promise<ConnectorTestInfo>;
    previewTestConnector(request: PreviewConnectorRequest): Promise<ConnectorTestInfo>;
    browseConnector(connectorId: string): Promise<ConnectorBrowseResult>;
    previewBrowseConnector(request: PreviewConnectorRequest): Promise<ConnectorBrowseResult>;
    createRepositorySnapshot(
      repositoryId: string,
      request: RepositorySnapshotCreateRequest,
    ): Promise<RepositorySnapshotResponse>;
    getRepositoryIntelligenceCapabilities(): Promise<RepositoryIntelligenceCapabilitiesResponse>;
    getRepositorySnapshot(
      repositoryId: string,
      snapshotId: string,
    ): Promise<RepositorySnapshotResponse>;
    triageRepository(
      repositoryId: string,
      request: RepositoryTriageRequest,
    ): Promise<RepositoryTriageResponse>;
    createRepositoryDecisionPlan(
      repositoryId: string,
      request: RepositoryDecisionPlanCreateRequest,
    ): Promise<RepositoryDecisionPlanRevisionResponse>;
    queryRepositoryGraph(
      repositoryId: string,
      request: RepositoryGraphQueryRequest,
    ): Promise<RepositoryGraphQueryResponse>;
    simulateRepository(
      repositoryId: string,
      request: RepositorySimulationRequest,
    ): Promise<DecisionEnvelope>;
    applyRepository(
      repositoryId: string,
      request: RepositoryApplyRequest,
    ): Promise<RepositoryApplyResponse>;
    deleteConnector(connectorId: string): Promise<void>;
    connectData(request: ConnectDataRequest): Promise<DatasetConnectResult>;
    listDatasets(options?: {
      page?: number;
      limit?: number;
      search?: string;
      status?: string;
      sourceName?: string;
      compact?: boolean;
    }): Promise<DatasetListResult>;
    getDataset(datasetId: string): Promise<DatasetDetailResult>;
    getDatasetSummary(datasetId: string): Promise<DatasetSummaryResult>;
    refreshDataset(datasetId: string): Promise<DatasetConnectResult>;
    deleteDataset(datasetId: string): Promise<DatasetDeleteResult>;
  }
}

DecisionEngineClient.prototype.listModels = async function (
  this: DecisionEngineClient,
): Promise<LLMModelListResponse> {
  return this.request<LLMModelListResponse>("GET", "/v1/models");
};

DecisionEngineClient.prototype.resolveArtifactBridge = async function (
  this: DecisionEngineClient,
  request: ArtifactBridgeResolveRequest,
): Promise<ArtifactBridgeResolveResponse> {
  return this.request<ArtifactBridgeResolveResponse>("POST", "/v1/artifacts/resolve", {
    local_files_only: true,
    ...request,
  });
};

DecisionEngineClient.prototype.chatCompletions = async function (
  this: DecisionEngineClient,
  request: ChatCompletionsRequest,
): Promise<ChatCompletionsResponse> {
  return this.request<ChatCompletionsResponse>("POST", "/v1/chat/completions", {
    ...request,
    stream: false,
  });
};

DecisionEngineClient.prototype.streamChatCompletions = async function* (
  this: DecisionEngineClient,
  request: ChatCompletionsRequest,
): AsyncGenerator<ChatCompletionsStreamChunkResponse> {
  for await (const chunk of this.requestStream<ChatCompletionsStreamChunkResponse>(
    "POST",
    "/v1/chat/completions",
    { ...request, stream: true },
  )) {
    yield chunk;
  }
};

DecisionEngineClient.prototype.tokenize = async function (
  this: DecisionEngineClient,
  request: TokenizeRequest,
): Promise<TokenizeResponse> {
  return this.request<TokenizeResponse>("POST", "/v1/tokenize", request);
};

DecisionEngineClient.prototype.countTokens = async function (
  this: DecisionEngineClient,
  request: CountTokensRequest,
): Promise<CountTokensResponse> {
  return this.request<CountTokensResponse>("POST", "/v1/count_tokens", request);
};

DecisionEngineClient.prototype.responses = async function (
  this: DecisionEngineClient,
  request: ResponsesRequest,
): Promise<ResponsesResponse> {
  return this.request<ResponsesResponse>("POST", "/v1/responses", { ...request, stream: false });
};

DecisionEngineClient.prototype.streamResponses = async function* (
  this: DecisionEngineClient,
  request: ResponsesRequest,
): AsyncGenerator<ResponseStreamEventResponse> {
  for await (const event of this.requestStream<ResponseStreamEventResponse>(
    "POST",
    "/v1/responses",
    { ...request, stream: true },
  )) {
    yield event;
  }
};

DecisionEngineClient.prototype.embeddings = async function (
  this: DecisionEngineClient,
  request: EmbeddingsRequest,
): Promise<EmbeddingsResponse> {
  return this.request<EmbeddingsResponse>("POST", "/v1/embeddings", request);
};

DecisionEngineClient.prototype.embeddingSimilarity = async function (
  this: DecisionEngineClient,
  request: EmbeddingSimilarityRequest,
): Promise<EmbeddingSimilarityResponse> {
  return this.request<EmbeddingSimilarityResponse>("POST", "/v1/embeddings/similarity", request);
};

DecisionEngineClient.prototype.rerank = async function (
  this: DecisionEngineClient,
  request: RerankRequest,
): Promise<RerankResponse> {
  return this.request<RerankResponse>("POST", "/v1/rerank", request);
};

DecisionEngineClient.prototype.getContract = async function (
  this: DecisionEngineClient,
): Promise<PlatformContractResponse> {
  try {
    return assertPlatformContractResponse(
      await this.request<unknown>("GET", "/v1/meta/contract"),
    );
  } catch (error) {
    if (!(error instanceof NotFoundError)) {
      throw error;
    }
    const openapiSchema = await this.request<Record<string, unknown>>("GET", "/openapi.json");
    return assertPlatformContractResponse(
      buildPlatformContractFromOpenApi(this.baseUrl, openapiSchema),
    );
  }
};

DecisionEngineClient.prototype.getRuntimeManifest = async function (
  this: DecisionEngineClient,
): Promise<RuntimeManifestResponse> {
  return assertRuntimeManifestResponse(
    await this.request<unknown>("GET", "/v1/runtime/manifest"),
  );
};

DecisionEngineClient.prototype.getRuntimeModules = async function (
  this: DecisionEngineClient,
): Promise<RuntimeAdminModulesResponse> {
  return assertRuntimeAdminModulesResponse(
    await this.request<unknown>("GET", "/v1/admin/runtime/modules"),
  );
};

DecisionEngineClient.prototype.getRuntimeBenchmarks = async function (
  this: DecisionEngineClient,
): Promise<RuntimeAdminBenchmarksResponse> {
  return assertRuntimeAdminBenchmarksResponse(
    await this.request<unknown>("GET", "/v1/admin/runtime/benchmarks"),
  );
};

DecisionEngineClient.prototype.getRuntimeReleaseValidation = async function (
  this: DecisionEngineClient,
): Promise<RuntimeReleaseValidationResponse> {
  return assertRuntimeReleaseValidationResponse(
    await this.request<unknown>("GET", "/v1/admin/runtime/validation"),
  );
};

DecisionEngineClient.prototype.registerSource = async function (
  this: DecisionEngineClient,
  source: SourceRegistrationRequest | Record<string, unknown>,
  options: { description?: string; name?: string } = {},
): Promise<SourceRegistrationResponse> {
  return this.request<SourceRegistrationResponse>(
    "POST",
    "/v1/sources/register",
    normalizeSourceRegistrationRequest(
      source,
      options.description,
      options.name ? { name: options.name } : {},
    ),
  );
};

DecisionEngineClient.prototype.refreshSource = async function (
  this: DecisionEngineClient,
  datasetId: string,
): Promise<SourceRegistrationResponse> {
  return this.request<SourceRegistrationResponse>("POST", `/v1/data/${datasetId}/refresh`);
};

DecisionEngineClient.prototype.createConnector = async function (
  this: DecisionEngineClient,
  request: CreateConnectorRequest,
): Promise<ConnectorInfo> {
  return this.request<ConnectorInfo>("POST", "/v1/connectors", request);
};

DecisionEngineClient.prototype.listConnectors = async function (
  this: DecisionEngineClient,
  options: { page?: number; limit?: number } = {},
): Promise<ConnectorListResult> {
  const page = options.page ?? 1;
  const limit = options.limit ?? 200;
  const path = appendQueryParameters("/v1/connectors", {
    page,
    limit,
  });
  return assertConnectorListResponse(
    await this.request<unknown>("GET", path),
    page,
  );
};

DecisionEngineClient.prototype.getConnector = async function (
  this: DecisionEngineClient,
  connectorId: string,
): Promise<ConnectorInfo> {
  return this.request<ConnectorInfo>("GET", `/v1/connectors/${connectorId}`);
};

DecisionEngineClient.prototype.updateConnector = async function (
  this: DecisionEngineClient,
  connectorId: string,
  request: UpdateConnectorRequest,
): Promise<ConnectorInfo> {
  return this.request<ConnectorInfo>("PATCH", `/v1/connectors/${connectorId}`, request);
};

DecisionEngineClient.prototype.testConnector = async function (
  this: DecisionEngineClient,
  connectorId: string,
): Promise<ConnectorTestInfo> {
  return this.request<ConnectorTestInfo>("POST", `/v1/connectors/${connectorId}/test`);
};

DecisionEngineClient.prototype.previewTestConnector = async function (
  this: DecisionEngineClient,
  request: PreviewConnectorRequest,
): Promise<ConnectorTestInfo> {
  return this.request<ConnectorTestInfo>("POST", "/v1/connectors/test", request);
};

DecisionEngineClient.prototype.browseConnector = async function (
  this: DecisionEngineClient,
  connectorId: string,
): Promise<ConnectorBrowseResult> {
  return this.request<ConnectorBrowseResult>("GET", `/v1/connectors/${connectorId}/browse`);
};

DecisionEngineClient.prototype.previewBrowseConnector = async function (
  this: DecisionEngineClient,
  request: PreviewConnectorRequest,
): Promise<ConnectorBrowseResult> {
  return this.request<ConnectorBrowseResult>("POST", "/v1/connectors/browse", request);
};

DecisionEngineClient.prototype.createRepositorySnapshot = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositorySnapshotCreateRequest,
): Promise<RepositorySnapshotResponse> {
  return this.request<RepositorySnapshotResponse>(
    "POST",
    `/v1/repositories/${repositoryId}/snapshots`,
    request,
  );
};

DecisionEngineClient.prototype.getRepositoryIntelligenceCapabilities = async function (
  this: DecisionEngineClient,
): Promise<RepositoryIntelligenceCapabilitiesResponse> {
  return this.request<RepositoryIntelligenceCapabilitiesResponse>(
    "GET",
    "/v1/repositories/capabilities",
  );
};

DecisionEngineClient.prototype.getRepositorySnapshot = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  snapshotId: string,
): Promise<RepositorySnapshotResponse> {
  return this.request<RepositorySnapshotResponse>(
    "GET",
    `/v1/repositories/${repositoryId}/snapshots/${snapshotId}`,
  );
};

DecisionEngineClient.prototype.triageRepository = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositoryTriageRequest,
): Promise<RepositoryTriageResponse> {
  return this.request<RepositoryTriageResponse>(
    "POST",
    `/v1/repositories/${repositoryId}/triage`,
    request,
  );
};

DecisionEngineClient.prototype.createRepositoryDecisionPlan = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositoryDecisionPlanCreateRequest,
): Promise<RepositoryDecisionPlanRevisionResponse> {
  return this.request<RepositoryDecisionPlanRevisionResponse>(
    "POST",
    `/v1/repositories/${repositoryId}/decision-plans`,
    request,
  );
};

DecisionEngineClient.prototype.queryRepositoryGraph = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositoryGraphQueryRequest,
): Promise<RepositoryGraphQueryResponse> {
  return this.request<RepositoryGraphQueryResponse>(
    "POST",
    `/v1/repositories/${repositoryId}/graph-query`,
    request,
  );
};

DecisionEngineClient.prototype.simulateRepository = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositorySimulationRequest,
): Promise<DecisionEnvelope> {
  return this.request<DecisionEnvelope>(
    "POST",
    `/v1/repositories/${repositoryId}/simulate`,
    request,
  );
};

DecisionEngineClient.prototype.applyRepository = async function (
  this: DecisionEngineClient,
  repositoryId: string,
  request: RepositoryApplyRequest,
): Promise<RepositoryApplyResponse> {
  return this.request<RepositoryApplyResponse>(
    "POST",
    `/v1/repositories/${repositoryId}/apply`,
    request,
  );
};

DecisionEngineClient.prototype.deleteConnector = async function (
  this: DecisionEngineClient,
  connectorId: string,
): Promise<void> {
  await this.request("DELETE", `/v1/connectors/${connectorId}`);
};

DecisionEngineClient.prototype.connectData = async function (
  this: DecisionEngineClient,
  request: ConnectDataRequest,
): Promise<DatasetConnectResult> {
  return this.request<DatasetConnectResult>("POST", "/v1/data/connect", request);
};

DecisionEngineClient.prototype.listDatasets = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    search?: string;
    status?: string;
    sourceName?: string;
    compact?: boolean;
  } = {},
): Promise<DatasetListResult> {
  const page = options.page ?? 1;
  const limit = options.limit ?? 200;
  const path = appendQueryParameters("/v1/data", {
    page,
    limit,
    search: options.search,
    status: options.status,
    source_name: options.sourceName,
    compact: options.compact ? 1 : undefined,
  });
  return assertDatasetListResponse(
    await this.request<unknown>("GET", path),
    page,
  );
};

DecisionEngineClient.prototype.getDataset = async function (
  this: DecisionEngineClient,
  datasetId: string,
): Promise<DatasetDetailResult> {
  return this.request<DatasetDetailResult>("GET", `/v1/data/${datasetId}`);
};

DecisionEngineClient.prototype.getDatasetSummary = async function (
  this: DecisionEngineClient,
  datasetId: string,
): Promise<DatasetSummaryResult> {
  return assertDatasetSummaryResponse(
    await this.request<unknown>("GET", `/v1/data/${datasetId}/summary`),
  );
};

DecisionEngineClient.prototype.refreshDataset = async function (
  this: DecisionEngineClient,
  datasetId: string,
): Promise<DatasetConnectResult> {
  return this.request<DatasetConnectResult>("POST", `/v1/data/${datasetId}/refresh`);
};

DecisionEngineClient.prototype.deleteDataset = async function (
  this: DecisionEngineClient,
  datasetId: string,
): Promise<DatasetDeleteResult> {
  return this.request<DatasetDeleteResult>("DELETE", `/v1/data/${datasetId}`);
};
