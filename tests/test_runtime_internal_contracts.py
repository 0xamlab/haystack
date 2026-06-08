from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("pyarrow")

from apps.api_server.services.runtime_internal_contracts import (
    ArtifactRecord,
    AuditEventRecord,
    CapabilityRecord,
    CheckpointRecord,
    DependencyGraphRecord,
    MissionEvent,
    PatchImpactReportRecord,
    PolicySnapshotRecord,
    RepositoryGraphRecord,
    RepositorySnapshotRecord,
    SymbolGraphRecord,
    TelemetryBatch,
    WorkspaceEvidenceBundleRecord,
    artifact_record_schema,
    audit_event_record_schema,
    capability_record_schema,
    checkpoint_record_schema,
    dependency_graph_record_schema,
    mission_event_schema,
    parquet_bytes_from_records,
    patch_impact_report_record_schema,
    policy_snapshot_record_schema,
    record_batches_from_records,
    repository_graph_record_schema,
    repository_snapshot_record_schema,
    symbol_graph_record_schema,
    table_from_parquet_bytes,
    table_from_records,
    telemetry_batch_schema,
    validate_table_schema,
    workspace_evidence_bundle_record_schema,
)


def _utc() -> datetime:
    return datetime(2026, 5, 24, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("schema_fn", "contract_name"),
    [
        (capability_record_schema, "capability_record"),
        (mission_event_schema, "mission_event"),
        (checkpoint_record_schema, "checkpoint_record"),
        (artifact_record_schema, "artifact_record"),
        (telemetry_batch_schema, "telemetry_batch"),
        (policy_snapshot_record_schema, "policy_snapshot_record"),
        (audit_event_record_schema, "audit_event_record"),
        (repository_snapshot_record_schema, "repository_snapshot"),
        (repository_graph_record_schema, "repository_graph"),
        (symbol_graph_record_schema, "symbol_graph"),
        (dependency_graph_record_schema, "dependency_graph"),
        (workspace_evidence_bundle_record_schema, "workspace_evidence_bundle"),
        (patch_impact_report_record_schema, "patch_impact_report"),
    ],
)
def test_runtime_internal_contract_schemas_publish_arrow_and_parquet_metadata(
    schema_fn,
    contract_name: str,
) -> None:
    schema = schema_fn()

    assert schema.metadata is not None
    assert schema.metadata[b"algenta.contract_name"] == contract_name.encode()
    assert schema.metadata[b"algenta.contract_version"] == b"runtime-internal-contracts-v1"
    assert schema.metadata[b"algenta.in_process_transport"] == b"pyarrow.record_batch"
    assert schema.metadata[b"algenta.durable_format"] == b"parquet"


@pytest.mark.parametrize(
    ("record", "record_type"),
    [
        (
            CapabilityRecord(
                capability_id="cap.search.timeline",
                tool_name="timeline_scan",
                input_schema_ref="schemas/capability-input.json",
                output_schema_ref="schemas/capability-output.json",
                side_effect_class="read_only",
                risk_level="low",
                required_policy="policy.read.timeline",
                replayability="deterministic",
                approval_required=False,
                trust_tier="first_party",
            ),
            CapabilityRecord,
        ),
        (
            MissionEvent(
                mission_id="mission-1",
                thread_id="thread-1",
                tenant_scope="tenant-a",
                workspace_scope="workspace-a",
                event_index=0,
                superstep=1,
                node_name="retrieval",
                event_type="tool_call_requested",
                event_message="Requested tool execution.",
                details_json='{"tool":"search"}',
                event_ts=_utc(),
                request_hash="req-hash-1",
                policy_snapshot_id="policy-v1",
                schema_snapshot_id="schema-v1",
                manifest_version="runtime-manifest-v1",
                checkpoint_id="cp-1",
                artifact_refs=["artifact-1"],
                latency_ms=12,
                cost_usd_micros=44,
            ),
            MissionEvent,
        ),
        (
            CheckpointRecord(
                checkpoint_id="cp-1",
                parent_checkpoint_id="cp-0",
                tenant_scope="tenant-a",
                workspace_scope="workspace-a",
                request_hash="req-hash-1",
                policy_snapshot_id="policy-v1",
                schema_snapshot_id="schema-v1",
                manifest_version="runtime-manifest-v1",
                content_hash="sha256:cp1",
                event_start_index=0,
                event_end_index=2,
                artifact_refs=["artifact-1", "artifact-2"],
                created_at=_utc(),
            ),
            CheckpointRecord,
        ),
        (
            ArtifactRecord(
                artifact_id="artifact-1",
                artifact_kind="summary",
                tenant_scope="tenant-a",
                workspace_scope="workspace-a",
                schema_revision="artifact-v1",
                content_hash="sha256:artifact-1",
                storage_format="parquet",
                storage_path="artifacts/tenant-a/artifact-1.parquet",
                provenance_parent_hashes=["sha256:source-1"],
                created_at=_utc(),
            ),
            ArtifactRecord,
        ),
        (
            TelemetryBatch(
                batch_id="telemetry-1",
                telemetry_kind="provider_latency",
                module_name="bpe_tokenizer",
                tenant_scope="tenant-a",
                request_hash="req-hash-1",
                started_at=_utc(),
                ended_at=_utc(),
                success_count=10,
                failure_count=0,
                latency_ms_p95=3.2,
                cost_usd_micros=25,
            ),
            TelemetryBatch,
        ),
        (
            PolicySnapshotRecord(
                org_id="org-1",
                snapshot_id="execution-policy-v1-r2:abcd1234",
                previous_snapshot_id="execution-policy-v1-r1:aaaa1111",
                schema_revision="execution-policy-v1",
                revision=2,
                min_confidence=0.8,
                risk_floor=12500.0,
                require_calibration=True,
                allow_reexecution=False,
                content_hash="sha256:policy",
                created_at=_utc(),
                updated_at=_utc(),
            ),
            PolicySnapshotRecord,
        ),
        (
            AuditEventRecord(
                event_id="audit-1",
                org_id="org-1",
                actor_user_id="user-1",
                actor_email="owner@example.com",
                action="decision.execute",
                resource_type="decision_log",
                resource_id="decision-1",
                ip_address="203.0.113.10",
                result="success",
                metadata_json='{"policy_snapshot_id":"policy-v1"}',
                policy_snapshot_id="policy-v1",
                schema_snapshot_id="schema-v1",
                manifest_version="runtime-manifest-v1",
                request_hash="req-hash-1",
                content_hash="sha256:audit-1",
                created_at=_utc(),
            ),
            AuditEventRecord,
        ),
        (
            RepositorySnapshotRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                connector_type="local_repo",
                repository_url=None,
                resolved_revision="abc123",
                file_path="src/service.py",
                language="python",
                content_hash="sha256:file-1",
                line_count=12,
                byte_size=480,
                token_estimate=96,
                created_at=_utc(),
            ),
            RepositorySnapshotRecord,
        ),
        (
            RepositoryGraphRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                edge_id="edge-1",
                source_node="file:src/service.py",
                target_node="symbol:sym-1",
                edge_type="contains",
                weight=1.0,
                created_at=_utc(),
            ),
            RepositoryGraphRecord,
        ),
        (
            SymbolGraphRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                symbol_id="sym-1",
                file_path="src/service.py",
                symbol_name="handle_request",
                language="python",
                symbol_kind="function",
                start_line=1,
                end_line=8,
                parent_symbol_id=None,
                signature="handle_request",
                created_at=_utc(),
            ),
            SymbolGraphRecord,
        ),
        (
            DependencyGraphRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                dependency_edge_id="dep-1",
                source_file="tests/test_service.py",
                target_file="src/service.py",
                target_symbol="handle_request",
                dependency_type="imports",
                created_at=_utc(),
            ),
            DependencyGraphRecord,
        ),
        (
            WorkspaceEvidenceBundleRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                evidence_bundle_id="bundle-1",
                evidence_id="evidence-1",
                source_type="diagnostic",
                source_ref="src/service.py:4",
                file_path="src/service.py",
                symbol_name="handle_request",
                summary="Null user access",
                token_count=48,
                rank=1,
                created_at=_utc(),
            ),
            WorkspaceEvidenceBundleRecord,
        ),
        (
            PatchImpactReportRecord(
                repository_id="repo-1",
                snapshot_id="snapshot-1",
                patch_impact_report_id="impact-1",
                impacted_file="src/service.py",
                impacted_symbol="handle_request",
                risk_type="symbol_change",
                severity="medium",
                likely_failing_test="tests/test_service.py",
                dependency_target="tests/test_service.py",
                created_at=_utc(),
            ),
            PatchImpactReportRecord,
        ),
    ],
)
def test_runtime_internal_contracts_round_trip_record_batches_and_parquet(
    record,
    record_type,
) -> None:
    table = table_from_records([record], record_type=record_type)
    validate_table_schema(table, record_type)

    batches = record_batches_from_records([record], record_type=record_type)
    assert len(batches) == 1
    assert batches[0].num_rows == 1

    parquet_bytes = parquet_bytes_from_records([record], record_type=record_type)
    restored = table_from_parquet_bytes(parquet_bytes)
    validate_table_schema(restored, record_type)
    assert restored.num_rows == 1
    assert restored.column_names == table.column_names


def test_runtime_internal_contracts_reject_mixed_record_types() -> None:
    records = [
        CapabilityRecord(
            capability_id="cap.search.timeline",
            tool_name="timeline_scan",
            input_schema_ref="schemas/capability-input.json",
            output_schema_ref="schemas/capability-output.json",
            side_effect_class="read_only",
            risk_level="low",
            required_policy="policy.read.timeline",
            replayability="deterministic",
            approval_required=False,
            trust_tier="first_party",
        ),
        ArtifactRecord(
            artifact_id="artifact-1",
            artifact_kind="summary",
            tenant_scope="tenant-a",
            workspace_scope="workspace-a",
            schema_revision="artifact-v1",
            content_hash="sha256:artifact-1",
            storage_format="parquet",
            storage_path="artifacts/tenant-a/artifact-1.parquet",
            provenance_parent_hashes=["sha256:source-1"],
            created_at=_utc(),
        ),
    ]

    with pytest.raises(ValueError, match="same type"):
        table_from_records(records)


def test_runtime_internal_contracts_require_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MissionEvent(
            mission_id="mission-1",
            thread_id="thread-1",
            tenant_scope="tenant-a",
            workspace_scope="workspace-a",
            event_index=0,
            superstep=1,
            node_name="retrieval",
            event_type="tool_call_requested",
            event_message="Requested tool execution.",
            details_json='{"tool":"search"}',
            event_ts=datetime(2026, 5, 24, 12, 0),
            request_hash="req-hash-1",
            policy_snapshot_id="policy-v1",
            schema_snapshot_id="schema-v1",
            manifest_version="runtime-manifest-v1",
        )
