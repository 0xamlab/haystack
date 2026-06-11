from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    build_proof_context,
    create_artifact_provenance,
    repo_root,
    write_json,
)
from apps.api_server.services.repository_intelligence_runtime_language_support import (
    RepositoryRuntimeLanguageSupportReport,
    build_repository_runtime_language_support_report,
)

ADAPTER_REGISTRY_PATH = CLINE_PROOFS_DIR / "adapter_registry.json"
LIVE_MATRIX_SELECTION_PATH = CLINE_PROOFS_DIR / "live_matrix_selection.json"
RANKING_SOURCE = (
    "apps/api_server/services/repository_language_priority.py:"
    "supported_repository_languages"
)
ADAPTER_REGISTRY_SOURCE = (
    "apps/api_server/services/"
    "repository_intelligence_runtime_language_support.py:"
    "build_repository_runtime_language_support_report"
)
DEFAULT_TOP_RANKED_LANGUAGE_COUNT = 24


@dataclass(frozen=True)
class LiveMatrixSelectionEntry:
    language: str
    rank: int
    adapter_family: str
    selection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "rank": self.rank,
            "adapter_family": self.adapter_family,
            "selection_reason": self.selection_reason,
        }


@dataclass(frozen=True)
class ClineLiveMatrixArtifacts:
    adapter_registry_path: Path
    adapter_registry_payload: dict[str, Any]
    live_matrix_selection_path: Path
    live_matrix_selection_payload: dict[str, Any]


def build_live_matrix_selection_entries(
    *,
    report: RepositoryRuntimeLanguageSupportReport | None = None,
    top_ranked_language_count: int = DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
) -> tuple[LiveMatrixSelectionEntry, ...]:
    if top_ranked_language_count <= 0:
        raise ValueError("top_ranked_language_count must be positive")
    resolved_report = (
        build_repository_runtime_language_support_report()
        if report is None
        else report
    )
    if resolved_report.missing_languages:
        raise ValueError(
            "cannot build live matrix selection with missing runtime languages: "
            f"{list(resolved_report.missing_languages)}"
        )

    route_index = {route.language: route for route in resolved_report.runtime_routes}
    covered_families: set[str] = set()
    selection_entries: list[LiveMatrixSelectionEntry] = []
    top_rank_reason = f"top_{top_ranked_language_count}"
    for rank, language in enumerate(resolved_report.supported_languages, start=1):
        route = route_index[language]
        if rank <= top_ranked_language_count:
            selection_entries.append(
                LiveMatrixSelectionEntry(
                    language=language,
                    rank=rank,
                    adapter_family=route.route_family,
                    selection_reason=top_rank_reason,
                )
            )
            covered_families.add(route.route_family)
            continue
        if route.route_family in covered_families:
            continue
        selection_entries.append(
            LiveMatrixSelectionEntry(
                language=language,
                rank=rank,
                adapter_family=route.route_family,
                selection_reason="first_uncovered_adapter_family",
            )
        )
        covered_families.add(route.route_family)
    return tuple(selection_entries)


def build_cline_live_matrix_artifacts(
    *,
    root: str | Path | None = None,
    top_ranked_language_count: int = DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
) -> ClineLiveMatrixArtifacts:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    report = build_repository_runtime_language_support_report()
    selection_entries = build_live_matrix_selection_entries(
        report=report,
        top_ranked_language_count=top_ranked_language_count,
    )

    adapter_registry_payload = {
        **create_artifact_provenance(
            context,
            run_id="adapter_registry",
            schema_version="cline-adapter-registry/v1",
        ),
        "ranking_source": RANKING_SOURCE,
        "adapter_registry_source": ADAPTER_REGISTRY_SOURCE,
        **report.to_dict(),
    }
    live_matrix_selection_payload = {
        **create_artifact_provenance(
            context,
            run_id="live_matrix_selection",
            schema_version="cline-live-matrix-selection/v1",
        ),
        "supported_language_count": report.supported_language_count,
        "ranking_source": RANKING_SOURCE,
        "adapter_registry": str(ADAPTER_REGISTRY_PATH),
        "registered_adapter_language_count": report.registered_adapter_language_count,
        "workflow_special_case_language_count": report.workflow_special_case_language_count,
        "runtime_covered_language_count": report.runtime_covered_language_count,
        "registry_coverage_percent": report.registered_adapter_progress_percent,
        "runtime_coverage_percent": report.runtime_coverage_percent,
        "missing_languages": list(report.missing_languages),
        "selected_live_languages": [entry.to_dict() for entry in selection_entries],
    }

    adapter_registry_path = write_json(
        resolved_root / ADAPTER_REGISTRY_PATH,
        adapter_registry_payload,
    )
    live_matrix_selection_path = write_json(
        resolved_root / LIVE_MATRIX_SELECTION_PATH,
        live_matrix_selection_payload,
    )
    return ClineLiveMatrixArtifacts(
        adapter_registry_path=adapter_registry_path,
        adapter_registry_payload=adapter_registry_payload,
        live_matrix_selection_path=live_matrix_selection_path,
        live_matrix_selection_payload=live_matrix_selection_payload,
    )
