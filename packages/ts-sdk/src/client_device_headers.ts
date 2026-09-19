// SPDX-License-Identifier: Apache-2.0
const DEVICE_ID_HEADER = "X-Algenta-Device-Id";
const PLATFORM_HEADER = "X-Algenta-Platform";
const PLATFORM_VERSION_HEADER = "X-Algenta-Platform-Version";
const HOSTNAME_HASH_HEADER = "X-Algenta-Hostname-Hash";
const SDK_VERSION_HEADER = "X-Algenta-SDK-Version";
const DEVICE_ID_STORAGE_KEY = "algenta_sdk_device_id_v1";
const DEVICE_ID_MIN_LENGTH = 16;
const DEVICE_ID_MAX_LENGTH = 64;

type NodeProcessRef = {
  env?: Record<string, string | undefined>;
  versions?: { node?: string };
  platform?: string;
  version?: string;
  arch?: string;
  getBuiltinModule?: ((id: string) => unknown) | undefined;
};

type NodeFsModule = {
  readFileSync(path: string, encoding: "utf8"): string;
  existsSync(path: string): boolean;
  mkdirSync(path: string, options?: { recursive?: boolean }): void;
  writeFileSync(path: string, data: string, encoding: "utf8"): void;
};

type NodeOsModule = {
  hostname(): string;
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

function nodeInstallIdFile(builtins: NodeBuiltins): string {
  return builtins.path.join(nodeRuntimeDir(builtins), "install_id");
}

function createInstallId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return [
    Date.now().toString(36),
    Math.random().toString(36).slice(2),
    Math.random().toString(36).slice(2),
  ].join("-");
}

function nodeInstallId(builtins: NodeBuiltins): string | null {
  const runtimeDir = nodeRuntimeDir(builtins);
  const installIdFile = nodeInstallIdFile(builtins);
  try {
    if (builtins.fs.existsSync(installIdFile)) {
      const existing = builtins.fs.readFileSync(installIdFile, "utf8").trim();
      if (existing) {
        return existing;
      }
    }
    builtins.fs.mkdirSync(runtimeDir, { recursive: true });
    const generated = createInstallId();
    builtins.fs.writeFileSync(installIdFile, generated, "utf8");
    return generated;
  } catch {
    return null;
  }
}

function linuxMachineId(builtins: NodeBuiltins): string | null {
  for (const filePath of ["/etc/machine-id", "/var/lib/dbus/machine-id"]) {
    try {
      const value = builtins.fs.readFileSync(filePath, "utf8").trim();
      if (value) {
        return value;
      }
    } catch {
      // Continue to the next candidate machine-id path.
    }
  }
  return null;
}

function nodeRuntimeInfo(): {
  platform: string;
  platformVersion: string;
  arch: string;
  hostname: string;
  deviceSeed: string;
} | null {
  const processRef = nodeProcessRef();
  if (!processRef) {
    return null;
  }
  const platform = processRef.platform?.trim() ?? "";
  const builtins = nodeBuiltins();
  let hostname = envValue("HOSTNAME") ?? envValue("COMPUTERNAME") ?? "";
  if (builtins) {
    try {
      const resolvedHostname = builtins.os.hostname().trim();
      if (resolvedHostname) {
        hostname = resolvedHostname;
      }
    } catch {
      // Fall back to hostname environment variables.
    }
  }
  const machineId = platform === "linux" && builtins ? linuxMachineId(builtins) : null;
  const hostnameSeed = hostname || null;
  let installIdSeed: string | null = null;
  if (machineId === null && hostnameSeed === null && builtins) {
    installIdSeed = nodeInstallId(builtins);
  }
  const machineSeed = machineId ?? hostnameSeed ?? installIdSeed;
  if (!machineSeed) {
    return null;
  }
  return {
    platform,
    platformVersion: processRef.version?.trim() ?? "",
    arch: processRef.arch?.trim() ?? "",
    hostname,
    deviceSeed: machineSeed,
  };
}

function browserRuntimeInfo(): { platform: string } | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  return {
    platform: typeof navigator.platform === "string" ? navigator.platform.trim() : "",
  };
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

function stableDeviceId(seed: string): string {
  return `${fnv1a64(`algenta-device:${seed}`)}${fnv1a64(`algenta-device:v2:${seed}`)}`.slice(
    0,
    32,
  );
}

function hostnameHash(seed: string): string {
  return fnv1a64(`algenta-host:${seed}`);
}

function browserStoredDeviceId(): string | null {
  if (typeof localStorage === "undefined") {
    return null;
  }
  try {
    const existing = localStorage.getItem(DEVICE_ID_STORAGE_KEY);
    if (existing) {
      return existing;
    }
    const browserSeed = [
      typeof navigator !== "undefined" ? navigator.userAgent : "",
      typeof navigator !== "undefined" ? navigator.language : "",
      Date.now().toString(10),
      Math.random().toString(36),
    ].join("|");
    const generated = stableDeviceId(browserSeed);
    localStorage.setItem(DEVICE_ID_STORAGE_KEY, generated);
    return generated;
  } catch {
    return null;
  }
}

function validateDeviceId(deviceId: string, source: string): string {
  const normalized = deviceId.trim();
  if (normalized.length < DEVICE_ID_MIN_LENGTH || normalized.length > DEVICE_ID_MAX_LENGTH) {
    throw new Error(
      `${source} must be between ${DEVICE_ID_MIN_LENGTH} and ${DEVICE_ID_MAX_LENGTH} characters.`,
    );
  }
  return normalized;
}

export function resolveClientDeviceHeaders(
  sdkVersion: string,
  providedHeaders: Record<string, string> = {},
): Record<string, string> {
  const resolved: Record<string, string> = {
    [SDK_VERSION_HEADER]: sdkVersion,
  };

  const providedDeviceId = providedHeaders[DEVICE_ID_HEADER];
  let resolvedDeviceId: string | null = null;
  if (typeof providedDeviceId === "string" && providedDeviceId.trim().length > 0) {
    resolvedDeviceId = validateDeviceId(providedDeviceId, DEVICE_ID_HEADER);
  }

  const explicitDeviceId = envValue("ALGENTA_DEVICE_ID") ?? envValue("DE_DEVICE_ID") ?? null;
  if (!resolvedDeviceId && explicitDeviceId) {
    resolvedDeviceId = validateDeviceId(explicitDeviceId, "ALGENTA_DEVICE_ID");
  }

  const nodeInfo = nodeRuntimeInfo();
  let browserDeviceId: string | null = null;
  if (!resolvedDeviceId && nodeInfo) {
    const seed = [nodeInfo.deviceSeed, nodeInfo.platform, nodeInfo.arch].filter(Boolean).join("|");
    resolvedDeviceId = stableDeviceId(seed);
  }

  if (!resolvedDeviceId) {
    browserDeviceId = browserStoredDeviceId();
    if (browserDeviceId) {
      resolvedDeviceId = browserDeviceId;
    }
  }

  if (!resolvedDeviceId) {
    return resolved;
  }

  resolved[DEVICE_ID_HEADER] = resolvedDeviceId;
  if (nodeInfo) {
    if (nodeInfo.platform) {
      resolved[PLATFORM_HEADER] = nodeInfo.platform.slice(0, 50);
    }
    if (nodeInfo.platformVersion) {
      resolved[PLATFORM_VERSION_HEADER] = nodeInfo.platformVersion.slice(0, 50);
    }
  } else {
    const browserInfo = browserRuntimeInfo();
    if (browserInfo?.platform) {
      resolved[PLATFORM_HEADER] = browserInfo.platform.slice(0, 50);
    }
  }

  const fingerprintSeed =
    nodeInfo?.hostname || nodeInfo?.deviceSeed || browserDeviceId || resolvedDeviceId;
  if (fingerprintSeed) {
    resolved[HOSTNAME_HASH_HEADER] = hostnameHash(fingerprintSeed);
  }
  return resolved;
}

export {
  DEVICE_ID_HEADER,
  HOSTNAME_HASH_HEADER,
  PLATFORM_HEADER,
  PLATFORM_VERSION_HEADER,
  SDK_VERSION_HEADER,
};
