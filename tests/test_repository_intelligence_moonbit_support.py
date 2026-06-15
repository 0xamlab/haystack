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
    repository_intelligence_moonbit_parser_dispatch as repository_moonbit_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    moonbit_analysis_support as repository_moonbit_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    moonbit_primitives as repository_moonbit_primitives,
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


def test_repository_intelligence_moonbit_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["moonbit"] is (
        repository_moonbit_parser_dispatch._parse_moonbit_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["moonbit"] is (
        repository_moonbit_parser_dispatch._parse_moonbit_dependencies_only
    )


def test_repository_intelligence_moonbit_helpers_are_modularized() -> None:
    assert repository_service.moonbit_adapter.strip_comments is (
        repository_moonbit_primitives.strip_comments
    )
    assert repository_service.moonbit_adapter.has_moonbit_path_hints is (
        repository_moonbit_primitives.has_moonbit_path_hints
    )
    assert repository_service.moonbit_adapter.is_probable_moonbit_source is (
        repository_moonbit_analysis_support.is_probable_moonbit_source
    )
    assert repository_service.moonbit_adapter.is_probable_moonbit_config is (
        repository_moonbit_analysis_support.is_probable_moonbit_config
    )
    assert repository_service.moonbit_adapter.parse_import_entries is (
        repository_moonbit_primitives.parse_import_entries
    )
    assert repository_service.moonbit_adapter.module_aliases_for_path is (
        repository_moonbit_analysis_support.module_aliases_for_path
    )
    assert repository_service.moonbit_adapter.parse_dependencies_only is (
        repository_moonbit_analysis_support.parse_dependencies_only
    )
    assert repository_service.moonbit_adapter.parse_file is (
        repository_moonbit_analysis_support.parse_file
    )


def test_moonbit_strip_comments_reuses_cached_results() -> None:
    source_text = "pub fn main() -> Int {\n  1 // comment\n}\n"
    repository_moonbit_primitives.clear_strip_comments_cache()

    first_result = repository_moonbit_primitives.strip_comments(source_text)
    first_cache_info = repository_moonbit_primitives._strip_comments_cached.cache_info()
    second_result = repository_moonbit_primitives.strip_comments(source_text)
    second_cache_info = repository_moonbit_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_moonbit_adapter_module_aliases_include_package_import_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "moonbit-alias-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "math" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "math" / "math.mbt").write_text(
        "pub fn add(x : Int, y : Int) -> Int {\n  x + y\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.moonbit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="math/math.mbt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math/math.mbt" in aliases
    assert "math/math" in aliases
    assert "math" in aliases
    assert "moonbit/core/math" in aliases
    assert "add" in aliases
    assert "math.add" in aliases


def test_moonbit_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "moonbit-alias-module-only-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "math" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "math" / "math.mbt").write_text(
        "pub fn add(x : Int, y : Int) -> Int {\n  x + y\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.moonbit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="math/math.mbt",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "moonbit/core/math" in aliases
    assert "math" in aliases
    assert "add" not in aliases
    assert "math.add" not in aliases


def test_moonbit_adapter_module_aliases_reuse_supplied_stripped_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "moonbit-alias-reuse"
    (repo_path / "app").mkdir(parents=True)
    file_path = "app/main.mbt"
    text = "pub fn main() -> Int {\n  1\n}\n"
    strip_calls: list[str] = []

    def counting_strip_comments(source_text: str) -> str:
        strip_calls.append(source_text)
        return source_text

    monkeypatch.setattr(repository_moonbit_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(
        repository_moonbit_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    aliases = repository_service.moonbit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path=file_path,
        stable_identifier=repository_service._stable_identifier,
        text=text,
        stripped_text=text,
    )

    assert "main" in aliases
    assert strip_calls == []


def test_moonbit_adapter_parse_file_extracts_config_dependencies_and_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "moonbit-parse-repo"
    (repo_path / "util").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "util" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "util" / "util.mbt").write_text(
        "pub fn answer() -> Int {\n  42\n}\n",
        encoding="utf-8",
    )
    app_pkg_path = repo_path / "app" / "moon.pkg"
    app_pkg_path.write_text('import { "moonbit/core/util" @util }\n', encoding="utf-8")
    app_source = (
        "pub fn Helper::make() -> Int {\n  1\n}\n\n"
        "pub fn main() -> Int {\n  @util.answer() + Helper::make()\n}\n"
    )
    (repo_path / "app" / "app.mbt").write_text(app_source, encoding="utf-8")
    module_index = repository_service._build_module_index(
        [
            "moon.mod",
            "util/moon.pkg",
            "util/util.mbt",
            "app/moon.pkg",
            "app/app.mbt",
        ],
        root_path=repo_path,
    )

    config_dependencies = repository_service.moonbit_adapter.parse_dependencies_only(
        "app/moon.pkg",
        app_pkg_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, dependencies, references = repository_service.moonbit_adapter.parse_file(
        "app/app.mbt",
        app_source,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in config_dependencies} == {"util/util.mbt"}
    assert {dependency.target_file for dependency in dependencies} == {"app/moon.pkg", "moon.mod"}
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(symbol.symbol_name == "Helper::make" for symbol in symbols)
    assert any(reference.target_file == "util/util.mbt" for reference in references)
    assert any(reference.target_file == "app/app.mbt" for reference in references)


def test_moonbit_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_moonbit_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_moonbit_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_moonbit_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    repository_service.moonbit_adapter.parse_dependencies_only(
        "app/moon.pkg",
        'import { "moonbit/core/util" @util }\n',
        {"moonbit/core/util": "util/util.mbt"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    assert strip_call_count["value"] == 1

    strip_call_count["value"] = 0
    repository_service.moonbit_adapter.parse_file(
        "app/app.mbt",
        "pub fn helper() -> Int {\n  1\n}\n\npub fn main() -> Int {\n  helper()\n}\n",
        {"app/app.mbt": "app/app.mbt"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 1


def test_moonbit_language_detection_supports_sources_and_configs_without_overclaiming() -> None:
    assert ".mbt" in repository_service._TEXT_FILE_SUFFIXES
    assert ".mbti" in repository_service._TEXT_FILE_SUFFIXES
    assert "moon.mod" in repository_service._TEXT_FILE_BASENAMES
    assert "moon.pkg" in repository_service._TEXT_FILE_BASENAMES
    assert (
        repository_service._language_for_path(
            Path("math/math.mbt"),
            text="pub fn add(x : Int, y : Int) -> Int {\n  x + y\n}\n",
        )
        == "moonbit"
    )
    assert (
        repository_service._language_for_path(
            Path("moon.mod"),
            text='name = "moonbit/core"\n',
        )
        == "moonbit"
    )
    assert (
        repository_service._language_for_path(
            Path("app/moon.pkg"),
            text='import { "moonbit/core/util" @util }\n',
        )
        == "moonbit"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.mbt"),
            text="plain notes without moonbit markers\n",
        )
        == "unknown"
    )


def test_build_module_index_reuses_preloaded_text_for_moonbit_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-module-alias-reuse-repo"
    source_path = repo_path / "app" / "main.mbt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("pub fn main() -> Int {\n  1\n}\n", encoding="utf-8")

    original_read_text = Path.read_text
    source_reads: list[str] = []

    def tracking_read_text(self: Path, *args, **kwargs):
        if self == source_path:
            source_reads.append(str(self))
            if len(source_reads) > 1:
                raise AssertionError(
                    "expected moonbit root-scoped alias builder to reuse preloaded text"
                )
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracking_read_text)

    index = repository_service._build_module_index(
        ["app/main.mbt"],
        root_path=repo_path,
    )

    assert source_reads == [str(source_path)]
    assert index["main"] == "app/main.mbt"


def test_operational_seed_plan_without_diagnostics_promotes_moonbit_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "moonbit-profile-repo"
    (repo_path / "util").mkdir(parents=True)
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "util" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "util" / "util.mbt").write_text(
        "pub fn answer() -> Int {\n  42\n}\n",
        encoding="utf-8",
    )
    (repo_path / "math" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "math" / "math.mbt").write_text(
        "pub fn add(x : Int, y : Int) -> Int {\n  x + y\n}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "moon.pkg").write_text(
        'import { "moonbit/core/util" @util, "moonbit/core/math" @math }\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "app.mbt").write_text(
        "pub fn main() -> Int {\n  @util.answer() + @math.add(1, 2)\n}\n",
        encoding="utf-8",
    )
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "helper.py").write_text(
        "def helper() -> int:\n    return 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "moonbit" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "moonbit"
    assert "moon.mod" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_does_not_force_moonbit_first_in_rust_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "moonbit-mixed-rust-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests" / "fixtures" / "moon" / "app").mkdir(parents=True)
    (repo_path / "tests" / "fixtures" / "moon" / "moon.mod").write_text(
        'name = "moonbit/compiler"\n',
        encoding="utf-8",
    )
    (repo_path / "tests" / "fixtures" / "moon" / "app" / "moon.pkg").write_text(
        "",
        encoding="utf-8",
    )
    (repo_path / "tests" / "fixtures" / "moon" / "app" / "app.mbt").write_text(
        "pub fn main() -> Int {\n  1\n}\n",
        encoding="utf-8",
    )
    (repo_path / "Cargo.toml").write_text(
        '[package]\nname = "host"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "src" / f"lib_{index}.rs").write_text(
            f"pub fn value_{index}() -> usize {{ {index} }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "moonbit" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "moonbit"
    assert "rust" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_connects_moonbit_import_chain_and_symbols(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "moonbit-graph-repo"
    (repo_path / "util").mkdir(parents=True)
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "util" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "util" / "util.mbt").write_text(
        "pub fn answer() -> Int {\n  42\n}\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "moon.pkg").write_text(
        'import { "moonbit/core/util" @util }\n',
        encoding="utf-8",
    )
    (repo_path / "app" / "app.mbt").write_text(
        "pub fn main() -> Int {\n  @util.answer()\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=[
                "**/*.mbt",
                "*.mbt",
                "**/moon.mod",
                "moon.mod",
                "**/moon.pkg",
                "moon.pkg",
            ],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert any(
        row["edge_type"] == "imports"
        and row["source_node"] == "file:app/moon.pkg"
        and row["target_node"] == "file:util/util.mbt"
        for row in graph
    )
    assert any(
        row["symbol_name"] == "main" and row["file_path"] == "app/app.mbt" for row in symbol_rows
    )
    assert any(
        row["symbol_name"] == "answer" and row["file_path"] == "util/util.mbt"
        for row in symbol_rows
    )
