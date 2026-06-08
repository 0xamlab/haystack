const DEVICE_BINDING_TOKEN_HEADER = "X-Algenta-Device-Binding-Token";
const DEVICE_BINDING_STORE_KEY = "algenta_sdk_device_binding_tokens_v1";
const processBindingTokens = new Map<string, string>();

type NodeProcessRef = {
  env?: Record<string, string | undefined>;
  versions?: { node?: string };
  getBuiltinModule?: ((id: string) => unknown) | undefined;
};

type NodeFsModule = {
  readFileSync(path: string, encoding: "utf8"): string;
  existsSync(path: string): boolean;
  mkdirSync(path: string, options?: { recursive?: boolean }): void;
  writeFileSync(path: string, data: string, encoding: "utf8"): void;
  renameSync(oldPath: string, newPath: string): void;
};

type NodeOsModule = {
  homedir(): string;
};

type NodePathModule = {
  join(...parts: string[]): string;
};

type NodeBuiltins = {
  fs: NodeFsModule;
  os: NodeOsModule;
  path: NodePathModule;
};

function envValue(name: string): string | undefined {
  if (
    typeof globalThis === "undefined" ||
    !("process" in globalThis) ||
    !(globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
  ) {
    return undefined;
  }
  const value = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[
    name
  ];
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : undefined;
}

function nodeProcessRef(): NodeProcessRef | null {
  if (
    typeof globalThis === "undefined" ||
    !("process" in globalThis) ||
    !(globalThis as { process?: NodeProcessRef }).process?.versions?.node
  ) {
    return null;
  }
  return (globalThis as { process?: NodeProcessRef }).process ?? null;
}

function nodeBuiltin<T>(specifier: string): T | null {
  const processRef = nodeProcessRef();
  const getter = processRef?.getBuiltinModule;
  if (typeof getter !== "function") {
    return null;
  }
  const candidates = specifier.startsWith("node:")
    ? [specifier, specifier.slice("node:".length)]
    : [specifier, `node:${specifier}`];
  for (const candidate of candidates) {
    try {
      const builtin = getter.call(processRef, candidate);
      if (builtin !== undefined && builtin !== null) {
        return builtin as T;
      }
    } catch {
      // Continue to the next built-in specifier candidate.
    }
  }
  return null;
}

function nodeBuiltins(): NodeBuiltins | null {
  const fs = nodeBuiltin<NodeFsModule>("node:fs");
  const os = nodeBuiltin<NodeOsModule>("node:os");
  const path = nodeBuiltin<NodePathModule>("node:path");
  if (!fs || !os || !path) {
    return null;
  }
  return { fs, os, path };
}

function nodeRuntimeDir(builtins: NodeBuiltins): string {
  const configured = envValue("ALGENTA_RUNTIME_DIR");
  if (configured) {
    return configured;
  }
  return builtins.path.join(
    envValue("HOME") ?? envValue("USERPROFILE") ?? builtins.os.homedir(),
    ".algenta",
    "runtime",
  );
}

function nodeBindingStorePath(builtins: NodeBuiltins): string {
  return builtins.path.join(nodeRuntimeDir(builtins), "hosted_device_binding_tokens.json");
}

function fnv1a64(input: string): string {
  let hash = 0xcbf29ce484222325n;
  const prime = 0x100000001b3n;
  const mask = 0xffffffffffffffffn;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= BigInt(input.charCodeAt(index));
    hash = (hash * prime) & mask;
  }
  return hash.toString(16).padStart(16, "0");
}

function bindingStoreKey(baseUrl: string, apiKey: string, deviceId: string): string {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  return `${fnv1a64(`${normalizedBaseUrl}|${apiKey}|${deviceId}`)}${fnv1a64(
    `algenta-binding:${normalizedBaseUrl}|${apiKey}|${deviceId}`,
  )}`;
}

function loadBrowserBindingToken(baseUrl: string, apiKey: string, deviceId: string): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  try {
    const raw = localStorage.getItem(DEVICE_BINDING_STORE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Record<string, string>;
    const token = parsed[bindingStoreKey(baseUrl, apiKey, deviceId)];
    return typeof token === "string" && token.trim().length > 0 ? token : null;
  } catch {
    return null;
  }
}

function persistBrowserBindingToken(
  baseUrl: string,
  apiKey: string,
  deviceId: string,
  bindingToken: string,
): void {
  if (typeof localStorage === "undefined") {
    return;
  }
  try {
    const raw = localStorage.getItem(DEVICE_BINDING_STORE_KEY);
    const parsed =
      raw && raw.trim().length > 0 ? (JSON.parse(raw) as Record<string, string>) : {};
    parsed[bindingStoreKey(baseUrl, apiKey, deviceId)] = bindingToken;
    localStorage.setItem(DEVICE_BINDING_STORE_KEY, JSON.stringify(parsed));
  } catch {
    // Fail closed by skipping persistence; the current request still succeeded.
  }
}

function loadNodeBindingToken(baseUrl: string, apiKey: string, deviceId: string): string | null {
  const builtins = nodeBuiltins();
  if (!builtins) {
    return null;
  }
  const path = nodeBindingStorePath(builtins);
  try {
    if (!builtins.fs.existsSync(path)) {
      return null;
    }
    const raw = builtins.fs.readFileSync(path, "utf8");
    const parsed = JSON.parse(raw) as Record<string, string>;
    const token = parsed[bindingStoreKey(baseUrl, apiKey, deviceId)];
    return typeof token === "string" && token.trim().length > 0 ? token : null;
  } catch {
    return null;
  }
}

function persistNodeBindingToken(
  baseUrl: string,
  apiKey: string,
  deviceId: string,
  bindingToken: string,
): void {
  const builtins = nodeBuiltins();
  if (!builtins) {
    return;
  }
  const storePath = nodeBindingStorePath(builtins);
  const runtimeDir = nodeRuntimeDir(builtins);
  try {
    let parsed: Record<string, string> = {};
    if (builtins.fs.existsSync(storePath)) {
      const raw = builtins.fs.readFileSync(storePath, "utf8");
      parsed = JSON.parse(raw) as Record<string, string>;
    }
    parsed[bindingStoreKey(baseUrl, apiKey, deviceId)] = bindingToken;
    builtins.fs.mkdirSync(runtimeDir, { recursive: true });
    const tempPath = `${storePath}.tmp`;
    builtins.fs.writeFileSync(tempPath, JSON.stringify(parsed), "utf8");
    builtins.fs.renameSync(tempPath, storePath);
  } catch {
    // Fail closed by skipping persistence; the current request still succeeded.
  }
}

export function loadHostedDeviceBindingToken(
  baseUrl: string,
  apiKey: string,
  deviceId: string,
): string | null {
  const key = bindingStoreKey(baseUrl, apiKey, deviceId);
  const cached = processBindingTokens.get(key);
  if (cached && cached.trim().length > 0) {
    return cached;
  }
  const stored =
    loadNodeBindingToken(baseUrl, apiKey, deviceId) ?? loadBrowserBindingToken(baseUrl, apiKey, deviceId);
  if (stored) {
    processBindingTokens.set(key, stored);
  }
  return stored;
}

export function persistHostedDeviceBindingToken(
  baseUrl: string,
  apiKey: string,
  deviceId: string,
  bindingToken: string,
): void {
  const normalized = bindingToken.trim();
  if (!normalized) {
    return;
  }
  processBindingTokens.set(bindingStoreKey(baseUrl, apiKey, deviceId), normalized);
  persistNodeBindingToken(baseUrl, apiKey, deviceId, normalized);
  persistBrowserBindingToken(baseUrl, apiKey, deviceId, normalized);
}

export function clearHostedDeviceBindingTokenCacheForTests(): void {
  processBindingTokens.clear();
}

export { DEVICE_BINDING_TOKEN_HEADER };
