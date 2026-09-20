// SPDX-License-Identifier: Apache-2.0
// Unit tests for runtime helper module A: canonical hashing, runtime paths,
// trusted-time persistence, offline license parsing/exchange and banners.
import { createHash, createSign, generateKeyPairSync } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir, hostname, platform, release, tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACCENT,
  DEFAULT_GRACE_DAYS,
  MUTED,
  RESET,
  TITLE_ART,
  TITLE_COLORS,
  TRUSTED_TIME_VERSION,
} from "./_runtime_constants.js";
import type { LocalRuntimeLicense, TrustedTimeState } from "./_runtime_constants.js";
import {
  base64UrlDecode,
  base64UrlEncode,
  canonicalJson,
  deviceInfo,
  exchangeApiKeyForLicense,
  licenseHardExpired,
  licenseInGrace,
  loadLocalLicense,
  makeInvalidLicense,
  monotonicNowSeconds,
  normalizeText,
  observeTrustedTime,
  offlineLicensePublicKeys,
  parseStoredLicenseToken,
  readStoredLicenseToken,
  readTrustedTimeState,
  resetTrustedTimeSession,
  runtimeBanner,
  runtimeDirectory,
  runtimeEnv,
  runtimeLicensePath,
  runtimeTrustedTimePath,
  saveStoredLicenseToken,
  sessionTrustedEpoch,
  sha256Hex,
  stableHash,
  stableStringify,
  stripNullEntries,
  supportsColor,
  trustedNowEpoch,
  writeTrustedTimeState,
} from "./_runtime_helpers_a.js";
import { issueOfflineLocalLicense } from "./_runtime_test_helpers.js";

const ORIGINAL_ENV = { ...process.env };
const DAY_SECONDS = 86_400;
const REGISTER_URL = "https://api.algenta.ai/v1/device/register";
const REGISTRATION_FAILED =
  "Control plane registration failed. First-time local login requires a reachable control plane.";
const NO_STORED_LICENSE =
  "No stored license found. Run `algenta login` against the control plane before offline execution.";

// Every env key these helpers (or the privacy policy they call into) read. Cleared before each
// test so the developer's shell cannot change which branch a test takes.
const SCOPED_ENV_KEYS = [
  "ALGENTA_RUNTIME_DIR",
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_ALLOW_OUTBOUND_NETWORK",
  "ALGENTA_EGRESS_ALLOWLIST",
  "ALGENTA_CONTROL_PLANE_URL",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
  "ALGENTA_REQUIRE_LOCAL_LICENSE",
  "ALGENTA_LOCAL_LICENSE_PUBLIC_KEY",
  "ALGENTA_LICENSE_PUBLIC_KEY",
  "ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE",
  "ALGENTA_LICENSE_PUBLIC_KEY_FILE",
  "NO_COLOR",
];

let runtimeDir: string;

beforeEach(() => {
  for (const key of SCOPED_ENV_KEYS) {
    delete process.env[key];
  }
  runtimeDir = mkdtempSync(join(tmpdir(), "algenta-ts-helpers-"));
  process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
});

afterEach(() => {
  vi.unstubAllGlobals();
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
  rmSync(runtimeDir, { recursive: true, force: true });
});

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function readState(): TrustedTimeState {
  return JSON.parse(readFileSync(runtimeTrustedTimePath(), "utf8")) as TrustedTimeState;
}

function writeState(state: Record<string, unknown> | string): void {
  mkdirSync(runtimeDir, { recursive: true });
  writeFileSync(runtimeTrustedTimePath(), typeof state === "string" ? state : JSON.stringify(state));
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Mint an RS256 token over an arbitrary payload/header with a fresh key pair, so the
 * tests can exercise claim defaults and header rejection the shared fixture cannot. */
function signRs256(
  payload: Record<string, unknown>,
  header: Record<string, unknown> = { alg: "RS256", typ: "JWT" },
): { token: string; publicKey: string } {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    privateKeyEncoding: { format: "pem", type: "pkcs8" },
    publicKeyEncoding: { format: "pem", type: "spki" },
  });
  const headerSegment = base64UrlEncode(Buffer.from(JSON.stringify(header)));
  const payloadSegment = base64UrlEncode(Buffer.from(JSON.stringify(payload)));
  const signer = createSign("RSA-SHA256");
  signer.update(`${headerSegment}.${payloadSegment}`);
  signer.end();
  const signature = base64UrlEncode(signer.sign(privateKey));
  return { token: `${headerSegment}.${payloadSegment}.${signature}`, publicKey };
}

function storeOfflineLicense(expiresAt = 0): string {
  const { token, publicKey } = issueOfflineLocalLicense(expiresAt);
  writeFileSync(runtimeLicensePath(), token);
  process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
  return token;
}

function licenseExpiringAt(expiresAt: number): LocalRuntimeLicense {
  return { ...makeInvalidLicense("fixture"), valid: true, expiresAt, graceDays: DEFAULT_GRACE_DAYS };
}

/** Swap (or remove) the global `process` for the duration of one synchronous call. The
 * helpers guard against non-Node hosts; restoring inside `finally` keeps the vitest runner
 * (which needs `process` between tests) intact. */
function withGlobalProcess<T>(replacement: unknown, run: () => T): T {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "process");
  if (replacement === undefined) {
    delete (globalThis as { process?: unknown }).process;
  } else {
    Object.defineProperty(globalThis, "process", { value: replacement, configurable: true, writable: true });
  }
  try {
    return run();
  } finally {
    if (descriptor) {
      Object.defineProperty(globalThis, "process", descriptor);
    }
  }
}

function withStdoutTty<T>(isTTY: boolean, run: () => T): T {
  const descriptor = Object.getOwnPropertyDescriptor(process.stdout, "isTTY");
  Object.defineProperty(process.stdout, "isTTY", { value: isTTY, configurable: true, writable: true, enumerable: true });
  try {
    return run();
  } finally {
    if (descriptor) {
      Object.defineProperty(process.stdout, "isTTY", descriptor);
    } else {
      delete (process.stdout as { isTTY?: boolean }).isTTY;
    }
  }
}

describe("stableStringify", () => {
  it.each<[string, unknown, string]>([
    ["null", null, "null"],
    ["number", 3, "3"],
    ["string", "a", "\"a\""],
    ["array preserves order", [3, 1, 2], "[3,1,2]"],
    ["object sorts keys recursively", { b: [{ z: 1, y: 2 }], a: null }, "{\"a\":null,\"b\":[{\"y\":2,\"z\":1}]}"],
  ])("renders %s", (_label, value, expected) => {
    expect(stableStringify(value)).toBe(expected);
  });
});

describe("canonicalJson", () => {
  it.each<[string, unknown, string]>([
    ["null", null, "null"],
    ["undefined", undefined, "null"],
    ["true", true, "true"],
    ["false", false, "false"],
    ["integer", 42, "42"],
    ["negative zero", -0, "0"],
    ["float", 1.5, "1.5"],
    ["large exponent", 1e21, "1e+21"],
    ["ascii string", "plain", "\"plain\""],
    ["non-ascii string", "caf\u00e9", "\"caf\\u00e9\""],
    ["array with nested arrays", [1, "x", null, [2, [3]]], "[1,\"x\",null,[2,[3]]]"],
    ["object drops undefined entries and sorts keys", { b: 1, a: undefined, c: "\u00fc" }, "{\"b\":1,\"c\":\"\\u00fc\"}"],
    ["non-ascii key", { "\u00f1": true }, "{\"\\u00f1\":true}"],
    // Neither bigint nor symbol is JSON; both fall through to the String(value) rendering.
    ["bigint fallback", 10n, "\"10\""],
    ["symbol fallback", Symbol("tag"), "\"Symbol(tag)\""],
  ])("renders %s", (_label, value, expected) => {
    expect(canonicalJson(value)).toBe(expected);
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("rejects %s", value => {
    expect(() => canonicalJson(value)).toThrowError(TypeError);
    expect(() => canonicalJson({ nested: [value] })).toThrowError(/NaN and Infinity/);
  });
});

describe("stripNullEntries", () => {
  it("drops null and undefined object entries recursively but keeps array slots", () => {
    expect(
      stripNullEntries({ a: null, b: undefined, c: 0, d: { e: null, f: [null, { g: undefined, h: 1 }] } }),
    ).toEqual({ c: 0, d: { f: [null, { h: 1 }] } });
  });

  it.each([[5], ["x"], [null], [undefined], [false]])("returns primitive %s unchanged", value => {
    expect(stripNullEntries(value)).toBe(value);
  });
});

describe("stableHash", () => {
  it("is sha256 over the canonical JSON rendering", () => {
    const value = { z: [1, 2], a: "\u00e9", b: undefined };
    expect(stableHash(value)).toBe(createHash("sha256").update(canonicalJson(value), "utf-8").digest("hex"));
    expect(stableHash({ a: 1 })).toBe(createHash("sha256").update("{\"a\":1}").digest("hex"));
  });

  it("is independent of key insertion order", () => {
    expect(stableHash({ a: 1, b: 2 })).toBe(stableHash({ b: 2, a: 1 }));
  });
});

describe("runtimeEnv and runtime paths", () => {
  it("returns the live process environment", () => {
    expect(runtimeEnv()).toBe(process.env);
  });

  it("returns an empty environment when the host has no process global", () => {
    expect(withGlobalProcess(undefined, () => runtimeEnv())).toEqual({});
  });

  it("returns an empty environment when the process global has no env", () => {
    expect(withGlobalProcess({}, () => runtimeEnv())).toEqual({});
  });

  it("honours ALGENTA_RUNTIME_DIR for every derived path", () => {
    expect(runtimeDirectory()).toBe(runtimeDir);
    expect(runtimeLicensePath()).toBe(join(runtimeDir, "license.jwt"));
    expect(runtimeTrustedTimePath()).toBe(join(runtimeDir, "trusted_time.json"));
  });

  it("falls back to ~/.algenta/runtime without ALGENTA_RUNTIME_DIR", () => {
    delete process.env.ALGENTA_RUNTIME_DIR;
    expect(runtimeDirectory()).toBe(join(homedir(), ".algenta", "runtime"));
  });
});

describe("monotonicNowSeconds", () => {
  it("uses the high-resolution clock when available", () => {
    expect(Math.abs(monotonicNowSeconds() - performance.now() / 1000)).toBeLessThan(1);
  });

  it("falls back to Date.now when performance.now is missing", () => {
    // Restore synchronously: the vitest runner itself times tests with performance.now.
    vi.stubGlobal("performance", {});
    let observed: number;
    try {
      observed = monotonicNowSeconds();
    } finally {
      vi.unstubAllGlobals();
    }
    expect(Math.abs(observed - Date.now() / 1000)).toBeLessThan(1);
  });
});

describe("sha256Hex and base64url", () => {
  it("hashes utf-8 input", () => {
    expect(sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("round-trips bytes through unpadded base64url", () => {
    const encoded = base64UrlEncode(Buffer.from("hello?>"));
    expect(encoded).toBe("aGVsbG8_Pg");
    expect(base64UrlDecode(encoded).toString("utf8")).toBe("hello?>");
  });
});

describe("offlineLicensePublicKeys", () => {
  it("returns nothing when no key source is configured", () => {
    expect(offlineLicensePublicKeys()).toEqual([]);
  });

  it("collects trimmed inline keys and skips blank values", () => {
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = "  key-a  ";
    process.env.ALGENTA_LICENSE_PUBLIC_KEY = "   ";
    expect(offlineLicensePublicKeys()).toEqual([{ key: "key-a", source: "offline-local" }]);
  });

  it("reads *_FILE keys, skipping unreadable, blank-content and blank-path entries", () => {
    const keyFile = join(runtimeDir, "key.pem");
    writeFileSync(keyFile, "  key-from-file \n");
    writeFileSync(join(runtimeDir, "empty.pem"), "\n\n");
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE = keyFile;
    process.env.ALGENTA_LICENSE_PUBLIC_KEY_FILE = join(runtimeDir, "does-not-exist.pem");
    expect(offlineLicensePublicKeys()).toEqual([{ key: "key-from-file", source: "offline-local" }]);

    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE = join(runtimeDir, "empty.pem");
    process.env.ALGENTA_LICENSE_PUBLIC_KEY_FILE = "   ";
    expect(offlineLicensePublicKeys()).toEqual([]);
  });

  it("dedupes identical keys across inline and file sources", () => {
    const keyFile = join(runtimeDir, "key.pem");
    writeFileSync(keyFile, "shared-key");
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = "shared-key";
    process.env.ALGENTA_LICENSE_PUBLIC_KEY = "other-key";
    process.env.ALGENTA_LICENSE_PUBLIC_KEY_FILE = keyFile;
    expect(offlineLicensePublicKeys()).toEqual([
      { key: "shared-key", source: "offline-local" },
      { key: "other-key", source: "offline-local" },
    ]);
  });
});

describe("stored license token", () => {
  it("returns null when no token is stored", () => {
    expect(readStoredLicenseToken()).toBeNull();
  });

  it("returns the trimmed token when present", () => {
    writeFileSync(runtimeLicensePath(), "  a.b.c \n");
    expect(readStoredLicenseToken()).toBe("a.b.c");
  });

  it("returns null when the token path cannot be read as a file", () => {
    mkdirSync(runtimeLicensePath());
    expect(readStoredLicenseToken()).toBeNull();
  });

  it("creates the runtime directory and writes the token", () => {
    const nested = join(runtimeDir, "nested", "deeper");
    process.env.ALGENTA_RUNTIME_DIR = nested;
    saveStoredLicenseToken("tok.en.value");
    expect(readFileSync(join(nested, "license.jwt"), "utf8")).toBe("tok.en.value");
  });

  it.skipIf(process.platform === "win32")("stores the token owner-read/write only", () => {
    saveStoredLicenseToken("tok.en.value");
    expect(statSync(runtimeLicensePath()).mode & 0o777).toBe(0o600);
  });
});

describe("readTrustedTimeState", () => {
  it("returns null when the state file is missing", () => {
    expect(readTrustedTimeState()).toBeNull();
  });

  it.each<[string, Record<string, unknown> | string]>([
    ["invalid JSON", "{not json"],
    ["zero epoch", { trusted_epoch: 0, source: "local" }],
    ["negative epoch", { trusted_epoch: -5, source: "local" }],
    ["string epoch", { trusted_epoch: "5", source: "local" }],
    ["non-finite epoch", { trusted_epoch: "Infinity", source: "local" }],
    ["missing source", { trusted_epoch: 5 }],
    ["blank source", { trusted_epoch: 5, source: "   " }],
  ])("returns null for %s", (_label, state) => {
    writeState(state);
    expect(readTrustedTimeState()).toBeNull();
  });

  it("returns the stored state and defaults a missing version", () => {
    writeState({ trusted_epoch: 5, source: "local" });
    expect(readTrustedTimeState()).toEqual({ version: TRUSTED_TIME_VERSION, trusted_epoch: 5, source: "local" });
    writeState({ version: 7, trusted_epoch: 5, source: "local" });
    expect(readTrustedTimeState()?.version).toBe(7);
    writeState({ version: "7", trusted_epoch: 5, source: "local" });
    expect(readTrustedTimeState()?.version).toBe(TRUSTED_TIME_VERSION);
  });
});

describe("writeTrustedTimeState", () => {
  it("writes pretty JSON atomically without leaving the temp file behind", () => {
    const state: TrustedTimeState = { version: 1, trusted_epoch: 123, source: "local" };
    writeTrustedTimeState(state);
    expect(readFileSync(runtimeTrustedTimePath(), "utf8")).toBe(`${JSON.stringify(state, null, 2)}\n`);
    expect(existsSync(`${runtimeTrustedTimePath()}.tmp`)).toBe(false);
  });

  it("swallows filesystem errors when the runtime directory cannot be created", () => {
    const blocker = join(runtimeDir, "blocker");
    writeFileSync(blocker, "not a directory");
    process.env.ALGENTA_RUNTIME_DIR = join(blocker, "runtime");
    expect(() => writeTrustedTimeState({ version: 1, trusted_epoch: 1, source: "local" })).not.toThrow();
    expect(existsSync(runtimeTrustedTimePath())).toBe(false);
  });
});

describe("trusted time session", () => {
  it("resets the session base and keeps advancing from it", () => {
    const farFuture = nowSeconds() + 30 * DAY_SECONDS;
    expect(resetTrustedTimeSession(farFuture, monotonicNowSeconds())).toBe(farFuture);
    const continued = sessionTrustedEpoch(0);
    expect(continued).toBeGreaterThanOrEqual(farFuture);
    expect(continued).toBeLessThan(farFuture + 5);
  });

  it("jumps forward to a higher floor instead of returning the session epoch", () => {
    resetTrustedTimeSession(nowSeconds());
    const floor = nowSeconds() + 1000;
    expect(sessionTrustedEpoch(floor)).toBe(floor);
  });

  it("re-seeds from local time when the runtime directory changes", () => {
    const farFuture = nowSeconds() + 30 * DAY_SECONDS;
    resetTrustedTimeSession(farFuture);
    expect(sessionTrustedEpoch(0)).toBeGreaterThanOrEqual(farFuture);
    const otherDir = mkdtempSync(join(tmpdir(), "algenta-ts-helpers-"));
    try {
      process.env.ALGENTA_RUNTIME_DIR = otherDir;
      const reseeded = sessionTrustedEpoch(0);
      expect(reseeded).toBeLessThan(farFuture);
      expect(Math.abs(reseeded - Date.now() / 1000)).toBeLessThan(5);
    } finally {
      rmSync(otherDir, { recursive: true, force: true });
    }
  });
});

describe("trustedNowEpoch", () => {
  it("seeds a fresh runtime directory from local time and persists it", () => {
    const epoch = trustedNowEpoch();
    expect(Math.abs(epoch - Date.now() / 1000)).toBeLessThan(5);
    expect(readState()).toEqual({ version: TRUSTED_TIME_VERSION, trusted_epoch: epoch, source: "local" });
  });

  it("never returns less than the persisted floor and leaves a fresh floor untouched", () => {
    const floor = nowSeconds() + 10 * DAY_SECONDS;
    writeState({ version: 1, trusted_epoch: floor, source: "control-plane-register" });
    const before = readFileSync(runtimeTrustedTimePath(), "utf8");
    expect(trustedNowEpoch()).toBeGreaterThanOrEqual(floor);
    expect(readFileSync(runtimeTrustedTimePath(), "utf8")).toBe(before);
  });

  it("re-persists once the session has advanced past the persist interval", () => {
    writeState({ version: 1, trusted_epoch: 1000, source: "local" });
    const epoch = trustedNowEpoch();
    expect(epoch).toBeGreaterThan(1000 + 60);
    expect(readState()).toEqual({ version: TRUSTED_TIME_VERSION, trusted_epoch: epoch, source: "local" });
  });
});

describe("observeTrustedTime", () => {
  it("falls back to the trusted clock for non-finite or non-positive observations", () => {
    for (const bad of [Number.NaN, 0, -5, Number.POSITIVE_INFINITY]) {
      const epoch = observeTrustedTime(bad, "control-plane-register");
      expect(Math.abs(epoch - Date.now() / 1000)).toBeLessThan(5);
    }
    expect(readState().source).toBe("local");
  });

  it("persists a first observation with its source", () => {
    const observed = 1_800_000_000;
    expect(observeTrustedTime(observed, "control-plane-register")).toBe(observed);
    expect(readState()).toEqual({
      version: TRUSTED_TIME_VERSION,
      trusted_epoch: observed,
      source: "control-plane-register",
    });
  });

  it("raises the floor when the observation is newer", () => {
    writeState({ version: 1, trusted_epoch: 1_800_000_000, source: "control-plane-register" });
    expect(observeTrustedTime(1_800_000_500, "control-plane-register")).toBe(1_800_000_500);
    expect(readState().trusted_epoch).toBe(1_800_000_500);
  });

  it("keeps the floor and skips the write for an older observation from the same source", () => {
    const floor = nowSeconds() + 10 * DAY_SECONDS;
    writeState({ version: 1, trusted_epoch: floor, source: "control-plane-register" });
    const before = readFileSync(runtimeTrustedTimePath(), "utf8");
    expect(observeTrustedTime(floor - 1000, "control-plane-register")).toBe(floor);
    expect(readFileSync(runtimeTrustedTimePath(), "utf8")).toBe(before);
  });

  it("rewrites the state when only the source changes", () => {
    const floor = nowSeconds() + 10 * DAY_SECONDS;
    writeState({ version: 1, trusted_epoch: floor, source: "local" });
    expect(observeTrustedTime(floor - 10, "control-plane-register")).toBe(floor);
    expect(readState()).toEqual({ version: TRUSTED_TIME_VERSION, trusted_epoch: floor, source: "control-plane-register" });
  });
});

describe("deviceInfo and makeInvalidLicense", () => {
  it("derives stable identifiers from the host", () => {
    expect(deviceInfo()).toEqual({
      device_id: sha256Hex(`${hostname()}|${platform()}|${release()}`),
      platform: platform(),
      platform_version: release(),
      hostname_hash: sha256Hex(hostname()),
      sdk_version: "algenta-sdk/0.1.0",
    });
  });

  it("builds an invalid license carrying the message and key prefix", () => {
    const license = makeInvalidLicense("nope", "de_live_1234567890abcdef");
    expect(license).toMatchObject({
      valid: false,
      plan: "unknown",
      deviceId: deviceInfo().device_id,
      deviceLimit: 0,
      permittedModules: [],
      expiresAt: 0,
      keyExpiresAt: 0,
      graceDays: DEFAULT_GRACE_DAYS,
      apiKeyPrefix: "de_live_1234",
      message: "nope",
      source: "none",
    });
    expect(Math.abs(license.issuedAt - nowSeconds())).toBeLessThanOrEqual(1);
    expect(makeInvalidLicense("x").apiKeyPrefix).toBe("");
  });
});

describe("parseStoredLicenseToken", () => {
  it.each([["a.b"], ["a.b.c.d"], [""]])("rejects %j: not three segments", token => {
    expect(parseStoredLicenseToken(token)).toBeNull();
  });

  it("rejects a header that does not decode to JSON", () => {
    expect(parseStoredLicenseToken("!!!.payload.signature")).toBeNull();
  });

  it("rejects any algorithm other than RS256 even with a trusted key configured", () => {
    const { token, publicKey } = signRs256({ plan: "pro" }, { alg: "HS256", typ: "JWT" });
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
    expect(parseStoredLicenseToken(token)).toBeNull();
  });

  it("verifies an RS256 token against the configured public key", () => {
    const { token, publicKey } = issueOfflineLocalLicense(0);
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
    const parsed = parseStoredLicenseToken(token, "de_test_ignored");
    expect(parsed).toMatchObject({
      valid: true,
      plan: "enterprise",
      deviceId: "ts-device-offline",
      deviceLimit: 0,
      permittedModules: ["*"],
      expiresAt: 0,
      keyExpiresAt: 0,
      graceDays: 14,
      apiKeyPrefix: "offline",
      message: "",
      source: "offline-local",
    });
    expect(Math.abs((parsed?.issuedAt ?? 0) - nowSeconds())).toBeLessThanOrEqual(1);
  });

  it("returns null when no configured key verifies the signature", () => {
    const { token } = issueOfflineLocalLicense(0);
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = issueOfflineLocalLicense(0).publicKey;
    expect(parseStoredLicenseToken(token)).toBeNull();
    // A malformed PEM makes the verifier throw; that key must be skipped, not surfaced.
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = "not-a-pem";
    expect(parseStoredLicenseToken(token)).toBeNull();
    delete process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY;
    expect(parseStoredLicenseToken(token)).toBeNull();
  });

  it("applies claim defaults when the payload omits them", () => {
    const { token, publicKey } = signRs256({});
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
    expect(parseStoredLicenseToken(token, "de_test_abcdefghijkl")).toEqual({
      valid: true,
      plan: "enterprise",
      deviceId: "",
      deviceLimit: 0,
      permittedModules: ["*"],
      expiresAt: 0,
      keyExpiresAt: 0,
      graceDays: DEFAULT_GRACE_DAYS,
      apiKeyPrefix: "de_test_abcd",
      issuedAt: 0,
      message: "",
      source: "offline-local",
    });
  });

  it("coerces present claims to their declared types", () => {
    const { token, publicKey } = signRs256({
      plan: "team",
      device_id: 42,
      device_limit: "3",
      permitted_modules: [1, "forecast"],
      expires_at: "1900000000",
      key_expires_at: 1900000001,
      grace_days: "7",
      api_key_prefix: "de_live_abcd",
      issued_at: 1700000000,
      message: "hello",
    });
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
    expect(parseStoredLicenseToken(token)).toEqual({
      valid: true,
      plan: "team",
      deviceId: "42",
      deviceLimit: 3,
      permittedModules: ["1", "forecast"],
      expiresAt: 1900000000,
      keyExpiresAt: 1900000001,
      graceDays: 7,
      apiKeyPrefix: "de_live_abcd",
      issuedAt: 1700000000,
      message: "hello",
      source: "offline-local",
    });
  });
});

describe("licenseHardExpired and licenseInGrace", () => {
  it.each<[string, number, boolean, boolean]>([
    ["no expiry", 0, false, false],
    ["future expiry", nowSeconds() + DAY_SECONDS, false, false],
    ["expired one day ago (inside grace)", nowSeconds() - DAY_SECONDS, false, true],
    ["expired twenty days ago (past grace)", nowSeconds() - 20 * DAY_SECONDS, true, false],
  ])("%s", (_label, expiresAt, hardExpired, inGrace) => {
    const license = licenseExpiringAt(expiresAt);
    expect(licenseHardExpired(license)).toBe(hardExpired);
    expect(licenseInGrace(license)).toBe(inGrace);
  });
});

describe("exchangeApiKeyForLicense", () => {
  it("refuses control-plane egress that the privacy policy denies", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    process.env.ALGENTA_CONTROL_PLANE_URL = "https://api.algenta.ai";
    await expect(exchangeApiKeyForLicense("de_test_key")).resolves.toEqual({
      token: null,
      invalidMessage:
        "Control-plane egress is blocked by the active privacy policy. Reason: algenta_cloud_disabled.",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each<[string, string | undefined, string]>([
    ["a non-http(s) control-plane URL", "ftp://example.com", "ALGENTA_CONTROL_PLANE_URL must use an absolute http(s) URL."],
    [
      "a private profile without any control-plane URL",
      undefined,
      "ALGENTA_CONTROL_PLANE_URL must be configured explicitly before hosted registration can run in this deployment profile.",
    ],
  ])("surfaces the configuration error for %s", async (_label, controlPlaneUrl, message) => {
    vi.stubGlobal("fetch", vi.fn());
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    if (controlPlaneUrl !== undefined) {
      process.env.ALGENTA_CONTROL_PLANE_URL = controlPlaneUrl;
    }
    await expect(exchangeApiKeyForLicense("de_test_key")).resolves.toEqual({ token: null, invalidMessage: message });
  });

  it.each<[string, Response, string]>([
    ["402 with a detail message", jsonResponse(402, { detail: { message: "Device limit of 2 reached." } }), "Device limit of 2 reached."],
    ["402 without a detail message", jsonResponse(402, {}), "Device limit reached."],
    ["a non-2xx status", jsonResponse(500, { detail: { message: "boom" } }), REGISTRATION_FAILED],
    ["a 2xx body without license_token", jsonResponse(200, { plan: "pro" }), REGISTRATION_FAILED],
    ["a 2xx body that is not JSON", new Response("not json", { status: 200 }), REGISTRATION_FAILED],
  ])("returns no token for %s", async (_label, response, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    await expect(exchangeApiKeyForLicense("de_test_key")).resolves.toEqual({ token: null, invalidMessage: message });
  });

  it("returns no token when the network call itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));
    await expect(exchangeApiKeyForLicense("de_test_key")).resolves.toEqual({
      token: null,
      invalidMessage: REGISTRATION_FAILED,
    });
  });

  it("posts the device descriptor and anchors trusted time to the server clock", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { license_token: "h.p.s", server_time: 1_900_000_000 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(exchangeApiKeyForLicense("de_test_key")).resolves.toEqual({
      token: "h.p.s",
      invalidMessage: null,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(REGISTER_URL);
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ Authorization: "Bearer de_test_key", "Content-Type": "application/json" });
    expect(JSON.parse(String(init.body))).toEqual({ device: deviceInfo() });
    expect(readState()).toEqual({
      version: TRUSTED_TIME_VERSION,
      trusted_epoch: 1_900_000_000,
      source: "control-plane-register",
    });
  });

  it("uses the explicit base URL when no env override exists", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { license_token: "h.p.s" }));
    vi.stubGlobal("fetch", fetchMock);
    process.env.ALGENTA_ALLOW_OUTBOUND_NETWORK = "1";
    await expect(exchangeApiKeyForLicense("de_test_key", "https://control.example.com/")).resolves.toEqual({
      token: "h.p.s",
      invalidMessage: null,
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://control.example.com/v1/device/register");
    // Without server_time the local clock seeds trusted time.
    const state = readState();
    expect(state.source).toBe("control-plane-register");
    expect(Math.abs(state.trusted_epoch - nowSeconds())).toBeLessThanOrEqual(2);
  });
});

describe("loadLocalLicense", () => {
  it("returns a stored license that verifies and is current", async () => {
    storeOfflineLicense(0);
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({
      valid: true,
      plan: "enterprise",
      source: "offline-local",
      message: "",
    });
  });

  it("marks a stored license past its grace period as expired", async () => {
    storeOfflineLicense(nowSeconds() - 20 * DAY_SECONDS);
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({
      valid: false,
      plan: "enterprise",
      message: "License expired - run `algenta login` to renew.",
    });
  });

  it("keeps a stored license valid inside its grace period with a renewal hint", async () => {
    storeOfflineLicense(nowSeconds() - DAY_SECONDS);
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({
      valid: true,
      message: "License in grace period - run `algenta login` to renew.",
    });
  });

  it("ignores a stored token that no configured key verifies", async () => {
    storeOfflineLicense(0);
    delete process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY;
    await expect(loadLocalLicense("")).resolves.toMatchObject({ valid: false, message: NO_STORED_LICENSE });
  });

  it("requires provisioning when the profile mandates a local license", async () => {
    process.env.ALGENTA_REQUIRE_LOCAL_LICENSE = "1";
    vi.stubGlobal("fetch", vi.fn());
    const license = await loadLocalLicense("de_test_abcdefghijkl");
    expect(license.valid).toBe(false);
    expect(license.message).toContain("Provision an offline license file before startup.");
    expect(license.apiKeyPrefix).toBe("de_test_abcd");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("exchanges the API key, stores the token and returns the parsed license", async () => {
    const { token, publicKey } = issueOfflineLocalLicense(0);
    process.env.ALGENTA_LOCAL_LICENSE_PUBLIC_KEY = publicKey;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, { license_token: token, server_time: nowSeconds() })));
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({ valid: true, source: "offline-local" });
    expect(readFileSync(runtimeLicensePath(), "utf8")).toBe(token);
  });

  it("stores but rejects an exchanged token that no configured key verifies", async () => {
    const { token } = issueOfflineLocalLicense(0);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, { license_token: token })));
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({
      valid: false,
      message: REGISTRATION_FAILED,
    });
    expect(readFileSync(runtimeLicensePath(), "utf8")).toBe(token);
  });

  it("propagates the exchange failure message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(402, { detail: { message: "Too many devices." } })));
    await expect(loadLocalLicense("de_test_key")).resolves.toMatchObject({ valid: false, message: "Too many devices." });
    expect(existsSync(runtimeLicensePath())).toBe(false);
  });

  it("asks for a login when nothing is stored and no API key is available", async () => {
    vi.stubGlobal("fetch", vi.fn());
    await expect(loadLocalLicense("")).resolves.toMatchObject({ valid: false, message: NO_STORED_LICENSE });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("supportsColor", () => {
  it("is disabled by NO_COLOR", () => {
    process.env.NO_COLOR = "1";
    expect(withStdoutTty(true, () => supportsColor())).toBe(false);
  });

  it("is disabled by a dumb terminal", () => {
    process.env.TERM = "dumb";
    expect(withStdoutTty(true, () => supportsColor())).toBe(false);
  });

  it("follows stdout.isTTY otherwise", () => {
    process.env.TERM = "xterm-256color";
    expect(withStdoutTty(true, () => supportsColor())).toBe(true);
    expect(withStdoutTty(false, () => supportsColor())).toBe(false);
  });

  it("is disabled on hosts without a usable process global", () => {
    expect(withGlobalProcess(undefined, () => supportsColor())).toBe(false);
    expect(withGlobalProcess({}, () => supportsColor())).toBe(false);
  });
});

describe("runtimeBanner", () => {
  const PLAIN_ART = TITLE_ART.join("\n");
  const PLAIN_BORDER = `+${"-".repeat(60)}+`;
  const plainRow = (text: string): string => `| ${text.padEnd(58, " ")} |`;
  const COLOR_ART = TITLE_ART.map((segment, index) => `${TITLE_COLORS[index]}${segment}${RESET}`).join("\n");
  const COLOR_HEADER = `${MUTED}\u250c${"\u2500".repeat(60)}\u2510${RESET}`;
  const COLOR_FOOTER = `${MUTED}\u2514${"\u2500".repeat(60)}\u2518${RESET}`;
  const colorTitle = (title: string): string =>
    `${MUTED}\u2502${RESET} ${ACCENT}${title}${RESET}${" ".repeat(Math.max(0, 59 - title.length))}${MUTED}\u2502${RESET}`;
  const colorRow = (text: string): string => `${MUTED}\u2502${RESET} ${text.padEnd(58, " ")} ${MUTED}\u2502${RESET}`;

  it("renders a plain box, trimming trailing whitespace on detail lines", () => {
    expect(runtimeBanner("Algenta", ["first", "second   "], false)).toBe(
      [PLAIN_ART, PLAIN_BORDER, plainRow("Algenta"), plainRow("first"), plainRow("second"), PLAIN_BORDER].join("\n"),
    );
  });

  it("truncates over-long plain titles and lines to the box width", () => {
    expect(runtimeBanner("T".repeat(70), ["L".repeat(70)], false)).toBe(
      [PLAIN_ART, PLAIN_BORDER, plainRow("T".repeat(58)), plainRow("L".repeat(58)), PLAIN_BORDER].join("\n"),
    );
  });

  it("renders exactly one blank detail row when there are no lines", () => {
    expect(runtimeBanner("Algenta", [], false)).toBe(
      [PLAIN_ART, PLAIN_BORDER, plainRow("Algenta"), plainRow(""), PLAIN_BORDER].join("\n"),
    );
  });

  it("renders an ANSI box when color is enabled", () => {
    expect(runtimeBanner("Algenta", ["first"], true)).toBe(
      [COLOR_ART, COLOR_HEADER, colorTitle("Algenta"), colorRow("first"), COLOR_FOOTER].join("\n"),
    );
  });

  it("keeps a long colored title unpadded and truncates long colored lines", () => {
    const title = "T".repeat(70);
    expect(runtimeBanner(title, ["L".repeat(70)], true)).toBe(
      [COLOR_ART, COLOR_HEADER, colorTitle(title), colorRow("L".repeat(58)), COLOR_FOOTER].join("\n"),
    );
  });

  it("defaults the color flag to supportsColor()", () => {
    process.env.NO_COLOR = "1";
    expect(runtimeBanner("Algenta", ["first"])).toBe(runtimeBanner("Algenta", ["first"], false));
  });
});

describe("normalizeText", () => {
  it.each<[string | null | undefined, string]>([
    [null, ""],
    [undefined, ""],
    ["", ""],
    ["  Net Sales (excl. tax)  ", "net sales excl tax"],
    ["Order__ID", "order id"],
    ["ALREADY normal", "already normal"],
  ])("normalizes %j", (value, expected) => {
    expect(normalizeText(value)).toBe(expected);
  });
});
