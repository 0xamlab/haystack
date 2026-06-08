"""Tests for repository_intelligence_real_repo_probe: load_snapshot.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_load_snapshot_graph_summary_includes_symbol_risk_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "summary-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    helper_path = repo_path / "services" / "app" / "src" / "util.ts"
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    helper_path.write_text(
        "export function helper(): string {\n"
        "  return 'ready';\n"
        "}\n",
        encoding="utf-8",
    )
    target_path.write_text(
        "import { helper } from './util';\n"
        "\n"
        "export class Planner {\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return `${helper()}-${value.toUpperCase()}`;\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    connector = repository_service._InlineConnector(  # type: ignore[attr-defined]
        id=repository_service._coerce_scope_uuid("summary-repo"),  # type: ignore[attr-defined]
        org_id=repository_service._coerce_scope_uuid("summary-org"),  # type: ignore[attr-defined]
        connector_type=repository_service._InlineConnectorType("local_repo"),  # type: ignore[attr-defined]
    )
    connector = type(
        "Connector",
        (),
        {
            "id": connector.id,
            "org_id": connector.org_id,
            "owner_key_id": None,
            "connector_type": type("ConnectorType", (), {"value": "local_repo"})(),
            "config_json": '{"path": "' + str(repo_path) + '"}',
        },
    )()
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    summary = _load_snapshot_graph_summary(
        repository_graph_path=snapshot.repository_graph_artifact.storage_path,
        dependency_graph_path=snapshot.dependency_graph_artifact.storage_path,
        symbol_graph_path=snapshot.symbol_graph_artifact.storage_path,
        seed_files=["services/app/src/main.ts"],
    )

    assert summary["parent_child_symbol_count"] >= 2
    assert summary["symbol_reference_edge_count"] >= 2
    assert summary["highest_change_risk_symbols"]
    assert summary["highest_change_risk_operational_symbols"]
    assert summary["highest_change_risk_operational_edges"]
    top_symbol = summary["highest_change_risk_operational_symbols"][0]
    assert top_symbol["symbol_name"] in {"Planner", "build", "finalize", "helper"}
    assert any(
        edge["target_symbol"] == "helper" for edge in summary["top_symbol_reference_edges"]
    )


