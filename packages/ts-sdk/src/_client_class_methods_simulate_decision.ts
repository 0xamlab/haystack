// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of client.ts — simulation, query, decision logging,
 * recommendation, score, batch, and compare methods for DecisionEngineClient.
 *
 * This module augments the {@link DecisionEngineClient} class via TypeScript
 * declaration merging and prototype assignment. Importing this file (for its
 * side effects) is required so the prototype assignments execute and the
 * augmented methods are available on `DecisionEngineClient` instances.
 */

import type {
  BatchResult,
  CompareResponse,
  DecisionEnvelope,
  DecisionListResponse,
  DecisionLogResponse,
  DecisionPlanResponse,
  ExecuteDecisionRequest,
  ExecutionReceiptResponse,
  ExplainResponse,
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
  QueryBatchResponse,
  QueryFilterSpec,
  QueryResponse,
  QuerySqlReportRequest,
  QuerySqlReportResponse,
  QueryWithMetadataResponse,
  RecommendResponse,
  RecordOutcomeRequest,
  ResolveResponse,
  ScoreResponse,
  SimulateRequest,
  VerifyResponse,
} from "./types.js";
import { DecisionEngineClient } from "./_client_class.js";
import {
  mergeRequestPayload,
  normalizeQueryLikeRequest,
} from "./_client_constants.js";
import { buildExplainResponse } from "./_client_platform_validators_a1.js";
import { buildQueryExecutionMetadata } from "./_client_runtime_release.js";

declare module "./_client_class.js" {
  interface DecisionEngineClient {
    simulate(request: SimulateRequest): Promise<DecisionEnvelope>;
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
    recordOutcome(decisionId: string, request: RecordOutcomeRequest): Promise<DecisionLogResponse>;
    executeDecision(
      decisionId: string,
      request: ExecuteDecisionRequest,
    ): Promise<ExecutionReceiptResponse>;
    deleteDecision(decisionId: string): Promise<Record<string, unknown>>;
    resolve(request: Record<string, unknown>): Promise<ResolveResponse>;
    query(request: Record<string, unknown>): Promise<QueryResponse>;
    queryWithMetadata(request: Record<string, unknown>): Promise<QueryWithMetadataResponse>;
    verify(request: Record<string, unknown>): Promise<VerifyResponse>;
    queryBatch(request: {
      defaults?: {
        dataset_id?: string | null;
        filter?: QueryFilterSpec | null;
        limit?: number | null;
        order?: "asc" | "desc" | null;
      } | null;
      queries: Array<{ key: string; request: Record<string, unknown> }>;
    }): Promise<QueryBatchResponse>;
    querySqlReport(request: QuerySqlReportRequest): Promise<QuerySqlReportResponse>;
    explain(request: Record<string, unknown>): Promise<ExplainResponse>;
    recommend(
      actions: Array<{ name: string; request: SimulateRequest }>,
      options?: { runs?: number; seed?: number },
    ): Promise<RecommendResponse>;
    score(
      request: SimulateRequest,
      scoringWeights?: Record<string, number>,
    ): Promise<ScoreResponse>;
    batch(items: SimulateRequest[]): Promise<BatchResult>;
    compare(
      scenarios: Array<{ name: string; request: SimulateRequest }>,
      options?: { runs?: number; seed?: number },
    ): Promise<CompareResponse>;
  }
}

DecisionEngineClient.prototype.simulate = async function (
  this: DecisionEngineClient,
  request: SimulateRequest,
): Promise<DecisionEnvelope> {
  return this.request<DecisionEnvelope>("POST", "/v1/simulate", request);
};

DecisionEngineClient.prototype.planDecision = async function (
  this: DecisionEngineClient,
  request: SimulateRequest,
): Promise<DecisionPlanResponse> {
  return this.request<DecisionPlanResponse>("POST", "/v1/decisions/plan", request);
};

DecisionEngineClient.prototype.productDecision = async function (
  this: DecisionEngineClient,
  request: ProductDecisionRequest,
): Promise<ProductDecisionResponse> {
  return this.request<ProductDecisionResponse>("POST", "/v1/decision", request);
};

DecisionEngineClient.prototype.productAgentRun = async function (
  this: DecisionEngineClient,
  request: ProductAgentRunRequest,
): Promise<ProductAgentRunResponse> {
  return this.request<ProductAgentRunResponse>("POST", "/v1/agent/run", request);
};

DecisionEngineClient.prototype.productOptimize = async function (
  this: DecisionEngineClient,
  request: ProductOptimizeRequest,
): Promise<ProductOptimizeResponse> {
  return this.request<ProductOptimizeResponse>("POST", "/v1/optimize", request);
};

DecisionEngineClient.prototype.productRetrieve = async function (
  this: DecisionEngineClient,
  request: ProductRetrieveRequest,
): Promise<ProductRetrieveResponse> {
  return this.request<ProductRetrieveResponse>("POST", "/v1/retrieve", request);
};

DecisionEngineClient.prototype.productForecast = async function (
  this: DecisionEngineClient,
  request: ProductForecastRequest,
): Promise<ProductForecastResponse> {
  return this.request<ProductForecastResponse>("POST", "/v1/forecast", request);
};

DecisionEngineClient.prototype.logDecision = async function (
  this: DecisionEngineClient,
  request: LogDecisionRequest,
): Promise<DecisionLogResponse> {
  return this.request<DecisionLogResponse>("POST", "/v1/decisions", request);
};

DecisionEngineClient.prototype.listDecisions = async function (
  this: DecisionEngineClient,
  options: {
    page?: number;
    limit?: number;
    page_size?: number;
    with_outcome_only?: boolean;
  } = {},
): Promise<DecisionListResponse> {
  const params = new URLSearchParams();
  if (options.page !== undefined) params.set("page", String(options.page));
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.page_size !== undefined) params.set("page_size", String(options.page_size));
  if (options.with_outcome_only !== undefined) {
    params.set("with_outcome_only", String(options.with_outcome_only));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return this.request<DecisionListResponse>("GET", `/v1/decisions${suffix}`);
};

DecisionEngineClient.prototype.getDecision = async function (
  this: DecisionEngineClient,
  decisionId: string,
): Promise<DecisionLogResponse> {
  return this.request<DecisionLogResponse>("GET", `/v1/decisions/${decisionId}`);
};

DecisionEngineClient.prototype.recordOutcome = async function (
  this: DecisionEngineClient,
  decisionId: string,
  request: RecordOutcomeRequest,
): Promise<DecisionLogResponse> {
  return this.request<DecisionLogResponse>(
    "PATCH",
    `/v1/decisions/${decisionId}/outcome`,
    request,
  );
};

DecisionEngineClient.prototype.executeDecision = async function (
  this: DecisionEngineClient,
  decisionId: string,
  request: ExecuteDecisionRequest,
): Promise<ExecutionReceiptResponse> {
  return this.request<ExecutionReceiptResponse>(
    "POST",
    `/v1/decisions/${decisionId}/execute`,
    request,
  );
};

DecisionEngineClient.prototype.deleteDecision = async function (
  this: DecisionEngineClient,
  decisionId: string,
): Promise<Record<string, unknown>> {
  return this.request<Record<string, unknown>>("DELETE", `/v1/decisions/${decisionId}`);
};

DecisionEngineClient.prototype.resolve = async function (
  this: DecisionEngineClient,
  request: Record<string, unknown>,
): Promise<ResolveResponse> {
  return this.request<ResolveResponse>("POST", "/v1/resolve", normalizeQueryLikeRequest(request));
};

DecisionEngineClient.prototype.query = async function (
  this: DecisionEngineClient,
  request: Record<string, unknown>,
): Promise<QueryResponse> {
  return this.request<QueryResponse>("POST", "/v1/query", normalizeQueryLikeRequest(request));
};

DecisionEngineClient.prototype.queryWithMetadata = async function (
  this: DecisionEngineClient,
  request: Record<string, unknown>,
): Promise<QueryWithMetadataResponse> {
  const { data, headers } = await this.requestWithMetadata<QueryResponse>(
    "POST",
    "/v1/query",
    normalizeQueryLikeRequest(request),
  );
  return {
    data,
    metadata: buildQueryExecutionMetadata(data, headers),
    headers,
  };
};

DecisionEngineClient.prototype.verify = async function (
  this: DecisionEngineClient,
  request: Record<string, unknown>,
): Promise<VerifyResponse> {
  return this.request<VerifyResponse>("POST", "/v1/verify", normalizeQueryLikeRequest(request));
};

DecisionEngineClient.prototype.queryBatch = async function (
  this: DecisionEngineClient,
  request: {
    defaults?: {
      dataset_id?: string | null;
      filter?: QueryFilterSpec | null;
      limit?: number | null;
      order?: "asc" | "desc" | null;
    } | null;
    queries: Array<{ key: string; request: Record<string, unknown> }>;
  },
): Promise<QueryBatchResponse> {
  return this.request<QueryBatchResponse>("POST", "/v1/query/batch", request);
};

DecisionEngineClient.prototype.querySqlReport = async function (
  this: DecisionEngineClient,
  request: QuerySqlReportRequest,
): Promise<QuerySqlReportResponse> {
  return this.request<QuerySqlReportResponse>("POST", "/v1/query/sql-report", request);
};

DecisionEngineClient.prototype.explain = async function (
  this: DecisionEngineClient,
  request: Record<string, unknown>,
): Promise<ExplainResponse> {
  const result = await this.query(mergeRequestPayload(request));
  return buildExplainResponse(request, result);
};

DecisionEngineClient.prototype.recommend = async function (
  this: DecisionEngineClient,
  actions: Array<{ name: string; request: SimulateRequest }>,
  options?: { runs?: number; seed?: number },
): Promise<RecommendResponse> {
  return this.request<RecommendResponse>("POST", "/v1/recommend", { actions, ...options });
};

DecisionEngineClient.prototype.score = async function (
  this: DecisionEngineClient,
  request: SimulateRequest,
  scoringWeights?: Record<string, number>,
): Promise<ScoreResponse> {
  return this.request<ScoreResponse>("POST", "/v1/score", {
    request,
    scoring_weights: scoringWeights,
  });
};

DecisionEngineClient.prototype.batch = async function (
  this: DecisionEngineClient,
  items: SimulateRequest[],
): Promise<BatchResult> {
  return this.request<BatchResult>("POST", "/v1/batch", { items });
};

DecisionEngineClient.prototype.compare = async function (
  this: DecisionEngineClient,
  scenarios: Array<{ name: string; request: SimulateRequest }>,
  options?: { runs?: number; seed?: number },
): Promise<CompareResponse> {
  return this.request<CompareResponse>("POST", "/v1/compare", {
    scenarios,
    ...options,
  });
};
