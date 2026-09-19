// SPDX-License-Identifier: Apache-2.0
import { resolve as resolvePath } from "node:path";

import type {
  LibraryExecutionRequest,
  LibraryExecutionResponse,
  LibraryHealthResponse,
  LibraryModuleDescriptor,
} from "./types.js";
import {
  MojoExecutionError,
  MojoFunctionNotRegisteredError,
  MojoModuleNotRegisteredError,
  MojoRuntimeConfigurationError,
  type MojoRuntimeError,
} from "./mojo_errors.js";

const DEFAULT_DAEMON_TCP = process.env.ALGENTA_DAEMON_TCP ?? "127.0.0.1:50099";
const DEFAULT_TIMEOUT_MS = 30_000;
const RUNTIME_PROTO_PATH = resolvePath(__dirname, "../proto/runtime.proto");
const SIMULATION_MODULES = new Set([
  "bootstrap",
  "decision_tree",
  "importance_sampling",
  "lhs",
  "mcmc",
  "monte_carlo",
  "qmc_sobol",
  "scenario",
  "sensitivity",
  "time_series",
]);

type GrpcJs = typeof import("@grpc/grpc-js");
type ProtoLoader = typeof import("@grpc/proto-loader");

interface RuntimeDaemonConfig {
  tcpAddress?: string;
  timeout?: number;
}

interface RuntimeGrpcClient {
  Health(
    request: Record<string, never>,
    options: { deadline: number },
    callback: (error: unknown, response: GrpcHealthResponse) => void,
  ): void;
  ListModules(
    request: Record<string, never>,
    options: { deadline: number },
    callback: (error: unknown, response: GrpcListModulesResponse) => void,
  ): void;
  ExecuteModule(
    request: GrpcExecuteRequest,
    options: { deadline: number },
    callback: (error: unknown, response: GrpcExecuteResponse) => void,
  ): void;
  ExecuteQuery(
    request: GrpcQueryExecuteRequest,
    options: { deadline: number },
    callback: (error: unknown, response: GrpcQueryExecuteResponse) => void,
  ): void;
  close(): void;
}

interface LoadedRuntimeGrpc {
  grpc: GrpcJs;
  Client: new (
    address: string,
    credentials: ReturnType<GrpcJs["credentials"]["createInsecure"]>,
    options?: Record<string, unknown>,
  ) => RuntimeGrpcClient;
}

/**
 * gRPC defaults to a 4 MiB receive limit, which is far below what the local
 * transport supports (the Python worker allows 64 MiB) and is applied silently —
 * a larger result just fails. Match the worker's ceiling so both transports agree.
 */
const MAX_MESSAGE_BYTES = 64 * 1024 * 1024;

interface GrpcHealthResponse {
  ok: boolean;
  version: string;
  uptime_seconds: number;
  engine: string;
}

interface GrpcModuleInfo {
  name: string;
  engine: string;
  functions: string[];
}

interface GrpcListModulesResponse {
  modules?: GrpcModuleInfo[];
}

interface GrpcExecuteRequest {
  module: string;
  function: string;
  args_json: string;
  request_id: string;
}

interface GrpcExecuteResponse {
  result_json?: string;
  latency_ms: number;
  engine_used: string;
  success: boolean;
  error?: string;
  request_id?: string;
}

interface GrpcQueryExecuteRequest {
  request_json: string;
  request_id: string;
}

interface GrpcQueryExecuteResponse {
  response_json?: string;
  latency_ms: number;
  engine_used: string;
  success: boolean;
  error?: string;
  request_id?: string;
}

let loadedRuntimeGrpcPromise: Promise<LoadedRuntimeGrpc> | undefined;

function resolveDaemonTarget(config: RuntimeDaemonConfig): string {
  return config.tcpAddress ?? DEFAULT_DAEMON_TCP;
}

function resolveTimeoutMs(config: RuntimeDaemonConfig): number {
  const timeout = config.timeout ?? DEFAULT_TIMEOUT_MS;
  if (!Number.isFinite(timeout) || timeout <= 0) {
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "Mojo runtime timeout must be a positive number of milliseconds.",
      { timeout },
    );
  }
  return timeout;
}

function parseJsonResult(resultJson: string | undefined): unknown {
  if (!resultJson) {
    return null;
  }
  try {
    return JSON.parse(resultJson);
  } catch (error) {
    throw new MojoExecutionError(
      "compute_runtime_unavailable",
      "The local runtime returned malformed JSON for a runtime call.",
      {
        result_json: resultJson,
        error: error instanceof Error ? error.message : String(error),
      },
    );
  }
}

function runtimeErrorFromResponse(
  response: GrpcExecuteResponse,
  request: LibraryExecutionRequest,
): MojoRuntimeError {
  const rawMessage = response.error?.trim() || "Runtime-backed Mojo execution failed.";
  const prefixed = /^([a-z0-9_]+):\s*(.+)$/i.exec(rawMessage);
  const code = prefixed?.[1] ?? (response.engine_used === "unavailable"
    ? "compute_runtime_unavailable"
    : "compute_runtime_unavailable");
  const message = prefixed?.[2] ?? rawMessage;
  const details = {
    module: request.module,
    function: request.function,
    engine_used: response.engine_used,
    request_id: response.request_id ?? request.request_id ?? null,
  };
  if (code === "module_not_registered") {
    return new MojoModuleNotRegisteredError(code, message, details);
  }
  if (code === "function_not_registered") {
    return new MojoFunctionNotRegisteredError(code, message, details);
  }
  if (code === "compute_runtime_unavailable") {
    return new MojoRuntimeConfigurationError(code, message, details);
  }
  return new MojoExecutionError(code, message, details);
}

function invalidLibraryInventory(
  message: string,
  details: Record<string, unknown>,
): MojoRuntimeConfigurationError {
  return new MojoRuntimeConfigurationError(
    "compute_runtime_unavailable",
    message,
    details,
  );
}

function normalizeModuleName(rawName: unknown): string {
  if (typeof rawName !== "string" || rawName.trim().length === 0) {
    throw invalidLibraryInventory(
      "The local runtime returned a malformed Mojo library descriptor.",
      { module: rawName },
    );
  }
  return rawName.trim();
}

function normalizeEngine(moduleName: string, rawEngine: unknown): string {
  if (typeof rawEngine !== "string" || rawEngine.trim().length === 0) {
    throw invalidLibraryInventory(
      `The local runtime returned a malformed engine for '${moduleName}'.`,
      { module: moduleName, engine: rawEngine },
    );
  }
  return rawEngine.trim();
}

function normalizeFunctions(moduleName: string, rawFunctions: unknown): string[] {
  if (!Array.isArray(rawFunctions)) {
    throw invalidLibraryInventory(
      `The local runtime returned malformed functions for '${moduleName}'.`,
      { module: moduleName, functions: rawFunctions },
    );
  }
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const rawFunction of rawFunctions) {
    if (typeof rawFunction !== "string" || rawFunction.trim().length === 0) {
      throw invalidLibraryInventory(
        `The local runtime returned a malformed function for '${moduleName}'.`,
        { module: moduleName, function: rawFunction },
      );
    }
    const functionName = rawFunction.trim();
    if (seen.has(functionName)) {
      throw invalidLibraryInventory(
        `The local runtime returned duplicate functions for '${moduleName}'.`,
        { module: moduleName, function: functionName },
      );
    }
    seen.add(functionName);
    normalized.push(functionName);
  }
  if (normalized.length === 0) {
    throw invalidLibraryInventory(
      `The local runtime exposed '${moduleName}' without executable functions.`,
      { module: moduleName },
    );
  }
  return normalized.sort((left, right) => left.localeCompare(right));
}

function normalizeModuleDescriptor(rawModule: unknown): LibraryModuleDescriptor {
  if (typeof rawModule !== "object" || rawModule === null) {
    throw invalidLibraryInventory(
      "The local runtime returned a malformed Mojo library descriptor.",
      { descriptor: rawModule },
    );
  }
  const module = rawModule as Partial<GrpcModuleInfo>;
  const moduleName = normalizeModuleName(module.name);
  return {
    name: moduleName,
    engine: normalizeEngine(moduleName, module.engine),
    functions: normalizeFunctions(moduleName, module.functions),
  };
}

function filterLibraryModules(modules: unknown[]): LibraryModuleDescriptor[] {
  const descriptors: LibraryModuleDescriptor[] = [];
  const seenModules = new Set<string>();
  for (const rawModule of modules) {
    const descriptor = normalizeModuleDescriptor(rawModule);
    const moduleName = descriptor.name;
    if (SIMULATION_MODULES.has(moduleName)) {
      continue;
    }
    if (seenModules.has(moduleName)) {
      throw invalidLibraryInventory(
        "The local runtime returned duplicate Mojo libraries.",
        { module: moduleName },
      );
    }
    seenModules.add(moduleName);
    descriptors.push(descriptor);
  }
  return descriptors.sort((left, right) => left.name.localeCompare(right.name));
}

function normalizeListModulesResponse(response: unknown): LibraryModuleDescriptor[] {
  if (typeof response !== "object" || response === null) {
    throw invalidLibraryInventory(
      "The local runtime returned a malformed Mojo library inventory.",
      { response },
    );
  }
  const modules = (response as GrpcListModulesResponse).modules;
  if (modules == null) {
    return [];
  }
  if (!Array.isArray(modules)) {
    throw invalidLibraryInventory(
      "The local runtime returned a malformed Mojo library inventory.",
      { modules },
    );
  }
  return filterLibraryModules(modules);
}

async function loadRuntimeGrpc(): Promise<LoadedRuntimeGrpc> {
  if (!loadedRuntimeGrpcPromise) {
    loadedRuntimeGrpcPromise = (async () => {
      let grpc: GrpcJs;
      let protoLoader: ProtoLoader;
      try {
        [grpc, protoLoader] = await Promise.all([
          import("@grpc/grpc-js"),
          import("@grpc/proto-loader"),
        ]);
      } catch (error) {
        throw new MojoRuntimeConfigurationError(
          "compute_runtime_unavailable",
          "The TypeScript gRPC runtime client is unavailable. Install the local runtime transport dependencies before using Mojo libraries.",
          { error: error instanceof Error ? error.message : String(error) },
        );
      }
      const packageDefinition = await protoLoader.load(RUNTIME_PROTO_PATH, {
        keepCase: true,
        defaults: true,
        enums: String,
        oneofs: true,
      });
      const loaded = grpc.loadPackageDefinition(packageDefinition) as {
        algenta?: { runtime?: { v1?: { CodnaRuntime?: LoadedRuntimeGrpc["Client"] } } };
      };
      const Client = loaded.algenta?.runtime?.v1?.CodnaRuntime;
      if (!Client) {
        throw new MojoRuntimeConfigurationError(
          "compute_runtime_unavailable",
          "The Algenta runtime gRPC contract is unavailable.",
          { proto_path: RUNTIME_PROTO_PATH },
        );
      }
      return { grpc, Client };
    })();
  }
  return loadedRuntimeGrpcPromise;
}

async function withRuntimeClient<T>(
  config: RuntimeDaemonConfig,
  callback: (client: RuntimeGrpcClient, deadline: number) => Promise<T>,
): Promise<T> {
  const { grpc, Client } = await loadRuntimeGrpc();
  const client = new Client(resolveDaemonTarget(config), grpc.credentials.createInsecure(), {
    "grpc.max_receive_message_length": MAX_MESSAGE_BYTES,
    "grpc.max_send_message_length": MAX_MESSAGE_BYTES,
  });
  try {
    return await callback(client, Date.now() + resolveTimeoutMs(config));
  } catch (error) {
    if (error instanceof MojoExecutionError || error instanceof MojoRuntimeConfigurationError) {
      throw error;
    }
    if (error instanceof MojoModuleNotRegisteredError || error instanceof MojoFunctionNotRegisteredError) {
      throw error;
    }
    const message =
      typeof error === "object" &&
      error !== null &&
      "details" in error &&
      typeof (error as { details?: unknown }).details === "string"
        ? (error as { details: string }).details
        : error instanceof Error
          ? error.message
          : String(error);
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "The local Algenta runtime daemon is unavailable. Start it before accessing runtime-backed Mojo libraries.",
      {
        daemon_target: resolveDaemonTarget(config),
        error: message,
      },
    );
  } finally {
    client.close();
  }
}

function callUnary<RequestShape, ResponseShape>(
  client: RuntimeGrpcClient,
  methodName: keyof Pick<
    RuntimeGrpcClient,
    "Health" | "ListModules" | "ExecuteModule" | "ExecuteQuery"
  >,
  request: RequestShape,
  deadline: number,
): Promise<ResponseShape> {
  return new Promise((resolve, reject) => {
    const callback = (error: unknown, response: ResponseShape) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(response);
    };
    if (methodName === "Health") {
      client.Health(request as Record<string, never>, { deadline }, callback as never);
      return;
    }
    if (methodName === "ListModules") {
      client.ListModules(request as Record<string, never>, { deadline }, callback as never);
      return;
    }
    if (methodName === "ExecuteQuery") {
      client.ExecuteQuery(request as GrpcQueryExecuteRequest, { deadline }, callback as never);
      return;
    }
    client.ExecuteModule(request as GrpcExecuteRequest, { deadline }, callback as never);
  });
}

export async function listRuntimeLibraryModules(
  config: RuntimeDaemonConfig = {},
): Promise<LibraryModuleDescriptor[]> {
  return withRuntimeClient(config, async (client, deadline) => {
    const response = await callUnary<Record<string, never>, unknown>(
      client,
      "ListModules",
      {},
      deadline,
    );
    return normalizeListModulesResponse(response);
  });
}

export async function getRuntimeLibraryHealth(
  config: RuntimeDaemonConfig = {},
): Promise<LibraryHealthResponse> {
  try {
    const [health, modules] = await Promise.all([
      withRuntimeClient(config, async (client, deadline) =>
        callUnary<Record<string, never>, GrpcHealthResponse>(client, "Health", {}, deadline)),
      listRuntimeLibraryModules(config),
    ]);
    const runtimeAvailable = health.ok && health.engine === "mojo";
    return {
      status: runtimeAvailable ? "ok" : "unavailable",
      engine: runtimeAvailable ? "mojo" : "unavailable",
      module_count: modules.length,
      runtime_available: runtimeAvailable,
    };
  } catch {
    return {
      status: "unavailable",
      engine: "unavailable",
      module_count: 0,
      runtime_available: false,
    };
  }
}

export async function executeRuntimeLibrary(
  config: RuntimeDaemonConfig = {},
  request: LibraryExecutionRequest,
): Promise<LibraryExecutionResponse> {
  return withRuntimeClient(config, async (client, deadline) => {
    const response = await callUnary<GrpcExecuteRequest, GrpcExecuteResponse>(
      client,
      "ExecuteModule",
      {
        module: request.module,
        function: request.function,
        args_json: JSON.stringify(request.args ?? null),
        request_id: request.request_id ?? "",
      },
      deadline,
    );
    if (!response.success) {
      throw runtimeErrorFromResponse(response, request);
    }
    return {
      module: request.module,
      function: request.function,
      result: parseJsonResult(response.result_json),
      latency_ms: response.latency_ms,
      engine_used: response.engine_used,
      request_id: response.request_id || request.request_id || null,
    };
  });
}

export interface QueryExecutionRequest {
  /** The `{"ops":[...], "columns":[...], ...}` body a `Query` builder produces.
   * `"type"` is stamped server-side and is never read from this object. */
  request: Record<string, unknown>;
  request_id?: string;
}

export interface QueryExecutionResponse {
  /** The engine's raw response: either `{"result":{...},"lineage":[...],
   * "plan_hash":...,"ops":N}` or `{"error_code":...,"error_message":...}` on a
   * refused plan -- that is an ENGINE-side answer. A transport/availability
   * failure (the worker unreachable, request_json malformed) throws instead,
   * exactly as `executeRuntimeLibrary` does for a library call. */
  response: Record<string, unknown>;
  latency_ms: number;
  engine_used: string;
  request_id: string | null;
}

export async function executeQuery(
  config: RuntimeDaemonConfig = {},
  request: QueryExecutionRequest,
): Promise<QueryExecutionResponse> {
  return withRuntimeClient(config, async (client, deadline) => {
    const response = await callUnary<GrpcQueryExecuteRequest, GrpcQueryExecuteResponse>(
      client,
      "ExecuteQuery",
      {
        request_json: JSON.stringify(request.request ?? {}),
        request_id: request.request_id ?? "",
      },
      deadline,
    );
    if (!response.success) {
      const rawMessage = response.error?.trim() || "Local runtime query execution failed.";
      const prefixed = /^([a-z0-9_]+):\s*(.+)$/i.exec(rawMessage);
      throw new MojoRuntimeConfigurationError(
        prefixed?.[1] ?? "compute_runtime_unavailable",
        prefixed?.[2] ?? rawMessage,
        {
          engine_used: response.engine_used,
          request_id: response.request_id ?? request.request_id ?? null,
        },
      );
    }
    return {
      response: (parseJsonResult(response.response_json) ?? {}) as Record<string, unknown>,
      latency_ms: response.latency_ms,
      engine_used: response.engine_used,
      request_id: response.request_id || request.request_id || null,
    };
  });
}
