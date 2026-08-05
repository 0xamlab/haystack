import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./runtime_daemon_client.js", () => ({
  executeQuery: vi.fn(),
  executeRuntimeLibrary: vi.fn(),
  getRuntimeLibraryHealth: vi.fn(),
  listRuntimeLibraryModules: vi.fn(),
}));

vi.mock("./native_worker_client.js", () => ({
  callNativeWorker: vi.fn(),
  nativeWorkerAvailable: vi.fn(() => false),
}));

import { libraries, MojoRuntime } from "./libraries.js";
import {
  MojoFunctionNotRegisteredError,
  MojoRuntimeConfigurationError,
} from "./mojo_errors.js";
import { callNativeWorker, nativeWorkerAvailable } from "./native_worker_client.js";
import { Query, QueryError } from "./query.js";
import {
  executeQuery,
  executeRuntimeLibrary,
  getRuntimeLibraryHealth,
  listRuntimeLibraryModules,
} from "./runtime_daemon_client.js";

const listRuntimeLibraryModulesMock = vi.mocked(listRuntimeLibraryModules);
const executeRuntimeLibraryMock = vi.mocked(executeRuntimeLibrary);
const getRuntimeLibraryHealthMock = vi.mocked(getRuntimeLibraryHealth);
const executeQueryMock = vi.mocked(executeQuery);
const callNativeWorkerMock = vi.mocked(callNativeWorker);
const nativeWorkerAvailableMock = vi.mocked(nativeWorkerAvailable);

describe("MojoRuntime libraries surface", () => {
  afterEach(() => {
    vi.clearAllMocks();
    // clearAllMocks preserves a factory-set implementation, so a test that flips
    // this to true would otherwise leak into every later test in file order.
    nativeWorkerAvailableMock.mockReturnValue(false);
  });

  it("keeps the 22-library rollout inventory on canonical module names and alias dispatch", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "bpe_tokenizer", engine: "mojo", functions: ["bpe_merge_score"] },
      { name: "text.tokenizer", engine: "mojo", functions: ["word_tokenize", "pad_sequence"] },
      { name: "embeddings", engine: "mojo", functions: ["cosine_similarity"] },
      { name: "flash_attention", engine: "mojo", functions: ["flash_block_output"] },
      { name: "sparse_attention", engine: "mojo", functions: ["block_sparse_mask_density"] },
      { name: "transformer_attention", engine: "mojo", functions: ["scaled_dot_product_attention"] },
      { name: "transformer_blocks", engine: "mojo", functions: ["feedforward_layer1"] },
      { name: "llm_sampling", engine: "mojo", functions: ["top_k_threshold"] },
      { name: "vector_similarity", engine: "mojo", functions: ["cosine_similarity"] },
      { name: "vector_search", engine: "mojo", functions: ["recall_at_k"] },
      { name: "vector_kernels.ranker", engine: "mojo", functions: ["run_column_rank_v2"] },
      {
        name: "vector_kernels.table",
        engine: "mojo",
        functions: ["build_query", "source_id_of", "role_id_of", "build_table_json"],
      },
      { name: "sparse_vector", engine: "mojo", functions: ["nnz_ratio"] },
      { name: "rlhf_dpo", engine: "mojo", functions: ["dpo_reward_margin"] },
      {
        name: "rerank_eval",
        engine: "mojo",
        functions: ["precision_at_k", "hit_rate_at_k"],
      },
      {
        name: "inference_cost_latency",
        engine: "mojo",
        functions: ["prompt_token_estimate", "queue_delay_estimate"],
      },
      {
        name: "kv_cache",
        engine: "mojo",
        functions: ["kv_cache_total_memory", "kv_cache_utilization"],
      },
      {
        name: "paged_kv_cache",
        engine: "mojo",
        functions: ["page_table_lookup", "context_extension_factor"],
      },
      {
        name: "continuous_batching",
        engine: "mojo",
        functions: ["iteration_level_batch_size", "batching_efficiency"],
      },
      {
        name: "inference_engine",
        engine: "mojo",
        functions: ["kv_cache_hit_ratio", "decode_time_per_token"],
      },
      {
        name: "speculative_decoding",
        engine: "mojo",
        functions: ["speculative_accept_prob", "draft_model_speedup"],
      },
      {
        name: "generation_loop",
        engine: "mojo",
        functions: ["top_k_accept", "typical_sampling_accept"],
      },
    ]);
    executeRuntimeLibraryMock.mockImplementation(async (_config, request) => {
      if (request.module === "text.tokenizer") {
        return {
          module: "text.tokenizer",
          function: request.function,
          result: ["alpha", "beta"],
          latency_ms: 0.4,
          engine_used: "mojo",
          request_id: null,
        };
      }
      if (request.module === "vector_kernels.ranker") {
        return {
          module: "vector_kernels.ranker",
          function: request.function,
          result: '{"matches":[{"column":"unit_price","score":1.0}],"ambiguous":false}',
          latency_ms: 0.6,
          engine_used: "mojo",
          request_id: null,
        };
      }
      if (request.module === "vector_kernels.table") {
        return {
          module: "vector_kernels.table",
          function: request.function,
          result: {
            source_id: 1,
            role_id: 1,
            top_k: 2,
            query_norm_inv: 0.33,
            query_vec: { data: [0, 1], norm_inv: 0.0 },
          },
          latency_ms: 0.7,
          engine_used: "mojo",
          request_id: null,
        };
      }
      if (request.module === "rerank_eval") {
        return {
          module: "rerank_eval",
          function: request.function,
          result: 0.75,
          latency_ms: 0.3,
          engine_used: "mojo",
          request_id: null,
        };
      }
      if (request.module === "kv_cache") {
        return {
          module: "kv_cache",
          function: request.function,
          result: 131072,
          latency_ms: 0.3,
          engine_used: "mojo",
          request_id: null,
        };
      }
      if (request.module === "generation_loop") {
        return {
          module: "generation_loop",
          function: request.function,
          result: 1.0,
          latency_ms: 0.3,
          engine_used: "mojo",
          request_id: null,
        };
      }
      return {
        module: "inference_cost_latency",
        function: request.function,
        result: 25,
        latency_ms: 0.3,
        engine_used: "mojo",
        request_id: null,
      };
    });

    const catalog = await libraries({
      mode: "local",
      tcpAddress: "127.0.0.1:50099",
      timeout: 1_000,
    });

    expect(catalog.names()).toEqual([
      "bpe_tokenizer",
      "continuous_batching",
      "embeddings",
      "flash_attention",
      "generation_loop",
      "inference_cost_latency",
      "inference_engine",
      "kv_cache",
      "llm_sampling",
      "paged_kv_cache",
      "rerank_eval",
      "rlhf_dpo",
      "sparse_attention",
      "sparse_vector",
      "speculative_decoding",
      "text.tokenizer",
      "transformer_attention",
      "transformer_blocks",
      "vector_kernels.ranker",
      "vector_kernels.table",
      "vector_search",
      "vector_similarity",
    ]);
    expect(catalog.listFunctions("text.tokenizer")).toEqual(["word_tokenize", "pad_sequence"]);
    expect(catalog.listFunctions("vector_kernels.ranker")).toEqual(["run_column_rank_v2"]);
    expect(catalog.listFunctions("vector_kernels.table")).toEqual([
      "build_query",
      "source_id_of",
      "role_id_of",
      "build_table_json",
    ]);
    expect(catalog.listFunctions("rerank_eval")).toEqual(["precision_at_k", "hit_rate_at_k"]);
    expect(catalog.listFunctions("inference_cost_latency")).toEqual([
      "prompt_token_estimate",
      "queue_delay_estimate",
    ]);
    expect(catalog.listFunctions("kv_cache")).toEqual([
      "kv_cache_total_memory",
      "kv_cache_utilization",
    ]);
    expect(catalog.listFunctions("generation_loop")).toEqual([
      "top_k_accept",
      "typical_sampling_accept",
    ]);

    const textTokenizer = (catalog as Record<string, unknown>).text_tokenizer as {
      word_tokenize: (input: string) => Promise<string[]>;
    };
    const vectorRanker = (catalog as Record<string, unknown>).vector_kernels_ranker as {
      run_column_rank_v2: (input: Record<string, unknown>) => Promise<string>;
    };
    const vectorTable = (catalog as Record<string, unknown>).vector_kernels_table as {
      build_query: (...args: unknown[]) => Promise<Record<string, unknown>>;
    };
    const rerankEval = (catalog as Record<string, unknown>).rerank_eval as {
      precision_at_k: (...args: unknown[]) => Promise<number>;
    };
    const inferenceCostLatency = (catalog as Record<string, unknown>).inference_cost_latency as {
      prompt_token_estimate: (...args: unknown[]) => Promise<number>;
    };
    const kvCache = (catalog as Record<string, unknown>).kv_cache as {
      kv_cache_total_memory: (...args: unknown[]) => Promise<number>;
    };
    const generationLoop = (catalog as Record<string, unknown>).generation_loop as {
      top_k_accept: (...args: unknown[]) => Promise<number>;
    };

    await expect(textTokenizer.word_tokenize("alpha beta")).resolves.toEqual(["alpha", "beta"]);
    await expect(
      vectorRanker.run_column_rank_v2({ query: { name: "unit_price" } }),
    ).resolves.toContain('"ambiguous":false');
    await expect(vectorTable.build_query("unit_price", 1, 1, 2)).resolves.toMatchObject({
      source_id: 1,
      role_id: 1,
      top_k: 2,
    });
    await expect(rerankEval.precision_at_k([1, 0, 1], 3)).resolves.toBe(0.75);
    await expect(inferenceCostLatency.prompt_token_estimate(100, 4.0)).resolves.toBe(25);
    await expect(kvCache.kv_cache_total_memory(4096, 32)).resolves.toBe(131072);
    await expect(generationLoop.top_k_accept(1, 10)).resolves.toBe(1.0);

    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      1,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "text.tokenizer",
        function: "word_tokenize",
        args: "alpha beta",
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      2,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "vector_kernels.ranker",
        function: "run_column_rank_v2",
        args: { query: { name: "unit_price" } },
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      3,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "vector_kernels.table",
        function: "build_query",
        args: ["unit_price", 1, 1, 2],
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      4,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "rerank_eval",
        function: "precision_at_k",
        args: [[1, 0, 1], 3],
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      5,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "inference_cost_latency",
        function: "prompt_token_estimate",
        args: [100, 4],
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      6,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "kv_cache",
        function: "kv_cache_total_memory",
        args: [4096, 32],
        request_id: undefined,
      },
    );
    expect(executeRuntimeLibraryMock).toHaveBeenNthCalledWith(
      7,
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "generation_loop",
        function: "top_k_accept",
        args: [1, 10],
        request_id: undefined,
      },
    );
  });

  it("lists runtime-backed modules from the local daemon", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "ab_testing", engine: "mojo", functions: ["sample_size", "power"] },
      { name: "pricing", engine: "mojo", functions: ["elasticity"] },
    ]);

    const runtime = new MojoRuntime({
      mode: "local",
      tcpAddress: "127.0.0.1:50099",
      timeout: 1_000,
    });

    const modules = await runtime.listModules();

    expect(modules.map(module => module.name)).toEqual(["ab_testing", "pricing"]);
    expect(listRuntimeLibraryModulesMock).toHaveBeenCalledWith({
      mode: "local",
      tcpAddress: "127.0.0.1:50099",
      timeout: 1_000,
    });
  });

  it("builds a dynamic catalog and executes module functions without exposing source", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "ab_testing", engine: "mojo", functions: ["sample_size_proportion"] },
    ]);
    executeRuntimeLibraryMock.mockResolvedValue({
      module: "ab_testing",
      function: "sample_size_proportion",
      result: 3841,
      latency_ms: 4.2,
      engine_used: "mojo",
      request_id: "req_lib_1",
    });

    const catalog = await libraries({
      mode: "local",
      tcpAddress: "127.0.0.1:50099",
      timeout: 1_000,
    });

    const result = await catalog.ab_testing.sample_size_proportion({
      p1: 0.10,
      p2: 0.12,
      alpha: 0.05,
      power: 0.8,
    });

    expect(catalog.names()).toEqual(["ab_testing"]);
    expect(catalog.listFunctions("ab_testing")).toEqual(["sample_size_proportion"]);
    expect(result).toEqual(3841);
    expect(executeRuntimeLibraryMock).toHaveBeenCalledWith(
      {
        mode: "local",
        tcpAddress: "127.0.0.1:50099",
        timeout: 1_000,
      },
      {
        module: "ab_testing",
        function: "sample_size_proportion",
        args: { p1: 0.10, p2: 0.12, alpha: 0.05, power: 0.8 },
        request_id: undefined,
      },
    );
  });

  it("supports explicit module lookups and positional arg execution", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "pricing", engine: "mojo", functions: ["elasticity"] },
    ]);
    executeRuntimeLibraryMock.mockResolvedValue({
      module: "pricing",
      function: "elasticity",
      result: 1.18,
      latency_ms: 3.8,
      engine_used: "mojo",
      request_id: null,
    });

    const runtime = new MojoRuntime({
      mode: "local",
      timeout: 1_000,
    });

    const catalog = await runtime.libraries();
    const pricing = catalog.module("pricing");
    const result = await pricing.elasticity(12, 24);

    expect(pricing.name).toBe("pricing");
    expect(pricing.functions).toEqual(["elasticity"]);
    expect(result).toBe(1.18);
    expect(executeRuntimeLibraryMock).toHaveBeenCalledWith(
      {
        mode: "local",
        timeout: 1_000,
      },
      {
        module: "pricing",
        function: "elasticity",
        args: [12, 24],
        request_id: undefined,
      },
    );
  });

  it("does not leak mutable module descriptors through catalog listing or iteration", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "ab_testing", engine: "mojo", functions: ["sample_size_proportion"] },
    ]);

    const catalog = await libraries({ mode: "local" });
    const listed = catalog.listModules();
    listed[0]!.name = "tampered";
    listed[0]!.functions.push("power");

    const iterated = Array.from(catalog);
    iterated[0]!.name = "iterated_tampered";
    iterated[0]!.functions.push("sensitivity");

    expect(catalog.names()).toEqual(["ab_testing"]);
    expect(catalog.listFunctions("ab_testing")).toEqual(["sample_size_proportion"]);
    expect(catalog.listModules()).toEqual([
      { name: "ab_testing", engine: "mojo", functions: ["sample_size_proportion"] },
    ]);
    expect(() => catalog.ab_testing.power).toThrowError(MojoFunctionNotRegisteredError);
  });

  it("surfaces local runtime health without hosted fallback", async () => {
    getRuntimeLibraryHealthMock.mockResolvedValue({
      status: "ok",
      engine: "mojo",
      module_count: 424,
      runtime_available: true,
    });

    const runtime = new MojoRuntime({ mode: "local", timeout: 2_000 });
    const health = await runtime.health();

    expect(health).toEqual({
      status: "ok",
      engine: "mojo",
      module_count: 424,
      runtime_available: true,
    });
    expect(getRuntimeLibraryHealthMock).toHaveBeenCalledWith({
      mode: "local",
      timeout: 2_000,
    });
  });

  it("fails closed when callers try to configure hosted access", () => {
    expect(
      () =>
        new MojoRuntime({
          baseUrl: "https://example.test",
        } as never),
    ).toThrowError(MojoRuntimeConfigurationError);
  });

  it("raises explicit function errors for unknown exports", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "ab_testing", engine: "mojo", functions: ["sample_size_proportion"] },
    ]);

    const catalog = await libraries({ mode: "local" });

    expect(() => catalog.ab_testing.power).toThrowError(MojoFunctionNotRegisteredError);
  });

  it("keeps both modules catalog-addressable when public attribute aliases collide", async () => {
    listRuntimeLibraryModulesMock.mockResolvedValue([
      { name: "ab.testing", engine: "mojo", functions: ["sample_size_proportion"] },
      { name: "ab_testing", engine: "mojo", functions: ["power"] },
    ]);

    const catalog = await libraries({ mode: "local" });

    expect(catalog.names()).toEqual(["ab_testing", "ab.testing"]);
    expect(catalog.listFunctions("ab.testing")).toEqual(["sample_size_proportion"]);
    expect(catalog.listFunctions("ab_testing")).toEqual(["power"]);
    expect((catalog as Record<string, unknown>).ab_testing).toBeDefined();
    expect((catalog as Record<string, unknown>)["ab.testing"]).toBeDefined();
  });

  it("runs a Query plan and decodes a successful engine response", async () => {
    executeQueryMock.mockResolvedValue({
      response: {
        result: { columns: ["a"], rows: [[1, null]] },
        lineage: [{ op: "select", detail: "1 columns" }],
        plan_hash: "deadbeef",
        ops: 1,
      },
      latency_ms: 12,
      engine_used: "mojo",
      request_id: null,
    });

    const runtime = new MojoRuntime({ mode: "local" });
    const query = new Query({ columns: ["a", "b"], rows: [[1, 2]] }).select("a");
    const result = await runtime.query(query);

    expect(result.columns).toEqual(["a"]);
    expect(result.rows).toEqual([[1, null]]);
    expect(result.planHash).toBe("deadbeef");
    expect(result.ops).toBe(1);
    expect(result.nonFiniteCells).toBe(0);
    expect(executeQueryMock).toHaveBeenCalledWith(
      { mode: "local" },
      { request: query.toRequest() },
    );
  });

  it("throws QueryError, naming the op index, when the engine refuses a plan", async () => {
    executeQueryMock.mockResolvedValue({
      response: {
        error_code: "invalid_arguments",
        error_message: "join requires 'table'",
        op_index: 0,
      },
      latency_ms: 3,
      engine_used: "mojo",
      request_id: null,
    });

    const runtime = new MojoRuntime({ mode: "local" });
    const query = new Query({ columns: ["a"], rows: [[1]] }).select("a");

    await expect(runtime.query(query)).rejects.toMatchObject({
      code: "invalid_arguments",
      message: "join requires 'table'",
      opIndex: 0,
    });
    await expect(runtime.query(query)).rejects.toBeInstanceOf(QueryError);
  });

  it("query() uses the native worker directly when it's available, never the daemon", async () => {
    nativeWorkerAvailableMock.mockReturnValue(true);
    callNativeWorkerMock.mockResolvedValue({
      result: { columns: ["a"], rows: [[1]] },
      lineage: [],
      plan_hash: "cafef00d",
      ops: 1,
    });

    const runtime = new MojoRuntime({ mode: "local" });
    const query = new Query({ columns: ["a"], rows: [[1]] }).select("a");
    const result = await runtime.query(query);

    expect(result.columns).toEqual(["a"]);
    expect(result.planHash).toBe("cafef00d");
    expect(callNativeWorkerMock).toHaveBeenCalledWith({
      ...query.toRequest(),
      type: "query_execute",
    });
    expect(executeQueryMock).not.toHaveBeenCalled();
  });

  it("query() still throws QueryError on a native-worker engine-side refusal", async () => {
    nativeWorkerAvailableMock.mockReturnValue(true);
    callNativeWorkerMock.mockResolvedValue({
      error_code: "invalid_arguments",
      error_message: "join requires 'table'",
      op_index: 2,
    });

    const runtime = new MojoRuntime({ mode: "local" });
    const query = new Query({ columns: ["a"], rows: [[1]] }).select("a");

    await expect(runtime.query(query)).rejects.toMatchObject({
      code: "invalid_arguments",
      opIndex: 2,
    });
  });
});
