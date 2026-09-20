// SPDX-License-Identifier: Apache-2.0
/**
 * Runtime.connect() entry points in _runtime_class_methods_connect.ts that the
 * happy-path suites leave untouched: the managed-connector hand-off, argument
 * validation on both transports, connectMany / importBundlePreview bookkeeping and
 * the connector preview payload normalizer.
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
} from "./runtime.js";
import type { DatasetConnectResult } from "./types.js";

const ORIGINAL_ENV = { ...process.env };
const tempDirs: string[] = [];

function tempDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "algenta-ts-connect-"));
  tempDirs.push(dir);
  return dir;
}

function readyConnect(overrides: Partial<DatasetConnectResult> = {}): DatasetConnectResult {
  return {
    status: "ready",
    dataset_id: "ds_pg",
    source_id: null,
    dataset_name: " Postgres orders ",
    schema: { fields: ["revenue", "region"] },
    latency_ms: 8,
    connection_id: "conn_1",
    connection_type: "postgres",
    provider: "postgres",
    selection: { table: "orders" },
    visibility: "workspace",
    ...overrides,
  };
}

beforeEach(() => {
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  delete process.env.ALGENTA_DEPLOYMENT_MODE;
  delete process.env.ALGENTA_DISABLE_CLOUD;
});

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    rmSync(dir, { recursive: true, force: true });
  }
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) delete process.env[key];
  }
  Object.assign(process.env, ORIGINAL_ENV);
});

describe("Runtime.connect with a managed connector", () => {
  it("is an API-only flow", async () => {
    const runtime = new Runtime({ mode: "local" });
    const failure = runtime.connect(null, { connectorId: "conn_1", datasetName: "orders" });
    await expect(failure).rejects.toBeInstanceOf(RuntimeConfigurationError);
    await expect(failure).rejects.toMatchObject({ code: "local_mode_not_supported" });
  });

  it("requires a dataset name", async () => {
    const connectData = vi.fn();
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: { connectData } as never });
    await expect(runtime.connect(null, { connectorId: "conn_1", name: "   " })).rejects.toMatchObject({
      code: "missing_dataset_name",
      message: expect.stringContaining("requires datasetName or name"),
    });
    expect(connectData).not.toHaveBeenCalled();
  });

  it("surfaces needs_selection and other non-ready statuses as typed errors", async () => {
    const connectData = vi
      .fn()
      .mockResolvedValueOnce({
        status: "needs_selection",
        message: "Pick a table.",
        choices: [{ table: "orders" }],
        labels: { orders: "Orders" },
        discovery: { tables: 1 },
        connection_id: "conn_1",
      })
      .mockResolvedValueOnce({ status: "error" });
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: { connectData } as never });

    const selection = runtime.connect(null, { connectorId: "conn_1", datasetName: "orders" });
    await expect(selection).rejects.toBeInstanceOf(RuntimeValidationError);
    await expect(selection).rejects.toMatchObject({
      code: "selection_required",
      message: "Pick a table.",
      details: {
        status: "needs_selection",
        choices: [{ table: "orders" }],
        labels: { orders: "Orders" },
        discovery: { tables: 1 },
        connection_id: "conn_1",
      },
    });

    await expect(
      runtime.connect(null, { connector: { type: "postgres" }, persist: true, name: "orders" }),
    ).rejects.toMatchObject({
      code: "connect_error",
      message: "Connector-backed dataset connection did not complete.",
      details: { status: "error", choices: [], labels: {}, discovery: {}, connection_id: null },
    });
    // The inline connector and its options travel to the API unchanged.
    expect(connectData.mock.calls[1][0]).toEqual({
      dataset_name: "orders",
      description: undefined,
      selection: undefined,
      visibility: undefined,
      connection_name: undefined,
      connector: { type: "postgres" },
    });
  });

  it("registers a ready connector dataset and remembers it for exact resolves", async () => {
    const connectData = vi.fn(async () => readyConnect());
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: { connectData } as never });

    const registration = await runtime.connect(null, {
      connectorId: "conn_1",
      datasetName: "ignored when the API names the dataset",
      description: "Orders from Postgres",
      selection: { table: "orders" },
      visibility: "workspace",
      connectionName: "warehouse",
    });

    expect(connectData).toHaveBeenCalledWith({
      dataset_name: "ignored when the API names the dataset",
      description: "Orders from Postgres",
      selection: { table: "orders" },
      visibility: "workspace",
      connection_name: "warehouse",
      connection_id: "conn_1",
    });
    expect(registration).toEqual({
      status: "ready",
      source_id: "ds_pg",
      dataset_id: "ds_pg",
      name: "Postgres orders",
      dataset_name: "Postgres orders",
      schema: { fields: ["revenue", "region"] },
      source_schema: { fields: ["revenue", "region"] },
      latency_ms: 8,
      connection_id: "conn_1",
      connection_type: "postgres",
      provider: "postgres",
      selection: { table: "orders" },
      visibility: "workspace",
      row_count: null,
    });
    expect(runtime.apiRegistrationsByName.get("Postgres orders")).toBe(registration);
    expect(runtime.apiRegistrationsByDataset.get("ds_pg")).toBe(registration);
  });

  it("maps a connect result with only a source_id and no names", () => {
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key" });
    const registration = runtime.sourceRegistrationFromDatasetConnect(
      { status: "ready", source_id: " src_only ", dataset_name: "   " },
      "fallback name",
    );
    expect(registration).toEqual({
      status: "ready",
      source_id: "src_only",
      dataset_id: "src_only",
      name: "fallback name",
      dataset_name: "fallback name",
      schema: null,
      source_schema: null,
      latency_ms: null,
      connection_id: null,
      connection_type: null,
      provider: null,
      selection: null,
      visibility: null,
      row_count: null,
    });
    expect(runtime.sourceRegistrationFromDatasetConnect({ status: "ready" }, "n")).toMatchObject({
      source_id: null,
      dataset_id: null,
    });
  });
});

describe("Runtime.connect argument validation", () => {
  it.each([
    ["null", null, "null"],
    ["undefined", undefined, "undefined"],
    ["a string path", "./orders.csv", "string"],
    ["an array of records", [{ revenue: 1 }], "array"],
  ])("API mode rejects %s as a source descriptor", async (_label, source, received) => {
    const registerSource = vi.fn();
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_key", client: { registerSource } as never });
    const failure = runtime.connect(source as never);
    await expect(failure).rejects.toBeInstanceOf(RuntimeValidationError);
    await expect(failure).rejects.toMatchObject({
      code: "api_connect_requires_source_descriptor",
      details: { expected: "object", received },
    });
    expect(registerSource).not.toHaveBeenCalled();
  });

  it("local mode requires a source and rejects empty ones with the derived name", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expect(runtime.connect()).rejects.toMatchObject({
      code: "source_required",
      message: expect.stringContaining("Local Runtime.connect()"),
    });
    await expect(runtime.connect([])).rejects.toMatchObject({
      code: "empty_source",
      details: { name: "source_0" },
    });
    await expect(runtime.connect([], { name: "explicit" })).rejects.toMatchObject({
      code: "empty_source",
      details: { name: "explicit" },
    });
  });

  it("registerSource is an alias of connect", async () => {
    const runtime = new Runtime({ mode: "local" });
    const registration = await runtime.registerSource([{ revenue: 1 }], { name: "aliased" });
    expect(registration.name).toBe("aliased");
    expect(runtime.localSources.has("aliased")).toBe(true);
  });
});

describe("Runtime.connectMany and importBundlePreview", () => {
  it("connectMany checks the names length and connects in order", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expect(
      runtime.connectMany([[{ a: 1 }], [{ b: 2 }]], { names: ["only-one"] }),
    ).rejects.toMatchObject({
      code: "invalid_names_length",
      details: { sources: 2, names: 1 },
    });

    const registrations = await runtime.connectMany([[{ a: 1 }], [{ b: 2 }]], {
      names: ["first", undefined],
      description: "bundle",
    });
    expect(registrations.map(registration => registration.name)).toEqual(["first", "source_1"]);
  });

  it("importBundlePreview validates its parallel option arrays", async () => {
    const runtime = new Runtime({ mode: "local" });
    await expect(
      runtime.importBundlePreview([[{ a: 1 }]], { names: [] }),
    ).rejects.toMatchObject({ code: "invalid_names_length", details: { sources: 1, names: 0 } });
    await expect(
      runtime.importBundlePreview([[{ a: 1 }]], { sourceRefs: ["a", "b"] }),
    ).rejects.toMatchObject({
      code: "invalid_source_refs_length",
      details: { sources: 1, sourceRefs: 2 },
    });
  });

  it("importBundlePreview records runtime failures per source and keeps going", async () => {
    const runtime = new Runtime({ mode: "local" });
    const result = await runtime.importBundlePreview(
      [[{ revenue: 1 }], [], [{ revenue: 2 }]],
      { names: ["good", "empty", undefined], sourceRefs: [undefined, "empty.csv", undefined], color: false },
    );

    expect(result.registrations.map(registration => registration.name)).toEqual(["good", "source_1"]);
    expect(result.failures).toEqual([
      {
        sourceRef: "empty.csv",
        code: "empty_source",
        message: "Connected source is empty and cannot be queried.",
        name: "empty",
      },
    ]);
    expect(result.preview).toContain("Imported: 2 | Failures: 1");
    expect(result.preview).toContain("- empty: empty_source");

    // Without an explicit sourceRef the failure falls back to the derived reference.
    const derived = await runtime.importBundlePreview([[]], { color: false });
    expect(derived.failures[0]).toMatchObject({ sourceRef: "in-memory records", name: undefined });
  });

  it("importBundlePreview rethrows errors that are not runtime errors", async () => {
    const dir = tempDir();
    const brokenJson = join(dir, "broken.json");
    writeFileSync(brokenJson, "{ not json");
    const runtime = new Runtime({ mode: "local" });
    await expect(runtime.importBundlePreview([brokenJson])).rejects.toBeInstanceOf(SyntaxError);
  });
});

describe("Runtime.normalizePreviewConnectorPayload", () => {
  it("flattens canonical envelopes and separates the connector type from its config", () => {
    const runtime = new Runtime({ mode: "local" });

    expect(
      runtime.normalizePreviewConnectorPayload({
        type: " Postgres-DB ",
        location: { host: "db.internal", port: 5432 },
        options: { ssl: true },
      }),
    ).toEqual({
      connector_type: "postgres_db",
      config: { host: "db.internal", port: 5432, ssl: true },
    });

    expect(runtime.normalizePreviewConnectorPayload({ connector_type: "rest", url: undefined })).toEqual({
      connector_type: "rest",
    });
    expect(runtime.normalizePreviewConnectorPayload({ provider: "S3", bucket: "b" })).toEqual({
      connector_type: "s3",
      config: { bucket: "b" },
    });

    expect(() => runtime.normalizePreviewConnectorPayload({ url: "https://x" })).toThrow(
      RuntimeValidationError,
    );
    expect(() => runtime.normalizePreviewConnectorPayload({ url: "https://x" })).toThrow(
      "require an explicit connector type",
    );
  });
});
