// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import {
  DEFAULT_JOIN_PATH_HOPS,
  MAX_JOIN_PATH_HOPS,
  appendQueryParameters,
  cloneJsonValue,
  endpointSuffix,
  invalidStreamError,
  iterateSsePayloads,
  mergeContractSections,
  mergeRequestPayload,
  normalizeJoinPathSpec,
  normalizeMaxJoinHops,
  normalizeQueryLikeRequest,
  normalizeSourceRegistrationRequest,
  parseSseEvent,
  rebaseEndpoint,
  requireNonNegativeInteger,
  requirePositiveInteger,
} from "./_client_constants.js";
import { DecisionEngineError } from "./_client_errors.js";
import { DEFAULT_BASE_URL, MCP_ENDPOINT } from "./contract.js";

function captureError(run: () => unknown): unknown {
  try {
    run();
  } catch (error) {
    return error;
  }
  throw new Error("expected the call to throw");
}

function streamFromChunks(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(chunk);
      }
      controller.close();
    },
  });
}

async function collectSsePayloads(chunks: Uint8Array[]): Promise<unknown[]> {
  const payloads: unknown[] = [];
  for await (const payload of iterateSsePayloads(streamFromChunks(chunks))) {
    payloads.push(payload);
  }
  return payloads;
}

const encoder = new TextEncoder();

describe("normalizeMaxJoinHops", () => {
  it.each([1, 3, MAX_JOIN_PATH_HOPS])("accepts the integer %d", (value) => {
    expect(normalizeMaxJoinHops(value, "join_path.max_hops")).toBe(value);
  });

  it.each([1.5, "3", null, Number.NaN])("rejects the non-integer %j", (value) => {
    expect(() => normalizeMaxJoinHops(value, "join_path.max_hops")).toThrowError(
      `join_path.max_hops must be an integer between 1 and ${MAX_JOIN_PATH_HOPS}.`,
    );
  });

  it.each([0, -2, MAX_JOIN_PATH_HOPS + 1])("rejects the out-of-range integer %d", (value) => {
    expect(() => normalizeMaxJoinHops(value, "constraints.max_join_hops")).toThrowError(
      `constraints.max_join_hops must be between 1 and ${MAX_JOIN_PATH_HOPS}.`,
    );
  });
});

describe("requireNonNegativeInteger and requirePositiveInteger", () => {
  it("returns non-negative integers unchanged", () => {
    expect(requireNonNegativeInteger(0, "limit must be >= 0")).toBe(0);
    expect(requireNonNegativeInteger(7, "limit must be >= 0")).toBe(7);
  });

  it.each([-1, 2.5, "4", undefined])("rejects %j with the caller's message", (value) => {
    const error = captureError(() => requireNonNegativeInteger(value, "limit must be >= 0"));
    expect(error).toBeInstanceOf(DecisionEngineError);
    expect((error as DecisionEngineError).message).toBe("limit must be >= 0");
    expect((error as DecisionEngineError).errorCode).toBe("unknown_error");
  });

  it("requires strictly positive integers", () => {
    expect(requirePositiveInteger(1, "page must be >= 1")).toBe(1);
    expect(() => requirePositiveInteger(0, "page must be >= 1")).toThrowError("page must be >= 1");
    expect(() => requirePositiveInteger(-3, "page must be >= 1")).toThrowError(
      "page must be >= 1",
    );
  });
});

describe("normalizeJoinPathSpec", () => {
  it("defaults max_hops when absent", () => {
    const spec = { edges: [{ from: "orders", to: "customers" }] };
    const normalized = normalizeJoinPathSpec(spec);
    expect(normalized).toEqual({ ...spec, max_hops: DEFAULT_JOIN_PATH_HOPS });
    // The input object is not mutated.
    expect(spec).not.toHaveProperty("max_hops");
  });

  it("keeps an explicit max_hops that covers the edges", () => {
    expect(normalizeJoinPathSpec({ max_hops: 2, edges: ["a", "b"] })).toEqual({
      max_hops: 2,
      edges: ["a", "b"],
    });
  });

  it("rejects an explicit max_hops that is out of range", () => {
    expect(() => normalizeJoinPathSpec({ max_hops: 0 })).toThrowError(
      `join_path.max_hops must be between 1 and ${MAX_JOIN_PATH_HOPS}.`,
    );
  });

  it("rejects more edges than max_hops allows", () => {
    expect(() => normalizeJoinPathSpec({ max_hops: 2, edges: ["a", "b", "c"] })).toThrowError(
      "join_path.edges has 3 entries but join_path.max_hops=2.",
    );
  });

  it("ignores a non-array edges value", () => {
    expect(normalizeJoinPathSpec({ edges: "orders->customers" })).toEqual({
      edges: "orders->customers",
      max_hops: DEFAULT_JOIN_PATH_HOPS,
    });
  });
});

describe("normalizeQueryLikeRequest and mergeRequestPayload", () => {
  it("normalizes a join_path object and a constraints.max_join_hops value", () => {
    const request = {
      metric: "revenue",
      join_path: { edges: ["orders->customers"] },
      constraints: { max_join_hops: 3, allow_scan: false },
    };
    const normalized = normalizeQueryLikeRequest(request);
    expect(normalized).toEqual({
      metric: "revenue",
      join_path: { edges: ["orders->customers"], max_hops: DEFAULT_JOIN_PATH_HOPS },
      constraints: { max_join_hops: 3, allow_scan: false },
    });
    expect(normalized.constraints).not.toBe(request.constraints);
  });

  it("copies constraints without max_join_hops unchanged", () => {
    expect(normalizeQueryLikeRequest({ constraints: { allow_scan: true } })).toEqual({
      constraints: { allow_scan: true },
    });
  });

  it("rejects an invalid constraints.max_join_hops", () => {
    expect(() =>
      normalizeQueryLikeRequest({ constraints: { max_join_hops: MAX_JOIN_PATH_HOPS + 1 } }),
    ).toThrowError(`constraints.max_join_hops must be between 1 and ${MAX_JOIN_PATH_HOPS}.`);
  });

  it.each([
    { join_path: "orders->customers", constraints: null },
    { join_path: undefined },
    {},
  ])("leaves non-object join_path/constraints alone for %j", (request) => {
    expect(normalizeQueryLikeRequest(request)).toEqual(request);
  });

  it("merges extra fields over the request before normalizing", () => {
    expect(
      mergeRequestPayload({ metric: "revenue", limit: 5 }, { limit: 10, join_path: {} }),
    ).toEqual({ metric: "revenue", limit: 10, join_path: { max_hops: DEFAULT_JOIN_PATH_HOPS } });
  });

  it("treats an undefined request as empty and defaults extra to nothing", () => {
    expect(mergeRequestPayload(undefined)).toEqual({});
    expect(mergeRequestPayload(undefined, { metric: "orders" })).toEqual({ metric: "orders" });
  });
});

describe("cloneJsonValue and mergeContractSections", () => {
  it("deep clones plain JSON data", () => {
    const value = { nested: { list: [1, { flag: true }] } };
    const clone = cloneJsonValue(value);
    expect(clone).toEqual(value);
    expect(clone).not.toBe(value);
    expect(clone.nested).not.toBe(value.nested);
  });

  it("deep merges nested objects and replaces arrays and primitives", () => {
    const base = {
      api: { contract_endpoint: "/v1/meta/contract", discovery_endpoint: "/v1/meta/discover" },
      flows: ["a", "b"],
      version: 1,
    };
    const merged = mergeContractSections(base, {
      api: { contract_endpoint: "/custom" },
      flows: ["c"],
      version: 2,
    });
    expect(merged).toEqual({
      api: { contract_endpoint: "/custom", discovery_endpoint: "/v1/meta/discover" },
      flows: ["c"],
      version: 2,
    });
    expect(base.api.contract_endpoint).toBe("/v1/meta/contract");
    expect(merged.api).not.toBe(base.api);
  });

  it("returns a clone of the override when either side is not an object", () => {
    const override = { replaced: true };
    const merged = mergeContractSections<unknown>("primitive-base", override);
    expect(merged).toEqual(override);
    expect(merged).not.toBe(override);
    expect(mergeContractSections<unknown>({ kept: 1 }, ["list"])).toEqual(["list"]);
    expect(mergeContractSections<unknown>({ kept: 1 }, null)).toBeNull();
  });
});

describe("appendQueryParameters", () => {
  it("returns the path unchanged when no parameter has a value", () => {
    expect(appendQueryParameters("/v1/items", {})).toBe("/v1/items");
    expect(appendQueryParameters("/v1/items", { cursor: undefined })).toBe("/v1/items");
  });

  it("skips undefined values, stringifies numbers and encodes reserved characters", () => {
    expect(
      appendQueryParameters("/v1/items", { limit: 25, cursor: undefined, q: "a b&c" }),
    ).toBe("/v1/items?limit=25&q=a+b%26c");
  });
});

describe("invalidStreamError", () => {
  it("builds a DecisionEngineError carrying a structured response body", () => {
    const error = invalidStreamError("invalid_sse_event", "bad frame", { payload: "x" });
    expect(error).toBeInstanceOf(DecisionEngineError);
    expect(error.statusCode).toBe(0);
    expect(error.errorCode).toBe("invalid_sse_event");
    expect(error.message).toBe("bad frame");
    expect(error.responseBody).toEqual({
      error: { code: "invalid_sse_event", message: "bad frame", details: { payload: "x" } },
    });
    expect(error.details).toEqual({ payload: "x" });
  });
});

describe("parseSseEvent", () => {
  it.each(["", ": keep-alive", "event: ping\nid: 7", "   \n:comment\n"])(
    "returns null when %j carries no data line",
    (rawEvent) => {
      expect(parseSseEvent(rawEvent)).toBeNull();
    },
  );

  it("parses a single data line and tolerates trailing whitespace", () => {
    expect(parseSseEvent('event: delta\ndata: {"token":"hi"}   ')).toEqual({ token: "hi" });
    expect(parseSseEvent("data:42")).toBe(42);
  });

  it.each(["data: [DONE]", "data:[DONE]", "data: [DONE]\r\n"])(
    "recognizes the terminal sentinel in %j",
    (rawEvent) => {
      expect(parseSseEvent(rawEvent)).toBe("[DONE]");
    },
  );

  it("joins multi-line data with newlines before parsing, including CRLF input", () => {
    expect(parseSseEvent("data: [1,\r\ndata: 2]")).toEqual([1, 2]);
    // Invalid JSON surfaces the joined payload verbatim, proving the join delimiter.
    const error = captureError(() => parseSseEvent("data: not\ndata: json"));
    expect(error).toBeInstanceOf(DecisionEngineError);
    const streamError = error as DecisionEngineError;
    expect(streamError.errorCode).toBe("invalid_sse_event");
    expect(streamError.message).toBe("Received invalid JSON in Server-Sent Events payload.");
    expect(streamError.details).toEqual({ payload: "not\njson" });
  });
});

describe("iterateSsePayloads", () => {
  it("reassembles events split across chunks, including inside a UTF-8 sequence", async () => {
    const bytes = encoder.encode('data: {"text":"héllo"}\n\ndata: {"n":2}\n\n');
    // 0xC3 starts the two-byte encoding of "é"; split right after it.
    const splitAt = bytes.indexOf(0xc3) + 1;
    const payloads = await collectSsePayloads([
      bytes.slice(0, splitAt),
      bytes.slice(splitAt, splitAt + 9),
      bytes.slice(splitAt + 9),
    ]);
    expect(payloads).toEqual([{ text: "héllo" }, { n: 2 }]);
  });

  it("stops at [DONE] and ignores anything after it", async () => {
    const payloads = await collectSsePayloads([
      encoder.encode('data: {"n":1}\n\ndata: [DONE]\n\ndata: {"n":2}\n\n'),
    ]);
    expect(payloads).toEqual([{ n: 1 }]);
  });

  it("skips comment-only events and yields a trailing event without a blank line", async () => {
    const payloads = await collectSsePayloads([
      encoder.encode(': ping\n\ndata: {"n":1}\n\n'),
      encoder.encode('data: {"n":2}'),
    ]);
    expect(payloads).toEqual([{ n: 1 }, { n: 2 }]);
  });

  it.each([
    { label: "[DONE]", tail: "data: [DONE]" },
    { label: "a comment", tail: ": bye" },
    { label: "whitespace", tail: "  \n" },
  ])("does not yield a trailing $label fragment", async ({ tail }) => {
    const payloads = await collectSsePayloads([encoder.encode(`data: {"n":1}\n\n${tail}`)]);
    expect(payloads).toEqual([{ n: 1 }]);
  });

  it("yields nothing for an empty stream", async () => {
    expect(await collectSsePayloads([])).toEqual([]);
  });

  it("propagates invalid JSON as a DecisionEngineError", async () => {
    const error = await collectSsePayloads([encoder.encode("data: nope\n\n")]).catch(
      (failure: unknown) => failure,
    );
    expect(error).toBeInstanceOf(DecisionEngineError);
    expect((error as DecisionEngineError).errorCode).toBe("invalid_sse_event");
  });
});

describe("normalizeSourceRegistrationRequest", () => {
  it("passes a pre-wrapped request through and merges extra and description", () => {
    const payload = normalizeSourceRegistrationRequest(
      { source: { path: "orders.csv" } },
      "Orders export",
      { tags: ["finance"] },
    );
    expect(payload).toEqual({
      source: { path: "orders.csv" },
      tags: ["finance"],
      description: "Orders export",
    });
  });

  it("does not add description or extra keys when they are absent", () => {
    expect(normalizeSourceRegistrationRequest({ source: { path: "orders.csv" } })).toEqual({
      source: { path: "orders.csv" },
    });
  });

  it("wraps a bare source and folds extra into it instead of the envelope", () => {
    expect(
      normalizeSourceRegistrationRequest({ path: "orders.csv" }, undefined, { kind: "csv" }),
    ).toEqual({ source: { path: "orders.csv", kind: "csv" } });
  });

  it("wraps an undefined source as an empty object", () => {
    expect(normalizeSourceRegistrationRequest(undefined, "empty")).toEqual({
      source: {},
      description: "empty",
    });
  });
});

describe("endpointSuffix and rebaseEndpoint", () => {
  it.each([
    { endpoint: `${DEFAULT_BASE_URL}/v1/meta/contract`, suffix: "/v1/meta/contract" },
    { endpoint: DEFAULT_BASE_URL, suffix: "/" },
    { endpoint: `${DEFAULT_BASE_URL}/`, suffix: "/" },
    { endpoint: "https://other.example.com/a/b?c=1", suffix: "/a/b?c=1" },
    { endpoint: "https://other.example.com", suffix: "/" },
    // Non-special schemes expose an empty pathname, which falls back to "/".
    { endpoint: "custom://host", suffix: "/" },
    { endpoint: "/v1/relative", suffix: "/v1/relative" },
    { endpoint: "v1/relative", suffix: "/v1/relative" },
  ])("maps $endpoint to $suffix", ({ endpoint, suffix }) => {
    expect(endpointSuffix(endpoint)).toBe(suffix);
  });

  it("rebases default-hosted and relative endpoints onto a self-hosted base", () => {
    expect(rebaseEndpoint("https://engine.customer.internal/", MCP_ENDPOINT)).toBe(
      "https://engine.customer.internal/mcp",
    );
    expect(rebaseEndpoint("https://engine.customer.internal", "v1/query")).toBe(
      "https://engine.customer.internal/v1/query",
    );
    expect(rebaseEndpoint("https://engine.customer.internal", DEFAULT_BASE_URL)).toBe(
      "https://engine.customer.internal/",
    );
  });
});
