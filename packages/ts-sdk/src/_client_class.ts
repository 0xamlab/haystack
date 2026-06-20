/** Auto-split sub-module of client.ts — the DecisionEngineClient class. */

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
 *
 * The full method surface (simulate, query, recordOutcome, capability plane,
 * agent runs, jobs, billing, etc.) is implemented across the
 * `_client_class_methods_*.ts` sibling files via TypeScript declaration
 * merging + prototype augmentation. Importing the client barrel
 * (`./client.js`) runs those side-effect imports so every method is
 * available on `DecisionEngineClient` instances.
 */

import type { DecisionEngineClientConfig } from './types.js';
import { DEVICE_ID_HEADER, resolveClientDeviceHeaders } from './client_device_headers.js';
import {
  DEVICE_BINDING_TOKEN_HEADER,
  loadHostedDeviceBindingToken,
  persistHostedDeviceBindingToken,
} from './client_device_binding.js';
import { apiKeyHelpText, resolveClientBaseUrl } from './privacy_profile.js';


import {
  DEFAULT_MAX_RETRIES,
  DEFAULT_TIMEOUT,
  SDK_USER_AGENT,
  invalidStreamError,
  iterateSsePayloads,
} from "./_client_constants.js";
import {
  AuthenticationError,
  DecisionEngineError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
  normalizedErrorCode,
  normalizedErrorMessage,
} from "./_client_errors.js";

export class DecisionEngineClient {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
  readonly defaultHeaders: Record<string, string>;
  readonly deviceId: string | null;

  constructor(config: DecisionEngineClientConfig = {}) {
    const resolvedBaseUrl = resolveClientBaseUrl(config.baseUrl, "DecisionEngineClient");
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
      throw new Error(
        'API key required. Pass apiKey or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n' +
          apiKeyHelpText("DecisionEngineClient", resolvedBaseUrl),
      );
    }
    this.apiKey = key;
    this.baseUrl = resolvedBaseUrl;
    this.timeout = config.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = config.maxRetries ?? DEFAULT_MAX_RETRIES;
    const deviceHeaders = resolveClientDeviceHeaders(SDK_USER_AGENT, config.defaultHeaders);
    this.defaultHeaders = {
      'Authorization': `Bearer ${this.apiKey}`,
      'Content-Type': 'application/json',
      'User-Agent': SDK_USER_AGENT,
      ...deviceHeaders,
      ...config.defaultHeaders,
    };
    this.deviceId =
      typeof this.defaultHeaders[DEVICE_ID_HEADER] === "string" &&
      this.defaultHeaders[DEVICE_ID_HEADER].trim().length > 0
        ? this.defaultHeaders[DEVICE_ID_HEADER].trim()
        : null;
  }

  currentRequestHeaders(): Record<string, string> {
    const headers = { ...this.defaultHeaders };
    if (this.deviceId) {
      const bindingToken = loadHostedDeviceBindingToken(this.baseUrl, this.apiKey, this.deviceId);
      if (bindingToken) {
        headers[DEVICE_BINDING_TOKEN_HEADER] = bindingToken;
      }
    }
    return headers;
  }

  captureBindingToken(response: Response, requestHeaders: Record<string, string>): void {
    const deviceId = requestHeaders[DEVICE_ID_HEADER]?.trim();
    const bindingToken = response.headers.get(DEVICE_BINDING_TOKEN_HEADER)?.trim();
    if (!deviceId || !bindingToken) {
      return;
    }
    persistHostedDeviceBindingToken(this.baseUrl, this.apiKey, deviceId, bindingToken);
    this.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER] = bindingToken;
  }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
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
          const requestHeaders = this.currentRequestHeaders();
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
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

  async requestWithMetadata<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<{ data: T; headers: Record<string, string> }> {
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
          const requestHeaders = this.currentRequestHeaders();
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
          const data = await this.handleResponse<T>(response);
          const headers: Record<string, string> = {};
          response.headers.forEach((value, key) => {
            headers[key] = value;
          });
          return { data, headers };
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

  async *requestStream<T>(
    method: string,
    path: string,
    body?: unknown,
  ): AsyncGenerator<T> {
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
          const requestHeaders = this.currentRequestHeaders();
          requestHeaders.Accept = "text/event-stream";
          const response = await fetch(`${this.baseUrl}${path}`, {
            method,
            headers: requestHeaders,
            body: body !== undefined ? JSON.stringify(body) : undefined,
            signal: controller.signal,
          });
          clearTimeout(timer);
          this.captureBindingToken(response, requestHeaders);
          if (!(response.status >= 200 && response.status < 300)) {
            await this.handleResponse<unknown>(response);
            throw invalidStreamError(
              "stream_request_failed",
              "Streaming request failed without a structured API error.",
              { status_code: response.status },
            );
          }
          const contentType = response.headers.get("content-type") ?? "";
          if (!contentType.includes("text/event-stream")) {
            throw invalidStreamError(
              "invalid_stream_content_type",
              "Expected text/event-stream response for streaming request.",
              { content_type: contentType },
            );
          }
          if (!response.body) {
            throw invalidStreamError(
              "stream_body_missing",
              "Streaming response body is unavailable.",
              {},
            );
          }
          for await (const payload of iterateSsePayloads(response.body)) {
            yield payload as T;
          }
          return;
        } finally {
          clearTimeout(timer);
        }
      } catch (err) {
        if (
          err instanceof AuthenticationError ||
          err instanceof ValidationError ||
          err instanceof NotFoundError
        ) {
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

    throw lastError ?? new DecisionEngineError('Streaming request failed after retries');
  }

  async handleResponse<T>(response: Response): Promise<T> {
    let body: unknown = {};
    try {
      body = await response.json();
    } catch { /* empty body */ }

    const msg = normalizedErrorMessage(body);
    const errorCode = normalizedErrorCode(body, "unknown_error");

    if (response.status >= 200 && response.status < 300) return body as T;
    if (response.status === 401) throw new AuthenticationError(msg, body, errorCode);
    if (response.status === 404) throw new NotFoundError(msg, body, errorCode);
    if (response.status === 422) throw new ValidationError(msg, body, errorCode);
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') ?? '60', 10);
      throw new RateLimitError(msg, retryAfter, body, errorCode);
    }
    if (response.status >= 500) throw new ServerError(msg, response.status, body, errorCode);
    throw new DecisionEngineError(msg, response.status, errorCode, body);
  }
}

export { DecisionEngineClient as AlgentaClient };
export type { DecisionEngineClientConfig as AlgentaClientConfig };

// Back-compat: historically exported as CodnaClient (#157 rename). Algenta is the engine/SDK;
// Algenta is a consumer. Keep the old name working so existing integrations don't break.
export { DecisionEngineClient as CodnaClient };
export type { DecisionEngineClientConfig as CodnaClientConfig };

export default DecisionEngineClient;
