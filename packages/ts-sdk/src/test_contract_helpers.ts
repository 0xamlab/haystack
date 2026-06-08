import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect } from "vitest";

type ManifestBackedIntegration = {
  name: string;
  description: string;
  icon: string;
  capabilities: string[];
  auth_scheme: string;
  required_scopes: string[];
  read_only_default: boolean;
  write_actions: string[];
  admin_controls: string[];
  docs_url: string;
  privacy_url: string;
  terms_url: string;
  support_url: string;
  regions: string[];
  status: string;
};

const MANIFEST_BACKED_INTEGRATIONS = JSON.parse(
  readFileSync(resolve(__dirname, "../../../tests/manifest_backed_integrations.fixture.json"), "utf8"),
) as ManifestBackedIntegration[];

function normalizeManifestBackedValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeManifestBackedValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, normalizeManifestBackedValue(entry)]),
    );
  }
  return value;
}

function normalizeManifestBackedIntegrations(
  integrations: ManifestBackedIntegration[],
): ManifestBackedIntegration[] {
  const fields = Object.keys(MANIFEST_BACKED_INTEGRATIONS[0]) as Array<keyof ManifestBackedIntegration>;
  return integrations.map((entry) =>
    Object.fromEntries(
      fields.map((field) => [
        field,
        normalizeManifestBackedValue(entry[field]),
      ]),
    ),
  ) as ManifestBackedIntegration[];
}

function normalizeOrReuseManifestBackedIntegrations(
  integrations: ManifestBackedIntegration[],
): ManifestBackedIntegration[] {
  return integrations === MANIFEST_BACKED_INTEGRATIONS
    ? MANIFEST_BACKED_INTEGRATIONS
    : normalizeManifestBackedIntegrations(integrations);
}

export function expectManifestBackedIntegrationsEqual(
  leftIntegrations: ManifestBackedIntegration[],
  rightIntegrations: ManifestBackedIntegration[],
): void {
  const normalizedLeftIntegrations = normalizeOrReuseManifestBackedIntegrations(leftIntegrations);
  const normalizedRightIntegrations =
    rightIntegrations === leftIntegrations
      ? normalizedLeftIntegrations
      : normalizeOrReuseManifestBackedIntegrations(rightIntegrations);
  expect(normalizedLeftIntegrations).toEqual(normalizedRightIntegrations);
}

export function expectManifestBackedIntegrationExportTextsEqual(
  leftText: string,
  rightText: string,
): void {
  const leftMatch = leftText.match(
    /(?:export const INTEGRATIONS =|exports\.INTEGRATIONS =)\s*(\[[\s\S]*?\]);/,
  );
  expect(leftMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();
  const leftIntegrations = JSON.parse(leftMatch![1]) as ManifestBackedIntegration[];
  expectManifestBackedIntegrationsEqual(leftIntegrations, MANIFEST_BACKED_INTEGRATIONS);
  if (rightText === leftText) {
    return;
  }
  const rightMatch = rightText.match(
    /(?:export const INTEGRATIONS =|exports\.INTEGRATIONS =)\s*(\[[\s\S]*?\]);/,
  );
  expect(rightMatch?.[1], "missing exported INTEGRATIONS array").toBeDefined();
  const rightIntegrations = JSON.parse(rightMatch![1]) as ManifestBackedIntegration[];
  expectManifestBackedIntegrationsEqual(leftIntegrations, rightIntegrations);
}
