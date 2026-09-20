// SPDX-License-Identifier: Apache-2.0
// Transport-layer behaviour of DecisionEngineClient: constructor resolution, the
// retry ladder shared by request()/requestWithMetadata()/requestStream(), the
// status classifier in handleResponse(), and hosted device-binding token capture.
// Every test is network-free (fetch is stubbed) and clock-free (fake timers).
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT } from "./_client_constants.js";
import {
  AuthenticationError,
  DecisionEngineClient,
  DecisionEngineError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
} from "./client.js";
import {
  DEVICE_BINDING_TOKEN_HEADER,
  clearHostedDeviceBindingTokenCacheForTests,
} from "./client_device_binding.js";
import { DEVICE_ID_HEADER } from "./client_device_headers.js";
import type { DecisionEngineClientConfig } from "./types.js";

const ORIGINAL_ENV = { ...process.env };
// Any of these may be present in a developer shell and would change how the
// client resolves its key, base URL, privacy profile or device identity.
const HERMETIC_ENV_KEYS = [
  "ALGENTA_API_KEY",
  "DE_API_KEY",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
  "ALGENTA_API_URL",
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_DEVICE_ID",
  "DE_DEVICE_ID",
  "ALGENTA_RUNTIME_DIR",
  "ALGENTA_APP_BASE_URL",
  "APP_BASE_URL",
  "DE_APP_BASE_URL",
];
const BASE_URL = "https://example.test";
const BINDING_STORE_FILE = "hosted_device_binding_tokens.json";

function restoreEnv(): void {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
}

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

function sseResponse(events: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

function newClient(overrides: Partial<DecisionEngineClientConfig> = {}): DecisionEngineClient {
  return new DecisionEngineClient({
    apiKey: "de_test_transport",
    baseUrl: BASE_URL,
    ...overrides,
  });
}

function fetchCall(fetchMock: ReturnType<typeof vi.fn>, index: number): [string, RequestInit] {
  return fetchMock.mock.calls[index] as [string, RequestInit];
}

async function collect<T>(iterator: AsyncGenerator<T>): Promise<T[]> {
  const items: T[] = [];
  for await (const item of iterator) {
    items.push(item);
  }
  return items;
}

describe("DecisionEngineClient transport", () => {
  let runtimeDir: string;

  beforeEach(() => {
    for (const key of HERMETIC_ENV_KEYS) {
      delete process.env[key];
    }
    // Binding tokens are looked up on disk before every request; point the store
    // at a scratch directory so a developer's real ~/.algenta never leaks in.
    runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-ts-transport-"));
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    clearHostedDeviceBindingTokenCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    clearHostedDeviceBindingTokenCacheForTests();
    fs.rmSync(runtimeDir, { recursive: true, force: true });
    restoreEnv();
  });

  describe("constructor", () => {
    it("prefers an explicit apiKey over both environment keys", () => {
      process.env.ALGENTA_API_KEY = "de_env_primary";
      process.env.DE_API_KEY = "de_env_legacy";

      const client = newClient({ apiKey: "de_explicit" });

      expect(client.apiKey).toBe("de_explicit");
      expect(client.defaultHeaders.Authorization).toBe("Bearer de_explicit");
    });

    it.each([
      ["ALGENTA_API_KEY", "de_env_primary"],
      ["DE_API_KEY", "de_env_legacy"],
    ])("falls back to %s when apiKey is omitted", (variable, value) => {
      process.env[variable] = value;

      const client = new DecisionEngineClient({ baseUrl: BASE_URL });

      expect(client.apiKey).toBe(value);
    });

    it("prefers ALGENTA_API_KEY over DE_API_KEY when both are set", () => {
      process.env.ALGENTA_API_KEY = "de_env_primary";
      process.env.DE_API_KEY = "de_env_legacy";

      expect(new DecisionEngineClient({ baseUrl: BASE_URL }).apiKey).toBe("de_env_primary");
    });

    it("fails closed with a pointed message when no key is available anywhere", () => {
      expect(() => new DecisionEngineClient({ baseUrl: BASE_URL })).toThrowError(
        /API key required\. Pass apiKey or set ALGENTA_API_KEY \/ DE_API_KEY[\s\S]*dashboard\/api-keys/,
      );
    });

    it("applies the documented timeout and retry defaults and honours overrides", () => {
      const defaults = newClient();
      const overridden = newClient({ timeout: 5_000, maxRetries: 1 });

      expect(defaults.timeout).toBe(DEFAULT_TIMEOUT);
      expect(defaults.maxRetries).toBe(DEFAULT_MAX_RETRIES);
      expect(overridden.timeout).toBe(5_000);
      expect(overridden.maxRetries).toBe(1);
    });

    it("sends bearer auth, JSON content type, the SDK user agent and caller headers", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ ok: true }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ defaultHeaders: { "X-Trace": "trace-1" } });

      await client.request("GET", "/v1/me");

      const [url, init] = fetchCall(fetchMock, 0);
      const headers = init.headers as Record<string, string>;
      expect(url).toBe(`${BASE_URL}/v1/me`);
      expect(init.method).toBe("GET");
      expect(init.body).toBeUndefined();
      expect(headers.Authorization).toBe("Bearer de_test_transport");
      expect(headers["Content-Type"]).toBe("application/json");
      expect(headers["User-Agent"]).toMatch(/^algenta-ts\//);
      expect(headers["X-Trace"]).toBe("trace-1");
      expect(headers[DEVICE_ID_HEADER]).toMatch(/^[0-9a-f]{32}$/);
    });
  });

  describe("request() retry ladder", () => {
    it("retries 5xx with exponential backoff and returns the eventual success", async () => {
      vi.useFakeTimers();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ error: { message: "upstream down" } }, 500))
        .mockResolvedValueOnce(jsonResponse({ error: { message: "still down" } }, 503))
        .mockResolvedValueOnce(jsonResponse({ ok: true }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 2 });

      const pending = client.request<{ ok: boolean }>("POST", "/v1/ping", { probe: 1 });

      await vi.advanceTimersByTimeAsync(0);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      // Attempt 1 waits 2^0 s, attempt 2 waits 2^1 s: nothing fires a tick early.
      await vi.advanceTimersByTimeAsync(999);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      await vi.advanceTimersByTimeAsync(1_999);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchMock).toHaveBeenCalledTimes(3);

      await expect(pending).resolves.toEqual({ ok: true });
      for (const index of [0, 1, 2]) {
        const [url, init] = fetchCall(fetchMock, index);
        expect(url).toBe(`${BASE_URL}/v1/ping`);
        expect(init.method).toBe("POST");
        expect(init.body).toBe(JSON.stringify({ probe: 1 }));
      }
    });

    it.each([
      [401, AuthenticationError, "invalid_api_key"],
      [404, NotFoundError, "dataset_not_found"],
      [422, ValidationError, "invalid_request"],
    ])("rethrows a %i immediately without retrying", async (status, errorClass, code) => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { code, message: `status ${status}` } }, status),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 3 });

      const error = await client.request("GET", "/v1/me").catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(errorClass);
      expect((error as DecisionEngineError).statusCode).toBe(status);
      expect((error as DecisionEngineError).errorCode).toBe(code);
      expect((error as DecisionEngineError).message).toBe(`status ${status}`);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("honours Retry-After on a 429, then applies the backoff before retrying", async () => {
      vi.useFakeTimers();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse(
            { error: { code: "rate_limited", message: "slow down" } },
            429,
            { "Retry-After": "2" },
          ),
        )
        .mockResolvedValueOnce(jsonResponse({ ok: true }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const pending = client.request("GET", "/v1/me");

      await vi.advanceTimersByTimeAsync(0);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      // 2 s from Retry-After, then the loop's own 1 s backoff for attempt 1.
      await vi.advanceTimersByTimeAsync(2_999);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      await expect(pending).resolves.toEqual({ ok: true });
    });

    it("defaults Retry-After to 60 s and throws at once when there is no retry budget", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { code: "rate_limited", message: "slow down" } }, 429),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const error = await client.request("GET", "/v1/me").catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(RateLimitError);
      expect((error as RateLimitError).retryAfter).toBe(60);
      expect((error as RateLimitError).errorCode).toBe("rate_limited");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("gives up on a 429 once the retry budget is spent", async () => {
      vi.useFakeTimers();
      const limited = () =>
        jsonResponse({ error: { message: "slow down" } }, 429, { "Retry-After": "1" });
      const fetchMock = vi.fn().mockResolvedValueOnce(limited()).mockResolvedValueOnce(limited());
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const assertion = expect(client.request("GET", "/v1/me")).rejects.toBeInstanceOf(
        RateLimitError,
      );
      await vi.advanceTimersByTimeAsync(2_000);
      await assertion;
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("retries a network failure and rethrows it once the budget is spent", async () => {
      vi.useFakeTimers();
      const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const assertion = expect(client.request("GET", "/v1/me")).rejects.toThrowError(
        new TypeError("fetch failed"),
      );
      await vi.advanceTimersByTimeAsync(1_000);
      await assertion;
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("aborts a request that exceeds the configured timeout", async () => {
      vi.useFakeTimers();
      const fetchMock = vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("The operation was aborted.", "AbortError")),
            );
          }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0, timeout: 50 });

      const assertion = expect(client.request("GET", "/v1/me")).rejects.toMatchObject({
        name: "AbortError",
      });
      await vi.advanceTimersByTimeAsync(49);
      expect(fetchCall(fetchMock, 0)[1].signal?.aborted).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      await assertion;
      expect(fetchCall(fetchMock, 0)[1].signal?.aborted).toBe(true);
    });

    it("surfaces a ServerError carrying the status once retries are exhausted", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ detail: { code: "gateway_down", message: "bad gateway" } }, 502),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const error = await client.request("GET", "/v1/me").catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(ServerError);
      expect((error as ServerError).statusCode).toBe(502);
      expect((error as ServerError).errorCode).toBe("gateway_down");
      expect((error as ServerError).message).toBe("bad gateway");
    });

    it("throws a DecisionEngineError with the raw status for other 4xx bodies", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(new Response("forbidden", { status: 403 }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const error = await client.request("GET", "/v1/me").catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(DecisionEngineError);
      expect(error).not.toBeInstanceOf(ServerError);
      expect((error as DecisionEngineError).statusCode).toBe(403);
      expect((error as DecisionEngineError).errorCode).toBe("unknown_error");
      expect((error as DecisionEngineError).message).toBe("Unknown error");
      expect((error as DecisionEngineError).responseBody).toEqual({});
    });

    it.each([
      ["request", (client: DecisionEngineClient) => client.request("GET", "/v1/me")],
      [
        "requestWithMetadata",
        (client: DecisionEngineClient) => client.requestWithMetadata("GET", "/v1/me"),
      ],
      [
        "requestStream",
        (client: DecisionEngineClient) => collect(client.requestStream("GET", "/v1/me")),
      ],
    ])("%s with a negative retry budget never issues a request and fails closed", async (_name, run) => {
      // maxRetries is not validated, so a negative budget skips the loop entirely;
      // the fallback error must still be a DecisionEngineError rather than a null.
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: -1 });

      const error = await run(client).catch((caught: unknown) => caught);

      expect(error).toBeInstanceOf(DecisionEngineError);
      expect((error as DecisionEngineError).message).toMatch(/request failed after retries/i);
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  describe("requestWithMetadata()", () => {
    it("returns the parsed body with lower-cased response headers", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ id: "dec-1" }, 200, {
          "X-Request-Id": "req-123",
          "X-RateLimit-Remaining": "41",
        }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const result = await client.requestWithMetadata<{ id: string }>("POST", "/v1/query", {
        source_name: "orders",
      });

      expect(result.data).toEqual({ id: "dec-1" });
      expect(result.headers["x-request-id"]).toBe("req-123");
      expect(result.headers["x-ratelimit-remaining"]).toBe("41");
      expect(result.headers["content-type"]).toBe("application/json");
      expect(fetchCall(fetchMock, 0)[1].body).toBe(JSON.stringify({ source_name: "orders" }));
    });

    it("waits out a 429 and retries with the same backoff as request()", async () => {
      vi.useFakeTimers();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ error: { message: "slow down" } }, 429, { "Retry-After": "1" }),
        )
        .mockResolvedValueOnce(jsonResponse({ ok: true }, 200, { "X-Attempt": "2" }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const pending = client.requestWithMetadata("GET", "/v1/me");

      await vi.advanceTimersByTimeAsync(1_999);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);
      await expect(pending).resolves.toEqual({
        data: { ok: true },
        headers: { "content-type": "application/json", "x-attempt": "2" },
      });
    });

    it("rethrows a 422 immediately without retrying", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { code: "invalid_request", message: "bad filter" } }, 422),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 3 });

      await expect(client.requestWithMetadata("GET", "/v1/me")).rejects.toBeInstanceOf(
        ValidationError,
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("throws the RateLimitError at once when there is no retry budget", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { message: "slow down" } }, 429, { "Retry-After": "3" }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      await expect(client.requestWithMetadata("GET", "/v1/me")).rejects.toMatchObject({
        name: "RateLimitError",
        retryAfter: 3,
      });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("retries a network failure then rethrows it after the last attempt", async () => {
      vi.useFakeTimers();
      const fetchMock = vi.fn().mockRejectedValue(new TypeError("socket hang up"));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const assertion = expect(client.requestWithMetadata("GET", "/v1/me")).rejects.toThrowError(
        "socket hang up",
      );
      await vi.advanceTimersByTimeAsync(1_000);
      await assertion;
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });
  });

  describe("requestStream()", () => {
    it("yields parsed SSE payloads, skips comments and stops at [DONE]", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        sseResponse([
          ": keep-alive\n\n",
          'data: {"seq":1}\n\n',
          "event: step\ndata: {\"seq\":2}\n\n",
          "data: [DONE]\n\n",
          'data: {"seq":3}\n\n',
        ]),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const events = await collect(
        client.requestStream<{ seq: number }>("POST", "/v1/agent/runs/run-1/events", { a: 1 }),
      );

      expect(events).toEqual([{ seq: 1 }, { seq: 2 }]);
      const [url, init] = fetchCall(fetchMock, 0);
      expect(url).toBe(`${BASE_URL}/v1/agent/runs/run-1/events`);
      expect(init.method).toBe("POST");
      expect(init.body).toBe(JSON.stringify({ a: 1 }));
      expect((init.headers as Record<string, string>).Accept).toBe("text/event-stream");
    });

    it.each([
      [401, AuthenticationError],
      [404, NotFoundError],
      [422, ValidationError],
    ])("surfaces the structured API error for a %i without retrying", async (status, errorClass) => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { code: "nope", message: "no stream" } }, status),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 3 });

      await expect(collect(client.requestStream("GET", "/v1/x"))).rejects.toBeInstanceOf(
        errorClass,
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it.each([
      ["a JSON content type", () => jsonResponse({ not: "a stream" }), "application/json"],
      // A bodiless 200 carries no content-type header at all; it is reported as "".
      ["no content type", () => new Response(null, { status: 200 }), ""],
    ])("rejects a 2xx response with %s instead of text/event-stream", async (_label, build, seen) => {
      const fetchMock = vi.fn().mockResolvedValueOnce(build());
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      const error = await collect(client.requestStream("GET", "/v1/x")).catch(
        (caught: unknown) => caught,
      );

      expect(error).toBeInstanceOf(DecisionEngineError);
      expect((error as DecisionEngineError).errorCode).toBe("invalid_stream_content_type");
      expect((error as DecisionEngineError).statusCode).toBe(0);
      expect((error as DecisionEngineError).details).toEqual({ content_type: seen });
    });

    it("rejects a 2xx event-stream response that has no body", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        new Response(null, { status: 200, headers: { "content-type": "text/event-stream" } }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      await expect(collect(client.requestStream("GET", "/v1/x"))).rejects.toMatchObject({
        errorCode: "stream_body_missing",
        message: "Streaming response body is unavailable.",
      });
    });

    it("retries a 5xx with backoff before the stream opens", async () => {
      vi.useFakeTimers();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ error: { message: "down" } }, 500))
        .mockResolvedValueOnce(sseResponse(['data: {"seq":1}\n\n']));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const iterator = client.requestStream<{ seq: number }>("GET", "/v1/x");
      const first = iterator.next();
      await vi.advanceTimersByTimeAsync(999);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      expect(fetchMock).toHaveBeenCalledTimes(2);

      await expect(first).resolves.toEqual({ value: { seq: 1 }, done: false });
      await expect(iterator.next()).resolves.toEqual({ value: undefined, done: true });
    });

    it("waits out a 429 before retrying the stream", async () => {
      vi.useFakeTimers();
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ error: { message: "slow down" } }, 429, { "Retry-After": "1" }),
        )
        .mockResolvedValueOnce(sseResponse(['data: {"seq":7}\n\n']));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 1 });

      const pending = collect(client.requestStream<{ seq: number }>("GET", "/v1/x"));
      await vi.advanceTimersByTimeAsync(1_999);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      await expect(pending).resolves.toEqual([{ seq: 7 }]);
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it.each([
      [500, ServerError],
      [429, RateLimitError],
    ])("gives up on a %i stream when there is no retry budget", async (status, errorClass) => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ error: { message: "nope" } }, status),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      await expect(collect(client.requestStream("GET", "/v1/x"))).rejects.toBeInstanceOf(
        errorClass,
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("handleResponse()", () => {
    it("returns an empty object for a 2xx response without a JSON body", async () => {
      const client = newClient();

      await expect(client.handleResponse(new Response(null, { status: 204 }))).resolves.toEqual(
        {},
      );
    });

    it("parses Retry-After into retryAfter seconds and defaults it to 60", async () => {
      const client = newClient();
      const withHeader = (await client
        .handleResponse(new Response("{}", { status: 429, headers: { "Retry-After": "7" } }))
        .catch((caught: unknown) => caught)) as RateLimitError;
      const withoutHeader = (await client
        .handleResponse(new Response("{}", { status: 429 }))
        .catch((caught: unknown) => caught)) as RateLimitError;

      expect(withHeader).toBeInstanceOf(RateLimitError);
      expect(withHeader.retryAfter).toBe(7);
      expect(withoutHeader.retryAfter).toBe(60);
      expect(withoutHeader.errorCode).toBe("unknown_error");
    });

    it("reads nested detail envelopes for the message and code", async () => {
      const client = newClient();

      const error = (await client
        .handleResponse(
          jsonResponse({ detail: { error: { code: "quota", message: "Quota exceeded" } } }, 500),
        )
        .catch((caught: unknown) => caught)) as ServerError;

      expect(error).toBeInstanceOf(ServerError);
      expect(error.errorCode).toBe("quota");
      expect(error.message).toBe("Quota exceeded");
      expect(error.statusCode).toBe(500);
    });
  });

  describe("device binding token capture", () => {
    it("persists a captured binding token and sends it on later requests", async () => {
      process.env.ALGENTA_DEVICE_ID = "ts-device-transport-00001";
      const fetchMock = vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ ok: true }, 200, { [DEVICE_BINDING_TOKEN_HEADER]: "  bind-token-abc  " }),
        )
        .mockResolvedValueOnce(jsonResponse({ ok: true }));
      vi.stubGlobal("fetch", fetchMock);
      const client = newClient({ maxRetries: 0 });

      expect(client.deviceId).toBe("ts-device-transport-00001");
      expect(client.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBeUndefined();

      await client.request("GET", "/v1/me");
      await client.request("GET", "/v1/me");

      expect(client.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBe("bind-token-abc");
      const storePath = path.join(runtimeDir, BINDING_STORE_FILE);
      expect(fs.existsSync(storePath)).toBe(true);
      expect(Object.values(JSON.parse(fs.readFileSync(storePath, "utf8")))).toEqual([
        "bind-token-abc",
      ]);
      const firstHeaders = fetchCall(fetchMock, 0)[1].headers as Record<string, string>;
      const secondHeaders = fetchCall(fetchMock, 1)[1].headers as Record<string, string>;
      expect(firstHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBeUndefined();
      expect(secondHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBe("bind-token-abc");
    });

    it("neither loads nor captures a binding token for a client without a device id", async () => {
      const fetchMock = vi.fn().mockResolvedValueOnce(
        jsonResponse({ ok: true }, 200, { [DEVICE_BINDING_TOKEN_HEADER]: "bind-token-xyz" }),
      );
      vi.stubGlobal("fetch", fetchMock);
      // An explicit blank device header disables device identity for this client.
      const client = newClient({ maxRetries: 0, defaultHeaders: { [DEVICE_ID_HEADER]: "" } });

      expect(client.deviceId).toBeNull();
      await client.request("GET", "/v1/me");

      expect(client.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBeUndefined();
      expect(fs.existsSync(path.join(runtimeDir, BINDING_STORE_FILE))).toBe(false);
      const headers = fetchCall(fetchMock, 0)[1].headers as Record<string, string>;
      expect(headers[DEVICE_BINDING_TOKEN_HEADER]).toBeUndefined();
    });

    it("ignores a response that carries no binding token", async () => {
      process.env.ALGENTA_DEVICE_ID = "ts-device-transport-00002";
      vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse({ ok: true })));
      const client = newClient({ maxRetries: 0 });

      await client.request("GET", "/v1/me");

      expect(client.defaultHeaders[DEVICE_BINDING_TOKEN_HEADER]).toBeUndefined();
      expect(fs.existsSync(path.join(runtimeDir, BINDING_STORE_FILE))).toBe(false);
    });
  });
});
