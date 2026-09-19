// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of types.ts — misc types. */

// Auto-split from types.ts. Cross-file type references use `import type`.
import type { CAPABILITY_PLANE_CONTRACT, PRIMARY_DATA_QUERY_CONTRACT } from "./contract.js";

export interface LibraryModuleDescriptor {
  name: string;
  engine: string;
  functions: string[];
}

export interface LibraryListResponse {
  modules: LibraryModuleDescriptor[];
  count: number;
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface LibraryHealthResponse {
  status: string;
  engine: string;
  module_count: number;
  runtime_available: boolean;
}

export interface LibraryExecutionRequest {
  module: string;
  function: string;
  args?: unknown;
  request_id?: string;
}

export interface LibraryExecutionResponse {
  module: string;
  function: string;
  result: unknown;
  latency_ms: number;
  engine_used: string;
  request_id?: string | null;
}

// ─── Error Types ───────────────────────────────────────────────────────────

export interface APIErrorDetail {
  field?: string;
  issue: string;
}

export interface APIError {
  code: string;
  message: string;
  details?: APIErrorDetail[];
  request_id?: string;
  docs_url?: string;
}

export interface APIErrorResponse {
  error: APIError;
}

// ─── Client Config ─────────────────────────────────────────────────────────

export interface DecisionEngineClientConfig {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  defaultHeaders?: Record<string, string>;
}
