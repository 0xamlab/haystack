import { describe, expect, it } from "vitest";

import { INTEGRATIONS } from "./contract.js";
import {
  expectManifestBackedIntegrationExportTextsEqual,
  expectManifestBackedIntegrationsEqual,
} from "./test_contract_helpers.js";

function cloneManifestBackedIntegrations() {
  return INTEGRATIONS.map((entry) => ({
    ...entry,
    capabilities: [...entry.capabilities],
    required_scopes: [...entry.required_scopes],
    write_actions: [...entry.write_actions],
    admin_controls: [...entry.admin_controls],
    regions: [...entry.regions],
  }));
}

describe("test contract helpers", () => {
  it("normalizes copied manifest-backed integrations before comparing", () => {
    expectManifestBackedIntegrationsEqual(cloneManifestBackedIntegrations(), INTEGRATIONS);
  });

  it("fails closed when a copied integration payload drifts from the manifest", () => {
    const mismatchedIntegrations = cloneManifestBackedIntegrations();
    mismatchedIntegrations[0] = {
      ...mismatchedIntegrations[0],
      status: "deprecated",
    };

    expect(() =>
      expectManifestBackedIntegrationsEqual(mismatchedIntegrations, INTEGRATIONS),
    ).toThrowError();
  });

  it("fails closed when the left-hand integration payload is empty", () => {
    expect(() => expectManifestBackedIntegrationsEqual([], INTEGRATIONS)).toThrowError();
  });

  it("fails closed when the right-hand integration payload is empty", () => {
    expect(() => expectManifestBackedIntegrationsEqual(INTEGRATIONS, [])).toThrowError();
  });

  it("accepts matching drifted integration payloads in the two-sided parity helper", () => {
    const leftDriftedIntegrations = cloneManifestBackedIntegrations();
    leftDriftedIntegrations[0] = {
      ...leftDriftedIntegrations[0],
      status: "deprecated",
    };
    const rightDriftedIntegrations = cloneManifestBackedIntegrations();
    rightDriftedIntegrations[0] = {
      ...rightDriftedIntegrations[0],
      status: "deprecated",
    };

    expectManifestBackedIntegrationsEqual(leftDriftedIntegrations, rightDriftedIntegrations);
  });

  it("accepts matching ESM and CommonJS integration exports", () => {
    const payload = JSON.stringify(INTEGRATIONS);

    expectManifestBackedIntegrationExportTextsEqual(
      `export const INTEGRATIONS = ${payload};`,
      `exports.INTEGRATIONS = ${payload};`,
    );
  });

  it("accepts identical integration export texts", () => {
    const payload = JSON.stringify(INTEGRATIONS);
    const text = `export const INTEGRATIONS = ${payload};`;

    expectManifestBackedIntegrationExportTextsEqual(text, text);
  });

  it("rejects identical drifted integration export texts because the left-hand export must stay canonical", () => {
    const driftedIntegrations = cloneManifestBackedIntegrations();
    driftedIntegrations[0] = {
      ...driftedIntegrations[0],
      status: "deprecated",
    };
    const text = `export const INTEGRATIONS = ${JSON.stringify(driftedIntegrations)};`;

    expect(() => expectManifestBackedIntegrationExportTextsEqual(text, text)).toThrowError();
  });

  it("fails closed when an integration export is missing", () => {
    const payload = JSON.stringify(INTEGRATIONS);

    expect(() =>
      expectManifestBackedIntegrationExportTextsEqual(
        `export const INTEGRATIONS = ${payload};`,
        "export const CONTRACT_VERSION = '2026.05.0';",
      ),
    ).toThrowError("missing exported INTEGRATIONS array");
  });

  it("fails closed when the left-hand integration export is missing", () => {
    const payload = JSON.stringify(INTEGRATIONS);

    expect(() =>
      expectManifestBackedIntegrationExportTextsEqual(
        "export const CONTRACT_VERSION = '2026.05.0';",
        `exports.INTEGRATIONS = ${payload};`,
      ),
    ).toThrowError("missing exported INTEGRATIONS array");
  });

  it("rejects matching drifted integration export payloads because the left-hand export must stay canonical", () => {
    const leftDriftedIntegrations = cloneManifestBackedIntegrations();
    leftDriftedIntegrations[0] = {
      ...leftDriftedIntegrations[0],
      status: "deprecated",
    };
    const rightDriftedIntegrations = cloneManifestBackedIntegrations();
    rightDriftedIntegrations[0] = {
      ...rightDriftedIntegrations[0],
      status: "deprecated",
    };

    expect(() =>
      expectManifestBackedIntegrationExportTextsEqual(
        `export const INTEGRATIONS = ${JSON.stringify(leftDriftedIntegrations)};`,
        `exports.INTEGRATIONS = ${JSON.stringify(rightDriftedIntegrations)};`,
      ),
    ).toThrowError();
  });

  it("fails closed when an integration export payload drifts from the manifest", () => {
    const mismatchedIntegrations = cloneManifestBackedIntegrations();
    mismatchedIntegrations[0] = {
      ...mismatchedIntegrations[0],
      status: "deprecated",
    };

    expect(() =>
      expectManifestBackedIntegrationExportTextsEqual(
        `export const INTEGRATIONS = ${JSON.stringify(INTEGRATIONS)};`,
        `exports.INTEGRATIONS = ${JSON.stringify(mismatchedIntegrations)};`,
      ),
    ).toThrowError();
  });
});
