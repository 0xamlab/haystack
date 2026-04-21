import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionEngineClient } from "./client.js";

function makeQueryResponse(overrides: Record<string, unknown> = {}) {
  return {
    query_id: "query-1",
    result: { rows: [] },
    result_type: "table",
    confidence: 0.98,
    plan: ["resolve metric", "execute query"],
    resolved_column: "revenue",
    resolved_role: "metric",
    resolved_source: "orders",
    row_count: 1,
    candidates: [],
    source_scores: { orders: 0.98 },
    ambiguous: false,
    exact_spec: true,
    explanation: ["used exact spec"],
    latency_ms: 12,
    decision_path: "exact_spec",
    plan_hash: "plan-1",
    validated: true,
    deterministic_scope: "exact",
    confidence_source: "schema_truth",
    ...overrides,
  };
}

describe("DecisionEngineClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends deterministic query requests with auth headers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(makeQueryResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    const request = {
      source_name: "orders",
      metric_column: "revenue",
      aggregation: "sum",
    };

    const result = await client.query(request);

    expect(result.plan_hash).toBe("plan-1");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://example.test/v1/query",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(request),
        headers: expect.objectContaining({
          Authorization: "Bearer de_test_123",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("derives explain output from query responses when source graph metadata is absent", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify(
            makeQueryResponse({
              exact_spec: false,
              decision_path: "planner_hint",
              resolved_source: "orders ⋈ stores",
              source_scores: { orders: 0.92, stores: 0.88 },
            }),
          ),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });

    const response = await client.explain({
      metric_column: "revenue",
      aggregation: "sum",
    });

    expect(response.source_set).toEqual(["orders", "stores"]);
    expect(response.join_path).toEqual([
      { left_source: "orders", right_source: "stores" },
    ]);
    expect(response.planner_mode).toBe("planner_hint");
  });
});
