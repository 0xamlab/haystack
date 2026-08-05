import type {
  LibraryExecutionResponse,
  LibraryHealthResponse,
  LibraryModuleDescriptor,
} from "./types.js";
import {
  MojoFunctionNotRegisteredError,
  MojoModuleNotRegisteredError,
  MojoRuntimeConfigurationError,
} from "./mojo_errors.js";
import {
  executeQuery,
  executeRuntimeLibrary,
  getRuntimeLibraryHealth,
  listRuntimeLibraryModules,
} from "./runtime_daemon_client.js";
import { callNativeWorker, nativeWorkerAvailable } from "./native_worker_client.js";
import { Query, QueryError, QueryResult } from "./query.js";

export interface MojoRuntimeConfig {
  mode?: "local";
  tcpAddress?: string;
  timeout?: number;
}

type LibraryCallable = (...args: unknown[]) => Promise<unknown>;

export type LibraryModuleProxy = LibraryModuleProxyTarget & Record<string, LibraryCallable>;
export type LibraryCatalog = LibraryCatalogTarget & Record<string, LibraryModuleProxy>;

function cloneLibraryModuleDescriptor(
  descriptor: LibraryModuleDescriptor,
): LibraryModuleDescriptor {
  return {
    name: descriptor.name,
    engine: descriptor.engine,
    functions: [...descriptor.functions],
  };
}

function normalizeInvocation(args: unknown[]): unknown {
  if (args.length === 0) return undefined;
  if (args.length === 1) return args[0];
  return args;
}

function validateRuntimeConfig(config: MojoRuntimeConfig): void {
  const unsupportedKeys = ["apiKey", "baseUrl", "client"].filter(
    key => key in (config as Record<string, unknown>),
  );
  if (config.mode && config.mode !== "local") {
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "TypeScript MojoRuntime only supports the local Algenta runtime daemon in this rollout.",
      { mode: config.mode },
    );
  }
  if (unsupportedKeys.length > 0) {
    throw new MojoRuntimeConfigurationError(
      "compute_runtime_unavailable",
      "TypeScript MojoRuntime is local/runtime-backed only in this rollout. Remove hosted API options and start the local runtime daemon.",
      { unsupported_keys: unsupportedKeys },
    );
  }
}

function invalidLibraryCatalog(
  message: string,
  details: Record<string, unknown>,
): MojoRuntimeConfigurationError {
  return new MojoRuntimeConfigurationError(
    "compute_runtime_unavailable",
    message,
    details,
  );
}

class LibraryModuleProxyTarget {
  private readonly callables = new Map<string, LibraryCallable>();

  constructor(
    private readonly runtime: MojoRuntime,
    private readonly descriptor: LibraryModuleDescriptor,
  ) {}

  get name(): string {
    return this.descriptor.name;
  }

  get functions(): string[] {
    return [...this.descriptor.functions];
  }

  hasFunction(functionName: string): boolean {
    return this.descriptor.functions.includes(functionName);
  }

  async execute(functionName: string, args?: unknown): Promise<unknown> {
    if (!this.hasFunction(functionName)) {
      throw new MojoFunctionNotRegisteredError(
        "function_not_registered",
        `Module '${this.descriptor.name}' does not expose '${functionName}'.`,
        { module: this.descriptor.name, function: functionName },
      );
    }
    const response = await this.runtime.execute(this.descriptor.name, functionName, args);
    return response.result;
  }

  callable(functionName: string): LibraryCallable {
    const cached = this.callables.get(functionName);
    if (cached) return cached;
    const callable: LibraryCallable = async (...args: unknown[]) =>
      this.execute(functionName, normalizeInvocation(args));
    this.callables.set(functionName, callable);
    return callable;
  }
}

function createLibraryModuleProxy(
  runtime: MojoRuntime,
  descriptor: LibraryModuleDescriptor,
): LibraryModuleProxy {
  const target = new LibraryModuleProxyTarget(runtime, descriptor);
  return new Proxy(target, {
    get(currentTarget, property, receiver) {
      if (typeof property !== "string") {
        return Reflect.get(currentTarget, property, receiver);
      }
      if (property === "then") {
        return undefined;
      }
      if (property in currentTarget) {
        return Reflect.get(currentTarget, property, receiver);
      }
      if (currentTarget.hasFunction(property)) {
        return currentTarget.callable(property);
      }
      throw new MojoFunctionNotRegisteredError(
        "function_not_registered",
        `Module '${currentTarget.name}' does not expose '${property}'.`,
        { module: currentTarget.name, function: property },
      );
    },
  }) as LibraryModuleProxy;
}

class LibraryCatalogTarget {
  private readonly orderedModules: LibraryModuleDescriptor[];
  private readonly descriptorsByName = new Map<string, LibraryModuleDescriptor>();
  private readonly descriptorsByAlias = new Map<string, LibraryModuleDescriptor>();
  private readonly proxiesByName = new Map<string, LibraryModuleProxy>();

  constructor(
    private readonly runtime: MojoRuntime,
    descriptors: LibraryModuleDescriptor[],
  ) {
    this.orderedModules = descriptors
      .map(cloneLibraryModuleDescriptor)
      .sort((left, right) => left.name.localeCompare(right.name));
    const moduleNames = new Set(this.orderedModules.map(descriptor => descriptor.name));
    const aliasSources = new Map<string, string>();
    for (const descriptor of this.orderedModules) {
      this.descriptorsByName.set(descriptor.name, descriptor);
      const alias = descriptor.name.replace(/\./g, "_");
      if (alias !== descriptor.name && moduleNames.has(alias)) {
        continue;
      }
      const existingName = aliasSources.get(alias);
      if (existingName && existingName !== descriptor.name) {
        continue;
      }
      aliasSources.set(alias, descriptor.name);
      this.descriptorsByAlias.set(alias, descriptor);
    }
  }

  names(): string[] {
    return this.orderedModules.map(descriptor => descriptor.name);
  }

  listModules(): LibraryModuleDescriptor[] {
    return this.orderedModules.map(cloneLibraryModuleDescriptor);
  }

  listFunctions(moduleName: string): string[] {
    return [...this.resolveDescriptor(moduleName).functions];
  }

  resolveAttribute(attribute: string): LibraryModuleDescriptor | undefined {
    return this.descriptorsByName.get(attribute) ?? this.descriptorsByAlias.get(attribute);
  }

  module(moduleName: string): LibraryModuleProxy {
    const descriptor = this.resolveDescriptor(moduleName);
    const cached = this.proxiesByName.get(descriptor.name);
    if (cached) return cached;
    const proxy = createLibraryModuleProxy(this.runtime, descriptor);
    this.proxiesByName.set(descriptor.name, proxy);
    return proxy;
  }

  async refresh(): Promise<LibraryCatalog> {
    return this.runtime.refreshLibraries();
  }

  [Symbol.iterator](): Iterator<LibraryModuleDescriptor> {
    return this.listModules()[Symbol.iterator]();
  }

  private resolveDescriptor(moduleName: string): LibraryModuleDescriptor {
    const descriptor = this.descriptorsByName.get(moduleName);
    if (descriptor) return descriptor;
    throw new MojoModuleNotRegisteredError(
      "module_not_registered",
      `Unknown runtime library '${moduleName}'.`,
      { module: moduleName },
    );
  }
}

function createLibraryCatalog(
  runtime: MojoRuntime,
  descriptors: LibraryModuleDescriptor[],
): LibraryCatalog {
  const target = new LibraryCatalogTarget(runtime, descriptors);
  return new Proxy(target, {
    get(currentTarget, property, receiver) {
      if (typeof property !== "string") {
        return Reflect.get(currentTarget, property, receiver);
      }
      if (property === "then") {
        return undefined;
      }
      if (property in currentTarget) {
        return Reflect.get(currentTarget, property, receiver);
      }
      const descriptor = currentTarget.resolveAttribute(property);
      if (descriptor) {
        return currentTarget.module(descriptor.name);
      }
      throw new MojoModuleNotRegisteredError(
        "module_not_registered",
        `Unknown runtime library '${property}'.`,
        { module: property },
      );
    },
  }) as LibraryCatalog;
}

export class MojoRuntime {
  private catalogPromise?: Promise<LibraryCatalog>;
  private readonly config: MojoRuntimeConfig;

  constructor(config: MojoRuntimeConfig = {}) {
    validateRuntimeConfig(config);
    this.config = config;
  }

  async health(): Promise<LibraryHealthResponse> {
    return getRuntimeLibraryHealth(this.config);
  }

  async listModules(): Promise<LibraryModuleDescriptor[]> {
    return listRuntimeLibraryModules(this.config);
  }

  async listFunctions(moduleName: string): Promise<string[]> {
    const catalog = await this.libraries();
    return catalog.listFunctions(moduleName);
  }

  async execute(
    module: string,
    functionName: string,
    args?: unknown,
    requestId?: string,
  ): Promise<LibraryExecutionResponse> {
    return executeRuntimeLibrary(this.config, {
      module,
      function: functionName,
      args,
      request_id: requestId,
    });
  }

  /** Execute a `Query` plan (`mojo/engine/query/plan.mojo`'s "query_execute" op) --
   * joins, filters, aggregates, sorts, window functions -- in one dispatch. Mirrors
   * Python's `Query.run(runtime)`, which calls this same method on its own
   * `MojoRuntime`; a caller normally reaches this via `query.run(runtime)` rather
   * than calling it directly.
   *
   * Two transports, picked per call by `nativeWorkerAvailable()`, both producing the
   * IDENTICAL `QueryResult`/`QueryError` decoding below -- a caller cannot tell which
   * one ran except by latency:
   *   - the bundled native worker directly (`callNativeWorker`), when
   *     `ALGENTA_NATIVE_WORKER`/`ALGENTA_RUNTIME_WORKER`/`ALGENTA_MOJO_BINARY` names a
   *     binary on this machine -- no daemon, no gRPC hop, the same story Python's own
   *     bundled worker already has.
   *   - the gRPC runtime daemon (`executeQuery`) otherwise -- unchanged, and still the
   *     ONLY transport for every other `MojoRuntime` method (`execute`, `health`,
   *     `listModules`): those still need a daemon to reach a function-spec-aware
   *     request/response shape this client does not (yet) build on its own. `query`
   *     is the one method whose wire shape is self-describing enough (the same JSON
   *     `Query.toRequest()` already produces) to bypass that entirely.
   */
  async query(query: Query): Promise<QueryResult> {
    const started = Date.now();
    const requestBody = { ...query.toRequest(), type: "query_execute" };
    const response = nativeWorkerAvailable()
      ? await callNativeWorker(requestBody)
      : (await executeQuery(this.config, { request: requestBody })).response;
    // Latency is measured HERE, client round-trip inclusive, matching Python's
    // `run_query` (`perf_counter() - started`) rather than reusing the daemon's own
    // `latency_ms` (server-side-only, excludes the gRPC hop) -- so both SDKs report
    // the same kind of number for the same kind of call, on either transport.
    const latencyMs = Date.now() - started;
    const errorCode = response.error_code;
    if (typeof errorCode === "string" && errorCode.length > 0) {
      const opIndex = typeof response.op_index === "number" ? response.op_index : null;
      throw new QueryError(
        errorCode,
        String(response.error_message ?? response.error ?? ""),
        opIndex,
      );
    }
    const result = (response.result as Record<string, unknown>) ?? {};
    const lineage = Array.isArray(response.lineage) ? response.lineage : [];
    return new QueryResult({
      columns: (result.columns as string[]) ?? [],
      rows: (result.rows as Array<Array<number | null>>) ?? [],
      lineage: lineage as Array<Record<string, unknown>>,
      planHash: String(response.plan_hash ?? ""),
      ops: Number(response.ops ?? 0),
      latencyMs,
      // Absent from the envelope when zero -- the engine only emits the key when N > 0.
      nonFiniteCells: Number(response.non_finite_cells ?? 0),
    });
  }

  async libraries(): Promise<LibraryCatalog> {
    if (!this.catalogPromise) {
      this.catalogPromise = this.buildCatalog();
    }
    return this.catalogPromise;
  }

  async refreshLibraries(): Promise<LibraryCatalog> {
    this.catalogPromise = this.buildCatalog();
    return this.catalogPromise;
  }

  private async buildCatalog(): Promise<LibraryCatalog> {
    const descriptors = await this.listModules();
    return createLibraryCatalog(this, descriptors);
  }
}

export async function libraries(config: MojoRuntimeConfig = {}): Promise<LibraryCatalog> {
  return new MojoRuntime(config).libraries();
}
