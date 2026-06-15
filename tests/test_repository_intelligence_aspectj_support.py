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
    repository_intelligence_aspectj_parser_dispatch as repository_aspectj_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    aspectj_analysis_support as repository_aspectj_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aspectj_primitives as repository_aspectj_primitives,
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


def test_repository_intelligence_aspectj_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["aspectj"] is (
        repository_aspectj_parser_dispatch._parse_aspectj_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["aspectj"] is (
        repository_aspectj_parser_dispatch._parse_aspectj_dependencies_only
    )


def test_repository_intelligence_aspectj_helpers_are_modularized() -> None:
    assert repository_service.aspectj_adapter.has_aspectj_path_hints is (
        repository_aspectj_primitives.has_aspectj_path_hints
    )
    assert repository_service.aspectj_adapter.is_probable_aspectj_source is (
        repository_aspectj_analysis_support.is_probable_aspectj_source
    )
    assert repository_service.aspectj_adapter.module_aliases_for_path is (
        repository_aspectj_analysis_support.module_aliases_for_path
    )
    assert repository_service.aspectj_adapter.parse_dependencies_only is (
        repository_aspectj_analysis_support.parse_dependencies_only
    )
    assert repository_service.aspectj_adapter.parse_file is (
        repository_aspectj_analysis_support.parse_file
    )


def test_aspectj_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspectj-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "TraceAspect.aj").write_text(
        "package demo;\n"
        "public aspect TraceAspect {\n"
        "  pointcut traced(): execution(* demo..*(..));\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.aspectj_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/TraceAspect.aj",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/TraceAspect.aj" in aliases
    assert "TraceAspect" in aliases
    assert "demo.TraceAspect" in aliases
    assert "traced" in aliases


def test_aspectj_adapter_parse_file_resolves_imports_and_pointcut_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "src/demo/TraceAspect.aj",
            "src/demo/Support.java",
        ],
        root_path=Path("/tmp/aspectj-index"),
    )
    text = (
        "package demo;\n"
        "import demo.Support;\n"
        "public aspect TraceAspect {\n"
        "  pointcut traced(): execution(* demo..*(..));\n"
        "  before(): traced() { Support.log(); }\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.aspectj_adapter.parse_file(
        "src/demo/TraceAspect.aj",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        symbol.symbol_name == "TraceAspect" and symbol.symbol_kind == "aspect"
        for symbol in symbols
    )
    assert any(
        symbol.symbol_name == "traced" and symbol.symbol_kind == "pointcut"
        for symbol in symbols
    )
    assert any(
        dependency.target_file == "src/demo/Support.java"
        and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("traced",) for reference in references)


def test_aspectj_language_detection_supports_aj_sources_without_overclaiming() -> None:
    assert (
        repository_service._language_for_path(
            Path("src/demo/TraceAspect.aj"),
            text="package demo;\npublic aspect TraceAspect {}\n",
        )
        == "aspectj"
    )
    assert (
        repository_service._language_for_path(
            Path("src/demo/TraceAspect.aj"),
            text="#!/bin/sh\necho hi\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_aspectj_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspectj-profile-repo"
    (repo_path / "src" / "main" / "aspect" / "demo").mkdir(parents=True)
    (repo_path / "src" / "main" / "java" / "demo").mkdir(parents=True)
    for index in range(6):
        (repo_path / "src" / "main" / "aspect" / "demo" / f"Trace{index}.aj").write_text(
            "package demo;\n"
            f"public aspect Trace{index} {{\n"
            f"  pointcut traced{index}(): execution(* demo..*(..));\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "main" / "java" / "demo" / "Support.java").write_text(
        "package demo;\npublic class Support {}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "aspectj" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "aspectj"


def test_operational_seed_plan_respects_explicit_aspect_focus_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aspectj-focused-profile-repo"
    aspect_root = repo_path / "impl" / "src" / "main" / "aspect" / "demo"
    java_root = repo_path / "envs" / "se" / "src" / "main" / "java" / "demo"
    aspect_root.mkdir(parents=True)
    java_root.mkdir(parents=True)
    for relative_path in ("pom.xml", "impl/pom.xml", "envs/pom.xml", "envs/se/pom.xml"):
        target = repo_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<project />\n", encoding="utf-8")
    for index in range(6):
        (aspect_root / f"Trace{index}.aj").write_text(
            "package demo;\n"
            f"public aspect Trace{index} {{\n"
            f"  pointcut traced{index}(): execution(* demo..*(..));\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(18):
        (java_root / f"Support{index}.java").write_text(
            "package demo;\n"
            f"public class Support{index} {{}}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["impl/src/main/aspect"],
        max_files=128,
    )

    assert seed_plan["operational_ecosystems"][0] == "aspectj"
    aspect_entrypoints = [
        path for path in seed_plan["entrypoint_files"] if path.endswith(".aj")
    ]
    assert len(aspect_entrypoints) == 6
    assert all(
        path.startswith("impl/src/main/aspect/")
        for path in aspect_entrypoints
    )
    assert seed_plan["entrypoint_files"][: len(aspect_entrypoints)] == aspect_entrypoints
    ranked_code_candidates = [
        path
        for path in seed_plan["candidate_file_paths"]
        if path.endswith(".aj") or path.endswith(".java")
    ]
    assert all(
        path.startswith("impl/src/main/aspect/")
        for path in ranked_code_candidates[: len(aspect_entrypoints)]
    )


def test_repository_snapshot_graph_contains_aspectj_import_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "aspectj-graph-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Support.java").write_text(
        "package demo;\npublic class Support { public static void log() {} }\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "demo" / "TraceAspect.aj").write_text(
        "package demo;\n"
        "import demo.Support;\n"
        "public aspect TraceAspect {\n"
        "  pointcut traced(): execution(* demo..*(..));\n"
        "  before(): traced() { Support.log(); }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*"],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/demo/TraceAspect.aj"
        and str(row["target_node"]) == "file:src/demo/Support.java"
        for row in graph_rows
    )
