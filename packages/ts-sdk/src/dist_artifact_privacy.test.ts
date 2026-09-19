// SPDX-License-Identifier: Apache-2.0
import { createRequire } from "node:module";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

const requireModule = createRequire(import.meta.url);
const ORIGINAL_ENV = { ...process.env };

function loadFresh<T>(modulePath: string): T {
  const resolved = requireModule.resolve(modulePath);
  delete requireModule.cache[resolved];
  return requireModule(resolved) as T;
}

beforeEach(() => {
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
  delete process.env.ALGENTA_BASE_URL;
  delete process.env.DE_BASE_URL;
  delete process.env.ALGENTA_API_URL;
  delete process.env.ALGENTA_APP_BASE_URL;
  delete process.env.APP_BASE_URL;
  delete process.env.DE_APP_BASE_URL;
});

afterEach(() => {
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("dist artifact privacy contract", () => {
  it("blocks Algenta-owned cloud defaults in dist privacy profile helpers", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const privacy = loadFresh<{
      resolveClientBaseUrl(explicitBaseUrl: string | undefined, component: string): string;
    }>("../dist/privacy_profile.js");

    try {
      privacy.resolveClientBaseUrl(undefined, "dist client");
      throw new Error("expected dist privacy profile helper to fail closed");
    } catch (error) {
      expect(String(error)).toContain("private profiles cannot target Algenta-owned cloud URLs");
      expect(String(error)).toContain("ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL");
    }
    expect(privacy.resolveClientBaseUrl("http://localhost:8000", "dist client")).toBe(
      "http://localhost:8000",
    );
    process.env.ALGENTA_API_URL = "http://localhost:8000";
    expect(privacy.resolveClientBaseUrl(undefined, "dist client")).toBe("http://localhost:8000");
  });

  it("requires an explicit dashboard or api origin in dist private-profile console helpers", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";

    const privacy = loadFresh<{
      resolveConsoleBaseUrl(component: string, fallbackBaseUrl?: string): string;
    }>("../dist/privacy_profile.js");

    expect(() => privacy.resolveConsoleBaseUrl("dist client")).toThrow(
      /explicit self-hosted dashboard or API baseUrl/,
    );

    process.env.DE_APP_BASE_URL = "https://console.customer.internal";
    expect(privacy.resolveConsoleBaseUrl("dist client")).toBe("https://console.customer.internal");
  });

  it("rejects Algenta-owned dashboard aliases in dist private-profile console helpers", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_APP_BASE_URL = "https://app.algenta.ai";

    const privacy = loadFresh<{
      resolveConsoleBaseUrl(component: string, fallbackBaseUrl?: string): string;
    }>("../dist/privacy_profile.js");

    expect(() => privacy.resolveConsoleBaseUrl("dist client")).toThrow(
      /ALGENTA_APP_BASE_URL \/ APP_BASE_URL \/ DE_APP_BASE_URL or a self-hosted baseUrl/,
    );
  });

  it("blocks dist DecisionEngineClient and AlgentaClient when private profiles lack a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const client = loadFresh<{
      DecisionEngineClient: new (config?: { apiKey?: string; baseUrl?: string }) => unknown;
      AlgentaClient: new (config?: { apiKey?: string; baseUrl?: string }) => unknown;
    }>("../dist/client.js");

    expect(() => new client.DecisionEngineClient({ apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
    expect(() => new client.AlgentaClient({ apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
  });

  it("blocks dist Runtime api mode when private profiles lack a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const runtimeModule = loadFresh<{
      Runtime: new (config?: { mode?: string; apiKey?: string; baseUrl?: string }) => unknown;
    }>("../dist/runtime.js");

    expect(() => new runtimeModule.Runtime({ mode: "api", apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
  });

  it("allows dist Runtime self_hosted mode with an explicit private baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const runtimeModule = loadFresh<{
      Runtime: new (config?: { mode?: string; apiKey?: string; baseUrl?: string }) => {
        baseUrl?: string;
      };
    }>("../dist/runtime.js");

    const runtime = new runtimeModule.Runtime({
      mode: "self_hosted",
      apiKey: "de_live_dist_key",
      baseUrl: "http://localhost:8000",
    });

    expect(runtime.baseUrl).toBe("http://localhost:8000");
  });

  it("blocks package entrypoint exports when private profiles lack a self-hosted baseUrl", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";

    const sdk = loadFresh<{
      AlgentaClient: new (config?: { apiKey?: string; baseUrl?: string }) => unknown;
      DecisionEngineClient: new (config?: { apiKey?: string; baseUrl?: string }) => unknown;
      Runtime: new (config?: { mode?: string; apiKey?: string; baseUrl?: string }) => unknown;
    }>("../dist/index.js");

    expect(() => new sdk.AlgentaClient({ apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
    expect(() => new sdk.DecisionEngineClient({ apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
    expect(() => new sdk.Runtime({ mode: "api", apiKey: "de_live_dist_key" })).toThrowError(
      /private profiles cannot target Algenta-owned cloud URLs/,
    );
  });

  it("uses DE_* compatibility guidance in dist client and runtime missing-key errors", async () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_BASE_URL = "http://localhost:8000";

    const sdk = loadFresh<{
      DecisionEngineClient: new (config?: { apiKey?: string; baseUrl?: string }) => unknown;
      Runtime: new (config?: { mode?: string; apiKey?: string; baseUrl?: string }) => {
        resolve(request: Record<string, unknown>): Promise<unknown>;
      };
    }>("../dist/index.js");

    try {
      new sdk.DecisionEngineClient({ baseUrl: "http://localhost:8000" });
      throw new Error("expected dist DecisionEngineClient to require an API key");
    } catch (error) {
      expect(String(error)).toContain("ALGENTA_API_KEY / DE_API_KEY environment variables");
    }

    const runtime = new sdk.Runtime({ mode: "api" });
    await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toThrow(
      "ALGENTA_API_KEY / DE_API_KEY",
    );
  });

  it("exposes dist usage() and validates the payload shape", async () => {
    const clientModule = loadFresh<{
      DecisionEngineClient: new (config?: { apiKey?: string; baseUrl?: string }) => {
        usage(): Promise<unknown>;
        request(method: string, path: string): Promise<unknown>;
      };
    }>("../dist/client.js");

    const client = new clientModule.DecisionEngineClient({
      apiKey: "de_live_dist_key",
      baseUrl: "http://localhost:8000",
    });
    client.request = async (method: string, path: string) => {
      expect(method).toBe("GET");
      expect(path).toBe("/v1/usage");
      return {
        org_id: "org_123",
        billing_period: "2026-05",
        simulations_run: 12,
        api_calls: 34,
        quota_limit: 100,
        quota_used_pct: 34,
      };
    };

    await expect(client.usage()).resolves.toEqual({
      org_id: "org_123",
      billing_period: "2026-05",
      simulations_run: 12,
      api_calls: 34,
      quota_limit: 100,
      quota_used_pct: 34,
    });
  });

  it("exposes dist limits() and rejects invalid payloads", async () => {
    const clientModule = loadFresh<{
      DecisionEngineClient: new (config?: { apiKey?: string; baseUrl?: string }) => {
        limits(): Promise<unknown>;
        request(method: string, path: string): Promise<unknown>;
      };
    }>("../dist/client.js");

    const client = new clientModule.DecisionEngineClient({
      apiKey: "de_live_dist_key",
      baseUrl: "http://localhost:8000",
    });
    client.request = async (method: string, path: string) => {
      expect(method).toBe("GET");
      expect(path).toBe("/v1/limits");
      return {
        plan: "enterprise",
        simulations_per_month: 1000,
        rate_limit_per_minute: -1,
      };
    };

    await expect(client.limits()).rejects.toThrowError(
      /Limits response has an invalid rate_limit_per_minute/,
    );
  });
});
