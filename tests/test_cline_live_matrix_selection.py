from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from apps.api_server.services.cline_live_matrix_selection import (
    DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
    build_cline_live_matrix_artifacts,
    build_live_matrix_selection_entries,
)
from apps.api_server.services.cline_proof_common import (
    CLINE_DOCS_SNAPSHOT_HASH_PATH,
    CLINE_DOCS_SNAPSHOT_PATH,
    read_json,
    sha256_hex,
)
from apps.api_server.services.repository_intelligence_runtime_language_support import (
    repository_runtime_language_route_index,
)
from apps.api_server.services.repository_language_priority import supported_repository_languages


def _write_docs_snapshot(root: Path) -> None:
    snapshot_text = "\n".join(
        [
            "ClineCore",
            "Sessions",
            "Events",
            "Permission Handling",
            "Writing Plugins",
            "MCP",
            "ACP",
            "GitHub",
        ]
    )
    snapshot_path = root / CLINE_DOCS_SNAPSHOT_PATH
    snapshot_hash_path = root / CLINE_DOCS_SNAPSHOT_HASH_PATH
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(snapshot_text, encoding="utf-8")
    snapshot_hash_path.write_text(sha256_hex(snapshot_text), encoding="utf-8")


def test_build_live_matrix_selection_entries_preserves_rank_and_expands_families() -> None:
    report_languages = supported_repository_languages()
    route_index = repository_runtime_language_route_index()

    selection_entries = build_live_matrix_selection_entries()

    assert len(selection_entries) > DEFAULT_TOP_RANKED_LANGUAGE_COUNT
    assert [entry.language for entry in selection_entries[:DEFAULT_TOP_RANKED_LANGUAGE_COUNT]] == list(
        report_languages[:DEFAULT_TOP_RANKED_LANGUAGE_COUNT]
    )
    assert {
        entry.selection_reason
        for entry in selection_entries[:DEFAULT_TOP_RANKED_LANGUAGE_COUNT]
    } == {f"top_{DEFAULT_TOP_RANKED_LANGUAGE_COUNT}"}

    covered_families = {
        route_index[language].route_family
        for language in report_languages[:DEFAULT_TOP_RANKED_LANGUAGE_COUNT]
    }
    extra_families: set[str] = set()
    for entry in selection_entries[DEFAULT_TOP_RANKED_LANGUAGE_COUNT :]:
        assert entry.selection_reason == "first_uncovered_adapter_family"
        assert entry.adapter_family not in covered_families
        assert entry.adapter_family not in extra_families
        extra_families.add(entry.adapter_family)


def test_build_cline_live_matrix_artifacts_writes_registry_and_selection(tmp_path: Path) -> None:
    _write_docs_snapshot(tmp_path)

    artifacts = build_cline_live_matrix_artifacts(root=tmp_path)
    adapter_registry = read_json(artifacts.adapter_registry_path)
    live_matrix_selection = read_json(artifacts.live_matrix_selection_path)

    assert adapter_registry["schema_version"] == "cline-adapter-registry/v1"
    assert adapter_registry["supported_language_count"] == 180
    assert adapter_registry["registered_adapter_language_count"] == 149
    assert adapter_registry["workflow_special_case_language_count"] == 31
    assert adapter_registry["runtime_covered_language_count"] == 180
    assert adapter_registry["missing_languages"] == []

    assert live_matrix_selection["schema_version"] == "cline-live-matrix-selection/v1"
    assert live_matrix_selection["supported_language_count"] == 180
    assert live_matrix_selection["runtime_coverage_percent"] == 100.0
    assert live_matrix_selection["registry_coverage_percent"] == 82.78
    assert live_matrix_selection["missing_languages"] == []
    assert len(live_matrix_selection["selected_live_languages"]) == len(
        build_live_matrix_selection_entries()
    )


def test_generate_cline_live_matrix_selection_script(tmp_path: Path) -> None:
    _write_docs_snapshot(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/generate_cline_live_matrix_selection.py",
            "--root",
            str(tmp_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "build/proofs/cline/adapter_registry.json").exists()
    assert (tmp_path / "build/proofs/cline/live_matrix_selection.json").exists()
