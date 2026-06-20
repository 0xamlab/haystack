import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { resolveConsoleBaseUrl } from "./privacy_profile.js";

const ORIGINAL_ENV = { ...process.env };

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

describe("privacy profile console baseUrl contract", () => {
  it("requires an explicit dashboard or api origin in private profiles", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";

    expect(() => resolveConsoleBaseUrl("DecisionEngineClient")).toThrow(
      "explicit self-hosted dashboard or API baseUrl",
    );
  });

  it("accepts DE_APP_BASE_URL in private profiles", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "air_gapped";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.DE_APP_BASE_URL = "https://console.customer.internal";

    expect(resolveConsoleBaseUrl("DecisionEngineClient")).toBe(
      "https://console.customer.internal",
    );
  });

  it("rejects Algenta-owned dashboard aliases in private profiles with explicit app-base guidance", () => {
    process.env.ALGENTA_DEPLOYMENT_MODE = "self_hosted";
    process.env.ALGENTA_DISABLE_CLOUD = "1";
    process.env.ALGENTA_APP_BASE_URL = "https://app.algenta.ai";

    expect(() => resolveConsoleBaseUrl("DecisionEngineClient")).toThrow(
      "ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or a self-hosted baseUrl",
    );
  });
});
