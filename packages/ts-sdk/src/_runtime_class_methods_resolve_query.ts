// SPDX-License-Identifier: Apache-2.0
/** Auto-split sub-module of runtime.ts — resolve/query/verify entry points
 * and API-path resolve helpers (registration hydration, exact-spec resolve)
 * for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  DatasetDetailResult,
  QueryResponse,
  QueryWithMetadataResponse,
  ResolveResponse,
  ResolvedPlan,
  SourceRegistrationResponse,
  VerifyResponse,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";
import { RUNTIME_DATASET_SCOPE_KEY } from "./_runtime_constants.js";
import {
  mergeRequest,
  registrationDatasetId,
  registrationFields,
  registrationResolvedSourceName,
  resolveAggregation,
  roundLatency,
} from "./_runtime_helpers_b.js";
import { exactPlanHash, intentSignature } from "./_runtime_helpers_d.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    resolve(
      request?: Record<string, unknown>,
      overrides?: Record<string, unknown>,
    ): Promise<ResolveResponse>;
    query(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides?: Record<string, unknown>,
    ): Promise<QueryResponse>;
    queryWithMetadata(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides?: Record<string, unknown>,
    ): Promise<QueryWithMetadataResponse>;
    verify(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides?: Record<string, unknown>,
    ): Promise<VerifyResponse>;
    rememberApiRegistration(registration: SourceRegistrationResponse): void;
    hydrateApiRegistration(
      registration: SourceRegistrationResponse,
    ): Promise<SourceRegistrationResponse>;
    lookupApiRegistration(request: Record<string, unknown>): SourceRegistrationResponse | null;
    fetchApiSourceSchemaRevision(
      registration: SourceRegistrationResponse,
    ): Promise<string | null>;
    tryExactApiResolve(request: Record<string, unknown>): Promise<ResolveResponse | null>;
    exactResolveMetricField(
      request: Record<string, unknown>,
      fields: Set<string>,
    ): string | null;
    exactResolveGroupField(
      request: Record<string, unknown>,
      fields: Set<string>,
    ): string | null | undefined;
  }
}

Runtime.prototype.resolve = async function (
  this: Runtime,
  request: Record<string, unknown> = {},
  overrides: Record<string, unknown> = {},
): Promise<ResolveResponse> {
  const merged = mergeRequest(request, overrides);
  if (this.usesApiTransport()) {
    const exact = await this.tryExactApiResolve(merged);
    if (exact) {
      return exact;
    }
    return this.client().resolve(this.coerceApiResolvePayload(merged));
  }
  return this.resolveLocal(merged);
};

Runtime.prototype.query = async function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown> = {},
): Promise<QueryResponse> {
  if (this.usesApiTransport()) {
    return this.client().query(this.coerceApiQueryPayload(request, overrides));
  }
  return this.queryLocal(request, overrides);
};

Runtime.prototype.queryWithMetadata = async function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown> = {},
): Promise<QueryWithMetadataResponse> {
  if (this.usesApiTransport()) {
    return this.client().queryWithMetadata(this.coerceApiQueryPayload(request, overrides));
  }
  const data = await this.queryLocal(request, overrides);
  return {
    data,
    metadata: {
      request_id: data.request_id ?? undefined,
      latency_ms: data.latency_ms,
    },
  };
};

Runtime.prototype.verify = async function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown> = {},
): Promise<VerifyResponse> {
  if (this.usesApiTransport()) {
    return this.client().verify(this.coerceApiQueryPayload(request, overrides));
  }
  return this.verifyLocal(request, overrides);
};

Runtime.prototype.rememberApiRegistration = function (
  this: Runtime,
  registration: SourceRegistrationResponse,
): void {
  if (typeof registration.name === "string" && registration.name.trim()) {
    this.apiRegistrationsByName.set(registration.name.trim(), registration);
  }
  const datasetId = registrationDatasetId(registration);
  if (datasetId) {
    this.apiRegistrationsByDataset.set(datasetId, registration);
  }
};

Runtime.prototype.hydrateApiRegistration = async function (
  this: Runtime,
  registration: SourceRegistrationResponse,
): Promise<SourceRegistrationResponse> {
  const datasetId = registrationDatasetId(registration);
  if (!datasetId) {
    return registration;
  }
  const needsHydration =
    registration.row_count == null ||
    typeof registration.name !== "string" ||
    !registration.name.trim() ||
    typeof registration.dataset_name !== "string" ||
    !registration.dataset_name.trim() ||
    registration.schema == null ||
    registration.source_schema == null;
  if (!needsHydration) {
    return registration;
  }
  const clientWithGetDataset = this.client() as unknown as {
    getDataset?: (datasetId: string) => Promise<DatasetDetailResult>;
  };
  if (typeof clientWithGetDataset.getDataset !== "function") {
    return registration;
  }
  try {
    const detail = await clientWithGetDataset.getDataset(datasetId);
    const dataset = detail?.dataset;
    const schema =
      detail?.schema && typeof detail.schema === "object" ? detail.schema : null;
    return {
      ...registration,
      name:
        typeof registration.name === "string" && registration.name.trim()
          ? registration.name
          : typeof dataset?.name === "string" && dataset.name.trim()
            ? dataset.name
            : registration.name ?? null,
      dataset_name:
        typeof registration.dataset_name === "string" && registration.dataset_name.trim()
          ? registration.dataset_name
          : typeof dataset?.name === "string" && dataset.name.trim()
            ? dataset.name
            : registration.dataset_name ?? null,
      row_count:
        typeof registration.row_count === "number"
          ? registration.row_count
          : typeof dataset?.row_count === "number"
            ? dataset.row_count
            : registration.row_count ?? null,
      schema: registration.schema ?? schema,
      source_schema: registration.source_schema ?? schema,
    };
  } catch {
    return registration;
  }
};

Runtime.prototype.lookupApiRegistration = function (
  this: Runtime,
  request: Record<string, unknown>,
): SourceRegistrationResponse | null {
  const datasetId = request.dataset_id;
  if (typeof datasetId === "string" && datasetId.trim()) {
    const registration = this.apiRegistrationsByDataset.get(datasetId.trim());
    if (registration) {
      return registration;
    }
  }
  const sourceName = request.source_name;
  if (typeof sourceName === "string" && sourceName.trim()) {
    return this.apiRegistrationsByName.get(sourceName.trim()) ?? null;
  }
  return null;
};

Runtime.prototype.fetchApiSourceSchemaRevision = async function (
  this: Runtime,
  registration: SourceRegistrationResponse,
): Promise<string | null> {
  const sourceId = registrationDatasetId(registration);
  if (!sourceId) {
    return null;
  }
  const clientWithRequest = this.client() as unknown as {
    request?: (method: string, path: string, body?: unknown) => Promise<unknown>;
  };
  if (typeof clientWithRequest.request !== "function") {
    return null;
  }
  try {
    const payload = await clientWithRequest.request("GET", `/v1/sources/${sourceId}`);
    if (!payload || typeof payload !== "object") {
      return null;
    }
    const body = payload as Record<string, unknown>;
    const entry = body.entry;
    if (entry && typeof entry === "object") {
      const entryRecord = entry as Record<string, unknown>;
      const entryRevision = entryRecord.source_schema_revision ?? entryRecord.schema_revision;
      if (typeof entryRevision === "string" && entryRevision.trim()) {
        return entryRevision.trim();
      }
    }
    const schema = body.schema;
    if (schema && typeof schema === "object") {
      const schemaRevision = (schema as Record<string, unknown>).schema_revision;
      if (typeof schemaRevision === "string" && schemaRevision.trim()) {
        return schemaRevision.trim();
      }
    }
    return null;
  } catch {
    return null;
  }
};

Runtime.prototype.tryExactApiResolve = async function (
  this: Runtime,
  request: Record<string, unknown>,
): Promise<ResolveResponse | null> {
  const registration = this.lookupApiRegistration(request);
  if (!registration) {
    return null;
  }
  const resolvedSourceName = registrationResolvedSourceName(registration);
  if (!resolvedSourceName) {
    return null;
  }
  const schemaRevision =
    (await this.fetchApiSourceSchemaRevision(registration)) ??
    (typeof registration.planner_schema_revision === "string" &&
    registration.planner_schema_revision.trim()
      ? registration.planner_schema_revision.trim()
      : typeof registration.schema_revision === "string" && registration.schema_revision.trim()
        ? registration.schema_revision.trim()
        : null);
  if (!schemaRevision) {
    return null;
  }
  const fields = new Set(registrationFields(registration));
  if (fields.size === 0) {
    return null;
  }

  const metricColumn = this.exactResolveMetricField(request, fields);
  if (!metricColumn) {
    return null;
  }
  const groupColumn = this.exactResolveGroupField(request, fields);
  if (groupColumn === undefined) {
    return null;
  }

  const startMs = Date.now();
  const constraints =
    request.constraints && typeof request.constraints === "object"
      ? { ...(request.constraints as Record<string, unknown>) }
      : {};
  const datasetScope = registrationDatasetId(registration);
  if (datasetScope && constraints[RUNTIME_DATASET_SCOPE_KEY] === undefined) {
    constraints[RUNTIME_DATASET_SCOPE_KEY] = datasetScope;
  }
  const resolvedPlan: ResolvedPlan = {
    source_name: resolvedSourceName,
    metric_column: metricColumn,
    aggregation: resolveAggregation(request),
    ...(groupColumn ? { group_column: groupColumn } : {}),
    ...(request.join_path && typeof request.join_path === "object"
      ? { join_path: request.join_path as Record<string, unknown> }
      : {}),
    ...(request.filter && typeof request.filter === "object"
      ? { filter: request.filter as Record<string, unknown> }
      : {}),
    ...(typeof request.limit === "number" ? { limit: request.limit } : {}),
    order: typeof request.order === "string" ? request.order : "desc",
    constraints,
    schema_revision: schemaRevision,
  };
  const planHash = exactPlanHash(resolvedPlan);
  const signature = intentSignature(resolvedSourceName, request, schemaRevision);

  return {
    resolved_plan: resolvedPlan,
    confidence: 1,
    plan: [
      `Use exact source '${resolvedSourceName}'.`,
      `Use exact metric column '${metricColumn}'.`,
      ...(groupColumn ? [`Group by exact column '${groupColumn}'.`] : []),
    ],
    explanation: [
      `Using registered source '${resolvedSourceName}' as an exact source.`,
      `Using exact metric column '${metricColumn}'.`,
      ...(groupColumn ? [`Using exact group column '${groupColumn}'.`] : []),
    ],
    resolved_column: metricColumn,
    resolved_role: "measure",
    resolved_source: resolvedSourceName,
    candidates: [],
    source_scores: { [resolvedSourceName]: 1 },
    latency_ms: roundLatency(startMs),
    decision_path: "exact_spec",
    plan_hash: planHash,
    schema_revision: schemaRevision,
    validated: true,
    deterministic_scope: "api_registered_source",
    confidence_source: "runtime_exact_spec",
    clarification_required: false,
    rejection_reason: null,
    request_id: `runtime_exact_${signature.slice(0, 12)}`,
    intent_signature: signature,
    source_set: [resolvedSourceName],
    join_path: [],
    planner_mode: "runtime_exact_spec",
  };
};

Runtime.prototype.exactResolveMetricField = function (
  this: Runtime,
  request: Record<string, unknown>,
  fields: Set<string>,
): string | null {
  const metricColumn = request.metric_column;
  if (typeof metricColumn === "string" && fields.has(metricColumn)) {
    return metricColumn;
  }
  const metric = request.metric;
  if (typeof metric === "string" && fields.has(metric)) {
    return metric;
  }
  return null;
};

Runtime.prototype.exactResolveGroupField = function (
  this: Runtime,
  request: Record<string, unknown>,
  fields: Set<string>,
): string | null | undefined {
  const groupColumn = request.group_column;
  if (typeof groupColumn === "string") {
    return fields.has(groupColumn) ? groupColumn : undefined;
  }
  const groupBy = request.group_by;
  if (typeof groupBy === "string") {
    return fields.has(groupBy) ? groupBy : undefined;
  }
  if (Array.isArray(groupBy)) {
    const candidates = groupBy.filter(
      (value): value is string => typeof value === "string" && value.trim().length > 0,
    );
    if (candidates.length > 1) {
      return undefined;
    }
    if (candidates.length === 1) {
      return fields.has(candidates[0]) ? candidates[0] : undefined;
    }
  }
  return null;
};
