// SPDX-License-Identifier: Apache-2.0
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DEFAULT_BASE_URL } from "./contract.js";
import {
  apiKeyHelpText,
  cloudDisabled,
  isAlgentaOwnedBaseUrl,
  normalizeBaseUrl,
  privateProfileEnabled,
  resolveApiKeysUrl,
  resolveClientBaseUrl,
  resolveConsoleBaseUrl,
} from "./privacy_profile.js";

const ORIGINAL_ENV = { ...process.env };

const PROFILE_ENV_VARS = [
  "ALGENTA_DEPLOYMENT_MODE",
  "ALGENTA_DISABLE_CLOUD",
  "ALGENTA_BASE_URL",
  "DE_BASE_URL",
  "ALGENTA_API_URL",
  "ALGENTA_APP_BASE_URL",
  "APP_BASE_URL",
  "DE_APP_BASE_URL",
] as const;

const COMPONENT = "DecisionEngineClient";
const DEFAULT_CONSOLE_URL = "https://app.algenta.ai";
const OWNED_CLOUD_ERROR = `${COMPONENT} private profiles cannot target Algenta-owned cloud URLs.`;

beforeEach(() => {
  for (const key of PROFILE_ENV_VARS) {
    delete process.env[key];
  }
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("cloudDisabled", () => {
  it.each(["1", "true", "YES", " on "])("treats ALGENTA_DISABLE_CLOUD=%j as disabled", (value) => {
    process.env.ALGENTA_DISABLE_CLOUD = value;
    expect(cloudDisabled()).toBe(true);
  });

  it.each(["0", "false", "No", " OFF "])("treats ALGENTA_DISABLE_CLOUD=%j as enabled", (value) => {
    process.env.ALGENTA_DISABLE_CLOUD = value;
    // An explicit false wins over a private deployment mode.
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    expect(cloudDisabled()).toBe(false);
  });

  it.each(["maybe", "2", "enabled"])("rejects the non-boolean value %j", (value) => {
    process.env.ALGENTA_DISABLE_CLOUD = value;
    expect(() => cloudDisabled()).toThrowError(
      "ALGENTA_DISABLE_CLOUD must be a boolean-style value when set.",
    );
  });

  it.each(["", "   "])("treats a blank value %j as unset", (value) => {
    process.env.ALGENTA_DISABLE_CLOUD = value;
    expect(cloudDisabled()).toBe(false);
  });

  it("falls back to the deployment mode when unset", () => {
    expect(cloudDisabled()).toBe(false);
    process.env.ALGENTA_DEPLOYMENT_MODE = "Air_Gapped";
    expect(cloudDisabled()).toBe(true);
    process.env.ALGENTA_DEPLOYMENT_MODE = "vpc";
    expect(cloudDisabled()).toBe(false);
  });
});

describe("privateProfileEnabled", () => {
  it("is false in the default saas profile", () => {
    expect(privateProfileEnabled()).toBe(false);
  });

  it("is true for a private deployment mode or an explicit cloud opt-out", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    expect(privateProfileEnabled()).toBe(true);
    delete process.env.ALGENTA_DEPLOYMENT_MODE;
    process.env.ALGENTA_DISABLE_CLOUD = "true";
    expect(privateProfileEnabled()).toBe(true);
  });
});

describe("normalizeBaseUrl", () => {
  it("trims whitespace and trailing slashes", () => {
    expect(normalizeBaseUrl("  https://engine.customer.internal///  ", COMPONENT)).toBe(
      "https://engine.customer.internal",
    );
    expect(normalizeBaseUrl("http://localhost:8080/api", COMPONENT)).toBe(
      "http://localhost:8080/api",
    );
  });

  it.each(["engine.customer.internal", "not a url", "", "file:///var/algenta"])(
    "rejects %j as missing scheme or host",
    (value) => {
      expect(() => normalizeBaseUrl(value, `${COMPONENT} console`)).toThrowError(
        `${COMPONENT} console baseUrl must be an absolute URL including scheme and host.`,
      );
    },
  );
});

describe("isAlgentaOwnedBaseUrl", () => {
  it.each([
    { url: "https://api.algenta.ai", owned: true },
    { url: "https://APP.Algenta.AI/", owned: true },
    { url: "https://tenant.algenta.io/v1", owned: true },
    { url: "https://engine.customer.internal", owned: false },
    { url: "https://algenta.ai.example.com", owned: false },
  ])("classifies $url as owned=$owned", ({ url, owned }) => {
    expect(isAlgentaOwnedBaseUrl(url)).toBe(owned);
  });
});

describe("resolveClientBaseUrl", () => {
  it("defaults to the Algenta API in the saas profile", () => {
    expect(resolveClientBaseUrl(undefined, COMPONENT)).toBe(DEFAULT_BASE_URL);
  });

  it.each([
    { key: "ALGENTA_BASE_URL", value: "https://a.customer.internal/" },
    { key: "DE_BASE_URL", value: "https://b.customer.internal" },
    { key: "ALGENTA_API_URL", value: "https://c.customer.internal" },
  ])("reads $key when no explicit baseUrl is given", ({ key, value }) => {
    process.env[key] = value;
    expect(resolveClientBaseUrl(undefined, COMPONENT)).toBe(value.replace(/\/$/, ""));
  });

  it("prefers the explicit baseUrl over the environment", () => {
    process.env.ALGENTA_BASE_URL = "https://env.customer.internal";
    expect(resolveClientBaseUrl("https://explicit.customer.internal/", COMPONENT)).toBe(
      "https://explicit.customer.internal",
    );
  });

  it("fails closed when a private profile would reach Algenta cloud", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    expect(() => resolveClientBaseUrl(undefined, COMPONENT)).toThrowError(
      `${OWNED_CLOUD_ERROR} Configure a self-hosted baseUrl or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.`,
    );
    expect(resolveClientBaseUrl("https://engine.customer.internal", COMPONENT)).toBe(
      "https://engine.customer.internal",
    );
  });
});

describe("resolveConsoleBaseUrl", () => {
  it("returns the hosted console in the saas profile without configuration", () => {
    expect(resolveConsoleBaseUrl(COMPONENT)).toBe(DEFAULT_CONSOLE_URL);
    // A saas fallback baseUrl is irrelevant; the hosted console still wins.
    expect(resolveConsoleBaseUrl(COMPONENT, "https://engine.customer.internal")).toBe(
      DEFAULT_CONSOLE_URL,
    );
  });

  it.each([
    { key: "ALGENTA_APP_BASE_URL", value: "https://console-a.customer.internal/" },
    { key: "APP_BASE_URL", value: "https://console-b.customer.internal" },
  ])("normalizes a configured $key in the saas profile", ({ key, value }) => {
    process.env[key] = value;
    expect(resolveConsoleBaseUrl(COMPONENT)).toBe(value.replace(/\/$/, ""));
  });

  it("lets the saas profile point the console at Algenta-owned hosts", () => {
    process.env.ALGENTA_APP_BASE_URL = "https://app.algenta.ai/";
    expect(resolveConsoleBaseUrl(COMPONENT)).toBe("https://app.algenta.ai");
  });

  it("rejects a configured console URL that is not absolute", () => {
    process.env.ALGENTA_APP_BASE_URL = "console.customer.internal";
    expect(() => resolveConsoleBaseUrl(COMPONENT)).toThrowError(
      `${COMPONENT} console baseUrl must be an absolute URL including scheme and host.`,
    );
  });

  it("accepts a self-hosted fallback baseUrl in a private profile", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    expect(resolveConsoleBaseUrl(COMPONENT, "https://engine.customer.internal/")).toBe(
      "https://engine.customer.internal",
    );
  });

  it("rejects an Algenta-owned fallback baseUrl in a private profile", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    expect(() => resolveConsoleBaseUrl(COMPONENT, "https://api.algenta.ai")).toThrowError(
      `${OWNED_CLOUD_ERROR} Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted baseUrl.`,
    );
  });

  it("rejects a fallback baseUrl that is not absolute in a private profile", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "on";
    expect(() => resolveConsoleBaseUrl(COMPONENT, "engine.customer.internal")).toThrowError(
      `${COMPONENT} console baseUrl must be an absolute URL including scheme and host.`,
    );
  });

  it.each([
    { key: "ALGENTA_BASE_URL", value: "https://api-a.customer.internal" },
    { key: "DE_BASE_URL", value: "https://api-b.customer.internal" },
    { key: "ALGENTA_API_URL", value: "https://api-c.customer.internal/" },
  ])("falls back to $key when no console or fallback baseUrl is given", ({ key, value }) => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env[key] = value;
    expect(resolveConsoleBaseUrl(COMPONENT)).toBe(value.replace(/\/$/, ""));
  });

  it("prefers the explicit fallback over the API environment variables", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_BASE_URL = "https://env.customer.internal";
    expect(resolveConsoleBaseUrl(COMPONENT, "https://explicit.customer.internal")).toBe(
      "https://explicit.customer.internal",
    );
  });
});

describe("resolveApiKeysUrl", () => {
  it("joins the dashboard path onto the resolved console", () => {
    expect(resolveApiKeysUrl(COMPONENT)).toBe(`${DEFAULT_CONSOLE_URL}/dashboard/api-keys`);
    process.env.ALGENTA_APP_BASE_URL = "https://console.customer.internal/";
    expect(resolveApiKeysUrl(COMPONENT)).toBe(
      "https://console.customer.internal/dashboard/api-keys",
    );
  });

  it("uses the private-profile fallback baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    expect(resolveApiKeysUrl(COMPONENT, "https://engine.customer.internal")).toBe(
      "https://engine.customer.internal/dashboard/api-keys",
    );
  });
});

describe("apiKeyHelpText", () => {
  it("points saas users at the hosted dashboard", () => {
    expect(apiKeyHelpText(COMPONENT)).toBe(
      `Get a key at: ${DEFAULT_CONSOLE_URL}/dashboard/api-keys`,
    );
  });

  it("points private profiles without a console at their admin surface", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    expect(apiKeyHelpText(COMPONENT, "https://engine.customer.internal")).toBe(
      "Create a key from your self-hosted admin surface or API base URL: https://engine.customer.internal",
    );
  });

  it("uses the dashboard path when a private profile configures a console", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.DE_APP_BASE_URL = "https://console.customer.internal";
    expect(apiKeyHelpText(COMPONENT)).toBe(
      "Get a key at: https://console.customer.internal/dashboard/api-keys",
    );
  });

  it("fails closed when a private profile has nowhere to send the user", () => {
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    expect(() => apiKeyHelpText(COMPONENT)).toThrowError(
      `${COMPONENT} private profiles require an explicit self-hosted dashboard or API baseUrl.`,
    );
  });
});
