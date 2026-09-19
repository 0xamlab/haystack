// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — connect/connectMany/registerSource
 * entry points, managed connector hand-off, and import preview methods for
 * the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  ConnectorBrowseResult,
  ConnectorTestInfo,
  DatasetConnectResult,
  SourceRegistrationResponse,
} from "./types.js";
import {
  ImportBundlePreviewOptions,
  ImportBundlePreviewResult,
  ImportFailureResult,
  ImportPreviewOptions,
  ImportPreviewResult,
  LocalRecord,
  RuntimeConnectOptions,
} from "./_runtime_constants.js";
import { Runtime } from "./_runtime_class.js";
import { RuntimeError, RuntimeValidationError } from "./_runtime_errors.js";
import { stableHash } from "./_runtime_helpers_a.js";
import {
  inferTypedFields,
  orderedFields,
  registrationFields as _unused_registrationFields,
  roundLatency,
} from "./_runtime_helpers_b.js";
import {
  flattenConnectorEnvelope,
  isCanonicalConnectorEnvelope,
  normalizeApiSourcePayload,
  sourceReference,
  stripUndefined,
} from "./_runtime_helpers_c.js";
import {
  coerceRecords,
  localSourceName,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./_runtime_helpers_d.js";

// Mark helper exports as used to satisfy strict mode (defensive: imports are
// load-bearing for downstream side effects).
void _unused_registrationFields;

declare module "./_runtime_class.js" {
  interface Runtime {
    sourceRegistrationFromDatasetConnect(
      registration: DatasetConnectResult,
      datasetName: string,
    ): SourceRegistrationResponse;
    connectWithManagedConnector(
      options: RuntimeConnectOptions,
    ): Promise<SourceRegistrationResponse>;
    normalizePreviewConnectorPayload(
      connector: Record<string, unknown>,
    ): { connector_type: string; config?: Record<string, unknown> };
    connect(
      source?: string | LocalRecord[] | LocalRecord | Record<string, unknown> | null,
      options?: RuntimeConnectOptions,
    ): Promise<SourceRegistrationResponse>;
    registerSource(
      source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
      options?: { name?: string; description?: string },
    ): Promise<SourceRegistrationResponse>;
    connectMany(
      sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
      options?: { names?: Array<string | undefined>; description?: string },
    ): Promise<SourceRegistrationResponse[]>;
    importPreview(
      source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
      options?: ImportPreviewOptions,
    ): Promise<ImportPreviewResult>;
    importBundlePreview(
      sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
      options?: ImportBundlePreviewOptions,
    ): Promise<ImportBundlePreviewResult>;
    testConnectorWrapper?(
      input: string | Record<string, unknown>,
    ): Promise<ConnectorTestInfo | ConnectorBrowseResult>;
  }
}

Runtime.prototype.sourceRegistrationFromDatasetConnect = function (
  this: Runtime,
  registration: DatasetConnectResult,
  datasetName: string,
): SourceRegistrationResponse {
  return {
    status: registration.status,
    source_id:
      typeof registration.source_id === "string" && registration.source_id.trim()
        ? registration.source_id.trim()
        : typeof registration.dataset_id === "string" && registration.dataset_id.trim()
          ? registration.dataset_id.trim()
          : null,
    dataset_id:
      typeof registration.dataset_id === "string" && registration.dataset_id.trim()
        ? registration.dataset_id.trim()
        : typeof registration.source_id === "string" && registration.source_id.trim()
          ? registration.source_id.trim()
          : null,
    name:
      typeof registration.dataset_name === "string" && registration.dataset_name.trim()
        ? registration.dataset_name.trim()
        : datasetName,
    dataset_name:
      typeof registration.dataset_name === "string" && registration.dataset_name.trim()
        ? registration.dataset_name.trim()
        : datasetName,
    schema: registration.schema ?? null,
    source_schema: registration.schema ?? null,
    latency_ms: registration.latency_ms ?? null,
    connection_id: registration.connection_id ?? null,
    connection_type: registration.connection_type ?? null,
    provider: registration.provider ?? null,
    selection: registration.selection ?? null,
    visibility: registration.visibility ?? null,
    row_count: null,
  };
};

Runtime.prototype.connectWithManagedConnector = async function (
  this: Runtime,
  options: RuntimeConnectOptions,
): Promise<SourceRegistrationResponse> {
  this.requireApiTransport("connect");
  const hasInlineConnector = Boolean(options.connector);
  if (hasInlineConnector && !options.persist) {
    throw new RuntimeValidationError(
      "connector_persistence_required",
      "connect(connector=...) requires persist=true. Use testConnector() or browseConnector() for inline preview flows.",
    );
  }
  const datasetName = (options.datasetName ?? options.name ?? "").trim();
  if (!datasetName) {
    throw new RuntimeValidationError(
      "missing_dataset_name",
      "connect() requires datasetName or name when onboarding a connector-backed dataset.",
    );
  }
  const result = await this.client().connectData({
    dataset_name: datasetName,
    description: options.description,
    selection: options.selection,
    visibility: options.visibility,
    connection_name: options.connectionName,
    ...(options.connectorId ? { connection_id: options.connectorId } : {}),
    ...(options.connector ? { connector: options.connector } : {}),
  });
  if (result.status !== "ready") {
    const errorCode =
      result.status === "needs_selection" ? "selection_required" : `connect_${result.status}`;
    throw new RuntimeValidationError(
      errorCode,
      result.message ?? "Connector-backed dataset connection did not complete.",
      {
        status: result.status,
        choices: result.choices ?? [],
        labels: result.labels ?? {},
        discovery: result.discovery ?? {},
        connection_id: result.connection_id ?? null,
      },
    );
  }
  const registration = this.sourceRegistrationFromDatasetConnect(result, datasetName);
  const hydrated = await this.hydrateApiRegistration(registration);
  this.rememberApiRegistration(hydrated);
  return hydrated;
};

Runtime.prototype.normalizePreviewConnectorPayload = function (
  this: Runtime,
  connector: Record<string, unknown>,
): { connector_type: string; config?: Record<string, unknown> } {
  const normalized = isCanonicalConnectorEnvelope(connector)
    ? flattenConnectorEnvelope(connector)
    : stripUndefined({ ...connector });
  const connectorType = String(
    normalized.type ?? normalized.connector_type ?? normalized.provider ?? "",
  )
    .trim()
    .toLowerCase()
    .replace(/-/g, "_");
  if (!connectorType) {
    throw new RuntimeValidationError(
      "invalid_connector",
      "Connector previews require an explicit connector type.",
      { field: "type" },
    );
  }
  const config = stripUndefined(
    Object.fromEntries(
      Object.entries(normalized).filter(
        ([key]) => !["type", "connector_type", "provider"].includes(key),
      ),
    ),
  );
  return Object.keys(config).length > 0
    ? { connector_type: connectorType, config }
    : { connector_type: connectorType };
};

Runtime.prototype.connect = async function (
  this: Runtime,
  source?: string | LocalRecord[] | LocalRecord | Record<string, unknown> | null,
  options: RuntimeConnectOptions = {},
): Promise<SourceRegistrationResponse> {
  const startMs = Date.now();
  if (options.connectorId || options.connector) {
    return this.connectWithManagedConnector(options);
  }
  if (this.usesApiTransport()) {
    if (!source || typeof source !== "object" || Array.isArray(source)) {
      throw new RuntimeValidationError(
        "api_connect_requires_source_descriptor",
        "API and self_hosted mode connect() expect a structured source descriptor.",
        {
          expected: "object",
          received: source === null ? "null" : Array.isArray(source) ? "array" : typeof source,
        },
      );
    }
    const registration = await this.client().registerSource(
      normalizeApiSourcePayload(source, options.name),
      {
        description: options.description,
      },
    );
    const hydrated = await this.hydrateApiRegistration(registration);
    this.rememberApiRegistration(hydrated);
    return hydrated;
  }

  if (source === null || source === undefined) {
    throw new RuntimeValidationError(
      "source_required",
      "Local Runtime.connect() requires a local source path, records array, or structured local descriptor.",
    );
  }

  const records = await coerceRecords(source);
  if (records.length === 0) {
    throw new RuntimeValidationError(
      "empty_source",
      "Connected source is empty and cannot be queried.",
      {
        name: options.name ?? localSourceName(source, this.localSources.size),
      },
    );
  }

  const name = options.name ?? localSourceName(source, this.localSources.size);
  const fields = orderedFields(records);
  const typedFields = inferTypedFields(records, fields);
  const datasetId = stableHash({ name, fields }).slice(0, 24);
  const schemaRevision = stableHash({ datasetId, fields });
  this.localSources.set(name, {
    name,
    records,
    fields,
    schemaRevision,
    datasetId,
  });

  return {
    source_id: datasetId,
    dataset_id: datasetId,
    name,
    status: "ready",
    ingest_mode: "local",
    schema: { fields, typed_fields: typedFields },
    source_schema: { fields, typed_fields: typedFields },
    planner_cache_hit: false,
    planner_schema_revision: schemaRevision,
    planner_prewarm_ms: 0,
    latency_ms: roundLatency(startMs),
    row_count: records.length,
    typed_fields: typedFields,
  };
};

Runtime.prototype.registerSource = function (
  this: Runtime,
  source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
  options: { name?: string; description?: string } = {},
): Promise<SourceRegistrationResponse> {
  return this.connect(source, options);
};

Runtime.prototype.connectMany = async function (
  this: Runtime,
  sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
  options: { names?: Array<string | undefined>; description?: string } = {},
): Promise<SourceRegistrationResponse[]> {
  if (options.names && options.names.length !== sources.length) {
    throw new RuntimeValidationError(
      "invalid_names_length",
      "connectMany() names must match the number of sources.",
      { sources: sources.length, names: options.names.length },
    );
  }
  const registrations: SourceRegistrationResponse[] = [];
  for (const [index, source] of sources.entries()) {
    registrations.push(
      await this.connect(source, {
        name: options.names?.[index],
        description: options.description,
      }),
    );
  }
  return registrations;
};

Runtime.prototype.importPreview = async function (
  this: Runtime,
  source: string | LocalRecord[] | LocalRecord | Record<string, unknown>,
  options: ImportPreviewOptions = {},
): Promise<ImportPreviewResult> {
  const registration = await this.connect(source, options);
  return {
    registration,
    preview: renderSourceImportPreview(registration, {
      sourceRef: sourceReference(source, options.sourceRef),
      mode: this.mode,
      color: options.color,
    }),
  };
};

Runtime.prototype.importBundlePreview = async function (
  this: Runtime,
  sources: Array<string | LocalRecord[] | LocalRecord | Record<string, unknown>>,
  options: ImportBundlePreviewOptions = {},
): Promise<ImportBundlePreviewResult> {
  if (options.names && options.names.length !== sources.length) {
    throw new RuntimeValidationError(
      "invalid_names_length",
      "importBundlePreview() names must match the number of sources.",
      { sources: sources.length, names: options.names.length },
    );
  }
  if (options.sourceRefs && options.sourceRefs.length !== sources.length) {
    throw new RuntimeValidationError(
      "invalid_source_refs_length",
      "importBundlePreview() sourceRefs must match the number of sources.",
      { sources: sources.length, sourceRefs: options.sourceRefs.length },
    );
  }

  const registrations: SourceRegistrationResponse[] = [];
  const failures: ImportFailureResult[] = [];
  for (const [index, source] of sources.entries()) {
    try {
      registrations.push(
        await this.connect(source, {
          name: options.names?.[index],
          description: options.description,
        }),
      );
    } catch (error) {
      if (!(error instanceof RuntimeError)) {
        throw error;
      }
      failures.push({
        sourceRef: options.sourceRefs?.[index] ?? sourceReference(source),
        code: error.code,
        message: error.message,
        name: options.names?.[index],
      });
    }
  }

  return {
    registrations,
    failures,
    preview: renderSourceBundlePreview(registrations, failures, {
      mode: this.mode,
      color: options.color,
    }),
  };
};
