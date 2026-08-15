/** Auto-split sub-module of runtime.ts — local-mode license,
 * source-selection, planning, and execution helpers for the Runtime class.
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type {
  QueryCandidate,
  QueryResponse,
  ResolveResponse,
  ResolvedPlan,
  VerifyResponse,
} from "./types.js";
import { Runtime } from "./_runtime_class.js";
import {
  LocalSource,
  RankedField,
  RUNTIME_DATASET_SCOPE_KEY,
} from "./_runtime_constants.js";
import {
  RuntimeConfigurationError,
  RuntimeError,
  RuntimeValidationError,
} from "./_runtime_errors.js";
import {
  loadLocalLicense,
  normalizeText,
} from "./_runtime_helpers_a.js";
import {
  applyLocalFilterConditions,
  findLocalTimeField,
  isExactFieldMatch,
  isNumericField,
  metricSynonymSet,
  parseDateValue,
  resolveAggregation,
  resolveLocalFilterConditions,
  roundLatency,
  semanticScore,
  timeRange,
} from "./_runtime_helpers_b.js";
import {
  exactPlanHash,
  executePlan,
  intentSignature,
  looksLikeResolvedPlan,
} from "./_runtime_helpers_d.js";
import {
  privateProfile,
  requireLocalLicense,
} from "./runtime_privacy.js";

declare module "./_runtime_class.js" {
  interface Runtime {
    usesHostedLocalLimits(): boolean;
    ensureLocalExecutionEntitlement(): Promise<void>;
    selectLocalSource(request: Record<string, unknown>): LocalSource;
    rankFields(source: LocalSource, hint: string, numericOnly: boolean): RankedField[];
    buildCandidates(
      source: LocalSource,
      ranked: RankedField[],
      role: string,
    ): QueryCandidate[];
    resolveLocal(request: Record<string, unknown>): ResolveResponse;
    rejectedResolve(
      source: LocalSource,
      request: Record<string, unknown>,
      reason: string,
      explanation: string[],
      startMs: number,
      candidates?: QueryCandidate[],
    ): ResolveResponse;
    clarifyResolve(
      source: LocalSource,
      request: Record<string, unknown>,
      explanation: string[],
      startMs: number,
      candidates: QueryCandidate[],
    ): ResolveResponse;
    coercePlan(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides: Record<string, unknown>,
    ): ResolvedPlan;
    queryLocal(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides: Record<string, unknown>,
    ): Promise<QueryResponse>;
    verifyLocal(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides: Record<string, unknown>,
    ): VerifyResponse;
    coerceApiQueryPayload(
      request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
      overrides: Record<string, unknown>,
    ): Record<string, unknown>;
    extractRuntimeDatasetScope(payload: Record<string, unknown>): Record<string, unknown>;
    coerceApiResolvePayload(request: Record<string, unknown>): Record<string, unknown>;
  }
}

Runtime.prototype.usesHostedLocalLimits = function (this: Runtime): boolean {
  return this.mode === "local" && this.enforceLimits && !privateProfile();
};

Runtime.prototype.ensureLocalExecutionEntitlement = async function (
  this: Runtime,
): Promise<void> {
  if (!this.usesHostedLocalLimits() && !requireLocalLicense()) {
    return;
  }
  if (this.usesHostedLocalLimits() && !this.apiKey) {
    throw new RuntimeConfigurationError(
      "api_key_required",
      "Hosted local mode requires an API key. Pass apiKey explicitly when constructing Runtime.",
    );
  }
  if (!this.licensePromise) {
    this.licensePromise = loadLocalLicense(this.apiKey ?? "", this.baseUrl).finally(() => {
      this.licensePromise = undefined;
    });
  }
  this.localLicense = await this.licensePromise;
  if (!this.localLicense.valid) {
    throw new RuntimeConfigurationError(
      "license_required",
      this.localLicense.message || "A valid local device license is required.",
      {
        plan: this.localLicense.plan,
        source: this.localLicense.source,
      },
    );
  }
};

Runtime.prototype.selectLocalSource = function (
  this: Runtime,
  request: Record<string, unknown>,
): LocalSource {
  const requested =
    typeof request.source_name === "string"
      ? request.source_name
      : typeof request.dataset_id === "string"
        ? request.dataset_id
        : null;

  if (requested) {
    if (this.localSources.has(requested)) {
      return this.localSources.get(requested)!;
    }
    for (const source of this.localSources.values()) {
      if (source.datasetId === requested) return source;
    }
    throw new RuntimeValidationError(
      "unknown_source",
      "Requested source is not connected to this runtime.",
      {
        requested,
        available: [...this.localSources.keys()].sort(),
      },
    );
  }

  if (this.localSources.size === 1) {
    return [...this.localSources.values()][0];
  }
  if (this.localSources.size === 0) {
    throw new RuntimeConfigurationError(
      "source_required",
      "No local sources are connected. Call Runtime.connect(...) before resolve/query.",
    );
  }
  throw new RuntimeValidationError(
    "source_required",
    "Multiple local sources are connected. Provide source_name or dataset_id.",
    {
      available: [...this.localSources.keys()].sort(),
    },
  );
};

Runtime.prototype.rankFields = function (
  this: Runtime,
  source: LocalSource,
  hint: string,
  numericOnly: boolean,
): RankedField[] {
  const hintTerms = metricSynonymSet(hint);
  return source.fields
    .filter(field => !numericOnly || isNumericField(field, source.records))
    .map(field => {
      const base = semanticScore(field, hint);
      let score = base.score;
      const reasons = [...base.reasons];
      const normalizedField = normalizeText(field);
      if (hintTerms.has(normalizedField)) {
        score = Math.max(score, 1);
        reasons.push("canonical synonym match");
      }
      if (isExactFieldMatch(field, hint)) {
        score = 1;
      }
      return {
        field,
        score: Number(score.toFixed(4)),
        reasons: reasons.length > 0 ? reasons : ["schema similarity"],
      };
    })
    .sort((left, right) => {
      if (right.score !== left.score) return right.score - left.score;
      return left.field.localeCompare(right.field);
    });
};

Runtime.prototype.buildCandidates = function (
  this: Runtime,
  source: LocalSource,
  ranked: RankedField[],
  role: string,
): QueryCandidate[] {
  return ranked.slice(0, 5).map(item => ({
    source: source.name,
    column: item.field,
    role,
    confidence: item.score,
    notes: item.reasons,
    score_components: { schema_similarity: item.score },
  }));
};

Runtime.prototype.resolveLocal = function (
  this: Runtime,
  request: Record<string, unknown>,
): ResolveResponse {
  const startMs = Date.now();
  const source = this.selectLocalSource(request);
  const metricHint = typeof request.metric === "string" ? request.metric : null;
  if (!metricHint) {
    throw new RuntimeValidationError(
      "metric_required",
      "Local Runtime.resolve() requires a structured metric field.",
      { request },
    );
  }

  const aggregation = resolveAggregation(request);
  const metricRanked = this.rankFields(source, metricHint, true);
  if (metricRanked.length === 0) {
    return this.rejectedResolve(
      source,
      request,
      "schema_unresolved",
      [`No numeric field matched metric '${metricHint}'.`],
      startMs,
    );
  }

  const metricChoice = metricRanked[0];
  const metricCandidates = this.buildCandidates(source, metricRanked, "measure");
  const metricSecond = metricRanked[1]?.score ?? 0;
  const metricGap = Number((metricChoice.score - metricSecond).toFixed(4));

  if (metricChoice.score < 0.7) {
    return this.rejectedResolve(
      source,
      request,
      "schema_unresolved",
      [`Top metric match '${metricChoice.field}' scored below the 0.70 threshold.`],
      startMs,
      metricCandidates,
    );
  }
  if (metricChoice.score < 0.85 || metricGap < 0.1) {
    return this.clarifyResolve(
      source,
      request,
      [`Metric mapping for '${metricHint}' is not decisive enough for execution.`],
      startMs,
      metricCandidates,
    );
  }

  let resolvedGroup: string | null = null;
  let groupCandidates: QueryCandidate[] = [];
  if (typeof request.group_by === "string" && request.group_by.trim()) {
    const groupRanked = this.rankFields(source, request.group_by, false);
    groupCandidates = this.buildCandidates(source, groupRanked, "dimension");
    if (groupRanked.length === 0) {
      return this.rejectedResolve(
        source,
        request,
        "schema_unresolved",
        [`No field matched group_by '${request.group_by}'.`],
        startMs,
        metricCandidates,
      );
    }
    const groupChoice = groupRanked[0];
    const groupSecond = groupRanked[1]?.score ?? 0;
    const groupGap = Number((groupChoice.score - groupSecond).toFixed(4));
    if (groupChoice.score < 0.7) {
      return this.rejectedResolve(
        source,
        request,
        "schema_unresolved",
        [`Top group_by match '${groupChoice.field}' scored below the 0.70 threshold.`],
        startMs,
        [...metricCandidates, ...groupCandidates],
      );
    }
    if (groupChoice.score < 0.85 || groupGap < 0.1) {
      return this.clarifyResolve(
        source,
        request,
        [`Group_by mapping for '${request.group_by}' is not decisive enough for execution.`],
        startMs,
        [...metricCandidates, ...groupCandidates],
      );
    }
    resolvedGroup = groupChoice.field;
  }

  const resolvedPlan: ResolvedPlan = {
    source_name: source.name,
    metric_column: metricChoice.field,
    aggregation,
    group_column: resolvedGroup,
    join_path: null,
    filter: (request.filter as Record<string, unknown> | undefined) ?? null,
    limit: typeof request.limit === "number" ? request.limit : null,
    order: typeof request.order === "string" ? request.order : "desc",
    constraints: (request.constraints as Record<string, unknown> | undefined) ?? {},
    schema_revision: source.schemaRevision,
  };
  const planHash = exactPlanHash(resolvedPlan);
  const signature = intentSignature(source.name, request, source.schemaRevision);
  const decisionPath =
    isExactFieldMatch(metricChoice.field, metricHint) &&
    (!resolvedGroup || isExactFieldMatch(resolvedGroup, String(request.group_by ?? "")))
      ? "exact_spec"
      : "planner_hint";

  return {
    resolved_plan: resolvedPlan,
    confidence: 1,
    plan: [
      `Use source '${source.name}'.`,
      `Aggregate '${metricChoice.field}' with '${aggregation}'.`,
      ...(resolvedGroup ? [`Group by '${resolvedGroup}'.`] : []),
    ],
    explanation: [
      `Resolved metric '${metricHint}' to '${metricChoice.field}'.`,
      ...(resolvedGroup ? [`Resolved group_by '${request.group_by}' to '${resolvedGroup}'.`] : []),
    ],
    resolved_column: metricChoice.field,
    resolved_role: "measure",
    resolved_source: source.name,
    candidates: [...metricCandidates, ...groupCandidates],
    source_scores: { [source.name]: 1 },
    latency_ms: roundLatency(startMs),
    decision_path: decisionPath,
    plan_hash: planHash,
    schema_revision: source.schemaRevision,
    validated: true,
    deterministic_scope: "local_registered_source",
    confidence_source: "local_schema_match",
    clarification_required: false,
    rejection_reason: null,
    request_id: `local_${signature.slice(0, 12)}`,
    intent_signature: signature,
    source_set: [source.name],
    join_path: [],
    planner_mode: "local_structured_intent",
  };
};

Runtime.prototype.rejectedResolve = function (
  this: Runtime,
  source: LocalSource,
  request: Record<string, unknown>,
  reason: string,
  explanation: string[],
  startMs: number,
  candidates: QueryCandidate[] = [],
): ResolveResponse {
  const signature = intentSignature(source.name, request, source.schemaRevision);
  return {
    resolved_plan: null,
    confidence: 0,
    plan: [],
    explanation,
    resolved_column: "",
    resolved_role: "",
    resolved_source: source.name,
    candidates,
    source_scores: { [source.name]: 1 },
    latency_ms: roundLatency(startMs),
    decision_path: "planner_hint",
    plan_hash: null,
    schema_revision: source.schemaRevision,
    validated: false,
    deterministic_scope: "local_registered_source",
    confidence_source: "local_schema_match",
    clarification_required: false,
    rejection_reason: reason,
    request_id: `local_${signature.slice(0, 12)}`,
    intent_signature: signature,
    source_set: [source.name],
    join_path: [],
    planner_mode: "local_structured_intent",
  };
};

Runtime.prototype.clarifyResolve = function (
  this: Runtime,
  source: LocalSource,
  request: Record<string, unknown>,
  explanation: string[],
  startMs: number,
  candidates: QueryCandidate[],
): ResolveResponse {
  const signature = intentSignature(source.name, request, source.schemaRevision);
  return {
    resolved_plan: null,
    confidence: 0.75,
    plan: [],
    explanation,
    resolved_column: "",
    resolved_role: "",
    resolved_source: source.name,
    candidates,
    source_scores: { [source.name]: 1 },
    latency_ms: roundLatency(startMs),
    decision_path: "planner_hint",
    plan_hash: null,
    schema_revision: source.schemaRevision,
    validated: false,
    deterministic_scope: "local_registered_source",
    confidence_source: "local_schema_match",
    clarification_required: true,
    rejection_reason: null,
    request_id: `local_${signature.slice(0, 12)}`,
    intent_signature: signature,
    source_set: [source.name],
    join_path: [],
    planner_mode: "local_structured_intent",
  };
};

Runtime.prototype.coercePlan = function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown>,
): ResolvedPlan {
  const payload =
    Object.keys(overrides).length > 0
      ? overrides
      : "resolved_plan" in request
        ? (request.resolved_plan as ResolvedPlan | null)
        : request;
  if (!payload) {
    throw new RuntimeValidationError(
      "query_requires_executable_plan",
      "Runtime.query() requires an executable plan.",
    );
  }
  return payload as ResolvedPlan;
};

Runtime.prototype.queryLocal = async function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown>,
): Promise<QueryResponse> {
  const startMs = Date.now();
  const plan = this.coercePlan(request, overrides);
  const source = this.localSources.get(plan.source_name);
  if (!source) {
    throw new RuntimeValidationError(
      "unknown_source",
      "Query plan references a source that is not connected to this runtime.",
      { source_name: plan.source_name },
    );
  }
  if (plan.schema_revision !== source.schemaRevision) {
    throw new RuntimeValidationError(
      "schema_revision_mismatch",
      "Query plan schema_revision does not match the connected source.",
      { expected: source.schemaRevision, received: plan.schema_revision },
    );
  }

  await this.ensureLocalExecutionEntitlement();

  let executionRecords = source.records;
  const localPlanSteps: string[] = [];
  const filterValue =
    plan.filter && typeof plan.filter === "object"
      ? (plan.filter as Record<string, unknown>)
      : {};
  const timeFilter =
    typeof filterValue.time_filter === "string" ? filterValue.time_filter.trim() : "";
  if (timeFilter) {
    const localTimeField = findLocalTimeField(source);
    const localTimeRange = timeRange(timeFilter);
    if (localTimeField && localTimeRange) {
      const before = executionRecords.length;
      executionRecords = executionRecords.filter(record => {
        const parsed = parseDateValue(record[localTimeField]);
        return (
          parsed !== null &&
          parsed.getTime() >= localTimeRange.start.getTime() &&
          parsed.getTime() <= localTimeRange.end.getTime()
        );
      });
      localPlanSteps.push(
        `Time filter '${timeFilter}' on '${localTimeField}': ${before}->${executionRecords.length} rows.`,
      );
    } else {
      localPlanSteps.push("No time-like field found. time_filter skipped.");
    }
  }

  const resolvedFilterConditions = resolveLocalFilterConditions(source, filterValue);
  const filteredLocalRecords = applyLocalFilterConditions(
    executionRecords,
    resolvedFilterConditions,
  );
  executionRecords = filteredLocalRecords.records;
  localPlanSteps.push(...filteredLocalRecords.planSteps);

  const rows = executePlan(
    executionRecords,
    plan.metric_column,
    plan.group_column,
    plan.aggregation,
    plan.limit ?? 100,
  );
  const result = plan.group_column ? rows : rows[0]?.[plan.metric_column] ?? null;

  return {
    query_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
    result,
    result_type: plan.group_column ? "table" : "scalar",
    confidence: 1,
    plan: [
      `Use source '${source.name}'.`,
      `Aggregate '${plan.metric_column}' with '${plan.aggregation}'.`,
      ...(plan.group_column ? [`Group by '${plan.group_column}'.`] : []),
      ...localPlanSteps,
    ],
    resolved_column: plan.metric_column,
    resolved_role: "measure",
    resolved_source: source.name,
    row_count: plan.group_column ? rows.length : result === null ? 0 : 1,
    candidates: [],
    source_scores: { [source.name]: 1 },
    ambiguous: false,
    exact_spec: true,
    explanation: ["Executed deterministic local plan."],
    latency_ms: roundLatency(startMs),
    decision_path: "exact_spec",
    plan_hash: exactPlanHash(plan),
    schema_revision: source.schemaRevision,
    validated: true,
    deterministic_scope: "local_registered_source",
    confidence_source: "local_exact_execution",
    clarification_required: false,
    rejection_reason: null,
    request_id: `local_query_${exactPlanHash(plan).slice(0, 12)}`,
    source_set: [source.name],
    join_path: [],
    planner_mode: "local_structured_intent",
  };
};

Runtime.prototype.verifyLocal = function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown>,
): VerifyResponse {
  const startMs = Date.now();
  try {
    const plan = this.coercePlan(request, overrides);
    const source = this.localSources.get(plan.source_name);
    const errors: string[] = [];
    if (!source) {
      errors.push(`Source '${plan.source_name}' is not connected.`);
    } else {
      if (plan.schema_revision !== source.schemaRevision) {
        errors.push("schema_revision mismatch");
      }
      if (!source.fields.includes(plan.metric_column)) {
        errors.push(`Metric column '${plan.metric_column}' is missing.`);
      }
      if (plan.group_column && !source.fields.includes(plan.group_column)) {
        errors.push(`Group column '${plan.group_column}' is missing.`);
      }
      try {
        resolveLocalFilterConditions(
          source,
          plan.filter && typeof plan.filter === "object"
            ? (plan.filter as Record<string, unknown>)
            : {},
        );
      } catch (error) {
        if (error instanceof RuntimeValidationError) {
          errors.push(error.message);
        } else {
          throw error;
        }
      }
    }
    const valid = errors.length === 0;
    return {
      valid,
      errors,
      suggestions: valid
        ? []
        : ["Reconnect the source or rerun resolve against the current schema."],
      resolved: {
        source_name: plan.source_name,
        metric_column: plan.metric_column,
        group_column: plan.group_column ?? "",
      },
      valid_dimensions: plan.group_column ? [plan.group_column] : [],
      valid_measures: [plan.metric_column],
      source_behavior: "local_registered_source",
      latency_ms: roundLatency(startMs),
      verified: valid,
      request_id: `local_verify_${exactPlanHash(plan).slice(0, 12)}`,
      schema_revision: plan.schema_revision,
      plan_hash: exactPlanHash(plan),
      verification_mode: "local",
      rejection_reason: valid ? null : "plan_verification_failed",
    };
  } catch (error) {
    if (error instanceof RuntimeError) {
      return {
        valid: false,
        errors: [error.message],
        suggestions: ["Run Runtime.resolve(...) again with a more explicit metric or source."],
        resolved: {},
        latency_ms: roundLatency(startMs),
        verified: false,
        verification_mode: "local",
        rejection_reason: error.code,
      };
    }
    throw error;
  }
};

Runtime.prototype.coerceApiQueryPayload = function (
  this: Runtime,
  request: ResolvedPlan | ResolveResponse | Record<string, unknown>,
  overrides: Record<string, unknown>,
): Record<string, unknown> {
  if (Object.keys(overrides).length > 0) {
    return this.extractRuntimeDatasetScope({ ...overrides });
  }
  if ("resolved_plan" in request) {
    if (!request.resolved_plan) {
      throw new RuntimeValidationError(
        "query_requires_executable_plan",
        "Runtime.query() requires an executable plan.",
      );
    }
    return this.extractRuntimeDatasetScope({
      resolved_plan: { ...(request.resolved_plan as Record<string, unknown>) },
    });
  }
  if (looksLikeResolvedPlan(request)) {
    return this.extractRuntimeDatasetScope({
      resolved_plan: { ...(request as unknown as Record<string, unknown>) },
    });
  }
  return this.extractRuntimeDatasetScope({ ...(request as Record<string, unknown>) });
};

Runtime.prototype.extractRuntimeDatasetScope = function (
  this: Runtime,
  payload: Record<string, unknown>,
): Record<string, unknown> {
  const resolvedPlan = payload.resolved_plan;
  if (!resolvedPlan || typeof resolvedPlan !== "object" || Array.isArray(resolvedPlan)) {
    return payload;
  }
  const resolvedPlanPayload = { ...(resolvedPlan as Record<string, unknown>) };
  const rawConstraints = resolvedPlanPayload.constraints;
  if (!rawConstraints || typeof rawConstraints !== "object" || Array.isArray(rawConstraints)) {
    payload.resolved_plan = resolvedPlanPayload;
    return payload;
  }
  const constraints = { ...(rawConstraints as Record<string, unknown>) };
  const datasetId = constraints[RUNTIME_DATASET_SCOPE_KEY];
  delete constraints[RUNTIME_DATASET_SCOPE_KEY];
  if (
    payload.dataset_id === undefined &&
    typeof datasetId === "string" &&
    datasetId.trim()
  ) {
    payload.dataset_id = datasetId.trim();
  }
  resolvedPlanPayload.constraints = constraints;
  payload.resolved_plan = resolvedPlanPayload;
  return payload;
};

Runtime.prototype.coerceApiResolvePayload = function (
  this: Runtime,
  request: Record<string, unknown>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = { ...request };
  const sourceName = payload.source_name;
  if (typeof sourceName === "string" && sourceName.trim()) {
    if (payload.preferred_source === undefined) {
      payload.preferred_source = sourceName.trim();
    }
    if (payload.allow_org_scope === undefined) {
      payload.allow_org_scope = true;
    }
  }
  delete payload.source_name;

  const metric = payload.metric;
  if (typeof metric === "string") {
    payload.metric = {
      role: "metric",
      hint: metric.trim(),
    };
  }

  const groupBy = payload.group_by;
  if (typeof groupBy === "string") {
    payload.group_by = [groupBy];
  } else if (groupBy == null) {
    const groupColumn = payload.group_column;
    if (typeof groupColumn === "string" && groupColumn.trim()) {
      payload.group_by = [groupColumn.trim()];
    }
  }
  delete payload.group_column;
  delete payload.metric_column;
  delete payload.resolved_plan;
  return payload;
};
