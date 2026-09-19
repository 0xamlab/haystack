// SPDX-License-Identifier: Apache-2.0
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import * as sourceClientModule from "./client.js";
import * as sourceContractModule from "./contract.js";
import * as sourceIndexModule from "./index.js";
import * as sourceRuntimeModule from "./runtime.js";
import {
  expectManifestBackedIntegrationExportTextsEqual,
  expectManifestBackedIntegrationsEqual,
} from "./test_contract_helpers.js";

const requireModule = createRequire(import.meta.url);

function ownMethodNames(value: object): string[] {
  return Object.entries(Object.getOwnPropertyDescriptors(value))
    .filter(([name]) => name !== "constructor")
    .filter(([, descriptor]) => {
      if (typeof descriptor.value === "function") {
        return true;
      }
      return typeof descriptor.get === "function" || typeof descriptor.set === "function";
    })
    .map(([name]) => name)
    .sort();
}

describe("dist artifact parity", () => {
  it("keeps the package root export keys aligned with source", () => {
    const distIndexModule = requireModule("../dist/index.js") as Record<string, unknown>;

    expect(Object.keys(distIndexModule).sort()).toEqual(Object.keys(sourceIndexModule).sort());
  });

  it("keeps the client module export keys aligned with source", () => {
    const distClientModule = requireModule("../dist/client.js") as Record<string, unknown>;

    expect(Object.keys(distClientModule).sort()).toEqual(Object.keys(sourceClientModule).sort());
  });

  it("keeps the runtime module export keys aligned with source", () => {
    const distRuntimeModule = requireModule("../dist/runtime.js") as Record<string, unknown>;

    expect(Object.keys(distRuntimeModule).sort()).toEqual(Object.keys(sourceRuntimeModule).sort());
  });

  it("keeps the contract module values aligned with source", () => {
    const distContractModule = requireModule("../dist/contract.js") as typeof sourceContractModule;
    const sourceContractText = readFileSync(resolve(__dirname, "contract.ts"), "utf8");
    const distContractText = readFileSync(resolve(__dirname, "../dist/contract.js"), "utf8");

    expect(distContractModule.CONTRACT_VERSION).toBe(sourceContractModule.CONTRACT_VERSION);
    expect(distContractModule.BRAND).toBe(sourceContractModule.BRAND);
    expect(distContractModule.DEFAULT_BASE_URL).toBe(sourceContractModule.DEFAULT_BASE_URL);
    expect(distContractModule.MCP_ENDPOINT).toBe(sourceContractModule.MCP_ENDPOINT);
    expect(distContractModule.MCP_TOOLS_ENDPOINT).toBe(sourceContractModule.MCP_TOOLS_ENDPOINT);
    expect(distContractModule.AUTH_SCHEME).toBe(sourceContractModule.AUTH_SCHEME);
    expect(distContractModule.API_KEY_PREFIX_LIVE).toBe(sourceContractModule.API_KEY_PREFIX_LIVE);
    expect(distContractModule.API_KEY_PREFIX_TEST).toBe(sourceContractModule.API_KEY_PREFIX_TEST);
    expect(distContractModule.LEGACY_HEADERS).toEqual(sourceContractModule.LEGACY_HEADERS);
    expect(distContractModule.LEGACY_ENV_VARS).toEqual(sourceContractModule.LEGACY_ENV_VARS);
    expect(distContractModule.LEGACY_DOMAINS).toEqual(sourceContractModule.LEGACY_DOMAINS);
    expect(distContractModule.DEPRECATION_WINDOW_DAYS).toBe(
      sourceContractModule.DEPRECATION_WINDOW_DAYS,
    );
    expect(distContractModule.READ_ONLY_DEFAULT).toBe(sourceContractModule.READ_ONLY_DEFAULT);
    expect(distContractModule.WRITE_CONFIRMATION_REQUIRED).toBe(
      sourceContractModule.WRITE_CONFIRMATION_REQUIRED,
    );
    expect(distContractModule.PLAN_LIMITS).toEqual(sourceContractModule.PLAN_LIMITS);
    expectManifestBackedIntegrationExportTextsEqual(distContractText, sourceContractText);
    expectManifestBackedIntegrationsEqual(
      distContractModule.INTEGRATIONS,
      sourceContractModule.INTEGRATIONS,
    );
    expect(distContractModule.PRIMARY_DATA_QUERY_CONTRACT).toEqual(
      sourceContractModule.PRIMARY_DATA_QUERY_CONTRACT,
    );
  });

  it("keeps DecisionEngineClient prototype methods aligned with source", () => {
    const distClientModule = requireModule("../dist/client.js") as typeof sourceClientModule;

    expect(ownMethodNames(distClientModule.DecisionEngineClient.prototype)).toEqual(
      ownMethodNames(sourceClientModule.DecisionEngineClient.prototype),
    );
  });

  it("keeps DecisionEngineError prototype methods aligned with source", () => {
    const distClientModule = requireModule("../dist/client.js") as typeof sourceClientModule;

    expect(ownMethodNames(distClientModule.DecisionEngineError.prototype)).toEqual(
      ownMethodNames(sourceClientModule.DecisionEngineError.prototype),
    );
  });

  it("keeps Runtime prototype methods aligned with source", () => {
    const distRuntimeModule = requireModule("../dist/runtime.js") as typeof sourceRuntimeModule;

    expect(ownMethodNames(distRuntimeModule.Runtime.prototype)).toEqual(
      ownMethodNames(sourceRuntimeModule.Runtime.prototype),
    );
  });

  it("keeps RuntimeError prototype methods aligned with source", () => {
    const distRuntimeModule = requireModule("../dist/runtime.js") as typeof sourceRuntimeModule;

    expect(ownMethodNames(distRuntimeModule.RuntimeError.prototype)).toEqual(
      ownMethodNames(sourceRuntimeModule.RuntimeError.prototype),
    );
  });
});
