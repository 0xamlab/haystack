from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable
from algenta.runtime_model_decision_plan import DecisionPlanOutput


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_boolean(data: dict[str, Any], key: str, context: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TypeError(f"{context}.{key} must be a boolean.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise TypeError(f"{context}.{key} must be a list of non-empty strings.")
    return [str(item) for item in value]


def _optional_string_list(data: dict[str, Any], key: str, context: str) -> list[str]:
    if key not in data:
        return []
    return _require_string_list(data, key, context)


def _require_integer_mapping(
    data: dict[str, Any],
    key: str,
    context: str,
) -> dict[str, int]:
    raw = data.get(key)
    if not isinstance(raw, dict):
        raise TypeError(f"{context}.{key} must be a mapping.")
    normalized: dict[str, int] = {}
    for item_key, item_value in raw.items():
        if not isinstance(item_key, str) or not item_key:
            raise TypeError(f"{context}.{key} keys must be non-empty strings.")
        if isinstance(item_value, bool) or not isinstance(item_value, int):
            raise TypeError(f"{context}.{key}.{item_key} must be an integer.")
        normalized[item_key] = item_value
    return normalized


def _optional_mapping(value: Any, context: str) -> dict[str, Any]:
    try:
        return coerce_payload_mapping(value)
    except Exception as exc:  # noqa: BLE001
        raise TypeError(f"{context} must be a mapping.") from exc


@dataclass(frozen=True)
class RepositoryArtifactRefOutput:
    artifact_id: str
    artifact_kind: str
    content_hash: str
    storage_path: str
    schema_revision: str | None = None
    created_at: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryArtifactRefOutput:
        context = "repository_artifact"
        data = coerce_payload_mapping(payload)
        return cls(
            artifact_id=_require_string(data, "artifact_id", context),
            artifact_kind=_require_string(data, "artifact_kind", context),
            content_hash=_require_string(data, "content_hash", context),
            storage_path=_require_string(data, "storage_path", context),
            schema_revision=_optional_string(data, "schema_revision", context),
            created_at=_require_datetime_text(data, "created_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryEvidenceItemOutput:
    evidence_id: str
    rank: int
    source_type: str
    source_ref: str
    summary: str
    snippet: str
    token_count: int
    score: float
    file_path: str | None = None
    symbol_name: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryEvidenceItemOutput:
        context = "repository_triage.evidence_items.item"
        data = coerce_payload_mapping(payload)
        return cls(
            evidence_id=_require_string(data, "evidence_id", context),
            rank=_require_integer(data, "rank", context),
            source_type=_require_string(data, "source_type", context),
            source_ref=_require_string(data, "source_ref", context),
            summary=_require_string(data, "summary", context),
            snippet=_require_string(data, "snippet", context),
            token_count=_require_integer(data, "token_count", context),
            score=_require_number(data, "score", context),
            file_path=_optional_string(data, "file_path", context),
            symbol_name=_optional_string(data, "symbol_name", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryLanguageSupportProgressOutput:
    supported_real_language_count: int
    ranked_target_language_count: int
    progress_fraction: float
    progress_label: str

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryLanguageSupportProgressOutput:
        context = "repository_capabilities.support_progress"
        data = coerce_payload_mapping(payload)
        return cls(
            supported_real_language_count=_require_integer(
                data, "supported_real_language_count", context
            ),
            ranked_target_language_count=_require_integer(
                data, "ranked_target_language_count", context
            ),
            progress_fraction=_require_number(data, "progress_fraction", context),
            progress_label=_require_string(data, "progress_label", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryIntelligenceCapabilitiesOutput:
    supported_languages: list[str] = field(default_factory=list)
    support_progress: RepositoryLanguageSupportProgressOutput = field(
        default_factory=lambda: RepositoryLanguageSupportProgressOutput(
            supported_real_language_count=0,
            ranked_target_language_count=1,
            progress_fraction=0.0,
            progress_label="0 / 1",
        )
    )

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryIntelligenceCapabilitiesOutput:
        context = "repository_capabilities"
        data = coerce_payload_mapping(payload)
        return cls(
            supported_languages=_require_string_list(data, "supported_languages", context),
            support_progress=RepositoryLanguageSupportProgressOutput.from_api(
                data.get("support_progress")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositorySnapshotOutput:
    repository_id: str
    snapshot_id: str
    connector_type: str
    resolved_revision: str
    content_hash: str
    status: str
    created_at: str
    file_count: int
    language_counts: dict[str, int] = field(default_factory=dict)
    raw_repo_token_estimate: int = 0
    repository_snapshot_artifact: RepositoryArtifactRefOutput = field(
        default_factory=lambda: RepositoryArtifactRefOutput(
            artifact_id="",
            artifact_kind="",
            content_hash="",
            storage_path="",
            created_at="",
        )
    )
    repository_graph_artifact: RepositoryArtifactRefOutput = field(
        default_factory=lambda: RepositoryArtifactRefOutput(
            artifact_id="",
            artifact_kind="",
            content_hash="",
            storage_path="",
            created_at="",
        )
    )
    symbol_graph_artifact: RepositoryArtifactRefOutput = field(
        default_factory=lambda: RepositoryArtifactRefOutput(
            artifact_id="",
            artifact_kind="",
            content_hash="",
            storage_path="",
            created_at="",
        )
    )
    dependency_graph_artifact: RepositoryArtifactRefOutput = field(
        default_factory=lambda: RepositoryArtifactRefOutput(
            artifact_id="",
            artifact_kind="",
            content_hash="",
            storage_path="",
            created_at="",
        )
    )
    ref: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RepositorySnapshotOutput:
        context = "repository_snapshot"
        data = coerce_payload_mapping(payload)
        return cls(
            repository_id=_require_string(data, "repository_id", context),
            snapshot_id=_require_string(data, "snapshot_id", context),
            connector_type=_require_string(data, "connector_type", context),
            ref=_optional_string(data, "ref", context),
            resolved_revision=_require_string(data, "resolved_revision", context),
            content_hash=_require_string(data, "content_hash", context),
            status=_require_string(data, "status", context),
            created_at=_require_datetime_text(data, "created_at", context),
            file_count=_require_integer(data, "file_count", context),
            language_counts=_require_integer_mapping(data, "language_counts", context),
            raw_repo_token_estimate=_require_integer(data, "raw_repo_token_estimate", context),
            repository_snapshot_artifact=RepositoryArtifactRefOutput.from_api(
                data.get("repository_snapshot_artifact")
            ),
            repository_graph_artifact=RepositoryArtifactRefOutput.from_api(
                data.get("repository_graph_artifact")
            ),
            symbol_graph_artifact=RepositoryArtifactRefOutput.from_api(
                data.get("symbol_graph_artifact")
            ),
            dependency_graph_artifact=RepositoryArtifactRefOutput.from_api(
                data.get("dependency_graph_artifact")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryTriageOutput:
    repository_id: str
    snapshot_id: str
    workspace_evidence_bundle_ref: str
    created_at: str
    raw_repo_token_estimate: int
    evidence_bundle_token_count: int
    reduction_ratio: float
    evidence_items: list[RepositoryEvidenceItemOutput] = field(default_factory=list)
    workspace_evidence_bundle_artifact: RepositoryArtifactRefOutput = field(
        default_factory=lambda: RepositoryArtifactRefOutput(
            artifact_id="",
            artifact_kind="",
            content_hash="",
            storage_path="",
            created_at="",
        )
    )
    suspect_files: list[str] = field(default_factory=list)
    suspect_symbols: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryTriageOutput:
        context = "repository_triage"
        data = coerce_payload_mapping(payload)
        raw_evidence_items = data.get("evidence_items") or []
        if not isinstance(raw_evidence_items, list):
            raise TypeError(f"{context}.evidence_items must be a list.")
        return cls(
            repository_id=_require_string(data, "repository_id", context),
            snapshot_id=_require_string(data, "snapshot_id", context),
            workspace_evidence_bundle_ref=_require_string(
                data,
                "workspace_evidence_bundle_ref",
                context,
            ),
            created_at=_require_datetime_text(data, "created_at", context),
            suspect_files=_optional_string_list(data, "suspect_files", context),
            suspect_symbols=_optional_string_list(data, "suspect_symbols", context),
            raw_repo_token_estimate=_require_integer(data, "raw_repo_token_estimate", context),
            evidence_bundle_token_count=_require_integer(
                data,
                "evidence_bundle_token_count",
                context,
            ),
            reduction_ratio=_require_number(data, "reduction_ratio", context),
            evidence_items=[
                RepositoryEvidenceItemOutput.from_api(item) for item in raw_evidence_items
            ],
            workspace_evidence_bundle_artifact=RepositoryArtifactRefOutput.from_api(
                data.get("workspace_evidence_bundle_artifact")
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryGraphEdgeOutput:
    source_file: str
    target_file: str
    edge_type: str

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryGraphEdgeOutput:
        context = "repository_graph_query.graph_edges.item"
        data = coerce_payload_mapping(payload)
        return cls(
            source_file=_require_string(data, "source_file", context),
            target_file=_require_string(data, "target_file", context),
            edge_type=_require_string(data, "edge_type", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryGraphNodeOutput:
    file_path: str
    depth: int
    is_seed: bool
    inbound_count: int
    outbound_count: int
    risk_score: float
    contained_symbols: list[str] = field(default_factory=list)
    parent_child_symbols: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryGraphNodeOutput:
        context = "repository_graph_query.graph_nodes.item"
        data = coerce_payload_mapping(payload)
        return cls(
            file_path=_require_string(data, "file_path", context),
            depth=_require_integer(data, "depth", context),
            is_seed=_require_boolean(data, "is_seed", context),
            inbound_count=_require_integer(data, "inbound_count", context),
            outbound_count=_require_integer(data, "outbound_count", context),
            risk_score=_require_number(data, "risk_score", context),
            contained_symbols=_optional_string_list(data, "contained_symbols", context),
            parent_child_symbols=_optional_string_list(data, "parent_child_symbols", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryGraphImpactItemOutput:
    file_path: str
    depth: int
    relationship: str
    risk_score: float
    top_symbol: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryGraphImpactItemOutput:
        context = "repository_graph_query.top_change_risk_files.item"
        data = coerce_payload_mapping(payload)
        return cls(
            file_path=_require_string(data, "file_path", context),
            depth=_require_integer(data, "depth", context),
            relationship=_require_string(data, "relationship", context),
            risk_score=_require_number(data, "risk_score", context),
            top_symbol=_optional_string(data, "top_symbol", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryGraphQueryOutput:
    repository_id: str
    snapshot_id: str
    created_at: str
    seed_file_paths: list[str] = field(default_factory=list)
    seed_symbols: list[str] = field(default_factory=list)
    direct_dependencies: list[str] = field(default_factory=list)
    direct_dependents: list[str] = field(default_factory=list)
    impacted_files: list[str] = field(default_factory=list)
    impacted_symbols: list[str] = field(default_factory=list)
    graph_nodes: list[RepositoryGraphNodeOutput] = field(default_factory=list)
    graph_edges: list[RepositoryGraphEdgeOutput] = field(default_factory=list)
    top_change_risk_files: list[RepositoryGraphImpactItemOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryGraphQueryOutput:
        context = "repository_graph_query"
        data = coerce_payload_mapping(payload)
        graph_nodes_raw = data.get("graph_nodes", [])
        if not isinstance(graph_nodes_raw, list):
            raise TypeError(f"{context}.graph_nodes must be a list.")
        graph_edges_raw = data.get("graph_edges", [])
        if not isinstance(graph_edges_raw, list):
            raise TypeError(f"{context}.graph_edges must be a list.")
        top_change_risk_raw = data.get("top_change_risk_files", [])
        if not isinstance(top_change_risk_raw, list):
            raise TypeError(f"{context}.top_change_risk_files must be a list.")
        return cls(
            repository_id=_require_string(data, "repository_id", context),
            snapshot_id=_require_string(data, "snapshot_id", context),
            created_at=_require_datetime_text(data, "created_at", context),
            seed_file_paths=_optional_string_list(data, "seed_file_paths", context),
            seed_symbols=_optional_string_list(data, "seed_symbols", context),
            direct_dependencies=_optional_string_list(data, "direct_dependencies", context),
            direct_dependents=_optional_string_list(data, "direct_dependents", context),
            impacted_files=_optional_string_list(data, "impacted_files", context),
            impacted_symbols=_optional_string_list(data, "impacted_symbols", context),
            graph_nodes=[
                RepositoryGraphNodeOutput.from_api(item) for item in graph_nodes_raw
            ],
            graph_edges=[
                RepositoryGraphEdgeOutput.from_api(item) for item in graph_edges_raw
            ],
            top_change_risk_files=[
                RepositoryGraphImpactItemOutput.from_api(item) for item in top_change_risk_raw
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryDecisionPlanRevisionOutput:
    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    created_at: str
    decision_plan: DecisionPlanOutput

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryDecisionPlanRevisionOutput:
        context = "repository_decision_plan"
        data = coerce_payload_mapping(payload)
        return cls(
            repository_id=_require_string(data, "repository_id", context),
            snapshot_id=_require_string(data, "snapshot_id", context),
            decision_plan_id=_require_string(data, "decision_plan_id", context),
            created_at=_require_datetime_text(data, "created_at", context),
            decision_plan=DecisionPlanOutput.from_api(data.get("decision_plan")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class RepositoryApplyOutput:
    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    simulation_id: str
    mode: str
    applied: bool
    created_at: str
    patch: str
    apply_gate: dict[str, Any] = field(default_factory=dict)
    validation_summary: dict[str, Any] = field(default_factory=dict)
    branch_name: str | None = None
    commit_sha: str | None = None
    local_checkout_path: str | None = None
    pull_request_url: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> RepositoryApplyOutput:
        context = "repository_apply"
        data = coerce_payload_mapping(payload)
        return cls(
            repository_id=_require_string(data, "repository_id", context),
            snapshot_id=_require_string(data, "snapshot_id", context),
            decision_plan_id=_require_string(data, "decision_plan_id", context),
            simulation_id=_require_string(data, "simulation_id", context),
            mode=_require_string(data, "mode", context),
            applied=_require_boolean(data, "applied", context),
            created_at=_require_datetime_text(data, "created_at", context),
            patch=_require_string(data, "patch", context),
            branch_name=_optional_string(data, "branch_name", context),
            commit_sha=_optional_string(data, "commit_sha", context),
            local_checkout_path=_optional_string(data, "local_checkout_path", context),
            pull_request_url=_optional_string(data, "pull_request_url", context),
            apply_gate=_optional_mapping(data.get("apply_gate") or {}, f"{context}.apply_gate"),
            validation_summary=_optional_mapping(
                data.get("validation_summary") or {},
                f"{context}.validation_summary",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
