/** Auto-split sub-module of runtime.ts — LLM, decision, agent run, and
 * product wrappers for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

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
  ArtifactBridgeResolveRequest,
  ArtifactBridgeResolveResponse,
  ChatCompletionsRequest,
  ChatCompletionsResponse,
  ChatCompletionsStreamChunkResponse,
  CountTokensRequest,
  CountTokensResponse,
  DecisionListResponse,
  DecisionLogResponse,
  DecisionPlanResponse,
  EmbeddingsRequest,
  EmbeddingsResponse,
  EmbeddingSimilarityRequest,
  EmbeddingSimilarityResponse,
  ExecuteDecisionRequest,
  ExecutionReceiptResponse,
  LLMModelListResponse,
  LogDecisionRequest,
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
  RecordOutcomeRequest,
  RerankRequest,
  RerankResponse,
  ResponsesRequest,
  ResponsesResponse,
  ResponseStreamEventResponse,
  SimulateRequest,
  TokenizeRequest,
  TokenizeResponse,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    listModels(): Promise<LLMModelListResponse>;
    resolveArtifactBridge(
      request: ArtifactBridgeResolveRequest,
    ): Promise<ArtifactBridgeResolveResponse>;
    tokenize(request: TokenizeRequest): Promise<TokenizeResponse>;
    countTokens(request: CountTokensRequest): Promise<CountTokensResponse>;
    chatCompletions(request: ChatCompletionsRequest): Promise<ChatCompletionsResponse>;
    streamChatCompletions(
      request: ChatCompletionsRequest,
    ): AsyncGenerator<ChatCompletionsStreamChunkResponse>;
    responses(request: ResponsesRequest): Promise<ResponsesResponse>;
    streamResponses(request: ResponsesRequest): AsyncGenerator<ResponseStreamEventResponse>;
    embeddings(request: EmbeddingsRequest): Promise<EmbeddingsResponse>;
    embeddingSimilarity(
      request: EmbeddingSimilarityRequest,
    ): Promise<EmbeddingSimilarityResponse>;
    rerank(request: RerankRequest): Promise<RerankResponse>;
    planDecision(request: SimulateRequest): Promise<DecisionPlanResponse>;
    productDecision(request: ProductDecisionRequest): Promise<ProductDecisionResponse>;
    productAgentRun(request: ProductAgentRunRequest): Promise<ProductAgentRunResponse>;
    productOptimize(request: ProductOptimizeRequest): Promise<ProductOptimizeResponse>;
    productRetrieve(request: ProductRetrieveRequest): Promise<ProductRetrieveResponse>;
    productForecast(request: ProductForecastRequest): Promise<ProductForecastResponse>;
    logDecision(request: LogDecisionRequest): Promise<DecisionLogResponse>;
    listDecisions(options?: {
      page?: number;
      limit?: number;
      page_size?: number;
      with_outcome_only?: boolean;
    }): Promise<DecisionListResponse>;
    getDecision(decisionId: string): Promise<DecisionLogResponse>;
    recordOutcome(
      decisionId: string,
      request: RecordOutcomeRequest,
    ): Promise<DecisionLogResponse>;
    executeDecision(
      decisionId: string,
      request: ExecuteDecisionRequest,
    ): Promise<ExecutionReceiptResponse>;
    deleteDecision(decisionId: string): Promise<Record<string, unknown>>;
    createAgentRun(request: AgentRunCreateRequest): Promise<AgentRunResponse>;
    getAgentRun(runId: string): Promise<AgentRunResponse>;
    listAgentRuns(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
    }): Promise<AgentRunListResponse>;
    getAgentRunEvents(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunEventsResponse>;
    streamAgentRunEvents(
      runId: string,
      options?: { limit?: number },
    ): AsyncGenerator<AgentRunStreamEventResponse>;
    listAgentRunCheckpoints(runId: string): Promise<AgentRunCheckpointsResponse>;
    queryAgentRunCheckpoints(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      checkpoint_id?: string;
    }): Promise<AgentRunCheckpointListResponse>;
    listAgentRunMissionEvents(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunMissionEventsResponse>;
    queryAgentRunMissionEvents(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      event_type?: string;
    }): Promise<AgentRunMissionEventListResponse>;
    replayAgentRun(
      runId: string,
      options?: { checkpoint_id?: string | null },
    ): Promise<AgentRunReplayResponse>;
    forkAgentRun(
      runId: string,
      options?: { checkpoint_id?: string | null },
    ): Promise<AgentRunResponse>;
    resumeAgentRun(runId: string): Promise<AgentRunResponse>;
    cancelAgentRun(runId: string): Promise<AgentRunResponse>;
    approveAgentRun(runId: string): Promise<AgentRunResponse>;
    listAgentRunTelemetry(
      runId: string,
      options?: { limit?: number },
    ): Promise<AgentRunTelemetryResponse>;
    queryAgentRunTelemetry(options?: {
      page?: number;
      limit?: number;
      status?: string;
      request_hash?: string;
      policy_snapshot_id?: string;
      schema_snapshot_id?: string;
      run_id?: string;
      telemetry_kind?: string;
      module_name?: string;
    }): Promise<AgentRunTelemetryListResponse>;
  }
}

Runtime.prototype.listModels = async function (this: Runtime): Promise<LLMModelListResponse> {
  this.requireApiTransport("listModels");
  return this.client().listModels();
};

Runtime.prototype.resolveArtifactBridge = async function (
  this: Runtime,
  request: ArtifactBridgeResolveRequest,
): Promise<ArtifactBridgeResolveResponse> {
  this.requireApiTransport("resolveArtifactBridge");
  return this.client().resolveArtifactBridge(request);
};

Runtime.prototype.tokenize = async function (
  this: Runtime,
  request: TokenizeRequest,
): Promise<TokenizeResponse> {
  this.requireApiTransport("tokenize");
  return this.client().tokenize(request);
};

Runtime.prototype.countTokens = async function (
  this: Runtime,
  request: CountTokensRequest,
): Promise<CountTokensResponse> {
  this.requireApiTransport("countTokens");
  return this.client().countTokens(request);
};

Runtime.prototype.chatCompletions = async function (
  this: Runtime,
  request: ChatCompletionsRequest,
): Promise<ChatCompletionsResponse> {
  this.requireApiTransport("chatCompletions");
  return this.client().chatCompletions(request);
};

Runtime.prototype.streamChatCompletions = async function* (
  this: Runtime,
  request: ChatCompletionsRequest,
): AsyncGenerator<ChatCompletionsStreamChunkResponse> {
  this.requireApiTransport("streamChatCompletions");
  yield* this.client().streamChatCompletions(request);
};

Runtime.prototype.responses = async function (
  this: Runtime,
  request: ResponsesRequest,
): Promise<ResponsesResponse> {
  this.requireApiTransport("responses");
  return this.client().responses(request);
};

Runtime.prototype.streamResponses = async function* (
  this: Runtime,
  request: ResponsesRequest,
): AsyncGenerator<ResponseStreamEventResponse> {
  this.requireApiTransport("streamResponses");
  yield* this.client().streamResponses(request);
};

Runtime.prototype.embeddings = async function (
  this: Runtime,
  request: EmbeddingsRequest,
): Promise<EmbeddingsResponse> {
  this.requireApiTransport("embeddings");
  return this.client().embeddings(request);
};

Runtime.prototype.embeddingSimilarity = async function (
  this: Runtime,
  request: EmbeddingSimilarityRequest,
): Promise<EmbeddingSimilarityResponse> {
  this.requireApiTransport("embeddingSimilarity");
  return this.client().embeddingSimilarity(request);
};

Runtime.prototype.rerank = async function (
  this: Runtime,
  request: RerankRequest,
): Promise<RerankResponse> {
  this.requireApiTransport("rerank");
  return this.client().rerank(request);
};

Runtime.prototype.planDecision = async function (
  this: Runtime,
  request: SimulateRequest,
): Promise<DecisionPlanResponse> {
  this.requireApiTransport("planDecision");
  return this.client().planDecision(request);
};

Runtime.prototype.productDecision = async function (
  this: Runtime,
  request: ProductDecisionRequest,
): Promise<ProductDecisionResponse> {
  this.requireApiTransport("productDecision");
  return this.client().productDecision(request);
};

Runtime.prototype.productAgentRun = async function (
  this: Runtime,
  request: ProductAgentRunRequest,
): Promise<ProductAgentRunResponse> {
  this.requireApiTransport("productAgentRun");
  return this.client().productAgentRun(request);
};

Runtime.prototype.productOptimize = async function (
  this: Runtime,
  request: ProductOptimizeRequest,
): Promise<ProductOptimizeResponse> {
  this.requireApiTransport("productOptimize");
  return this.client().productOptimize(request);
};

Runtime.prototype.productRetrieve = async function (
  this: Runtime,
  request: ProductRetrieveRequest,
): Promise<ProductRetrieveResponse> {
  this.requireApiTransport("productRetrieve");
  return this.client().productRetrieve(request);
};

Runtime.prototype.productForecast = async function (
  this: Runtime,
  request: ProductForecastRequest,
): Promise<ProductForecastResponse> {
  this.requireApiTransport("productForecast");
  return this.client().productForecast(request);
};

Runtime.prototype.logDecision = async function (
  this: Runtime,
  request: LogDecisionRequest,
): Promise<DecisionLogResponse> {
  this.requireApiTransport("logDecision");
  return this.client().logDecision(request);
};

Runtime.prototype.listDecisions = async function (
  this: Runtime,
  options: {
    page?: number;
    limit?: number;
    page_size?: number;
    with_outcome_only?: boolean;
  } = {},
): Promise<DecisionListResponse> {
  this.requireApiTransport("listDecisions");
  return this.client().listDecisions(options);
};

Runtime.prototype.getDecision = async function (
  this: Runtime,
  decisionId: string,
): Promise<DecisionLogResponse> {
  this.requireApiTransport("getDecision");
  return this.client().getDecision(decisionId);
};

Runtime.prototype.recordOutcome = async function (
  this: Runtime,
  decisionId: string,
  request: RecordOutcomeRequest,
): Promise<DecisionLogResponse> {
  this.requireApiTransport("recordOutcome");
  return this.client().recordOutcome(decisionId, request);
};

Runtime.prototype.executeDecision = async function (
  this: Runtime,
  decisionId: string,
  request: ExecuteDecisionRequest,
): Promise<ExecutionReceiptResponse> {
  this.requireApiTransport("executeDecision");
  return this.client().executeDecision(decisionId, request);
};

Runtime.prototype.deleteDecision = async function (
  this: Runtime,
  decisionId: string,
): Promise<Record<string, unknown>> {
  this.requireApiTransport("deleteDecision");
  return this.client().deleteDecision(decisionId);
};

Runtime.prototype.createAgentRun = async function (
  this: Runtime,
  request: AgentRunCreateRequest,
): Promise<AgentRunResponse> {
  this.requireApiTransport("createAgentRun");
  return this.client().createAgentRun(request);
};

Runtime.prototype.getAgentRun = async function (
  this: Runtime,
  runId: string,
): Promise<AgentRunResponse> {
  this.requireApiTransport("getAgentRun");
  return this.client().getAgentRun(runId);
};

Runtime.prototype.listAgentRuns = async function (
  this: Runtime,
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
};

Runtime.prototype.getAgentRunEvents = async function (
  this: Runtime,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunEventsResponse> {
  this.requireApiTransport("getAgentRunEvents");
  return this.client().getAgentRunEvents(runId, options);
};

Runtime.prototype.streamAgentRunEvents = async function* (
  this: Runtime,
  runId: string,
  options: { limit?: number } = {},
): AsyncGenerator<AgentRunStreamEventResponse> {
  this.requireApiTransport("streamAgentRunEvents");
  yield* this.client().streamAgentRunEvents(runId, options);
};

Runtime.prototype.listAgentRunCheckpoints = async function (
  this: Runtime,
  runId: string,
): Promise<AgentRunCheckpointsResponse> {
  this.requireApiTransport("listAgentRunCheckpoints");
  return this.client().listAgentRunCheckpoints(runId);
};

Runtime.prototype.queryAgentRunCheckpoints = async function (
  this: Runtime,
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
};

Runtime.prototype.listAgentRunMissionEvents = async function (
  this: Runtime,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunMissionEventsResponse> {
  this.requireApiTransport("listAgentRunMissionEvents");
  return this.client().listAgentRunMissionEvents(runId, options);
};

Runtime.prototype.queryAgentRunMissionEvents = async function (
  this: Runtime,
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
};

Runtime.prototype.replayAgentRun = async function (
  this: Runtime,
  runId: string,
  options: { checkpoint_id?: string | null } = {},
): Promise<AgentRunReplayResponse> {
  this.requireApiTransport("replayAgentRun");
  return this.client().replayAgentRun(runId, options);
};

Runtime.prototype.forkAgentRun = async function (
  this: Runtime,
  runId: string,
  options: { checkpoint_id?: string | null } = {},
): Promise<AgentRunResponse> {
  this.requireApiTransport("forkAgentRun");
  return this.client().forkAgentRun(runId, options);
};

Runtime.prototype.resumeAgentRun = async function (
  this: Runtime,
  runId: string,
): Promise<AgentRunResponse> {
  this.requireApiTransport("resumeAgentRun");
  return this.client().resumeAgentRun(runId);
};

Runtime.prototype.cancelAgentRun = async function (
  this: Runtime,
  runId: string,
): Promise<AgentRunResponse> {
  this.requireApiTransport("cancelAgentRun");
  return this.client().cancelAgentRun(runId);
};

Runtime.prototype.approveAgentRun = async function (
  this: Runtime,
  runId: string,
): Promise<AgentRunResponse> {
  this.requireApiTransport("approveAgentRun");
  return this.client().approveAgentRun(runId);
};

Runtime.prototype.listAgentRunTelemetry = async function (
  this: Runtime,
  runId: string,
  options: { limit?: number } = {},
): Promise<AgentRunTelemetryResponse> {
  this.requireApiTransport("listAgentRunTelemetry");
  return this.client().listAgentRunTelemetry(runId, options);
};

Runtime.prototype.queryAgentRunTelemetry = async function (
  this: Runtime,
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
};
