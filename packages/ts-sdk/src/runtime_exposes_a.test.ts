// SPDX-License-Identifier: Apache-2.0
// Tests for Runtime: exposes_a.
// Extracted from runtime.test.ts during modularization.
import { createHash, createHmac, createSign, generateKeyPairSync } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve as resolvePath } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DecisionEngineError } from "./client.js";
import { expectManifestBackedIntegrationsEqual } from "./test_contract_helpers.js";
import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./runtime.js";
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
  MCP_TOOLS_ENDPOINT,
  PLAN_LIMITS,
  PRIVATE_HOST_SUFFIXES,
  PRIMARY_DATA_QUERY_CONTRACT,
  READ_ONLY_DEFAULT,
  VENDOR_TELEMETRY_HOSTS,
  WRITE_CONFIRMATION_REQUIRED,
} from "./contract.js";
import type {
  RuntimeBenchmarkBaseline,
  RuntimeBenchmarkClassCode,
  RuntimeBenchmarkDiscoveryRule,
  RuntimeBenchmarkMetric,
  RuntimeEvaluationDimension,
  RuntimeEvaluationMethod,
  RuntimeExecutionStateField,
  RuntimeExecutionValidityRule,
  RuntimeExternalNondeterminismSource,
  RuntimeFailureCode,
  RuntimeInvariantName,
  RuntimeArtifactLineageStep,
  RuntimeAdminEndpoint,
  RuntimeCapabilityField,
  RuntimeCapabilityRule,
  RuntimeLineageNodeField,
  RuntimeNondeterminismArtifact,
  RuntimeMemoryRegion,
  RuntimeMemoryRule,
  RuntimeModuleId,
  RuntimeNonShippingRule,
  RuntimeProofObligation,
  RuntimePublicEndpoint,
  RuntimeReleaseArtifact,
  RuntimeReleaseBlocker,
  RuntimeReleaseGateId,
  RuntimeSLOBudgetAppliesTo,
  RuntimeSchedulerInvariant,
  RuntimeSchedulerMaximizeObjective,
  RuntimeSchedulerMinimizeObjective,
  RuntimeSLOBudgetName,
  RuntimeSchedulerPolicy,
  RuntimeFeatureFlagEndpoint,
  RuntimeThreatClass,
  RuntimeThreatControl,
  RuntimeThreatRule,
} from "./types.js";
import {
  SHIPPING_BENCHMARK_DISCOVERY_RULE,
  NON_SHIPPING_RULE,
  DECISION_WORKFLOW_BENCHMARK_EVIDENCE,
  makeDiscoveredSourceInventory,
  makeBenchmarkDiscoveryLanePayload,
  makeKernelPromotionCriteriaPayload,
  REAL_MARCH_ORDERS,
  REAL_MARCH_FINANCIAL,
  REAL_MARCH_EMPTY,
  ORIGINAL_ENV,
  cloneJsonValue,
  makeContractPayload,
  makeRuntimeManifestPayload,
  makeRuntimeAdminModulesPayload,
  makeRuntimeAdminBenchmarksPayload,
  makeRuntimeReleaseValidationPayload,
  runtimeTempDir,
  base64UrlJson,
  issueControlPlaneLicense,
  issueOfflineLocalLicense,
  seedStoredLicense,
  seedTrustedTime,
  readLedgerEvents,
  hasNodeSqlite,
  writeSqliteFixture,
} from "./_runtime_test_helpers.js";

beforeEach(() => {
  delete process.env.ALGENTA_RUNTIME_DIR;
  delete process.env.ALGENTA_JWT_SECRET;
  delete process.env.ALGENTA_CONTROL_PLANE_URL;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK;
  delete process.env.ALGENTA_EGRESS_ALLOWLIST;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

afterEach(() => {
  const runtimeDir = process.env.ALGENTA_RUNTIME_DIR;
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
  if (runtimeDir && runtimeDir.includes("algenta-ts-runtime-")) {
    rmSync(runtimeDir, { force: true, recursive: true });
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Runtime — exposes_a", () => {
    it("exposes the plan-aligned api helper surface through Runtime(mode='api')", async () => {
      const runtime = new Runtime({
        mode: "self_hosted",
        apiKey: "de_test_123",
        baseUrl: "http://localhost:8000",
        client: {
          listModels: async () => ({
            object: "list",
            data: [
              {
                id: "text.tokenizer",
                object: "model",
                owned_by: "algenta",
                runtime_module: "text.tokenizer",
                description: "Deterministic tokenizer utility model",
                capabilities: ["tokenize", "count_tokens", "chat_completions"],
                supported_endpoints: ["/v1/models", "/v1/tokenize", "/v1/count_tokens"],
                runtime_functions: ["tokenize_text", "count_text_tokens"],
                tokenizer_kind: "wordpiece",
                provider_backend: null,
                routing_targets: [],
                resolved_routing_targets: [],
                chat_routing_targets: [],
                resolved_chat_routing_targets: [],
                embedding_routing_targets: [],
                resolved_embedding_routing_targets: [],
                routing_fallback_policy: null,
                chat_routing_fallback_policy: null,
                embedding_routing_fallback_policy: null,
                routing_fallback_on: [],
                chat_routing_fallback_on: [],
                embedding_routing_fallback_on: [],
                routing_max_attempts: null,
                chat_routing_max_attempts: null,
                embedding_routing_max_attempts: null,
                timeout_seconds: null,
                chat_timeout_seconds: null,
                embedding_timeout_seconds: null,
                required_provider_headers: [],
                chat_required_provider_headers: [],
                embedding_required_provider_headers: [],
                provider_auth_env_vars: [],
                chat_provider_auth_env_vars: [],
                embedding_provider_auth_env_vars: [],
                provider_auth_configured: false,
                chat_provider_auth_configured: false,
                embedding_provider_auth_configured: false,
                bridge_cache_root: "/tmp/algenta-hf-cache",
                bridge_auth_env_vars: ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
                bridge_auth_configured: true,
                bridge_tokenizer_backends: ["tiktoken", "sentencepiece"],
                bridge_artifact_backends: ["safetensors", "huggingface_hub"],
                available: true,
              },
            ],
          }),
          resolveArtifactBridge: async () => ({
            object: "artifact_bridge_resolution",
            backend: "huggingface_hub",
            artifact_backend: "safetensors",
            repo_id: "org/model",
            filename: "model.safetensors",
            revision: "main",
            local_files_only: true,
            status: "not_cached",
            cache_root: "/tmp/algenta-hf-cache",
            auth_env_vars: ["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"],
            auth_configured: true,
            auth_env_var_used: "HF_TOKEN",
            resolved_path: null,
          }),
          tokenize: async () => ({
            object: "tokenization",
            model: "text.tokenizer",
            input: "alpha beta",
            tokens: ["alpha", "beta"],
            token_count: 2,
          }),
          countTokens: async () => ({
            object: "token_count",
            model: "text.tokenizer",
            input: "alpha beta",
            token_count: 2,
          }),
          chatCompletions: async () => ({
            id: "chatcmpl_123",
            object: "chat.completion",
            created: 1,
            model: "text.tokenizer",
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            choices: [
              {
                index: 0,
                message: { role: "assistant", content: "Deterministic utility response." },
                finish_reason: "stop",
              },
            ],
            usage: { prompt_tokens: 2, completion_tokens: 3, total_tokens: 5 },
          }),
          streamChatCompletions: async function* () {
            yield {
              id: "chatcmpl_stream_123",
              object: "chat.completion.chunk",
              model: "text.tokenizer",
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
            };
            yield {
              id: "chatcmpl_stream_123",
              object: "chat.completion.chunk",
              model: "text.tokenizer",
              provider_backend: null,
              provider_model_id: null,
              provider_attempts: [],
              choices: [{ index: 0, delta: { content: "Deterministic utility response." }, finish_reason: "stop" }],
            };
          },
          responses: async () => ({
            id: "resp_123",
            object: "response",
            created_at: 1,
            status: "completed",
            model: "text.tokenizer",
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            output: [
              {
                id: "resp_123_item_0",
                object: "response.output",
                index: 0,
                provider_backend: null,
                provider_model_id: null,
                provider_attempts: [],
                content: [
                  {
                    type: "tokenization",
                    text: "alpha beta",
                    tokens: ["alpha", "beta"],
                    token_count: 2,
                    embedding: null,
                  },
                ],
              },
            ],
            usage: { prompt_tokens: 2, total_tokens: 2 },
          }),
          streamResponses: async function* () {
            yield {
              type: "response.created",
              response: {
                id: "resp_123",
                object: "response",
                status: "in_progress",
                model: "text.tokenizer",
                provider_backend: null,
                provider_model_id: null,
                provider_attempts: [],
              },
            };
            yield {
              type: "response.completed",
              response: {
                id: "resp_123",
                object: "response",
                status: "completed",
                model: "text.tokenizer",
                provider_backend: null,
                provider_model_id: null,
                provider_attempts: [],
                usage: { prompt_tokens: 2, total_tokens: 2 },
              },
            };
          },
          embeddings: async () => ({
            object: "list",
            model: "text.hash_embedding_v1",
            dimensions: 3,
            provider_backend: null,
            provider_model_id: null,
            provider_attempts: [],
            data: [
              {
                object: "embedding",
                index: 0,
                embedding: [0.1, 0.2, 0.3],
                token_count: 3,
              },
            ],
            usage: { prompt_tokens: 3, total_tokens: 3 },
          }),
          embeddingSimilarity: async () => ({
            object: "embedding_similarity",
            model: "embeddings.cosine_similarity",
            similarity_metric: "cosine",
            score: 0.94,
            dimension: 3,
          }),
          rerank: async () => ({
            object: "list",
            model: "embeddings.cosine_similarity",
            similarity_metric: "cosine",
            total_documents: 2,
            returned_documents: 1,
            data: [
              {
                object: "rerank_result",
                id: "doc-1",
                index: 0,
                rank: 1,
                score: 0.94,
                text: "Top document",
                metadata: { source: "kb" },
              },
            ],
          }),
          planDecision: async () => ({
            recommended_action: "Expand sales coverage",
            confidence: 0.82,
            expected_value: 128000,
            risk: {
              p5: -15000,
              p95: 240000,
              probability_of_loss: 0.18,
              var_95: -15000,
            },
            options: [
              {
                name: "Expand sales coverage",
                rank: 1,
                expected_value: 128000,
                risk: {
                  p5: -15000,
                  p95: 240000,
                  probability_of_loss: 0.18,
                  var_95: -15000,
                },
                score: 0.82,
              },
            ],
            rationale: "Projected revenue upside outweighs downside risk.",
            integrity: {
              request_hash: "a".repeat(64),
              result_hash: "b".repeat(64),
            },
            calibration: "6 outcomes | bias=-2.0% | hit_rate=83%",
          }),
          productDecision: async () => ({
            decision_id: "decision_product_123",
            action: "proceed",
            confidence: 0.82,
            reasoning: "Expected value remains attractive within risk tolerance.",
            why: ["Positive expected value", "Downside bounded", "Risk acceptable"],
            expected_outcome: 125000,
            downside_risk: 81000,
            upside_potential: 189000,
            probability_of_loss: 0.14,
            scenarios_evaluated: 10000,
            latency_ms: 41.2,
          }),
          productAgentRun: async () => ({
            run_id: "agent_product_123",
            status: "completed",
            result: { summary: "done" },
            steps: [
              {
                step: 1,
                action: "search",
                tool: "search",
                result: "Found 3 documents",
                status: "completed",
              },
            ],
            tools_used: ["search", "simulate"],
            latency_ms: 88.4,
          }),
          productOptimize: async () => ({
            optimization_id: "opt_123",
            status: "completed",
            optimal_values: { price: 119 },
            objective_value: 183000,
            improvement_vs_midpoint: 14.6,
            constraints_satisfied: true,
            iterations_run: 1200,
            latency_ms: 63,
          }),
          productRetrieve: async () => ({
            retrieval_id: "ret_123",
            query: "launch checklist",
            results: [
              {
                rank: 1,
                document_id: "doc_1",
                content: "Launch checklist for product release.",
                relevance_score: 0.93,
                snippet: "Launch checklist",
              },
            ],
            total_searched: 4,
            latency_ms: 27.5,
          }),
          productForecast: async () => ({
            forecast_id: "forecast_123",
            metric: "monthly_revenue",
            baseline: 125000,
            forecast_mean: 149000,
            total_change_pct: 19.2,
            periods: [
              {
                period: 1,
                forecast: 129000,
                lower_bound: 118000,
                upper_bound: 141000,
                trend: "up",
              },
            ],
            scenarios_evaluated: 5000,
            latency_ms: 35.8,
          }),
          logDecision: async () => ({
            id: "decision_123",
            org_id: "org_123",
            run_id: "run_123",
            context: "Launch planning",
            chosen_action: "expand",
            options_considered: ["expand", "hold"],
            expected_value: 128000,
            confidence: 0.82,
            rationale: "Projected upside outweighs downside.",
            risk_p5: -15000,
            risk_p95: 240000,
            risk_pol: 0.18,
            request_hash: "a".repeat(64),
            result_hash: "b".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            actual_outcome: null,
            outcome_delta: null,
            outcome_notes: null,
            outcome_recorded_at: null,
            executed_at: null,
            execution_status: null,
            execution_webhook_url: null,
            execution_response_code: null,
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:00Z",
          }),
          listDecisions: async () => ({
            decisions: [
              {
                id: "decision_123",
                org_id: "org_123",
                run_id: "run_123",
                context: "Launch planning",
                chosen_action: "expand",
                options_considered: ["expand", "hold"],
                expected_value: 128000,
                confidence: 0.82,
                rationale: "Projected upside outweighs downside.",
                risk_p5: -15000,
                risk_p95: 240000,
                risk_pol: 0.18,
                request_hash: "a".repeat(64),
                result_hash: "b".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                actual_outcome: null,
                outcome_delta: null,
                outcome_notes: null,
                outcome_recorded_at: null,
                executed_at: null,
                execution_status: null,
                execution_webhook_url: null,
                execution_response_code: null,
                created_at: "2026-05-24T12:00:00Z",
                updated_at: "2026-05-24T12:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            limit: 20,
            pages: 1,
            page_size: 20,
          }),
          getDecision: async () => ({
            id: "decision_123",
            org_id: "org_123",
            run_id: "run_123",
            context: "Launch planning",
            chosen_action: "expand",
            options_considered: ["expand", "hold"],
            expected_value: 128000,
            confidence: 0.82,
            rationale: "Projected upside outweighs downside.",
            risk_p5: -15000,
            risk_p95: 240000,
            risk_pol: 0.18,
            request_hash: "a".repeat(64),
            result_hash: "b".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            actual_outcome: null,
            outcome_delta: null,
            outcome_notes: null,
            outcome_recorded_at: null,
            executed_at: null,
            execution_status: null,
            execution_webhook_url: null,
            execution_response_code: null,
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:00Z",
          }),
          recordOutcome: async () => ({
            id: "decision_123",
            org_id: "org_123",
            run_id: "run_123",
            context: "Launch planning",
            chosen_action: "expand",
            options_considered: ["expand", "hold"],
            expected_value: 128000,
            confidence: 0.82,
            rationale: "Projected upside outweighs downside.",
            risk_p5: -15000,
            risk_p95: 240000,
            risk_pol: 0.18,
            request_hash: "a".repeat(64),
            result_hash: "b".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            actual_outcome: 141000,
            outcome_delta: 13000,
            outcome_notes: "Launch outperformed baseline",
            outcome_recorded_at: "2026-05-24T12:30:00Z",
            executed_at: null,
            execution_status: null,
            execution_webhook_url: null,
            execution_response_code: null,
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:30:00Z",
          }),
          executeDecision: async () => ({
            decision_id: "decision_123",
            webhook_url: "https://hooks.example.test/decision",
            execution_status: "delivered",
            response_code: 202,
            executed_at: "2026-05-24T12:05:00Z",
            policy_snapshot_id: "execution-policy-v1-r2:abcd1234abcd1234",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            payload_summary: {
              chosen_action: "expand",
              expected_value: 128000,
              confidence: 0.82,
            },
            safety_overridden: false,
          }),
          deleteDecision: async () => ({}),
          createAgentRun: async () => ({
            run_id: "run_agent_123",
            status: "requires_approval",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: "approve",
            selected_tool: "search",
            result: { summary: "Found 3 relevant documents" },
            tools_available: ["search", "summarize"],
            tools_used: ["search"],
            steps: [
              { action: "Planning execution", status: "completed", step: 1 },
              { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
            ],
            request_hash: "a".repeat(64),
            decision_hash: "b".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            replayable: true,
            artifact_refs: ["art_1"],
            latest_checkpoint_id: "cp_2",
            checkpoint_count: 2,
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:03Z",
            latency_ms: 21.5,
          }),
          getAgentRun: async () => ({
            run_id: "run_agent_123",
            status: "requires_approval",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: "approve",
            selected_tool: "search",
            result: { summary: "Found 3 relevant documents" },
            tools_available: ["search", "summarize"],
            tools_used: ["search"],
            steps: [
              { action: "Planning execution", status: "completed", step: 1 },
              { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
            ],
            request_hash: "a".repeat(64),
            decision_hash: "b".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            replayable: true,
            artifact_refs: ["art_1"],
            latest_checkpoint_id: "cp_2",
            checkpoint_count: 2,
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:03Z",
            latency_ms: 21.5,
          }),
          listAgentRuns: async () => ({
            object: "list",
            data: [
              {
                run_id: "run_agent_123",
                status: "requires_approval",
                task: "Search the knowledge base",
                output_format: "markdown",
                approval_mode: "manual",
                pending_action: "approve",
                selected_tool: "search",
                result: { summary: "Found 3 relevant documents" },
                tools_available: ["search", "summarize"],
                tools_used: ["search"],
                steps: [
                  { action: "Planning execution", status: "completed", step: 1 },
                  { action: "Routing to search", tool: "search", result: "Found 3 relevant documents", status: "completed", step: 2 },
                ],
                request_hash: "a".repeat(64),
                decision_hash: "b".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                replayable: true,
                artifact_refs: ["art_1"],
                latest_checkpoint_id: "cp_2",
                checkpoint_count: 2,
                created_at: "2026-05-24T12:00:00Z",
                updated_at: "2026-05-24T12:00:03Z",
                latency_ms: 21.5,
              },
            ],
            total: 1,
            page: 1,
            limit: 25,
            pages: 1,
          }),
          getAgentRunEvents: async () => ({
            object: "list",
            run_id: "run_agent_123",
            data: [
              {
                event_id: "evt_1",
                event_type: "run_created",
                status: "paused",
                message: "Run created and awaiting approval.",
                created_at: "2026-05-24T12:00:00Z",
                details: { pending_action: "approve" },
              },
            ],
            total_events: 1,
          }),
          streamAgentRunEvents: async function* () {
            yield {
              type: "agent.run.event",
              event: {
                event_id: "evt_1",
                event_type: "run_created",
                status: "paused",
                message: "Run created and awaiting approval.",
                created_at: "2026-05-24T12:00:00Z",
                details: { pending_action: "approve" },
              },
            };
            yield { type: "agent.run.completed", status: "completed", run_id: "run_agent_123" };
          },
          listAgentRunCheckpoints: async () => ({
            object: "list",
            run_id: "run_agent_123",
            data: [
              {
                checkpoint_id: "cp_1",
                checkpoint_index: 1,
                run_id: "run_agent_123",
                parent_checkpoint_id: null,
                status: "requires_approval",
                event_start_index: 0,
                event_end_index: 2,
                request_hash: "a".repeat(64),
                decision_hash: "b".repeat(64),
                content_hash: "c".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                artifact_refs: ["art_1"],
                created_at: "2026-05-24T12:00:02Z",
              },
              {
                checkpoint_id: "cp_2",
                checkpoint_index: 2,
                run_id: "run_agent_123",
                parent_checkpoint_id: "cp_1",
                status: "completed",
                event_start_index: 3,
                event_end_index: 5,
                request_hash: "a".repeat(64),
                decision_hash: "b".repeat(64),
                content_hash: "d".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                artifact_refs: ["art_1", "art_2"],
                created_at: "2026-05-24T12:00:03Z",
              },
            ],
            total_checkpoints: 2,
          }),
          queryAgentRunCheckpoints: async () => ({
            object: "list",
            data: [
              {
                checkpoint_id: "cp_2",
                checkpoint_index: 2,
                run_id: "run_agent_123",
                parent_checkpoint_id: "cp_1",
                status: "completed",
                event_start_index: 3,
                event_end_index: 5,
                request_hash: "a".repeat(64),
                decision_hash: "b".repeat(64),
                content_hash: "d".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                artifact_refs: ["art_1", "art_2"],
                created_at: "2026-05-24T12:00:03Z",
                run_status: "completed",
              },
            ],
            total: 1,
            page: 1,
            limit: 25,
            pages: 1,
          }),
          listAgentRunMissionEvents: async () => ({
            object: "list",
            run_id: "run_agent_123",
            data: [
              {
                mission_id: "run_agent_123",
                thread_id: "run_agent_123",
                tenant_scope: "org_test",
                workspace_scope: "run_agent_123",
                event_index: 0,
                superstep: 1,
                node_name: "agent_run_service",
                event_type: "run_created",
                event_message: "Agent run created.",
                details_json: '{"approval_mode":"manual","start_paused":false}',
                event_ts: "2026-05-24T12:00:00Z",
                request_hash: "a".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                checkpoint_id: null,
                artifact_refs: ["evt_1"],
                failure_code: null,
                latency_ms: null,
                cost_usd_micros: null,
              },
            ],
            total_events: 1,
          }),
          queryAgentRunMissionEvents: async () => ({
            object: "list",
            data: [
              {
                mission_id: "run_agent_123",
                thread_id: "run_agent_123",
                tenant_scope: "org_test",
                workspace_scope: "run_agent_123",
                event_index: 0,
                superstep: 1,
                node_name: "agent_run_service",
                event_type: "run_created",
                event_message: "Agent run created.",
                details_json: '{"approval_mode":"manual","start_paused":false}',
                event_ts: "2026-05-24T12:00:00Z",
                request_hash: "a".repeat(64),
                policy_snapshot_id: "policy-v1",
                schema_snapshot_id: "schema-v1",
                manifest_version: "runtime-manifest-v1",
                checkpoint_id: null,
                artifact_refs: ["evt_1"],
                failure_code: null,
                latency_ms: null,
                cost_usd_micros: null,
                run_id: "run_agent_123",
                run_status: "completed",
              },
            ],
            total: 1,
            page: 1,
            limit: 25,
            pages: 1,
          }),
          listAgentRunTelemetry: async () => ({
            object: "list",
            run_id: "run_agent_123",
            data: [
              {
                batch_id: "telemetry_1",
                telemetry_kind: "agent_run_completion",
                module_name: "agent_run_service",
                tenant_scope: "org_test",
                request_hash: "a".repeat(64),
                started_at: "2026-05-24T12:00:00Z",
                ended_at: "2026-05-24T12:00:03Z",
                success_count: 1,
                failure_count: 0,
                latency_ms_p95: 21.5,
                cost_usd_micros: 0,
              },
            ],
            total_batches: 1,
          }),
          queryAgentRunTelemetry: async () => ({
            object: "list",
            data: [
              {
                batch_id: "telemetry_1",
                telemetry_kind: "agent_run_completion",
                module_name: "agent_run_service",
                tenant_scope: "org_test",
                request_hash: "a".repeat(64),
                started_at: "2026-05-24T12:00:00Z",
                ended_at: "2026-05-24T12:00:03Z",
                success_count: 1,
                failure_count: 0,
                latency_ms_p95: 21.5,
                cost_usd_micros: 0,
                run_id: "run_agent_123",
                run_status: "completed",
              },
            ],
            total: 1,
            page: 1,
            limit: 25,
            pages: 1,
          }),
          replayAgentRun: async () => ({
            object: "agent_run_replay",
            run_id: "run_agent_123",
            checkpoint_id: "cp_2",
            replay_status: "matched",
            compared_event_count: 3,
            checkpoint_count: 2,
            request_hash: "a".repeat(64),
            decision_hash: "b".repeat(64),
            content_hash: "d".repeat(64),
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            failure_code: null,
            created_at: "2026-05-24T12:00:04Z",
          }),
          forkAgentRun: async () => ({
            run_id: "run_agent_124",
            status: "paused",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: "resume",
            selected_tool: "search",
            result: null,
            tools_available: ["search", "summarize"],
            tools_used: [],
            steps: [],
            request_hash: "a".repeat(64),
            decision_hash: null,
            policy_snapshot_id: "policy-v1",
            schema_snapshot_id: "schema-v1",
            manifest_version: "runtime-manifest-v1",
            replayable: true,
            artifact_refs: ["art_3"],
            latest_checkpoint_id: "cp_3",
            checkpoint_count: 1,
            source_run_id: "run_agent_123",
            source_checkpoint_id: "cp_1",
            created_at: "2026-05-24T12:00:05Z",
            updated_at: "2026-05-24T12:00:05Z",
            latency_ms: null,
          }),
          resumeAgentRun: async () => ({
            run_id: "run_agent_123",
            status: "requires_approval",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: "approve",
            selected_tool: "search",
            result: { summary: "Found 3 relevant documents" },
            tools_available: ["search", "summarize"],
            tools_used: ["search"],
            steps: [],
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:03Z",
            latency_ms: 21.5,
          }),
          cancelAgentRun: async () => ({
            run_id: "run_agent_123",
            status: "cancelled",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: null,
            selected_tool: "search",
            result: { summary: "Cancelled" },
            tools_available: ["search", "summarize"],
            tools_used: ["search"],
            steps: [],
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:03Z",
            latency_ms: 21.5,
          }),
          approveAgentRun: async () => ({
            run_id: "run_agent_123",
            status: "completed",
            task: "Search the knowledge base",
            output_format: "markdown",
            approval_mode: "manual",
            pending_action: null,
            selected_tool: "search",
            result: { summary: "Found 3 relevant documents" },
            tools_available: ["search", "summarize"],
            tools_used: ["search"],
            steps: [],
            created_at: "2026-05-24T12:00:00Z",
            updated_at: "2026-05-24T12:00:03Z",
            latency_ms: 21.5,
          }),
          recommend: async () => ({
            recommended_action: "expand",
            confidence: 0.76,
            rationale: "Expand has the strongest expected value after risk adjustment.",
            action_results: [
              {
                name: "expand",
                rank: 1,
                envelope: {
                  run_id: "run_decision_123",
                  status: "completed",
                  engine_version: "2026.05.0",
                  recommended_action: "expand",
                  confidence: 0.82,
                  rationale: "Projected revenue upside outweighs downside risk.",
                  metrics: {
                    expected_value: 128000,
                    median: 121000,
                    std_deviation: 18000,
                    variance: 324000000,
                    probability_of_loss: 0.18,
                    var_95: -15000,
                    cvar_95: -28000,
                  },
                  percentiles: {
                    p5: -15000,
                    p25: 64000,
                    p50: 121000,
                    p75: 176000,
                    p95: 240000,
                  },
                  scenarios_run: 250,
                  execution_ms: 18.4,
                  metadata: {
                    mode: "expert",
                    seed: 42,
                    billing_units: 1,
                    engine_version: "2026.05.0",
                  },
                },
                expected_value: 140000,
                probability_of_loss: 0.15,
                score: 0.76,
              },
            ],
            total_actions: 1,
            decision_plan: {
              recommended_action: "expand",
              confidence: 0.76,
              expected_value: 140000,
              risk: {
                p5: -12000,
                p95: 240000,
                probability_of_loss: 0.15,
                var_95: -12000,
              },
              options: [],
              rationale: "Expand has the strongest expected value after risk adjustment.",
            },
          }),
          score: async () => ({
            envelope: {
              run_id: "run_decision_123",
              status: "completed",
              engine_version: "2026.05.0",
              recommended_action: "expand",
              confidence: 0.82,
              rationale: "Projected revenue upside outweighs downside risk.",
              metrics: {
                expected_value: 128000,
                median: 121000,
                std_deviation: 18000,
                variance: 324000000,
                probability_of_loss: 0.18,
                var_95: -15000,
                cvar_95: -28000,
              },
              percentiles: {
                p5: -15000,
                p25: 64000,
                p50: 121000,
                p75: 176000,
                p95: 240000,
              },
              scenarios_run: 250,
              execution_ms: 18.4,
              metadata: {
                mode: "expert",
                seed: 42,
                billing_units: 1,
                engine_version: "2026.05.0",
              },
            },
            score: 0.73,
            score_breakdown: { expected_value: 0.61, downside_risk: 0.12 },
          }),
          batch: async () => ({
            total: 2,
            succeeded: 2,
            failed: 0,
            results: [
              {
                index: 0,
                success: true,
                envelope: {
                  run_id: "run_batch_1",
                  status: "completed",
                  engine_version: "2026.05.0",
                  recommended_action: "base",
                  confidence: 0.71,
                  rationale: "Base scenario is stable.",
                  metrics: {
                    expected_value: 100,
                    median: 100,
                    std_deviation: 0,
                    variance: 0,
                    probability_of_loss: 0,
                  },
                  percentiles: { p5: 100, p25: 100, p50: 100, p75: 100, p95: 100 },
                  scenarios_run: 100,
                  execution_ms: 5,
                  metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
                },
              },
              {
                index: 1,
                success: true,
                envelope: {
                  run_id: "run_batch_2",
                  status: "completed",
                  engine_version: "2026.05.0",
                  recommended_action: "stretch",
                  confidence: 0.74,
                  rationale: "Stretch scenario has higher upside.",
                  metrics: {
                    expected_value: 120,
                    median: 120,
                    std_deviation: 0,
                    variance: 0,
                    probability_of_loss: 0,
                  },
                  percentiles: { p5: 120, p25: 120, p50: 120, p75: 120, p95: 120 },
                  scenarios_run: 100,
                  execution_ms: 5,
                  metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
                },
              },
            ],
          }),
          compare: async () => ({
            winner: "stretch",
            margin: {
              expected_value_delta: 20,
              probability_of_loss_delta: -0.04,
              score_delta: 0.09,
            },
            scenarios: [
              {
                name: "base",
                envelope: {
                  run_id: "run_compare_base",
                  status: "completed",
                  engine_version: "2026.05.0",
                  recommended_action: "base",
                  confidence: 0.7,
                  rationale: "Base scenario.",
                  metrics: {
                    expected_value: 100,
                    median: 100,
                    std_deviation: 0,
                    variance: 0,
                    probability_of_loss: 0,
                  },
                  percentiles: { p5: 100, p25: 100, p50: 100, p75: 100, p95: 100 },
                  scenarios_run: 150,
                  execution_ms: 6,
                  metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
                },
                delta_vs_best: {
                  expected_value_delta: -20,
                  probability_of_loss_delta: 0.04,
                  score_delta: -0.09,
                },
              },
              {
                name: "stretch",
                envelope: {
                  run_id: "run_compare_stretch",
                  status: "completed",
                  engine_version: "2026.05.0",
                  recommended_action: "stretch",
                  confidence: 0.79,
                  rationale: "Stretch scenario.",
                  metrics: {
                    expected_value: 120,
                    median: 120,
                    std_deviation: 0,
                    variance: 0,
                    probability_of_loss: 0,
                  },
                  percentiles: { p5: 120, p25: 120, p50: 120, p75: 120, p95: 120 },
                  scenarios_run: 150,
                  execution_ms: 6,
                  metadata: { mode: "expert", seed: 1, billing_units: 1, engine_version: "2026.05.0" },
                },
                delta_vs_best: {
                  expected_value_delta: 0,
                  probability_of_loss_delta: 0,
                  score_delta: 0,
                },
              },
            ],
          }),
          listDeploymentRegions: async () => ({
            providers: [
              {
                id: "algenta_shared",
                name: "Algenta Managed",
                description: "Multi-tenant shared pool.",
                icon: "🌐",
                regions: [
                  {
                    id: "algenta-shared",
                    name: "Algenta Shared",
                    label: "Algenta Shared",
                    location: "Global",
                  },
                ],
              },
            ],
          }),
          getDeployment: async () => ({
            deployment_id: "dep_123",
            org_id: "org_123",
            provider: "algenta_shared",
            region: "algenta-shared",
            status: "requested",
            endpoint_url: "https://example.test/runtime",
            cost_usd_month: 12.5,
            billable_cost_usd_month: 15.0,
            billing_markup_pct: 20.0,
            created_at: "2026-05-24T12:00:00Z",
            provisioned_at: null,
            error_message: null,
          }),
          createDeployment: async () => ({
            deployment_id: "dep_123",
            org_id: "org_123",
            provider: "algenta_shared",
            region: "algenta-shared",
            status: "requested",
            endpoint_url: "https://example.test/runtime",
            cost_usd_month: 12.5,
            billable_cost_usd_month: 15.0,
            billing_markup_pct: 20.0,
            created_at: "2026-05-24T12:00:00Z",
            provisioned_at: null,
            error_message: null,
          }),
          getDeploymentCost: async () => ({
            deployment_id: "dep_123",
            provider: "algenta_shared",
            region: "algenta-shared",
            year: 2026,
            month: 5,
            cost_usd_month: 12.5,
            billable_cost_usd_month: 15.0,
            billing_markup_pct: 20.0,
            last_updated: "2026-05-24T12:30:00Z",
          }),
          deleteDeployment: async () => ({
            status: "deprovisioning",
            deployment_id: "dep_123",
          }),
          me: async () => ({
            org_id: "org_123",
            email: "owner@example.com",
            organization: "Algenta Labs",
            plan: "enterprise",
          }),
          usage: async () => ({
            org_id: "org_123",
            billing_period: "2026-05",
            simulations_run: 120,
            api_calls: 340,
            quota_limit: 1000,
            quota_used_pct: 12,
          }),
          limits: async () => ({
            plan: "enterprise",
            simulations_per_month: "unlimited",
            rate_limit_per_minute: 10000,
            connectors: 64,
            jobs_enabled: true,
          }),
          distributions: async () => ({
            page: 1,
            limit: 50,
            total: 1,
            pages: 1,
            distributions: [
              {
                name: "normal",
                description: "Normal distribution.",
                required_params: ["mean", "std"],
                optional_params: [],
                example: { mean: 100, std: 12 },
              },
            ],
          }),
          templates: async () => ({
            page: 1,
            limit: 50,
            total: 1,
            pages: 1,
            templates: [
              {
                id: "product-launch",
                name: "Product Launch Decision",
                category: "business",
                description: "Compare launch scenarios.",
                example_request: { mode: "auto" },
              },
            ],
          }),
          getBillingInfo: async () => ({
            plan: "enterprise",
            stripe_customer_id: "cus_123",
            subscription_status: "active",
            current_period_end: "2026-06-30T00:00:00Z",
          }),
          createBillingCheckout: async () => ({
            url: "https://billing.example/checkout/session_123",
          }),
          createBillingPortal: async () => ({
            url: "https://billing.example/portal/session_123",
          }),
          refreshCredits: async () => ({
            credits_granted: 10000,
            credits_issued_this_month: 25000,
            monthly_limit: 500000,
            monthly_remaining: 475000,
            billing_period: "2026-05",
            expires_at: 1716547200,
            refresh_after: 1716545040,
            server_time: 1716460800,
          }),
          listApiKeys: async () => ([
            {
              id: "key_1",
              label: "Mission Runtime Key",
              key_prefix: "de_live_abcd",
              device_limit: 2,
              status: "active",
              created_at: "2026-05-24T12:00:00Z",
              expires_at: null,
            },
          ]),
          createApiKey: async () => ({
            id: "key_2",
            label: "Mission Rotation Key",
            key_prefix: "de_live_wxyz",
            device_limit: 3,
            raw_key: "de_live_wxyz_secret_value",
            created_at: "2026-05-24T12:00:00Z",
            expires_at: null,
          }),
          revokeApiKey: async () => ({}),
        } as never,
      });

      const models = await runtime.listModels();
      const artifact = await runtime.resolveArtifactBridge({
        repo_id: "org/model",
        filename: "model.safetensors",
        revision: "main",
      });
      const tokenized = await runtime.tokenize({ input: "alpha beta" });
      const counted = await runtime.countTokens({ input: "alpha beta" });
      const chat = await runtime.chatCompletions({
        messages: [{ role: "user", content: "Summarize" }],
      });
      const chatStream = [];
      for await (const chunk of runtime.streamChatCompletions({
        messages: [{ role: "user", content: "Summarize" }],
      })) {
        chatStream.push(chunk);
      }
      const response = await runtime.responses({ input: ["alpha beta"], model: "text.hash_embedding_v1", dimensions: 3 });
      const responseStream = [];
      for await (const item of runtime.streamResponses({ input: "alpha beta" })) {
        responseStream.push(item);
      }
      const embeddings = await runtime.embeddings({ input: "alpha beta", dimensions: 3 });
      const similarity = await runtime.embeddingSimilarity({ left: [0.1, 0.2, 0.3], right: [0.1, 0.2, 0.3] });
      const reranked = await runtime.rerank({
        query_embedding: [0.1, 0.2, 0.3],
        documents: [{ id: "doc-1", embedding: [0.1, 0.2, 0.3], text: "Top document" }],
        top_n: 1,
      });
      const plan = await runtime.planDecision({
        mode: "auto",
        scenario: {
          variables: { revenue: { low: 1, high: 2 } },
          objective: "maximize_score",
        },
      });
      const productDecision = await runtime.productDecision({
        inputs: [
          { name: "revenue", value: 125000, low: 100000, high: 160000 },
          { name: "cost", value: 72000, low: 65000, high: 90000 },
        ],
        objective: "maximize_expected_value",
        risk_tolerance: "balanced",
        scenarios: 10000,
        engine: "product",
        label: "launch-eval",
      });
      const productAgentRun = await runtime.productAgentRun({
        task: "Search launch preparation docs",
        context: { area: "operations" },
        tools: ["search", "simulate"],
        max_steps: 4,
        output_format: "markdown",
      });
      const productOptimize = await runtime.productOptimize({
        objective: "maximize_margin",
        variables: [{ name: "price", min: 95, max: 140, step: 1 }],
        constraints: [{ expression: "price >= 100", required: true }],
        iterations: 1200,
        engine: "product",
      });
      const productRetrieve = await runtime.productRetrieve({
        query: "launch checklist",
        documents: [
          { id: "doc_1", content: "Launch checklist for product release." },
          { id: "doc_2", content: "Retention analysis for pilot customers." },
        ],
        top_k: 2,
        rerank: true,
      });
      const productForecast = await runtime.productForecast({
        metric: "monthly_revenue",
        history: [118000, 121000, 125000, 128500],
        horizon: 3,
        seasonality: true,
        confidence_level: 0.9,
      });
      const loggedDecision = await runtime.logDecision({
        chosen_action: "expand",
        context: "Launch planning",
        expected_value: 128000,
      });
      const listedDecisions = await runtime.listDecisions({
        page: 1,
        limit: 20,
        with_outcome_only: true,
      });
      const fetchedDecision = await runtime.getDecision("decision_123");
      const recordedOutcome = await runtime.recordOutcome("decision_123", {
        actual_outcome: 141000,
        outcome_notes: "Launch outperformed baseline",
      });
      const executionReceipt = await runtime.executeDecision("decision_123", {
        webhook_url: "https://hooks.example.test/decision",
      });
      const deletedDecision = await runtime.deleteDecision("decision_123");
      const created = await runtime.createAgentRun({
        task: "Search the knowledge base",
        approval_mode: "manual",
        output_format: "markdown",
      });
      const listed = await runtime.listAgentRuns({ status: "requires_approval" });
      const fetched = await runtime.getAgentRun("run_agent_123");
      const events = await runtime.getAgentRunEvents("run_agent_123", { limit: 25 });
      const eventStream = [];
      for await (const item of runtime.streamAgentRunEvents("run_agent_123", { limit: 25 })) {
        eventStream.push(item);
      }
      const resumed = await runtime.resumeAgentRun("run_agent_123");
      const cancelled = await runtime.cancelAgentRun("run_agent_123");
      const approved = await runtime.approveAgentRun("run_agent_123");
      const checkpoints = await runtime.listAgentRunCheckpoints("run_agent_123");
      const checkpointQuery = await runtime.queryAgentRunCheckpoints({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "run_agent_123",
        checkpoint_id: "cp_2",
      });
      const missionEvents = await runtime.listAgentRunMissionEvents("run_agent_123", { limit: 25 });
      const missionEventQuery = await runtime.queryAgentRunMissionEvents({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "run_agent_123",
        event_type: "run_created",
      });
      const telemetry = await runtime.listAgentRunTelemetry("run_agent_123", { limit: 25 });
      const telemetryQuery = await runtime.queryAgentRunTelemetry({
        status: "completed",
        request_hash: "a".repeat(64),
        policy_snapshot_id: "policy-v1",
        schema_snapshot_id: "schema-v1",
        run_id: "run_agent_123",
        telemetry_kind: "agent_run_completion",
        module_name: "agent_run_service",
      });
      const replay = await runtime.replayAgentRun("run_agent_123", { checkpoint_id: "cp_2" });
      const forked = await runtime.forkAgentRun("run_agent_123", { checkpoint_id: "cp_1" });
      const recommendation = await runtime.recommend([
        {
          name: "expand",
          request: {
            mode: "expert",
            runs: 250,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 140000 } }],
              objective_function: "outcome",
            },
          },
        },
      ]);
      const score = await runtime.score(
        {
          mode: "expert",
          runs: 250,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 120000 } }],
            objective_function: "outcome",
          },
        },
        { expected_value: 0.7, downside_risk: 0.3 },
      );
      const batch = await runtime.batch([
        {
          mode: "expert",
          runs: 100,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
            objective_function: "outcome",
          },
        },
        {
          mode: "expert",
          runs: 100,
          simulation: {
            variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
            objective_function: "outcome",
          },
        },
      ]);
      const compare = await runtime.compare([
        {
          name: "base",
          request: {
            mode: "expert",
            runs: 150,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 100 } }],
              objective_function: "outcome",
            },
          },
        },
        {
          name: "stretch",
          request: {
            mode: "expert",
            runs: 150,
            simulation: {
              variables: [{ name: "outcome", distribution: "fixed", params: { value: 120 } }],
              objective_function: "outcome",
            },
          },
        },
      ]);
      const deploymentRegions = await runtime.listDeploymentRegions();
      const deployment = await runtime.getDeployment();
      const createdDeployment = await runtime.createDeployment();
      const deploymentCost = await runtime.getDeploymentCost("dep_123");
      const deletedDeployment = await runtime.deleteDeployment("dep_123");
      const me = await runtime.me();
      const usage = await runtime.usage();
      const limits = await runtime.limits();
      const distributions = await runtime.distributions();
      const templates = await runtime.templates();
      const billingInfo = await runtime.getBillingInfo();
      const checkout = await runtime.createBillingCheckout({ plan: "developer" });
      const portal = await runtime.createBillingPortal();
      const refreshed = await runtime.refreshCredits({
        device_id: "device_runtime_123",
        billing_period: "2026-05",
        credits_used: 17,
      });
      const listedApiKeys = await runtime.listApiKeys();
      const createdApiKey = await runtime.createApiKey({
        label: "Mission Rotation Key",
        device_limit: 3,
      });
      const revokedApiKey = await runtime.revokeApiKey("key_2");

      expect(models.data[0]?.id).toBe("text.tokenizer");
      expect(models.data[0]?.routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_routing_targets).toEqual([]);
      expect(models.data[0]?.chat_routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_chat_routing_targets).toEqual([]);
      expect(models.data[0]?.embedding_routing_targets).toEqual([]);
      expect(models.data[0]?.resolved_embedding_routing_targets).toEqual([]);
      expect(models.data[0]?.required_provider_headers).toEqual([]);
      expect(models.data[0]?.provider_auth_env_vars).toEqual([]);
      expect(models.data[0]?.provider_auth_configured).toBe(false);
      expect(models.data[0]?.routing_fallback_policy).toBeNull();
      expect(models.data[0]?.chat_routing_fallback_policy).toBeNull();
      expect(models.data[0]?.embedding_routing_fallback_policy).toBeNull();
      expect(models.data[0]?.routing_fallback_on).toEqual([]);
      expect(models.data[0]?.chat_routing_fallback_on).toEqual([]);
      expect(models.data[0]?.embedding_routing_fallback_on).toEqual([]);
      expect(models.data[0]?.routing_max_attempts).toBeNull();
      expect(models.data[0]?.chat_routing_max_attempts).toBeNull();
      expect(models.data[0]?.embedding_routing_max_attempts).toBeNull();
      expect(models.data[0]?.timeout_seconds).toBeNull();
      expect(models.data[0]?.chat_timeout_seconds).toBeNull();
      expect(models.data[0]?.embedding_timeout_seconds).toBeNull();
      expect(models.data[0]?.bridge_tokenizer_backends).toEqual(["tiktoken", "sentencepiece"]);
      expect(models.data[0]?.bridge_artifact_backends).toEqual([
        "safetensors",
        "huggingface_hub",
      ]);
      expect(models.data[0]?.bridge_cache_root).toBe("/tmp/algenta-hf-cache");
      expect(models.data[0]?.bridge_auth_env_vars).toEqual(["HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"]);
      expect(models.data[0]?.bridge_auth_configured).toBe(true);
      expect(artifact.status).toBe("not_cached");
      expect(artifact.auth_env_var_used).toBe("HF_TOKEN");
      expect(artifact.resolved_path).toBeNull();
      expect(tokenized.token_count).toBe(2);
      expect(counted.token_count).toBe(2);
      expect(chat.choices[0]?.message.content).toBe("Deterministic utility response.");
      expect(chat.provider_backend).toBeNull();
      expect(chat.provider_model_id).toBeNull();
      expect(chat.provider_attempts).toEqual([]);
      expect(chatStream).toHaveLength(2);
      expect(chatStream[0]?.provider_backend).toBeNull();
      expect(chatStream[0]?.provider_model_id).toBeNull();
      expect(chatStream[0]?.provider_attempts).toEqual([]);
      expect(response.output[0]?.content[0]?.type).toBe("tokenization");
      expect(response.provider_backend).toBeNull();
      expect(response.provider_model_id).toBeNull();
      expect(response.provider_attempts).toEqual([]);
      expect(response.output[0]?.provider_backend).toBeNull();
      expect(response.output[0]?.provider_model_id).toBeNull();
      expect(response.output[0]?.provider_attempts).toEqual([]);
      expect(responseStream[0]).toMatchObject({ type: "response.created" });
      expect(responseStream[0]?.response?.provider_backend).toBeNull();
      expect(responseStream[0]?.response?.provider_model_id).toBeNull();
      expect(responseStream[0]?.response?.provider_attempts).toEqual([]);
      expect(embeddings.dimensions).toBe(3);
      expect(embeddings.provider_backend).toBeNull();
      expect(embeddings.provider_model_id).toBeNull();
      expect(embeddings.provider_attempts).toEqual([]);
      expect(similarity.score).toBe(0.94);
      expect(reranked.data[0]?.rank).toBe(1);
      expect(plan.recommended_action).toBe("Expand sales coverage");
      expect(productDecision.action).toBe("proceed");
      expect(productAgentRun.steps[0]?.tool).toBe("search");
      expect(productOptimize.optimal_values.price).toBe(119);
      expect(productRetrieve.results[0]?.document_id).toBe("doc_1");
      expect(productForecast.periods[0]?.trend).toBe("up");
      expect(loggedDecision.chosen_action).toBe("expand");
      expect(loggedDecision.policy_snapshot_id).toBe("policy-v1");
      expect(listedDecisions.decisions[0]?.id).toBe("decision_123");
      expect(listedDecisions.decisions[0]?.schema_snapshot_id).toBe("schema-v1");
      expect(fetchedDecision.context).toBe("Launch planning");
      expect(fetchedDecision.manifest_version).toBe("runtime-manifest-v1");
      expect(recordedOutcome.outcome_delta).toBe(13000);
      expect(executionReceipt.execution_status).toBe("delivered");
      expect(executionReceipt.policy_snapshot_id).toBe("execution-policy-v1-r2:abcd1234abcd1234");
      expect(executionReceipt.schema_snapshot_id).toBe("schema-v1");
      expect(executionReceipt.manifest_version).toBe("runtime-manifest-v1");
      expect(deletedDecision).toEqual({});
      expect(created.pending_action).toBe("approve");
      expect(listed.total).toBe(1);
      expect(listed.data[0]?.run_id).toBe("run_agent_123");
      expect(created.latest_checkpoint_id).toBe("cp_2");
      expect(fetched.run_id).toBe("run_agent_123");
      expect(events.total_events).toBe(1);
      expect(eventStream.at(-1)).toMatchObject({ type: "agent.run.completed" });
      expect(resumed.status).toBe("requires_approval");
      expect(cancelled.status).toBe("cancelled");
      expect(approved.status).toBe("completed");
      expect(checkpoints.total_checkpoints).toBe(2);
      expect(checkpointQuery.total).toBe(1);
      expect(checkpointQuery.data[0]?.run_status).toBe("completed");
      expect(checkpointQuery.data[0]?.checkpoint_id).toBe("cp_2");
      expect(missionEvents.total_events).toBe(1);
      expect(missionEvents.data[0]?.event_message).toBe("Agent run created.");
      expect(missionEventQuery.total).toBe(1);
      expect(missionEventQuery.data[0]?.run_status).toBe("completed");
      expect(telemetry.total_batches).toBe(1);
      expect(telemetry.data[0]?.telemetry_kind).toBe("agent_run_completion");
      expect(telemetryQuery.total).toBe(1);
      expect(telemetryQuery.data[0]?.module_name).toBe("agent_run_service");
      expect(replay.replay_status).toBe("matched");
      expect(forked.source_checkpoint_id).toBe("cp_1");
      expect(recommendation.recommended_action).toBe("expand");
      expect(score.score).toBe(0.73);
      expect(batch.total).toBe(2);
      expect(compare.winner).toBe("stretch");
      expect(deploymentRegions.providers[0]?.regions[0]?.id).toBe("algenta-shared");
      expect(deploymentRegions.providers[0]?.regions[0]?.name).toBe("Algenta Shared");
      expect(deployment?.deployment_id).toBe("dep_123");
      expect(createdDeployment.status).toBe("requested");
      expect(deploymentCost.month).toBe(5);
      expect(deletedDeployment.status).toBe("deprovisioning");
      expect(me.organization).toBe("Algenta Labs");
      expect(usage.billing_period).toBe("2026-05");
      expect(usage.simulations_run).toBe(120);
      expect(limits.plan).toBe("enterprise");
      expect(distributions.distributions[0]?.name).toBe("normal");
      expect(templates.templates[0]?.id).toBe("product-launch");
      expect(limits.connectors).toBe(64);
      expect(billingInfo.stripe_customer_id).toBe("cus_123");
      expect(checkout.url).toContain("/checkout/");
      expect(portal.url).toContain("/portal/");
      expect(refreshed.credits_granted).toBe(10000);
      expect(refreshed.monthly_remaining).toBe(475000);
      expect(listedApiKeys[0]?.label).toBe("Mission Runtime Key");
      expect(createdApiKey.raw_key).toBe("de_live_wxyz_secret_value");
      expect(revokedApiKey).toEqual({});
    });
});
