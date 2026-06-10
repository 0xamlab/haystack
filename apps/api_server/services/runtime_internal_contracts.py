from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator

from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.runtime_manifest import Replayability, RiskLevel, RuntimeFailureCode, SideEffectClass

_CONTRACT_VERSION = "runtime-internal-contracts-v1"
_IN_PROCESS_TRANSPORT = "pyarrow.record_batch"
_DURABLE_FORMAT = "parquet"


class RuntimeInternalContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _ensure_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _ensure_unique_strings(values: list[str], field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates.")
    return values


class CapabilityRecord(RuntimeInternalContractModel):
    capability_id: StrictStr
    tool_name: StrictStr
    input_schema_ref: StrictStr
    output_schema_ref: StrictStr
    side_effect_class: SideEffectClass
    risk_level: RiskLevel
    required_policy: StrictStr
    replayability: Replayability
    approval_required: StrictBool
    trust_tier: StrictStr
    provider_id: StrictStr | None = None
    profile_id: StrictStr | None = None
    kind: StrictStr | None = None
    implementation_kind: StrictStr | None = None
    execution_owner: StrictStr | None = None
    manifest_hash: StrictStr | None = None
    artifact_affinities: list[StrictStr] = Field(default_factory=list)
    tags: list[StrictStr] = Field(default_factory=list)
    required_binding_ids: list[StrictStr] = Field(default_factory=list)

    @field_validator("artifact_affinities", "tags", "required_binding_ids")
    @classmethod
    def _validate_capability_record_lists(cls, value: list[str], info) -> list[str]:
        return _ensure_unique_strings(value, str(info.field_name))


class MissionEvent(RuntimeInternalContractModel):
    mission_id: StrictStr
    thread_id: StrictStr
    tenant_scope: StrictStr
    workspace_scope: StrictStr
    event_index: StrictInt
    superstep: StrictInt
    node_name: StrictStr
    event_type: StrictStr
    event_message: StrictStr | None = None
    details_json: StrictStr | None = None
    event_ts: datetime
    request_hash: StrictStr
    policy_snapshot_id: StrictStr
    schema_snapshot_id: StrictStr
    manifest_version: StrictStr
    checkpoint_id: StrictStr | None = None
    artifact_refs: list[StrictStr] = Field(default_factory=list)
    failure_code: RuntimeFailureCode | None = None
    latency_ms: StrictInt | None = None
    cost_usd_micros: StrictInt | None = None

    @field_validator("event_ts")
    @classmethod
    def _validate_event_ts(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "event_ts")

    @field_validator("artifact_refs")
    @classmethod
    def _validate_artifact_refs(cls, value: list[str]) -> list[str]:
        return _ensure_unique_strings(value, "artifact_refs")


class CheckpointRecord(RuntimeInternalContractModel):
    checkpoint_id: StrictStr
    parent_checkpoint_id: StrictStr | None = None
    tenant_scope: StrictStr
    workspace_scope: StrictStr
    request_hash: StrictStr
    policy_snapshot_id: StrictStr
    schema_snapshot_id: StrictStr
    manifest_version: StrictStr
    content_hash: StrictStr
    event_start_index: StrictInt
    event_end_index: StrictInt
    artifact_refs: list[StrictStr] = Field(default_factory=list)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")

    @field_validator("artifact_refs")
    @classmethod
    def _validate_artifact_refs(cls, value: list[str]) -> list[str]:
        return _ensure_unique_strings(value, "artifact_refs")


class ArtifactRecord(RuntimeInternalContractModel):
    artifact_id: StrictStr
    artifact_kind: StrictStr
    tenant_scope: StrictStr
    workspace_scope: StrictStr
    schema_revision: StrictStr
    content_hash: StrictStr
    storage_format: StrictStr
    storage_path: StrictStr
    provenance_parent_hashes: list[StrictStr] = Field(default_factory=list)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")

    @field_validator("provenance_parent_hashes")
    @classmethod
    def _validate_parent_hashes(cls, value: list[str]) -> list[str]:
        return _ensure_unique_strings(value, "provenance_parent_hashes")


class TelemetryBatch(RuntimeInternalContractModel):
    batch_id: StrictStr
    telemetry_kind: StrictStr
    module_name: StrictStr
    tenant_scope: StrictStr
    request_hash: StrictStr
    started_at: datetime
    ended_at: datetime
    success_count: StrictInt
    failure_count: StrictInt
    latency_ms_p95: StrictFloat
    cost_usd_micros: StrictInt

    @field_validator("started_at", "ended_at")
    @classmethod
    def _validate_timestamps(cls, value: datetime, info) -> datetime:
        return _ensure_utc(value, str(info.field_name))


class PolicySnapshotRecord(RuntimeInternalContractModel):
    org_id: StrictStr
    snapshot_id: StrictStr
    previous_snapshot_id: StrictStr | None = None
    schema_revision: StrictStr
    revision: StrictInt
    min_confidence: StrictFloat
    risk_floor: StrictFloat | None = None
    require_calibration: StrictBool
    allow_reexecution: StrictBool
    content_hash: StrictStr
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _validate_policy_timestamps(cls, value: datetime, info) -> datetime:
        return _ensure_utc(value, str(info.field_name))


class AuditEventRecord(RuntimeInternalContractModel):
    event_id: StrictStr
    org_id: StrictStr
    actor_user_id: StrictStr | None = None
    actor_email: StrictStr
    action: StrictStr
    resource_type: StrictStr | None = None
    resource_id: StrictStr | None = None
    ip_address: StrictStr | None = None
    result: StrictStr
    metadata_json: StrictStr | None = None
    policy_snapshot_id: StrictStr | None = None
    schema_snapshot_id: StrictStr | None = None
    manifest_version: StrictStr | None = None
    request_hash: StrictStr | None = None
    content_hash: StrictStr
    created_at: datetime
    # Sub-tenancy scope. Optional + last so pre-#7 artifacts (which lack the column) remain
    # readable via the legacy-tolerant reader; a None value means org-wide / pre-migration.
    workspace_id: StrictStr | None = None

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class RepositorySnapshotRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    connector_type: StrictStr
    repository_url: StrictStr | None = None
    resolved_revision: StrictStr
    file_path: StrictStr
    language: StrictStr
    content_hash: StrictStr
    line_count: StrictInt
    byte_size: StrictInt
    token_estimate: StrictInt
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class RepositoryGraphRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    edge_id: StrictStr
    source_node: StrictStr
    target_node: StrictStr
    edge_type: StrictStr
    weight: StrictFloat
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class SymbolGraphRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    symbol_id: StrictStr
    file_path: StrictStr
    symbol_name: StrictStr
    language: StrictStr
    symbol_kind: StrictStr
    start_line: StrictInt
    end_line: StrictInt
    parent_symbol_id: StrictStr | None = None
    signature: StrictStr | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class DependencyGraphRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    dependency_edge_id: StrictStr
    source_file: StrictStr
    target_file: StrictStr | None = None
    target_symbol: StrictStr | None = None
    dependency_type: StrictStr
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class SymbolReferenceRecord(RuntimeInternalContractModel):
    # AR-OPT-2: persists per-file symbol references so the slim (v2) manifest can hydrate
    # them from Parquet instead of inlining them in the manifest JSON. v1 manifests have
    # no such artifact and remain readable via their inline arrays.
    repository_id: StrictStr
    snapshot_id: StrictStr
    reference_edge_id: StrictStr
    source_file: StrictStr
    source_symbol_id: StrictStr
    target_symbol_id: StrictStr | None = None
    target_file: StrictStr | None = None
    reference_type: StrictStr
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class WorkspaceEvidenceBundleRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    evidence_bundle_id: StrictStr
    evidence_id: StrictStr
    source_type: StrictStr
    source_ref: StrictStr
    file_path: StrictStr | None = None
    symbol_name: StrictStr | None = None
    summary: StrictStr
    token_count: StrictInt
    rank: StrictInt
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


class PatchImpactReportRecord(RuntimeInternalContractModel):
    repository_id: StrictStr
    snapshot_id: StrictStr
    patch_impact_report_id: StrictStr
    impacted_file: StrictStr
    impacted_symbol: StrictStr | None = None
    risk_type: StrictStr
    severity: StrictStr
    likely_failing_test: StrictStr | None = None
    dependency_target: StrictStr | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        return _ensure_utc(value, "created_at")


RuntimeContractRecord = TypeVar(
    "RuntimeContractRecord",
    CapabilityRecord,
    MissionEvent,
    CheckpointRecord,
    ArtifactRecord,
    TelemetryBatch,
    PolicySnapshotRecord,
    AuditEventRecord,
    RepositorySnapshotRecord,
    RepositoryGraphRecord,
    SymbolGraphRecord,
    DependencyGraphRecord,
    WorkspaceEvidenceBundleRecord,
    PatchImpactReportRecord,
)


def _load_pyarrow() -> tuple[Any, Any]:
    initialize_pyarrow_parquet_runtime()
    import pyarrow as pa
    import pyarrow.parquet as pq

    return pa, pq


def _schema_metadata(contract_name: str) -> dict[bytes, bytes]:
    return {
        b"algenta.contract_name": contract_name.encode(),
        b"algenta.contract_version": _CONTRACT_VERSION.encode(),
        b"algenta.in_process_transport": _IN_PROCESS_TRANSPORT.encode(),
        b"algenta.durable_format": _DURABLE_FORMAT.encode(),
    }


def capability_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("capability_id", pa.string()),
            pa.field("tool_name", pa.string()),
            pa.field("input_schema_ref", pa.string()),
            pa.field("output_schema_ref", pa.string()),
            pa.field("side_effect_class", pa.string()),
            pa.field("risk_level", pa.string()),
            pa.field("required_policy", pa.string()),
            pa.field("replayability", pa.string()),
            pa.field("approval_required", pa.bool_()),
            pa.field("trust_tier", pa.string()),
            pa.field("provider_id", pa.string()),
            pa.field("profile_id", pa.string()),
            pa.field("kind", pa.string()),
            pa.field("implementation_kind", pa.string()),
            pa.field("execution_owner", pa.string()),
            pa.field("manifest_hash", pa.string()),
            pa.field("artifact_affinities", pa.list_(pa.string())),
            pa.field("tags", pa.list_(pa.string())),
            pa.field("required_binding_ids", pa.list_(pa.string())),
        ],
        metadata=_schema_metadata("capability_record"),
    )


def mission_event_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("mission_id", pa.string()),
            pa.field("thread_id", pa.string()),
            pa.field("tenant_scope", pa.string()),
            pa.field("workspace_scope", pa.string()),
            pa.field("event_index", pa.int64()),
            pa.field("superstep", pa.int64()),
            pa.field("node_name", pa.string()),
            pa.field("event_type", pa.string()),
            pa.field("event_message", pa.string()),
            pa.field("details_json", pa.string()),
            pa.field("event_ts", pa.timestamp("us", tz="UTC")),
            pa.field("request_hash", pa.string()),
            pa.field("policy_snapshot_id", pa.string()),
            pa.field("schema_snapshot_id", pa.string()),
            pa.field("manifest_version", pa.string()),
            pa.field("checkpoint_id", pa.string()),
            pa.field("artifact_refs", pa.list_(pa.string())),
            pa.field("failure_code", pa.string()),
            pa.field("latency_ms", pa.int64()),
            pa.field("cost_usd_micros", pa.int64()),
        ],
        metadata=_schema_metadata("mission_event"),
    )


def checkpoint_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("checkpoint_id", pa.string()),
            pa.field("parent_checkpoint_id", pa.string()),
            pa.field("tenant_scope", pa.string()),
            pa.field("workspace_scope", pa.string()),
            pa.field("request_hash", pa.string()),
            pa.field("policy_snapshot_id", pa.string()),
            pa.field("schema_snapshot_id", pa.string()),
            pa.field("manifest_version", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("event_start_index", pa.int64()),
            pa.field("event_end_index", pa.int64()),
            pa.field("artifact_refs", pa.list_(pa.string())),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("checkpoint_record"),
    )


def artifact_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("artifact_id", pa.string()),
            pa.field("artifact_kind", pa.string()),
            pa.field("tenant_scope", pa.string()),
            pa.field("workspace_scope", pa.string()),
            pa.field("schema_revision", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("storage_format", pa.string()),
            pa.field("storage_path", pa.string()),
            pa.field("provenance_parent_hashes", pa.list_(pa.string())),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("artifact_record"),
    )


def telemetry_batch_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("batch_id", pa.string()),
            pa.field("telemetry_kind", pa.string()),
            pa.field("module_name", pa.string()),
            pa.field("tenant_scope", pa.string()),
            pa.field("request_hash", pa.string()),
            pa.field("started_at", pa.timestamp("us", tz="UTC")),
            pa.field("ended_at", pa.timestamp("us", tz="UTC")),
            pa.field("success_count", pa.int64()),
            pa.field("failure_count", pa.int64()),
            pa.field("latency_ms_p95", pa.float64()),
            pa.field("cost_usd_micros", pa.int64()),
        ],
        metadata=_schema_metadata("telemetry_batch"),
    )


def policy_snapshot_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("org_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("previous_snapshot_id", pa.string()),
            pa.field("schema_revision", pa.string()),
            pa.field("revision", pa.int64()),
            pa.field("min_confidence", pa.float64()),
            pa.field("risk_floor", pa.float64()),
            pa.field("require_calibration", pa.bool_()),
            pa.field("allow_reexecution", pa.bool_()),
            pa.field("content_hash", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
            pa.field("updated_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("policy_snapshot_record"),
    )


def audit_event_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("event_id", pa.string()),
            pa.field("org_id", pa.string()),
            pa.field("actor_user_id", pa.string()),
            pa.field("actor_email", pa.string()),
            pa.field("action", pa.string()),
            pa.field("resource_type", pa.string()),
            pa.field("resource_id", pa.string()),
            pa.field("ip_address", pa.string()),
            pa.field("result", pa.string()),
            pa.field("metadata_json", pa.string()),
            pa.field("policy_snapshot_id", pa.string()),
            pa.field("schema_snapshot_id", pa.string()),
            pa.field("manifest_version", pa.string()),
            pa.field("request_hash", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
            pa.field("workspace_id", pa.string()),
        ],
        metadata=_schema_metadata("audit_event_record"),
    )


def repository_snapshot_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("connector_type", pa.string()),
            pa.field("repository_url", pa.string()),
            pa.field("resolved_revision", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("language", pa.string()),
            pa.field("content_hash", pa.string()),
            pa.field("line_count", pa.int64()),
            pa.field("byte_size", pa.int64()),
            pa.field("token_estimate", pa.int64()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("repository_snapshot"),
    )


def repository_graph_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("edge_id", pa.string()),
            pa.field("source_node", pa.string()),
            pa.field("target_node", pa.string()),
            pa.field("edge_type", pa.string()),
            pa.field("weight", pa.float64()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("repository_graph"),
    )


def symbol_graph_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("symbol_id", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("symbol_name", pa.string()),
            pa.field("language", pa.string()),
            pa.field("symbol_kind", pa.string()),
            pa.field("start_line", pa.int64()),
            pa.field("end_line", pa.int64()),
            pa.field("parent_symbol_id", pa.string()),
            pa.field("signature", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("symbol_graph"),
    )


def dependency_graph_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("dependency_edge_id", pa.string()),
            pa.field("source_file", pa.string()),
            pa.field("target_file", pa.string()),
            pa.field("target_symbol", pa.string()),
            pa.field("dependency_type", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("dependency_graph"),
    )


def symbol_reference_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("reference_edge_id", pa.string()),
            pa.field("source_file", pa.string()),
            pa.field("source_symbol_id", pa.string()),
            pa.field("target_symbol_id", pa.string()),
            pa.field("target_file", pa.string()),
            pa.field("reference_type", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("symbol_reference"),
    )


def workspace_evidence_bundle_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("evidence_bundle_id", pa.string()),
            pa.field("evidence_id", pa.string()),
            pa.field("source_type", pa.string()),
            pa.field("source_ref", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("symbol_name", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("token_count", pa.int64()),
            pa.field("rank", pa.int64()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("workspace_evidence_bundle"),
    )


def patch_impact_report_record_schema() -> Any:
    pa, _ = _load_pyarrow()
    return pa.schema(
        [
            pa.field("repository_id", pa.string()),
            pa.field("snapshot_id", pa.string()),
            pa.field("patch_impact_report_id", pa.string()),
            pa.field("impacted_file", pa.string()),
            pa.field("impacted_symbol", pa.string()),
            pa.field("risk_type", pa.string()),
            pa.field("severity", pa.string()),
            pa.field("likely_failing_test", pa.string()),
            pa.field("dependency_target", pa.string()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
        ],
        metadata=_schema_metadata("patch_impact_report"),
    )


_SCHEMA_BUILDERS: dict[type[RuntimeInternalContractModel], Any] = {
    CapabilityRecord: capability_record_schema,
    MissionEvent: mission_event_schema,
    CheckpointRecord: checkpoint_record_schema,
    ArtifactRecord: artifact_record_schema,
    TelemetryBatch: telemetry_batch_schema,
    PolicySnapshotRecord: policy_snapshot_record_schema,
    AuditEventRecord: audit_event_record_schema,
    RepositorySnapshotRecord: repository_snapshot_record_schema,
    RepositoryGraphRecord: repository_graph_record_schema,
    SymbolGraphRecord: symbol_graph_record_schema,
    DependencyGraphRecord: dependency_graph_record_schema,
    SymbolReferenceRecord: symbol_reference_record_schema,
    WorkspaceEvidenceBundleRecord: workspace_evidence_bundle_record_schema,
    PatchImpactReportRecord: patch_impact_report_record_schema,
}


def schema_for_record_type(record_type: type[RuntimeContractRecord]) -> Any:
    try:
        builder = _SCHEMA_BUILDERS[record_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported runtime contract record type: {record_type!r}") from exc
    return builder()


def table_from_records(
    records: Sequence[RuntimeContractRecord],
    *,
    record_type: type[RuntimeContractRecord] | None = None,
) -> Any:
    if record_type is None:
        if not records:
            raise ValueError("record_type must be provided when records is empty.")
        record_type = type(records[0])
    if any(type(record) is not record_type for record in records):
        raise ValueError("All runtime internal contract records must share the same type.")
    pa, _ = _load_pyarrow()
    schema = schema_for_record_type(record_type)
    rows = [record.model_dump(mode="python") for record in records]
    return pa.Table.from_pylist(rows, schema=schema)


def record_batches_from_records(
    records: Sequence[RuntimeContractRecord],
    *,
    record_type: type[RuntimeContractRecord] | None = None,
    max_chunksize: int | None = None,
) -> list[Any]:
    table = table_from_records(records, record_type=record_type)
    return table.to_batches(max_chunksize=max_chunksize)


def parquet_bytes_from_table(table: Any) -> bytes:
    _, pq = _load_pyarrow()
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    return buffer.getvalue()


def parquet_bytes_from_records(
    records: Sequence[RuntimeContractRecord],
    *,
    record_type: type[RuntimeContractRecord] | None = None,
) -> bytes:
    return parquet_bytes_from_table(table_from_records(records, record_type=record_type))


def table_from_parquet_bytes(parquet_bytes: bytes) -> Any:
    _, pq = _load_pyarrow()
    return pq.read_table(io.BytesIO(parquet_bytes))


def table_from_parquet_bytes_tolerant(
    parquet_bytes: bytes, record_type: type[RuntimeContractRecord]
) -> Any:
    """Read a parquet table, tolerating LEGACY files that predate OPTIONAL columns later added
    to ``record_type``'s schema. Any expected field absent from the file is appended as a
    null column, the columns are reordered to the expected schema order, and the expected
    schema metadata is restored — so the strict ``validate_table_schema`` and model parsing
    both succeed and legacy rows get ``None`` for the new optional fields.

    Files that already match (no missing fields) pass through unchanged, so current writers
    are unaffected. Only use this for record types whose added columns are OPTIONAL (None) on
    the model; a missing REQUIRED column would still (correctly) fail model validation.
    """
    pa, pq = _load_pyarrow()
    table = pq.read_table(io.BytesIO(parquet_bytes))
    expected = schema_for_record_type(record_type)
    missing = [name for name in expected.names if name not in table.schema.names]
    if not missing:
        return table
    for name in missing:
        field = expected.field(name)
        table = table.append_column(field, pa.array([None] * table.num_rows, type=field.type))
    # Reorder to the expected field order and restore the expected schema metadata so the
    # strict validator (which checks names-order + metadata) passes.
    return table.select(expected.names).replace_schema_metadata(expected.metadata)


def _field_type_signature(field_type: Any) -> Any:
    pa, _ = _load_pyarrow()
    if pa.types.is_list(field_type) or pa.types.is_large_list(field_type):
        return ("list", _field_type_signature(field_type.value_field.type))
    if pa.types.is_struct(field_type):
        return (
            "struct",
            tuple((field.name, _field_type_signature(field.type)) for field in field_type),
        )
    return str(field_type)


def validate_table_schema(table: Any, record_type: type[RuntimeContractRecord]) -> None:
    expected_schema = schema_for_record_type(record_type)
    if table.schema.metadata != expected_schema.metadata:
        raise ValueError(
            f"Arrow schema metadata mismatch for {record_type.__name__}: "
            f"{table.schema.metadata!r} != {expected_schema.metadata!r}"
        )
    if table.schema.names != expected_schema.names:
        raise ValueError(
            f"Arrow schema field ordering mismatch for {record_type.__name__}: "
            f"{table.schema.names!r} != {expected_schema.names!r}"
        )
    actual_types = [_field_type_signature(field.type) for field in table.schema]
    expected_types = [_field_type_signature(field.type) for field in expected_schema]
    if actual_types != expected_types:
        raise ValueError(
            f"Arrow schema mismatch for {record_type.__name__}: "
            f"{table.schema} != {expected_schema}"
        )
