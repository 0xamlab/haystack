// SPDX-License-Identifier: Apache-2.0
// The hosted device-binding token store (Node file store and browser
// localStorage) and the device-identity headers, in the environments
// client_device_headers.test.ts does not reach: caller-provided ids, the
// browser fallback, missing built-ins, and the install-id corner cases.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEVICE_BINDING_TOKEN_HEADER,
  clearHostedDeviceBindingTokenCacheForTests,
  loadHostedDeviceBindingToken,
  persistHostedDeviceBindingToken,
} from "./client_device_binding.js";
import {
  DEVICE_ID_HEADER,
  HOSTNAME_HASH_HEADER,
  PLATFORM_HEADER,
  PLATFORM_VERSION_HEADER,
  SDK_VERSION_HEADER,
  resolveClientDeviceHeaders,
} from "./client_device_headers.js";

const ORIGINAL_ENV = { ...process.env };
const ENV_KEYS = ["ALGENTA_RUNTIME_DIR", "ALGENTA_DEVICE_ID", "DE_DEVICE_ID", "HOSTNAME", "COMPUTERNAME"];
const STORE_FILE = "hosted_device_binding_tokens.json";
const BINDING_STORAGE_KEY = "algenta_sdk_device_binding_tokens_v1";
const DEVICE_ID_STORAGE_KEY = "algenta_sdk_device_id_v1";
const BASE_URL = "https://example.test";
const API_KEY = "de_test_binding";
const DEVICE_ID = "ts-device-binding-00001";
const TOKEN = "binding-token-000000000000000001";
const SDK_VERSION = "algenta-ts/test";
const HEX_32 = /^[0-9a-f]{32}$/;
const HEX_16 = /^[0-9a-f]{16}$/;

let runtimeDir: string;

function restoreEnv(): void {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
}

function storePath(): string {
  return path.join(runtimeDir, STORE_FILE);
}

function readStore(): Record<string, unknown> {
  return JSON.parse(fs.readFileSync(storePath(), "utf8")) as Record<string, unknown>;
}

function load(deviceId = DEVICE_ID, baseUrl = BASE_URL): string | null {
  return loadHostedDeviceBindingToken(baseUrl, API_KEY, deviceId);
}

function persist(token = TOKEN, deviceId = DEVICE_ID, baseUrl = BASE_URL): void {
  persistHostedDeviceBindingToken(baseUrl, API_KEY, deviceId, token);
}

function fakeLocalStorage(
  seed: Record<string, string> = {},
  failures: { get?: boolean; set?: boolean } = {},
) {
  const entries = new Map(Object.entries(seed));
  return {
    entries,
    getItem: vi.fn((key: string): string | null => {
      if (failures.get) throw new Error("storage denied");
      return entries.get(key) ?? null;
    }),
    setItem: vi.fn((key: string, value: string): void => {
      if (failures.set) throw new Error("quota exceeded");
      entries.set(key, value);
    }),
  };
}

type BuiltinStubs = { fs?: unknown; os?: unknown; path?: unknown };

function stubNodeBuiltins(stubs: BuiltinStubs): void {
  vi.spyOn(process, "getBuiltinModule").mockImplementation(((name: string): unknown => {
    if (name === "node:fs" || name === "fs") return stubs.fs;
    if (name === "node:os" || name === "os") return stubs.os;
    if (name === "node:path" || name === "path") return stubs.path;
    return undefined;
  }) as typeof process.getBuiltinModule);
}

/** Real fs for everything except the Linux machine-id files, which `machineId` answers. */
function realFsStub(machineId?: (filePath: string) => string) {
  return {
    readFileSync: vi.fn((filePath: string, encoding: "utf8"): string => {
      if (filePath === "/etc/machine-id" || filePath === "/var/lib/dbus/machine-id") {
        if (machineId) return machineId(filePath);
        throw new Error("missing machine id");
      }
      return fs.readFileSync(filePath, encoding);
    }),
    existsSync: (filePath: string) => fs.existsSync(filePath),
    mkdirSync: (filePath: string, options?: { recursive?: boolean }) => fs.mkdirSync(filePath, options),
    writeFileSync: vi.fn((filePath: string, data: string, encoding: "utf8") =>
      fs.writeFileSync(filePath, data, encoding),
    ),
  };
}

const REAL_PATH = { join: (...parts: string[]) => path.join(...parts) };

// Without ALGENTA_RUNTIME_DIR the runtime directory is derived from, in order,
// HOME, USERPROFILE and os.homedir(). Each configurer leaves exactly one source
// pointing at the scratch directory (a blank HOME counts as unset).
const RUNTIME_DIR_FALLBACKS: Array<[string, (dir: string) => void]> = [
  [
    "HOME",
    dir => {
      process.env.HOME = dir;
    },
  ],
  [
    "USERPROFILE",
    dir => {
      process.env.HOME = "";
      process.env.USERPROFILE = dir;
    },
  ],
  [
    "os.homedir()",
    () => {
      process.env.HOME = "";
      delete process.env.USERPROFILE;
    },
  ],
];

function withProcessProperty<T>(
  name: "platform" | "version" | "arch",
  value: unknown,
  run: () => T,
): T {
  const original = Object.getOwnPropertyDescriptor(process, name);
  Object.defineProperty(process, name, { value, configurable: true });
  try {
    return run();
  } finally {
    if (original) Object.defineProperty(process, name, original);
  }
}

function withoutBuiltinModuleLoader<T>(run: () => T): T {
  const original = Object.getOwnPropertyDescriptor(process, "getBuiltinModule");
  Object.defineProperty(process, "getBuiltinModule", {
    value: undefined,
    configurable: true,
    writable: true,
  });
  try {
    return run();
  } finally {
    if (original) Object.defineProperty(process, "getBuiltinModule", original);
  }
}

beforeEach(() => {
  for (const key of ENV_KEYS) {
    delete process.env[key];
  }
  runtimeDir = fs.mkdtempSync(path.join(os.tmpdir(), "algenta-ts-binding-edges-"));
  process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
  clearHostedDeviceBindingTokenCacheForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  clearHostedDeviceBindingTokenCacheForTests();
  fs.rmSync(runtimeDir, { recursive: true, force: true });
  restoreEnv();
});

describe("hosted device binding token store (Node)", () => {
  it("exports the header name the client reads tokens from", () => {
    expect(DEVICE_BINDING_TOKEN_HEADER).toBe("X-Algenta-Device-Binding-Token");
  });

  it("serves a persisted token from the process cache, then cold from disk", () => {
    persist();
    expect(Object.values(readStore())).toEqual([TOKEN]);
    expect(load()).toBe(TOKEN);

    // Deleting the file proves the second read is the in-process cache.
    fs.rmSync(storePath());
    expect(load()).toBe(TOKEN);

    clearHostedDeviceBindingTokenCacheForTests();
    expect(load()).toBeNull();

    persist();
    clearHostedDeviceBindingTokenCacheForTests();
    expect(load()).toBe(TOKEN);
  });

  it("keys the store by the base URL without trailing slashes", () => {
    persist(TOKEN, DEVICE_ID, `${BASE_URL}///`);
    clearHostedDeviceBindingTokenCacheForTests();

    expect(load(DEVICE_ID, BASE_URL)).toBe(TOKEN);
    expect(Object.keys(readStore())).toEqual([expect.stringMatching(HEX_32)]);
  });

  it("ignores a blank token", () => {
    persist("   ");

    expect(fs.existsSync(storePath())).toBe(false);
    expect(load()).toBeNull();
  });

  it("merges a second device into an existing store", () => {
    persist(TOKEN, DEVICE_ID);
    persist("other-token-00000000000000000002", "ts-device-binding-00002");
    clearHostedDeviceBindingTokenCacheForTests();

    expect(Object.keys(readStore())).toHaveLength(2);
    expect(load(DEVICE_ID)).toBe(TOKEN);
    expect(load("ts-device-binding-00002")).toBe("other-token-00000000000000000002");
  });

  it("returns null for a corrupt store file", () => {
    fs.writeFileSync(storePath(), "{not json", "utf8");

    expect(load()).toBeNull();
  });

  it.each([[""], ["   "], [42]])("returns null when the stored value is %j", storedValue => {
    persist();
    const [key] = Object.keys(readStore());
    fs.writeFileSync(storePath(), JSON.stringify({ [key]: storedValue }), "utf8");
    clearHostedDeviceBindingTokenCacheForTests();

    expect(load()).toBeNull();
  });

  it("creates a missing runtime directory on persist", () => {
    const nested = path.join(runtimeDir, "nested", "deeper");
    process.env.ALGENTA_RUNTIME_DIR = nested;

    persist();

    expect(fs.existsSync(path.join(nested, STORE_FILE))).toBe(true);
  });

  it.each(RUNTIME_DIR_FALLBACKS)(
    "stores tokens under %s/.algenta/runtime when no runtime dir is configured",
    (_label, configure) => {
      delete process.env.ALGENTA_RUNTIME_DIR;
      configure(runtimeDir);
      stubNodeBuiltins({ fs, os: { homedir: () => runtimeDir }, path: REAL_PATH });

      persist();
      clearHostedDeviceBindingTokenCacheForTests();

      expect(fs.existsSync(path.join(runtimeDir, ".algenta", "runtime", STORE_FILE))).toBe(true);
      expect(load()).toBe(TOKEN);
    },
  );

  it("swallows a store write failure but keeps the token for this process", () => {
    // A regular file where the runtime directory should be makes mkdirSync throw.
    const blocker = path.join(runtimeDir, "blocker");
    fs.writeFileSync(blocker, "", "utf8");
    process.env.ALGENTA_RUNTIME_DIR = blocker;

    expect(() => persist()).not.toThrow();
    expect(load()).toBe(TOKEN);

    clearHostedDeviceBindingTokenCacheForTests();
    expect(load()).toBeNull();
  });

  it("is a no-op without a built-in module loader and without localStorage", () => {
    withoutBuiltinModuleLoader(() => {
      persist();
      expect(load()).toBe(TOKEN);
      clearHostedDeviceBindingTokenCacheForTests();
      expect(load()).toBeNull();
    });

    expect(fs.existsSync(storePath())).toBe(false);
  });
});

describe("hosted device binding token store (browser)", () => {
  beforeEach(() => {
    // No usable Node built-ins: the store must fall through to localStorage.
    stubNodeBuiltins({});
  });

  it("round-trips a token through localStorage", () => {
    const storage = fakeLocalStorage();
    vi.stubGlobal("localStorage", storage);

    persist();
    clearHostedDeviceBindingTokenCacheForTests();

    expect(storage.setItem).toHaveBeenCalledOnce();
    const [key, raw] = storage.setItem.mock.calls[0] as [string, string];
    expect(key).toBe(BINDING_STORAGE_KEY);
    expect(Object.values(JSON.parse(raw) as Record<string, string>)).toEqual([TOKEN]);
    expect(load()).toBe(TOKEN);
    expect(fs.existsSync(storePath())).toBe(false);
  });

  it("merges into an existing localStorage store", () => {
    const storage = fakeLocalStorage({
      [BINDING_STORAGE_KEY]: JSON.stringify({ other: "other-token" }),
    });
    vi.stubGlobal("localStorage", storage);

    persist();

    const stored = JSON.parse(storage.entries.get(BINDING_STORAGE_KEY) ?? "{}") as Record<
      string,
      string
    >;
    expect(stored.other).toBe("other-token");
    expect(Object.values(stored)).toContain(TOKEN);
    expect(Object.keys(stored)).toHaveLength(2);
  });

  it.each([
    ["holds no store", {}],
    ["holds corrupt JSON", { [BINDING_STORAGE_KEY]: "{oops" }],
  ])("returns null when localStorage %s", (_label, seed) => {
    vi.stubGlobal("localStorage", fakeLocalStorage(seed));

    expect(load()).toBeNull();
  });

  it("returns null when the stored localStorage value is blank", () => {
    const storage = fakeLocalStorage();
    vi.stubGlobal("localStorage", storage);
    persist();
    const [key] = Object.keys(
      JSON.parse(storage.entries.get(BINDING_STORAGE_KEY) ?? "{}") as Record<string, string>,
    );
    storage.entries.set(BINDING_STORAGE_KEY, JSON.stringify({ [key]: "  " }));
    clearHostedDeviceBindingTokenCacheForTests();

    expect(load()).toBeNull();
  });

  it("swallows localStorage write and read failures", () => {
    vi.stubGlobal("localStorage", fakeLocalStorage({}, { set: true }));
    expect(() => persist()).not.toThrow();
    expect(load()).toBe(TOKEN);
    clearHostedDeviceBindingTokenCacheForTests();
    expect(load()).toBeNull();

    vi.stubGlobal("localStorage", fakeLocalStorage({}, { get: true }));
    expect(load()).toBeNull();
  });
});

describe("resolveClientDeviceHeaders", () => {
  describe("caller and environment device ids", () => {
    it.each([
      ["too short", "short-id"],
      ["too long", "x".repeat(65)],
    ])("rejects a caller-provided device id that is %s", (_label, deviceId) => {
      expect(() => resolveClientDeviceHeaders(SDK_VERSION, { [DEVICE_ID_HEADER]: deviceId })).toThrowError(
        "X-Algenta-Device-Id must be between 16 and 64 characters.",
      );
    });

    it("trims a valid caller-provided device id and ignores the environment", () => {
      process.env.ALGENTA_DEVICE_ID = "env-device-000000000001";

      const headers = resolveClientDeviceHeaders(SDK_VERSION, {
        [DEVICE_ID_HEADER]: "  caller-device-0001  ",
      });

      expect(headers[DEVICE_ID_HEADER]).toBe("caller-device-0001");
      expect(headers[SDK_VERSION_HEADER]).toBe(SDK_VERSION);
    });

    it("prefers ALGENTA_DEVICE_ID over DE_DEVICE_ID and accepts DE_DEVICE_ID alone", () => {
      process.env.ALGENTA_DEVICE_ID = "env-device-000000000001";
      process.env.DE_DEVICE_ID = "legacy-device-00000000001";
      expect(resolveClientDeviceHeaders(SDK_VERSION)[DEVICE_ID_HEADER]).toBe(
        "env-device-000000000001",
      );

      delete process.env.ALGENTA_DEVICE_ID;
      expect(resolveClientDeviceHeaders(SDK_VERSION)[DEVICE_ID_HEADER]).toBe(
        "legacy-device-00000000001",
      );
    });

    it("validates an environment device id under the ALGENTA_DEVICE_ID label", () => {
      process.env.DE_DEVICE_ID = "short";

      expect(() => resolveClientDeviceHeaders(SDK_VERSION)).toThrowError(
        "ALGENTA_DEVICE_ID must be between 16 and 64 characters.",
      );
    });

    it("fingerprints the caller-provided id itself when no other source exists", () => {
      const headers = withoutBuiltinModuleLoader(() =>
        resolveClientDeviceHeaders(SDK_VERSION, { [DEVICE_ID_HEADER]: "caller-device-0002" }),
      );

      expect(headers[DEVICE_ID_HEADER]).toBe("caller-device-0002");
      expect(headers[HOSTNAME_HASH_HEADER]).toMatch(HEX_16);
      // No Node identity means the browser platform is the only platform hint left.
      expect(headers[PLATFORM_HEADER]).toBe(navigator.platform.trim());
      expect(headers[PLATFORM_VERSION_HEADER]).toBeUndefined();
    });
  });

  describe("browser fallback", () => {
    beforeEach(() => {
      stubNodeBuiltins({});
    });

    it("uses a stored browser device id and the navigator platform", () => {
      const storage = fakeLocalStorage({ [DEVICE_ID_STORAGE_KEY]: "browser-device-000000001" });
      vi.stubGlobal("localStorage", storage);

      const headers = resolveClientDeviceHeaders(SDK_VERSION);

      expect(headers[DEVICE_ID_HEADER]).toBe("browser-device-000000001");
      expect(headers[PLATFORM_HEADER]).toBe(navigator.platform.trim());
      expect(headers[HOSTNAME_HASH_HEADER]).toMatch(HEX_16);
      expect(headers[PLATFORM_VERSION_HEADER]).toBeUndefined();
      expect(storage.setItem).not.toHaveBeenCalled();
    });

    it.each([
      ["with", () => {}],
      // The generated seed reads navigator.userAgent/language only when navigator exists.
      ["without", () => vi.stubGlobal("navigator", undefined)],
    ])("generates and stores a browser device id when none is saved, %s navigator", (_label, arrange) => {
      const storage = fakeLocalStorage();
      vi.stubGlobal("localStorage", storage);
      arrange();

      const first = resolveClientDeviceHeaders(SDK_VERSION);
      const second = resolveClientDeviceHeaders(SDK_VERSION);

      expect(first[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(storage.setItem).toHaveBeenCalledExactlyOnceWith(
        DEVICE_ID_STORAGE_KEY,
        first[DEVICE_ID_HEADER],
      );
      expect(second[DEVICE_ID_HEADER]).toBe(first[DEVICE_ID_HEADER]);
    });

    it.each([
      ["unavailable", undefined],
      ["missing a string platform", {}],
    ])("omits the platform header when navigator is %s", (_label, navigatorStub) => {
      vi.stubGlobal("localStorage", fakeLocalStorage({ [DEVICE_ID_STORAGE_KEY]: "browser-device-000000002" }));
      vi.stubGlobal("navigator", navigatorStub);

      const headers = resolveClientDeviceHeaders(SDK_VERSION);

      expect(headers[DEVICE_ID_HEADER]).toBe("browser-device-000000002");
      expect(headers[PLATFORM_HEADER]).toBeUndefined();
      expect(headers[HOSTNAME_HASH_HEADER]).toMatch(HEX_16);
    });

    it("returns only the SDK version header when no identity source exists", () => {
      expect(resolveClientDeviceHeaders(SDK_VERSION)).toEqual({ [SDK_VERSION_HEADER]: SDK_VERSION });
    });

    it("returns only the SDK version header when localStorage is unreadable", () => {
      vi.stubGlobal("localStorage", fakeLocalStorage({}, { get: true }));

      expect(resolveClientDeviceHeaders(SDK_VERSION)).toEqual({ [SDK_VERSION_HEADER]: SDK_VERSION });
    });

    it("returns only the SDK version header without a built-in module loader", () => {
      const headers = withoutBuiltinModuleLoader(() => resolveClientDeviceHeaders(SDK_VERSION));

      expect(headers).toEqual({ [SDK_VERSION_HEADER]: SDK_VERSION });
    });
  });

  describe("Node identity sources", () => {
    it("resolves the same identity whether built-ins load with or without the node: prefix", () => {
      const reference = resolveClientDeviceHeaders(SDK_VERSION);
      vi.spyOn(process, "getBuiltinModule").mockImplementation(((name: string): unknown => {
        // A loader that rejects the "node:" spelling must fall through to the bare one.
        if (name.startsWith("node:")) throw new Error(`unsupported specifier ${name}`);
        if (name === "fs") return fs;
        if (name === "os") return os;
        if (name === "path") return path;
        return undefined;
      }) as typeof process.getBuiltinModule);

      const resolved = resolveClientDeviceHeaders(SDK_VERSION);

      expect(resolved[DEVICE_ID_HEADER]).toBe(reference[DEVICE_ID_HEADER]);
      expect(resolved[HOSTNAME_HASH_HEADER]).toBe(reference[HOSTNAME_HASH_HEADER]);
    });

    it("derives the identity from HOSTNAME alone when a built-in is missing", () => {
      process.env.HOSTNAME = "env-host-02";
      // realFsStub() hides the Linux machine-id files: on a Linux host the real fs would
      // read /etc/machine-id, which outranks the hostname and makes the two arms differ.
      stubNodeBuiltins({
        fs: realFsStub(),
        os: { hostname: () => "env-host-02", homedir: os.homedir },
        path: REAL_PATH,
      });
      const viaBuiltins = resolveClientDeviceHeaders(SDK_VERSION);
      // Without `path` there are no usable built-ins, so only the environment remains.
      stubNodeBuiltins({ fs, os });

      const viaEnv = resolveClientDeviceHeaders(SDK_VERSION);

      expect(viaEnv[DEVICE_ID_HEADER]).toBe(viaBuiltins[DEVICE_ID_HEADER]);
      expect(viaEnv[HOSTNAME_HASH_HEADER]).toBe(viaBuiltins[HOSTNAME_HASH_HEADER]);
      expect(viaEnv[PLATFORM_HEADER]).toBe(process.platform);
    });

    it("reads the hostname from HOSTNAME when os.hostname() throws", () => {
      process.env.HOSTNAME = "env-host-01";
      stubNodeBuiltins({
        fs: realFsStub(),
        os: { hostname: () => { throw new Error("no hostname"); }, homedir: () => runtimeDir },
        path: REAL_PATH,
      });
      const viaEnv = resolveClientDeviceHeaders(SDK_VERSION);
      stubNodeBuiltins({
        fs: realFsStub(),
        os: { hostname: () => "env-host-01", homedir: () => runtimeDir },
        path: REAL_PATH,
      });

      const viaOs = resolveClientDeviceHeaders(SDK_VERSION);

      expect(viaEnv[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(viaEnv[DEVICE_ID_HEADER]).toBe(viaOs[DEVICE_ID_HEADER]);
      expect(viaEnv[HOSTNAME_HASH_HEADER]).toBe(viaOs[HOSTNAME_HASH_HEADER]);
    });

    it("skips blank machine-id files on linux and falls through to the hostname", () => {
      const fsStub = realFsStub(filePath => {
        if (filePath === "/etc/machine-id") return "  \n";
        throw new Error("missing alternate machine id");
      });
      stubNodeBuiltins({
        fs: fsStub,
        os: { hostname: () => "linux-host-01", homedir: () => runtimeDir },
        path: REAL_PATH,
      });

      const headers = withProcessProperty("platform", "linux", () =>
        resolveClientDeviceHeaders(SDK_VERSION),
      );

      expect(headers[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(headers[PLATFORM_HEADER]).toBe("linux");
      expect(fsStub.readFileSync).toHaveBeenCalledWith("/etc/machine-id", "utf8");
      expect(fsStub.readFileSync).toHaveBeenCalledWith("/var/lib/dbus/machine-id", "utf8");
      expect(fsStub.writeFileSync).not.toHaveBeenCalled();
    });

    it("omits platform headers when the process reports no platform, version or arch", () => {
      const headers = withProcessProperty("platform", undefined, () =>
        withProcessProperty("version", undefined, () =>
          withProcessProperty("arch", undefined, () => resolveClientDeviceHeaders(SDK_VERSION)),
        ),
      );

      expect(headers[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(headers[PLATFORM_HEADER]).toBeUndefined();
      expect(headers[PLATFORM_VERSION_HEADER]).toBeUndefined();
    });
  });

  describe("install id (no hostname, no machine id)", () => {
    const noHostnameOs = { hostname: () => "", homedir: () => runtimeDir };

    it("regenerates a blank install_id file", () => {
      fs.writeFileSync(path.join(runtimeDir, "install_id"), "   \n", "utf8");
      stubNodeBuiltins({ fs: realFsStub(), os: noHostnameOs, path: REAL_PATH });

      const headers = resolveClientDeviceHeaders(SDK_VERSION);

      expect(headers[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(fs.readFileSync(path.join(runtimeDir, "install_id"), "utf8").trim()).not.toBe("");
    });

    it("falls back to a time-and-random install id when crypto.randomUUID is unavailable", () => {
      vi.stubGlobal("crypto", {});
      stubNodeBuiltins({ fs: realFsStub(), os: noHostnameOs, path: REAL_PATH });

      const headers = resolveClientDeviceHeaders(SDK_VERSION);

      expect(headers[DEVICE_ID_HEADER]).toMatch(HEX_32);
      expect(fs.readFileSync(path.join(runtimeDir, "install_id"), "utf8")).toMatch(
        /^[0-9a-z]+-[0-9a-z]+-[0-9a-z]+$/,
      );
    });

    it.each(RUNTIME_DIR_FALLBACKS)(
      "writes the install id under %s/.algenta/runtime when no runtime dir is configured",
      (_label, configure) => {
        delete process.env.ALGENTA_RUNTIME_DIR;
        configure(runtimeDir);
        stubNodeBuiltins({ fs: realFsStub(), os: noHostnameOs, path: REAL_PATH });

        const headers = resolveClientDeviceHeaders(SDK_VERSION);

        expect(headers[DEVICE_ID_HEADER]).toMatch(HEX_32);
        expect(fs.existsSync(path.join(runtimeDir, ".algenta", "runtime", "install_id"))).toBe(true);
      },
    );

    it("reports no device id when the install id cannot be written", () => {
      stubNodeBuiltins({
        fs: {
          ...realFsStub(),
          existsSync: () => false,
          mkdirSync: () => {
            throw new Error("read-only file system");
          },
        },
        os: noHostnameOs,
        path: REAL_PATH,
      });

      expect(resolveClientDeviceHeaders(SDK_VERSION)).toEqual({ [SDK_VERSION_HEADER]: SDK_VERSION });
    });
  });
});
