from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api_server.schemas.common import ErrorDetail, ErrorResponse
from apps.api_server.schemas.data_map import DataSource

DERIVED_MEASURE = "derived_measure"
BASE_MEASURE = "base_measure"
UNIT_MEASURE = "unit_measure"
COMPONENT = "component"
RATIO = "ratio"
IDENTIFIER = "identifier"
TIME = "time"
CATEGORY = "category"
TEXT = "text"
METRIC = "metric"

ALL_ROLES = {
    DERIVED_MEASURE,
    BASE_MEASURE,
    UNIT_MEASURE,
    COMPONENT,
    RATIO,
    IDENTIFIER,
    TIME,
    CATEGORY,
    TEXT,
    METRIC,
}

_DEFAULT_JOIN_PATH_HOPS = 4
_MAX_JOIN_PATH_HOPS = 6
_DECISION_AUTO_ACCEPT_CONFIDENCE = 0.85
_DECISION_CLARIFY_CONFIDENCE = 0.70
_DECISION_MIN_CANDIDATE_GAP = 0.10
_COUNT_ANCHOR_ROLE_PRIORITY = (
    "identifier",
    "base_measure",
    "metric",
    "derived_measure",
    "unit_measure",
    "text",
    "category",
    "time",
)


def _error_details(items: list[tuple[str | None, str]] | None) -> list[ErrorDetail]:
    return [ErrorDetail(field=field, issue=issue) for field, issue in (items or [])]


def _http_error(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str | None = None,
    details: list[tuple[str | None, str]] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse.make(
            code=code,
            message=message,
            request_id=request_id,
            details=_error_details(details),
        ).model_dump(mode="python"),
    )


class ConstraintSpec(BaseModel):
    requires_derived: bool = Field(
        default=False,
        description="Reject if metric column is not a derived_measure (formula-proven).",
    )
    no_cross_source: bool = Field(
        default=False,
        description="Reject if query requires a cross-source join.",
    )
    min_column_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Reject if column_confidence component < this value.",
    )
    max_join_hops: int = Field(
        default=_DEFAULT_JOIN_PATH_HOPS,
        ge=1,
        le=_MAX_JOIN_PATH_HOPS,
        description=(
            "Safe default join-path budget for planner-generated cross-source queries. "
            "Defaults to 4 hops; explicit opt-in can raise this to 6 hops (7 tables)."
        ),
    )


class MetricSpec(BaseModel):
    """
    Structural role target. The LLM selects based on what the user wants.

    Use 'derived_measure' for revenue, spend, total value — the computed aggregate.
    Use 'base_measure' for counts, quantities, discrete amounts.
    Use 'unit_measure' for prices, rates, per-unit values.
    Use 'ratio' for percentages, margins, fill rates.
    Use 'metric' to let the engine pick the best numeric column.
    """

    role: str = Field(
        default=DERIVED_MEASURE,
        description=(
            f"Structural role. One of: {', '.join(sorted(ALL_ROLES))}. "
            "derived_measure = computed aggregate (revenue, total value). "
            "base_measure = count/quantity. unit_measure = price/rate. "
            "ratio = percentage/margin. metric = best numeric column."
        ),
    )
    hint: str | None = Field(
        default=None,
        description=(
            "Optional weak signal — a word from the user's question. "
            "Used only as a tiebreaker when multiple columns share the same role. "
            "Never the primary signal. Examples: 'revenue', 'quantity', 'price'."
        ),
    )


class FilterSpec(BaseModel):
    """Time or value filter."""

    time_filter: str | None = Field(
        default=None,
        description=(
            "Relative time window. One of: last_quarter, this_quarter, "
            "last_month, this_month, last_year, this_year."
        ),
    )
    conditions: list[FilterConditionSpec] = Field(
        default_factory=list,
        description=(
            "Optional deterministic non-time predicates applied on the metric source. "
            "These are record predicates over normalized rows, not SQL clauses. "
            "Use exact column when schema is known, or dimension_hint for categorical "
            "dimensions when only the semantic label is known, including Redis and "
            "other non-SQL sources after normalization. Supported ops: "
            "eq, in, gt, gte, lt, lte, is_null, is_not_null."
        ),
    )


class FilterConditionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column: str | None = Field(
        default=None,
        description="Exact source column name for this filter when schema is known.",
    )
    dimension_hint: str | None = Field(
        default=None,
        description=(
            "Weak semantic label for the filter dimension when the exact column "
            "name is not known yet. Best for status/type/category style filters."
        ),
    )
    op: Literal["eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"] = Field(
        default="eq",
        description="Deterministic filter operator.",
    )
    value: Any | None = Field(
        default=None,
        description="Scalar comparison value for eq/gt/gte/lt/lte.",
    )
    values: list[Any] | None = Field(
        default=None,
        description="List comparison values for in.",
    )

    @model_validator(mode="after")
    def _validate_filter_condition(self) -> FilterConditionSpec:
        column = (self.column or "").strip() or None
        dimension_hint = (self.dimension_hint or "").strip() or None
        if column is None and dimension_hint is None:
            raise ValueError("filter condition requires column or dimension_hint")
        self.column = column
        self.dimension_hint = dimension_hint

        if self.op == "in":
            if self.value is not None:
                raise ValueError("filter condition op='in' does not accept value")
            if not self.values:
                raise ValueError("filter condition op='in' requires non-empty values")
        elif self.op in {"is_null", "is_not_null"}:
            if self.value is not None or self.values is not None:
                raise ValueError("filter condition null checks do not accept value or values")
        else:
            if self.values is not None:
                raise ValueError(f"filter condition op='{self.op}' does not accept values")
            if self.value is None:
                raise ValueError(f"filter condition op='{self.op}' requires value")
        return self


class JoinEdgeSpec(BaseModel):
    """One explicit edge in a multi-hop join path."""

    model_config = ConfigDict(extra="forbid")

    left_source: str = Field(..., description="Source on the left side of the join edge.")
    right_source: str = Field(..., description="Source on the right side of the join edge.")
    left_key: str = Field(..., description="Exact join key column in left_source.")
    right_key: str = Field(..., description="Exact join key column in right_source.")
    join_type: str = Field(
        default="inner", description="Join type. Initial implementation supports inner."
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable confidence for this hop.",
    )
    expected_cardinality: str | None = Field(
        default=None,
        description=(
            "Optional expected cardinality such as one_to_many, many_to_one, or many_to_many."
        ),
    )
    allow_many_to_many: bool = Field(
        default=False,
        description="If false, planner/executor must reject many_to_many fanout on this hop.",
    )


class JoinPathSpec(BaseModel):
    """Explicit multi-hop join contract replacing single-hop join fields."""

    model_config = ConfigDict(extra="forbid")

    base_source: str = Field(
        ..., description="Source that owns the metric column and anchors the path."
    )
    group_source: str | None = Field(
        default=None,
        description=(
            "Final source expected to provide the group column, if different from base_source."
        ),
    )
    edges: list[JoinEdgeSpec] = Field(
        default_factory=list,
        description="Ordered join edges from base_source toward the dimension source.",
    )
    max_hops: int = Field(
        default=_DEFAULT_JOIN_PATH_HOPS,
        ge=1,
        le=_MAX_JOIN_PATH_HOPS,
        description=(
            "Maximum allowed join hops for this request. Defaults to 4; "
            "explicit opt-in can raise this to 6 hops (7 tables)."
        ),
    )
    min_path_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable composed confidence across the full join path.",
    )
    reject_on_ambiguity: bool = Field(
        default=True,
        description=(
            "Reject if more than one viable path exists with insufficient score separation."
        ),
    )
    reject_on_fanout: bool = Field(
        default=True,
        description="Reject if estimated path fanout exceeds safe execution thresholds.",
    )


class ResolvedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    metric_column: str
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    group_column: str | None = None
    join_path: JoinPathSpec | None = None
    filter: FilterSpec | None = None
    limit: int | None = None
    order: str = Field(default="desc", description="desc | asc")
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    schema_revision: str


class ResolveRequest(BaseModel):
    """Bounded planning request that returns an exact executable plan."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = Field(
        default=None,
        description=(
            "Public dataset ID alias for a registered source. "
            "Required unless allow_org_scope=true or only one visible dataset exists."
        ),
    )
    metric: MetricSpec = Field(default_factory=MetricSpec)
    group_by: list[str] = Field(default_factory=list)
    preferred_source: str | None = Field(default=None)
    reject_on_ambiguity: bool = Field(default=False)
    min_source_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    filter: FilterSpec | None = None
    limit: int | None = Field(default=None, description="Top-N limit")
    order: str = Field(default="desc", description="desc | asc")
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    raw_text: str | None = Field(
        default=None,
        description=(
            "Optional non-authoritative raw text hint. "
            "Structured intent remains the source of truth."
        ),
    )
    include_explanation: bool = Field(default=False)
    allow_org_scope: bool = Field(
        default=False,
        description="When true, resolve can consider all visible datasets in the org.",
    )


class QueryRequest(BaseModel):
    """
    Structured query execution request.

    ═══════════════════════════════════════════════════════════
    PRIMARY PATH  —  Exact spec  (use after reading the schema)
    ═══════════════════════════════════════════════════════════
    The correct flow:
      1. Call POST /v1/sources/register or POST /v1/sources/schema
      2. LLM reads the returned schema (column names, roles, formulas)
      3. LLM sends exact column names — Mojo validates and executes

    Example (top 5 customers by revenue):
      {
        "source_name": "S0",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "aggregation": "sum",
        "limit": 5
      }

    For multi-hop joins:
      {
        "source_name": "S0",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "join_path": {
          "base_source": "S0",
          "group_source": "S2",
          "edges": [
            {
              "left_source": "S0",
              "right_source": "S1",
              "left_key": "k01_left",
              "right_key": "k01_right"
            },
            {
              "left_source": "S1",
              "right_source": "S2",
              "left_key": "k12_left",
              "right_key": "k12_right"
            }
          ]
        },
        "aggregation": "sum"
      }

    ═══════════════════════════════════════════════════════════
    FALLBACK PATH  —  Hint spec  (when schema is not yet known)
    ═══════════════════════════════════════════════════════════
    The engine resolves source and columns from structural role hints.
    Use this ONLY for exploratory queries. Always migrate to exact spec
    once you have the schema — it is faster and never ambiguous.

    Example:
      {
        "metric": {"role": "derived_measure", "hint": "total value"},
        "group_by": ["segment"],
        "aggregation": "sum",
        "limit": 5
      }
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = Field(
        default=None,
        description=(
            "Public dataset ID alias for a registered source. "
            "When provided, query execution is scoped to that one registered dataset."
        ),
    )
    source_name: str | None = Field(
        default=None,
        description=(
            "EXACT source name from the registry "
            "(e.g. 'Bookings'). Bypasses source resolver entirely. "
            "Get this from POST /v1/sources/schema or the registration response."
        ),
    )
    metric_column: str | None = Field(
        default=None,
        description=(
            "EXACT column name for the metric "
            "(e.g. 'EXT_PRICE'). Bypasses column resolver. "
            "The engine validates this column exists in source_name."
        ),
    )
    group_column: str | None = Field(
        default=None,
        description=(
            "EXACT column name for group-by "
            "(e.g. 'CUSTOMER'). Bypasses group resolver. "
            "Can be in source_name or in the terminal source of join_path."
        ),
    )
    join_path: JoinPathSpec | None = Field(
        default=None,
        description=(
            "Explicit multi-hop join graph. Breaking replacement for single-hop join fields. "
            "Defaults to a safe 4-hop budget; explicit opt-in can raise this to 6 hops "
            "(7 tables) with per-edge constraints and path-level confidence gates."
        ),
    )
    sources: list[DataSource] = Field(
        default=[],
        description="Raw data sources (inline CSV/JSON). Usually empty — use registry.",
    )
    metric: MetricSpec = Field(default_factory=MetricSpec)
    group_by: list[str] = Field(
        default=[],
        description=(
            "Hint mode only: dimension words from the user's question "
            "(e.g. ['customer', 'region']). Ignored when group_column is set."
        ),
    )
    preferred_source: str | None = Field(
        default=None,
        description=(
            "Hint mode only: source name the LLM believes is correct. "
            "Hard-locks the source resolver. Ignored when source_name is set."
        ),
    )
    reject_on_ambiguity: bool = Field(
        default=False,
        description=(
            "Hint mode only: when True and resolver confidence < 0.40, "
            "return null result with source candidates instead of guessing."
        ),
    )
    min_source_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Hint mode only: minimum resolver confidence threshold.",
    )
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    filter: FilterSpec | None = None
    limit: int | None = Field(default=None, description="Top-N limit")
    order: str = Field(default="desc", description="desc | asc")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    resolved_plan: ResolvedPlan | None = Field(
        default=None,
        description="Exact plan returned by POST /v1/resolve.",
    )


class CandidateColumn(BaseModel):
    source: str
    column: str
    role: str
    magnitude: str
    formula: str | None
    confidence: float
    score_components: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    query_id: str
    result: Any
    result_type: str
    confidence: float
    plan: list[str]
    resolved_column: str
    resolved_role: str
    resolved_source: str
    row_count: int
    candidates: list[CandidateColumn]
    source_scores: dict[str, float]
    ambiguous: bool
    exact_spec: bool
    explanation: list[str] = []
    latency_ms: float
    decision_path: str
    plan_hash: str
    schema_revision: str | None = None
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    source_set: list[str] = []
    join_path: list[dict[str, Any]] = []
    planner_mode: str = "planner_hint"


class ResolveResponse(BaseModel):
    resolved_plan: ResolvedPlan | None = None
    confidence: float
    plan: list[str]
    explanation: list[str] = Field(default_factory=list)
    resolved_column: str = ""
    resolved_role: str = ""
    resolved_source: str = ""
    candidates: list[CandidateColumn] = Field(default_factory=list)
    source_scores: dict[str, float] = Field(default_factory=dict)
    latency_ms: float
    decision_path: str
    plan_hash: str | None = None
    schema_revision: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    intent_signature: str
    source_set: list[str] = Field(default_factory=list)
    join_path: list[dict[str, Any]] = Field(default_factory=list)
    planner_mode: str = "registry_planner"


class QueryExecutionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    cache_hit: bool | None = None


class QueryBatchDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = None
    filter: FilterSpec | None = None
    limit: int | None = None
    order: str | None = None


class QueryBatchItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    request: QueryRequest


class QueryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: QueryBatchDefaults | None = None
    queries: list[QueryBatchItemRequest] = Field(min_length=1)


class QueryBatchError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QueryBatchItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    data: QueryResponse | None = None
    metadata: QueryExecutionMetadata | None = None
    error: QueryBatchError | None = None


class QueryBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[QueryBatchItemResponse] = Field(default_factory=list)
    request_id: str | None = None


class SQLReportSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    alias: str | None = None


class SQLReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SQLReportSource] = Field(min_length=1)
    sql: str = Field(min_length=1)
    max_rows: int | None = Field(default=None, ge=1, le=1000)


class SQLReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int
    truncated: bool = False
    request_id: str | None = None
    latency_ms: float


QueryPayload = QueryRequest


def _candidate_confidence(candidate: CandidateColumn | dict[str, Any]) -> float:
    if isinstance(candidate, CandidateColumn):
        return float(candidate.confidence)
    return float(candidate.get("confidence", 0.0) or 0.0)


def _candidate_confidence_gap(
    candidates: list[CandidateColumn] | list[dict[str, Any]],
) -> float | None:
    if len(candidates) < 2:
        return None
    ordered = sorted(candidates, key=_candidate_confidence, reverse=True)
    return round(_candidate_confidence(ordered[0]) - _candidate_confidence(ordered[1]), 3)


def _classify_query_rejection(error_text: str | None) -> str | None:
    if not error_text:
        return None
    lowered = error_text.lower()
    if any(token in lowered for token in ("stale", "freshness")):
        return "stale_source"
    if any(token in lowered for token in ("verify", "verification", "constraint")):
        return "plan_verification_failed"
    if any(
        token in lowered
        for token in (
            "fanout",
            "many_to_many",
            "join path",
            "join_path",
            "join key",
            "join candidates",
            "no join path",
            "ambiguous multi-hop",
            "cross-source",
        )
    ):
        return "join_ambiguity"
    if any(token in lowered for token in ("schema", "column", "dimension", "source", "metadata")):
        return "schema_incomplete"
    return "schema_unresolved"


def _decision_contract_flags(
    confidence: float,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    *,
    error_text: str | None = None,
) -> tuple[bool, bool, str | None]:
    rejection_reason = _classify_query_rejection(error_text)
    if rejection_reason is not None:
        return False, False, rejection_reason
    if confidence < _DECISION_CLARIFY_CONFIDENCE:
        return False, False, "schema_unresolved"
    gap = _candidate_confidence_gap(candidates)
    if confidence < _DECISION_AUTO_ACCEPT_CONFIDENCE:
        return False, True, None
    if gap is not None and gap < _DECISION_MIN_CANDIDATE_GAP:
        return False, True, None
    return True, False, None


def _select_count_anchor_column(schema_meta: dict[str, Any]) -> tuple[str, str] | None:
    columns = schema_meta.get("columns") or []
    normalized = [column for column in columns if str(column.get("name", "")).strip()]
    if not normalized:
        return None

    for role in _COUNT_ANCHOR_ROLE_PRIORITY:
        for column in normalized:
            if str(column.get("role", "")).strip() == role:
                return str(column["name"]), role

    first = normalized[0]
    fallback_role = str(first.get("role", "")).strip() or "metric"
    if fallback_role not in _COUNT_ANCHOR_ROLE_PRIORITY:
        fallback_role = "metric"
    return str(first["name"]), fallback_role


def _query_plan_hash(
    *,
    decision_path: str,
    schema_revision: str | None,
    basis: dict[str, Any],
) -> str:
    payload = {
        "decision_path": decision_path,
        "schema_revision": schema_revision or "",
        "basis": basis,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :24
    ]


__all__ = (
    "ALL_ROLES",
    "BASE_MEASURE",
    "CATEGORY",
    "COMPONENT",
    "ConstraintSpec",
    "CandidateColumn",
    "DERIVED_MEASURE",
    "FilterSpec",
    "IDENTIFIER",
    "JoinEdgeSpec",
    "JoinPathSpec",
    "METRIC",
    "MetricSpec",
    "QueryPayload",
    "QueryBatchDefaults",
    "QueryBatchError",
    "QueryBatchItemRequest",
    "QueryBatchItemResponse",
    "QueryBatchRequest",
    "QueryBatchResponse",
    "QueryExecutionMetadata",
    "QueryRequest",
    "QueryResponse",
    "RATIO",
    "ResolveRequest",
    "ResolveResponse",
    "ResolvedPlan",
    "SQLReportRequest",
    "SQLReportResponse",
    "SQLReportSource",
    "TEXT",
    "TIME",
    "UNIT_MEASURE",
    "_DECISION_AUTO_ACCEPT_CONFIDENCE",
    "_DEFAULT_JOIN_PATH_HOPS",
    "_MAX_JOIN_PATH_HOPS",
    "_candidate_confidence",
    "_candidate_confidence_gap",
    "_classify_query_rejection",
    "_decision_contract_flags",
    "_error_details",
    "_http_error",
    "_query_plan_hash",
    "_select_count_anchor_column",
)
