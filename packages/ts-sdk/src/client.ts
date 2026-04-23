/**
 * Decision Engine TypeScript SDK — fetch-based client.
 * Works in Node.js 18+ and modern browsers.
 *
 * @example
 * import { DecisionEngineClient } from 'decision-engine-sdk';
 *
 * const client = new DecisionEngineClient({ apiKey: 'de_live_...' });
 * const result = await client.simulate({
 *   mode: 'auto',
 *   scenario: {
 *     variables: { revenue: { low: 80000, high: 200000 } },
 *     objective: 'maximize_net_value',
 *   },
 * });
 * console.log(result.recommended_action, result.confidence);
 */

import type {
  BatchResult,
  DecisionEnvelope,
  DecisionEngineClientConfig,
  ExplainResponse,
  JobStatusResponse,
  JobSubmitResponse,
  QueryResponse,
  ResolveResponse,
  SimulateRequest,
  SourceRegistrationRequest,
  SourceRegistrationResponse,
  VerifyResponse,
} from './types.js';
import { DEFAULT_BASE_URL } from './contract.js';

export { DecisionEngineClientConfig };

const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_MAX_RETRIES = 3;

function mergeRequestPayload(
  request: Record<string, unknown> | undefined,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return { ...(request ?? {}), ...extra };
}

function normalizeSourceRegistrationRequest(
  source?: SourceRegistrationRequest | Record<string, unknown>,
  description?: string,
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  let payload: Record<string, unknown>;
  if (source && typeof source === 'object' && 'source' in source) {
    payload = { ...(source as Record<string, unknown>) };
  } else {
    payload = { source: { ...(source ?? {}), ...extra } };
    extra = {};
  }

  if (Object.keys(extra).length > 0) {
    payload = { ...payload, ...extra };
  }
  if (description !== undefined) {
    payload.description = description;
  }
  return payload;
}

function dedupeStrings(values: string[]): string[] {
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

function sourceSetFromRequest(request: Record<string, unknown>): string[] {
  const values: string[] = [];
  if (typeof request.source_name === 'string') values.push(request.source_name);
  if (typeof request.join_source_name === 'string') values.push(request.join_source_name);

  if (Array.isArray(request.sources)) {
    for (const source of request.sources) {
      if (source && typeof source === 'object' && typeof (source as { name?: unknown }).name === 'string') {
        values.push((source as { name: string }).name);
      }
    }
  }

  if (request.join_path && typeof request.join_path === 'object') {
    const joinPath = request.join_path as Record<string, unknown>;
    for (const key of ['base_source', 'group_source']) {
      const value = joinPath[key];
      if (typeof value === 'string') values.push(value);
    }
    if (Array.isArray(joinPath.edges)) {
      for (const edge of joinPath.edges) {
        if (!edge || typeof edge !== 'object') continue;
        const edgeRecord = edge as Record<string, unknown>;
        for (const key of ['left_source', 'right_source']) {
          const value = edgeRecord[key];
          if (typeof value === 'string') values.push(value);
        }
      }
    }
  }

  return dedupeStrings(values);
}

function splitResolvedSources(resolvedSource: string | undefined): string[] {
  if (!resolvedSource) return [];
  return dedupeStrings(resolvedSource.split('⋈').map(part => part.trim()));
}

function buildExplainResponse(
  request: Record<string, unknown>,
  result: QueryResponse,
): ExplainResponse {
  let joinPath: Array<Record<string, unknown>> = [...(result.join_path ?? [])];
  if (request.join_path && typeof request.join_path === 'object') {
    const edges = (request.join_path as { edges?: unknown }).edges;
    if (joinPath.length === 0 && Array.isArray(edges)) {
      joinPath = edges.filter(
        (edge): edge is Record<string, unknown> => Boolean(edge) && typeof edge === 'object',
      );
    }
  }

  const sourceSet = (() => {
    const resolved = result.source_set ?? splitResolvedSources(result.resolved_source);
    return resolved.length > 0 ? resolved : sourceSetFromRequest(request);
  })();
  if (joinPath.length === 0 && sourceSet.length > 1) {
    joinPath = sourceSet.slice(0, -1).map((source, index) => ({
      left_source: source,
      right_source: sourceSet[index + 1],
    }));
  }

  return {
    source_set: sourceSet,
    join_path: joinPath,
    planner_mode: result.planner_mode ?? (result.exact_spec ? 'exact_spec' : result.decision_path),
    decision_path: result.decision_path,
    plan_hash: result.plan_hash,
    schema_revision: result.schema_revision,
    validated: result.validated,
    clarification_required: result.clarification_required,
    rejection_reason: result.rejection_reason,
    resolved_source: result.resolved_source,
    resolved_column: result.resolved_column,
    resolved_role: result.resolved_role,
    confidence: result.confidence,
    confidence_source: result.confidence_source,
    deterministic_scope: result.deterministic_scope,
    plan: result.plan,
    explanation: result.explanation,
    request_id: result.request_id,
  };
}

export class DecisionEngineError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number = 0,
    public readonly errorCode: string = 'unknown_error',
    public readonly responseBody: unknown = null,
  ) {
    super(message);
    this.name = 'DecisionEngineError';
  }
}

export class AuthenticationError extends DecisionEngineError {
  constructor(message: string, body: unknown) {
    super(message, 401, 'authentication_error', body);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends DecisionEngineError {
  constructor(message: string, public readonly retryAfter: number = 60, body: unknown) {
    super(message, 429, 'rate_limit_exceeded', body);
    this.name = 'RateLimitError';
  }
}

export class ValidationError extends DecisionEngineError {
  constructor(message: string, body: unknown) {
    super(message, 422, 'validation_error', body);
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends DecisionEngineError {
  constructor(message: string, body: unknown) {
    super(message, 404, 'not_found', body);
    this.name = 'NotFoundError';
  }
}

export class ServerError extends DecisionEngineError {
  constructor(message: string, statusCode: number, body: unknown) {
    super(message, statusCode, 'server_error', body);
    this.name = 'ServerError';
  }
}

export class DecisionEngineClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly defaultHeaders: Record<string, string>;

  constructor(config: DecisionEngineClientConfig = {}) {
    // Safe env var access — works in Node.js; undefined in browsers (use config.apiKey instead)
    const envKey: string | undefined = (typeof globalThis !== 'undefined' &&
      'process' in globalThis &&
      ((globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env?.[
        'ALGENTA_API_KEY'
      ] ||
        (globalThis as { process?: { env?: { ALGENTA_API_KEY?: string; DE_API_KEY?: string } } }).process?.env?.[
          'DE_API_KEY'
        ])) || undefined;
    const key = config.apiKey ?? envKey ?? '';
    if (!key) {
      throw new Error('API key required. Pass apiKey or set ALGENTA_API_KEY environment variable.');
    }
    this.apiKey = key;
    this.baseUrl = (config.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, '');
    this.timeout = config.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = config.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.defaultHeaders = {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'User-Agent': 'algenta-ts/1.0.0',
      ...config.defaultHeaders,
    };
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        const delay = Math.pow(2, attempt - 1) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }

      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        try {
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: this.defaultHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          return await this.handleResponse<T>(response);
        } finally {
          clearTimeout(timer);
        }
      } catch (err) {
        if (err instanceof AuthenticationError || err instanceof ValidationError || err instanceof NotFoundError) {
          throw err;
        }
        if (err instanceof RateLimitError) {
          if (attempt >= this.maxRetries) throw err;
          await new Promise(resolve => setTimeout(resolve, err.retryAfter * 1000));
          lastError = err;
          continue;
        }
        lastError = err as Error;
        if (attempt >= this.maxRetries) throw err;
      }
    }

    throw lastError ?? new DecisionEngineError('Request failed after retries');
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    let body: Record<string, unknown> = {};
    try {
      body = await response.json() as Record<string, unknown>;
    } catch { /* empty body */ }

    const errorBody = body as { error?: { message?: string; code?: string } };
    const msg = errorBody.error?.message ?? 'Unknown error';

    if (response.status >= 200 && response.status < 300) return body as T;
    if (response.status === 401) throw new AuthenticationError(msg, body);
    if (response.status === 404) throw new NotFoundError(msg, body);
    if (response.status === 422) throw new ValidationError(msg, body);
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') ?? '60', 10);
      throw new RateLimitError(msg, retryAfter, body);
    }
    if (response.status >= 500) throw new ServerError(msg, response.status, body);
    throw new DecisionEngineError(msg, response.status, errorBody.error?.code ?? 'unknown', body);
  }

  // ─── Simulation ───────────────────────────────────────────────────────────

  async simulate(request: SimulateRequest): Promise<DecisionEnvelope> {
    return this.request<DecisionEnvelope>('POST', '/v1/simulate', request);
  }

  async resolve(request: Record<string, unknown>): Promise<ResolveResponse> {
    return this.request<ResolveResponse>('POST', '/v1/resolve', request);
  }

  async query(request: Record<string, unknown>): Promise<QueryResponse> {
    return this.request<QueryResponse>('POST', '/v1/query', request);
  }

  async verify(request: Record<string, unknown>): Promise<VerifyResponse> {
    return this.request<VerifyResponse>('POST', '/v1/verify', request);
  }

  async registerSource(
    source: SourceRegistrationRequest | Record<string, unknown>,
    options: { description?: string; name?: string } = {},
  ): Promise<SourceRegistrationResponse> {
    return this.request<SourceRegistrationResponse>(
      'POST',
      '/v1/sources/register',
      normalizeSourceRegistrationRequest(
        source,
        options.description,
        options.name ? { name: options.name } : {},
      ),
    );
  }

  async refreshSource(datasetId: string): Promise<SourceRegistrationResponse> {
    return this.request<SourceRegistrationResponse>('POST', `/v1/data/${datasetId}/refresh`);
  }

  async explain(request: Record<string, unknown>): Promise<ExplainResponse> {
    const result = await this.query(mergeRequestPayload(request));
    return buildExplainResponse(request, result);
  }

  async recommend(actions: Array<{ name: string; request: SimulateRequest }>, options?: { runs?: number; seed?: number }): Promise<Record<string, unknown>> {
    return this.request('POST', '/v1/recommend', { actions, ...options });
  }

  async score(request: SimulateRequest, scoringWeights?: Record<string, number>): Promise<Record<string, unknown>> {
    return this.request('POST', '/v1/score', { request, scoring_weights: scoringWeights });
  }

  async batch(items: SimulateRequest[]): Promise<BatchResult> {
    return this.request<BatchResult>('POST', '/v1/batch', { items });
  }

  async compare(scenarios: Array<{ name: string; request: SimulateRequest }>, options?: { runs?: number; seed?: number }): Promise<Record<string, unknown>> {
    return this.request('POST', '/v1/compare', { scenarios, ...options });
  }

  // ─── Async Jobs ───────────────────────────────────────────────────────────

  async submitJob(request: SimulateRequest, callbackUrl?: string): Promise<JobSubmitResponse> {
    return this.request<JobSubmitResponse>('POST', '/v1/jobs', { request, callback_url: callbackUrl });
  }

  async getJob(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>('GET', `/v1/jobs/${jobId}`);
  }

  async getJobResult(jobId: string): Promise<Record<string, unknown>> {
    return this.request('GET', `/v1/jobs/${jobId}/result`);
  }

  async cancelJob(jobId: string): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>('POST', `/v1/jobs/${jobId}/cancel`);
  }

  async pollJob(jobId: string, options: { timeoutMs?: number; pollIntervalMs?: number } = {}): Promise<Record<string, unknown>> {
    const { timeoutMs = 300_000, pollIntervalMs = 2_000 } = options;
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const status = await this.getJob(jobId);
      if (status.status === 'completed') return this.getJobResult(jobId);
      if (status.status === 'failed' || status.status === 'cancelled') {
        throw new DecisionEngineError(`Job ${jobId} ended with status '${status.status}': ${status.error_message}`);
      }
      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
    }
    throw new DecisionEngineError(`Job ${jobId} timed out after ${timeoutMs}ms`);
  }

  // ─── Account ──────────────────────────────────────────────────────────────

  async me(): Promise<Record<string, unknown>> {
    return this.request('GET', '/v1/me');
  }

  async health(): Promise<{ status: string; timestamp: string }> {
    return this.request('GET', '/v1/health');
  }

  async version(): Promise<{ api_version: string; engine_version: string; environment: string }> {
    return this.request('GET', '/v1/version');
  }
}

export default DecisionEngineClient;
