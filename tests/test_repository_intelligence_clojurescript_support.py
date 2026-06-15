from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_clojurescript_parser_dispatch as repository_clojurescript_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    clojurescript_analysis_support as repository_clojurescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    clojurescript_primitives as repository_clojurescript_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_clojurescript_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["clojurescript"] is (
        repository_clojurescript_parser_dispatch._parse_clojurescript_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["clojurescript"] is (
        repository_clojurescript_parser_dispatch._parse_clojurescript_dependencies_only
    )


def test_repository_intelligence_clojurescript_helpers_are_modularized() -> None:
    assert repository_service.clojurescript_adapter.extract_ns_form is (
        repository_clojurescript_primitives.extract_ns_form
    )
    assert repository_service.clojurescript_adapter.has_clojurescript_path_hints is (
        repository_clojurescript_primitives.has_clojurescript_path_hints
    )
    assert repository_service.clojurescript_adapter.is_probable_clojurescript_source is (
        repository_clojurescript_analysis_support.is_probable_clojurescript_source
    )
    assert repository_service.clojurescript_adapter.module_aliases_for_path is (
        repository_clojurescript_analysis_support.module_aliases_for_path
    )
    assert repository_service.clojurescript_adapter.parse_dependencies_only is (
        repository_clojurescript_analysis_support.parse_dependencies_only
    )
    assert repository_service.clojurescript_adapter.parse_file is (
        repository_clojurescript_analysis_support.parse_file
    )


def test_clojurescript_adapter_module_aliases_include_namespace(tmp_path: Path) -> None:
    repo_path = tmp_path / "clojurescript-alias-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "src" / "acme" / "core.cljs").write_text(
        "(ns acme.core)\n"
        "(defn run [] :ok)\n",
        encoding="utf-8",
    )

    aliases = repository_service.clojurescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme/core.cljs",
    )

    assert "acme.core" in aliases


def test_clojurescript_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["src/acme/util.cljs", "src/acme/core.cljs"],
        root_path=Path("/tmp/clojurescript-index"),
    )
    text = (
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n"
    )

    symbols, dependencies, references = repository_service.clojurescript_adapter.parse_file(
        "src/acme/core.cljs",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, index: repository_service.clojurescript_adapter.resolve_import(
            import_target,
            module_index=index,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        ),
    )

    assert any(dependency.target_file == "src/acme/util.cljs" for dependency in dependencies)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(reference.target_file == "src/acme/util.cljs" for reference in references)
    assert any(reference.target_names == ("helper",) for reference in references)


def test_clojurescript_language_detection_prefers_explicit_clojurescript_bucket() -> None:
    assert repository_service._language_for_path(Path("src/app/core.cljs")) == "clojurescript"


def test_operational_seed_plan_without_diagnostics_promotes_clojurescript_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojurescript-profile-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shadow-cljs.edn").write_text(
        '{:source-paths ["src"]}\n',
        encoding="utf-8",
    )
    for name in ("core", "util", "events", "subs", "views", "router"):
        (repo_path / "src" / "acme" / f"{name}.cljs").write_text(
            f"(ns acme.{name})\n(defn run [] :ok)\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "acme" / "server.clj").write_text(
        "(ns acme.server)\n(defn run [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "clojurescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "clojurescript"


def test_operational_seed_plan_without_diagnostics_does_not_force_clojurescript_first_in_clojure_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojurescript-mixed-host-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shadow-cljs.edn").write_text(
        '{:source-paths ["src"]}\n',
        encoding="utf-8",
    )
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"] :main acme.server}\n',
        encoding="utf-8",
    )
    for name in ("core", "views", "events"):
        (repo_path / "src" / "acme" / f"{name}.cljs").write_text(
            f"(ns acme.{name})\n(defn run [] :ok)\n",
            encoding="utf-8",
        )
    for index in range(14):
        (repo_path / "src" / "acme" / f"server_{index}.clj").write_text(
            f"(ns acme.server-{index})\n(defn run [] :ok)\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "acme" / "server.clj").write_text(
        "(ns acme.server)\n(defn -main [] :ok)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "clojurescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "clojurescript"
    assert "clojure" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_prefers_clojurescript_in_shadow_cljs_public_style_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clojurescript-shadow-cljs-public-repo"
    (repo_path / "src" / "reagent").mkdir(parents=True)
    (repo_path / "demo" / "reagentdemo").mkdir(parents=True)
    (repo_path / "prerender" / "sitetools").mkdir(parents=True)
    (repo_path / "examples" / "sample").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "shadow-cljs.edn").write_text(
        '{:source-paths ["src" "demo" "prerender" "examples"]}\n',
        encoding="utf-8",
    )
    (repo_path / "deps.edn").write_text(
        '{:paths ["src"]}\n',
        encoding="utf-8",
    )
    (repo_path / "bb.edn").write_text(
        '{:tasks {}}\n',
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name": "reagent-like"}\n',
        encoding="utf-8",
    )
    (repo_path / "lib" / "modules.js").write_text(
        "module.exports = {}\n",
        encoding="utf-8",
    )
    for path in (
        "src/reagent/core.cljs",
        "src/reagent/debug.cljs",
        "src/reagent/impl.cljs",
        "src/reagent/dom.cljs",
        "demo/reagentdemo/common.cljs",
        "demo/reagentdemo/app.cljs",
        "prerender/sitetools/prerender.cljs",
        "examples/sample/example.cljs",
    ):
        file_path = repo_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "(ns demo.core)\n(defn run [] :ok)\n",
            encoding="utf-8",
        )
    for path in (
        "src/reagent/core.clj",
        "src/reagent/debug.clj",
        "demo/reagentdemo/syntax.clj",
    ):
        file_path = repo_path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "(ns demo.server)\n(defn run [] :ok)\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "clojurescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "clojurescript"


def test_repository_snapshot_graph_contains_clojurescript_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "clojurescript-graph-repo"
    (repo_path / "src" / "acme").mkdir(parents=True)
    (repo_path / "shadow-cljs.edn").write_text(
        '{:source-paths ["src"]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "util.cljs").write_text(
        "(ns acme.util)\n"
        "(defn helper [] :ok)\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "acme" / "core.cljs").write_text(
        "(ns acme.core\n"
        "  (:require [acme.util :as util]))\n"
        "(defn run []\n"
        "  (util/helper))\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "shadow-cljs.edn"],
            include_patterns=[
                "src/**/*.cljs",
                "src/*.cljs",
                "shadow-cljs.edn",
            ],
            max_files=64,
        ),
    )

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/acme/core.cljs"
        and str(row["target_node"]) == "file:src/acme/util.cljs"
        for row in graph_rows
    )
    run_symbol_id = symbol_ids[("src/acme/core.cljs", "run")]
    helper_symbol_id = symbol_ids[("src/acme/util.cljs", "helper")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
