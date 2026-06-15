from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import (
    repository_intelligence as repository_service,
)
from apps.api_server.services import (
    repository_intelligence_tex_parser_dispatch as repository_tex_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    tex_analysis_support as repository_tex_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    tex_primitives as repository_tex_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _build_connected_dependency_map,
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


def test_repository_intelligence_tex_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["tex"] is (
        repository_tex_parser_dispatch._parse_tex_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["tex"] is (
        repository_tex_parser_dispatch._parse_tex_dependencies_only
    )


def test_repository_intelligence_tex_helpers_are_modularized() -> None:
    assert repository_service.tex_adapter.strip_comments is (
        repository_tex_primitives.strip_comments
    )
    assert repository_service.tex_adapter.has_tex_path_hints is (
        repository_tex_primitives.has_tex_path_hints
    )
    assert repository_service.tex_adapter.is_probable_tex_source is (
        repository_tex_primitives.is_probable_tex_source
    )
    assert repository_service.tex_adapter.is_probable_tex_config is (
        repository_tex_primitives.is_probable_tex_config
    )
    assert repository_service.tex_adapter.iter_import_entries is (
        repository_tex_primitives.iter_import_entries
    )
    assert repository_service.tex_adapter.iter_symbol_entries is (
        repository_tex_primitives.iter_symbol_entries
    )
    assert repository_service.tex_adapter.iter_reference_entries is (
        repository_tex_primitives.iter_reference_entries
    )
    assert repository_service.tex_adapter.module_name_from_path is (
        repository_tex_primitives.module_name_from_path
    )
    assert repository_service.tex_adapter.provided_module_name is (
        repository_tex_primitives.provided_module_name
    )
    assert repository_service.tex_adapter.module_aliases_for_path is (
        repository_tex_analysis_support.module_aliases_for_path
    )
    assert repository_service.tex_adapter.resolve_import is (
        repository_tex_analysis_support.resolve_import
    )
    assert repository_service.tex_adapter.parse_dependencies_only is (
        repository_tex_analysis_support.parse_dependencies_only
    )
    assert repository_service.tex_adapter.parse_file is (
        repository_tex_analysis_support.parse_file
    )


def test_tex_adapter_module_aliases_include_provided_modules_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "acme.sty").write_text(
        "\\ProvidesPackage{acme}\n"
        "\\newcommand{\\BrandName}{Acme}\n",
        encoding="utf-8",
    )

    aliases = repository_service.tex_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/acme.sty",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "styles/acme.sty" in aliases
    assert "styles/acme" in aliases
    assert "styles.acme" in aliases
    assert "acme" in aliases
    assert "BrandName" in aliases
    assert "acme.BrandName" in aliases


def test_tex_adapter_parse_file_resolves_imports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-parse-repo"
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "classes" / "resume.cls").write_text(
        "\\ProvidesClass{resume}\n",
        encoding="utf-8",
    )
    (repo_path / "content" / "math.tex").write_text(
        "\\newcommand{\\MathMacro}{42}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "acme.sty").write_text(
        "\\ProvidesPackage{acme}\n"
        "\\newcommand{\\BrandName}{Acme}\n",
        encoding="utf-8",
    )
    (repo_path / "main.tex").write_text(
        "\\documentclass{classes/resume}\n"
        "\\usepackage{styles/acme}\n"
        "\\input{content/math}\n"
        "\\BrandName\n"
        "\\MathMacro\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["main.tex", "classes/resume.cls", "content/math.tex", "styles/acme.sty"],
        root_path=repo_path,
    )
    text = (repo_path / "main.tex").read_text(encoding="utf-8")

    dependencies = repository_service.tex_adapter.parse_dependencies_only(
        "main.tex",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.tex_adapter.parse_file(
        "main.tex",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {
        "classes/resume.cls",
        "content/math.tex",
        "styles/acme.sty",
    }
    assert any(symbol.symbol_kind == "tex" and symbol.symbol_name == "main" for symbol in symbols)
    assert any(
        reference.target_file == "styles/acme.sty" and "BrandName" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "content/math.tex" and "MathMacro" in reference.target_names
        for reference in references
    )


def test_tex_adapter_parse_file_ignores_commented_imports_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-commented-parse-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "real.sty").write_text(
        "\\ProvidesPackage{real}\n"
        "\\newcommand{\\RealMacro}{Acme}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "ghost.sty").write_text(
        "\\ProvidesPackage{ghost}\n"
        "\\newcommand{\\GhostMacro}{Nope}\n",
        encoding="utf-8",
    )
    (repo_path / "main.tex").write_text(
        "% \\usepackage{styles/ghost}\n"
        "\\usepackage{styles/real}\n"
        "% \\GhostMacro\n"
        "\\RealMacro\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["main.tex", "styles/real.sty", "styles/ghost.sty"],
        root_path=repo_path,
    )
    text = (repo_path / "main.tex").read_text(encoding="utf-8")

    dependencies = repository_service.tex_adapter.parse_dependencies_only(
        "main.tex",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    _symbols, _parsed_dependencies, references = repository_service.tex_adapter.parse_file(
        "main.tex",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {"styles/real.sty"}
    assert {reference.target_file for reference in references} == {"styles/real.sty"}
    assert all("GhostMacro" not in reference.target_names for reference in references)


def test_tex_language_detection_supports_tex_files_and_latexmkrc() -> None:
    assert repository_service._language_for_path(Path("main.tex")) == "tex"
    assert repository_service._language_for_path(
        Path("resume.cls"),
        text="\\ProvidesClass{resume}\n\\LoadClass{article}\n",
    ) == "tex"
    assert repository_service._language_for_path(
        Path(".latexmkrc"),
        text="latexmk -pdf\n",
    ) == "tex"


def test_tex_language_detection_does_not_claim_non_tex_class_files() -> None:
    assert repository_service._language_for_path(
        Path("AccountTriggerHandler.cls"),
        text="public with sharing class AccountTriggerHandler {\n}\n",
    ) != "tex"
    assert repository_service._language_for_path(
        Path("JsonData.cls"),
        text="VERSION 1.0 CLASS\nAttribute VB_Name = \"JsonData\"\n",
    ) != "tex"


def test_operational_seed_plan_without_diagnostics_promotes_tex_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-profile-repo"
    (repo_path / "chapters").mkdir(parents=True)
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "chapters" / "intro.tex").write_text(
        "\\newcommand{\\IntroSection}{Intro}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "acme.sty").write_text(
        "\\ProvidesPackage{acme}\n"
        "\\newcommand{\\BrandName}{Acme}\n",
        encoding="utf-8",
    )
    (repo_path / ".latexmkrc").write_text("latexmk -pdf\n", encoding="utf-8")
    (repo_path / "main.tex").write_text(
        "\\usepackage{styles/acme}\n"
        "\\input{chapters/intro}\n"
        "\\BrandName\n"
        "\\IntroSection\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def run() -> None:\n    return None\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "tex" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "tex"
    assert "main.tex" in seed_plan["entrypoint_files"]
    assert "chapters" in seed_plan["support_roots"]
    assert "styles" in seed_plan["support_roots"]
    assert ".latexmkrc" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_tex_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-rust-tex-repo"
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "Cargo.toml").write_text(
        "[package]\nname = 'acme'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (repo_path / ".latexmkrc").write_text("latexmk -pdf\n", encoding="utf-8")
    (repo_path / "docs" / "macros.tex").write_text(
        "\\newcommand{\\DocMacro}{Docs}\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "main.tex").write_text(
        "\\input{macros}\n\\DocMacro\n",
        encoding="utf-8",
    )
    for index in range(8):
        (repo_path / "src" / f"file_{index}.rs").write_text(
            f"pub fn run_{index}() -> usize {{ {index} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "tex" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "rust"
    assert seed_plan["operational_ecosystems"][0] != "tex"


def test_connected_dependency_map_follows_tex_input_package_and_class_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tex-connected-map-repo"
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "sections").mkdir(parents=True)
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "classes" / "resume.cls").write_text(
        "\\ProvidesClass{resume}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "acme.sty").write_text(
        "\\ProvidesPackage{acme}\n"
        "\\newcommand{\\BrandName}{Acme}\n",
        encoding="utf-8",
    )
    (repo_path / "sections" / "intro.tex").write_text(
        "\\newcommand{\\IntroSection}{Intro}\n",
        encoding="utf-8",
    )
    (repo_path / "main.tex").write_text(
        "\\documentclass{classes/resume}\n"
        "\\usepackage{styles/acme}\n"
        "\\input{sections/intro}\n"
        "\\BrandName\n"
        "\\IntroSection\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["main.tex"],
        bridge_paths=["classes", "sections", "styles"],
        include_patterns=[
            "*.tex",
            "*.cls",
            "*.sty",
            "classes/**/*.cls",
            "sections/**/*.tex",
            "styles/**/*.sty",
        ],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=32,
    )

    assert connected_map["connected_file_count"] == 4
    assert connected_map["resolved_dependency_edges"] >= 3
    assert sorted(connected_map["connected_files"]) == [
        "classes/resume.cls",
        "main.tex",
        "sections/intro.tex",
        "styles/acme.sty",
    ]


def test_repository_snapshot_graph_contains_tex_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "tex-snapshot-repo"
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "sections").mkdir(parents=True)
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "classes" / "resume.cls").write_text(
        "\\ProvidesClass{resume}\n",
        encoding="utf-8",
    )
    (repo_path / "sections" / "intro.tex").write_text(
        "\\newcommand{\\IntroSection}{Intro}\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "acme.sty").write_text(
        "\\ProvidesPackage{acme}\n"
        "\\newcommand{\\BrandName}{Acme}\n",
        encoding="utf-8",
    )
    (repo_path / "main.tex").write_text(
        "\\documentclass{classes/resume}\n"
        "\\usepackage{styles/acme}\n"
        "\\input{sections/intro}\n"
        "\\BrandName\n"
        "\\IntroSection\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "*.tex",
                "*.cls",
                "*.sty",
                "classes/**/*.cls",
                "sections/**/*.tex",
                "styles/**/*.sty",
            ],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:main.tex"
        and str(row["target_node"]) == "file:styles/acme.sty"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("main.tex", "main")]
    brand_symbol_id = symbol_ids[("styles/acme.sty", "BrandName")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{brand_symbol_id}"
        for row in graph_rows
    )
