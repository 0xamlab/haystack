from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_less_parser_dispatch as repository_less_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    less_analysis_support as repository_less_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    less_primitives as repository_less_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)
from benchmarks.repository_intelligence_real_repo_probe_profile_style_candidates_support import (
    _less_profile_hints_from_candidates,
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


def test_repository_intelligence_less_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["less"] is (
        repository_less_parser_dispatch._parse_less_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["less"] is (
        repository_less_parser_dispatch._parse_less_dependencies_only
    )


def test_repository_intelligence_less_helpers_are_modularized() -> None:
    assert repository_service.less_adapter.has_less_path_hints is (
        repository_less_primitives.has_less_path_hints
    )
    assert repository_service.less_adapter.iter_import_entries is (
        repository_less_primitives.iter_import_entries
    )
    assert repository_service.less_adapter.iter_symbol_entries is (
        repository_less_primitives.iter_symbol_entries
    )
    assert repository_service.less_adapter.iter_reference_entries is (
        repository_less_primitives.iter_reference_entries
    )
    assert repository_service.less_adapter.is_probable_less_source is (
        repository_less_analysis_support.is_probable_less_source
    )
    assert repository_service.less_adapter.module_aliases_for_path is (
        repository_less_analysis_support.module_aliases_for_path
    )
    assert repository_service.less_adapter.parse_dependencies_only is (
        repository_less_analysis_support.parse_dependencies_only
    )
    assert repository_service.less_adapter.parse_file is (
        repository_less_analysis_support.parse_file
    )


def test_less_adapter_module_aliases_include_path_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "less-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "theme.less").write_text(
        "@brand-color: #123456;\n.rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )

    aliases = repository_service.less_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/theme.less",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "styles/theme.less" in aliases
    assert "styles.theme" in aliases
    assert "brand-color" in aliases
    assert "rounded" in aliases


def test_less_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "less-inline-text-repo"
    (repo_path / "styles").mkdir(parents=True)
    source_text = "@brand-color: #123456;\n.rounded(@radius) { border-radius: @radius; }\n"
    file_path = repo_path / "styles" / "theme.less"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.less_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/theme.less",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_less_primitives.strip_comments(source_text),
    )

    assert "styles/theme.less" in aliases
    assert "styles.theme" in aliases
    assert "brand-color" in aliases
    assert "rounded" in aliases


def test_less_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "less-module-only-alias-repo"
    (repo_path / "styles").mkdir(parents=True)
    source_text = "@brand-color: #123456;\n.rounded(@radius) { border-radius: @radius; }\n"
    (repo_path / "styles" / "theme.less").write_text(source_text, encoding="utf-8")

    aliases = repository_service.less_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/theme.less",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_less_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "styles/theme.less" in aliases
    assert "styles.theme" in aliases
    assert "brand-color" not in aliases
    assert "rounded" not in aliases


def test_less_module_aliases_path_only_mode_skips_text_loading_and_symbol_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "less-path-only-fast-path-repo"
    (repo_path / "styles").mkdir(parents=True)
    file_path = repo_path / "styles" / "theme.less"
    file_path.write_text(
        "@brand-color: #123456;\n.rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )

    def _unexpected_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"path-only less aliases should not reread {self}")

    def _unexpected_iter_symbol_entries(*args: object, **kwargs: object) -> object:
        raise AssertionError("path-only less aliases should skip symbol scans")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)
    monkeypatch.setattr(
        repository_less_analysis_support,
        "iter_symbol_entries",
        _unexpected_iter_symbol_entries,
    )

    aliases = repository_service.less_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="styles/theme.less",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "styles/theme.less" in aliases
    assert "styles.theme" in aliases
    assert "theme" in aliases
    assert "brand-color" not in aliases
    assert "rounded" not in aliases


def test_less_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_less_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_less_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_less_analysis_support, "strip_comments", counting_strip_comments)

    source_text = (
        '@import "variables.less";\n'
        ".card {\n"
        "  color: @brand-color;\n"
        "  .rounded(4px);\n"
        "}\n"
    )
    module_index = {
        "variables.less": "styles/variables.less",
        "styles/variables.less": "styles/variables.less",
        "styles/main.less": "styles/main.less",
        "styles/main": "styles/main.less",
    }

    repository_service.less_adapter.parse_dependencies_only(
        "styles/main.less",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.less_adapter.parse_file(
        "styles/main.less",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_less_strip_comments_reuse_cached_results() -> None:
    repository_less_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "@brand-color: #123456;\n"
        "// comment\n"
        ".rounded(@radius) { border-radius: @radius; }\n"
    )

    first_result = repository_less_primitives.strip_comments(source_text)
    first_cache_info = repository_less_primitives._strip_comments_cached.cache_info()
    second_result = repository_less_primitives.strip_comments(source_text)
    second_cache_info = repository_less_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_less_adapter_parse_file_resolves_imports_and_references(tmp_path: Path) -> None:
    repo_path = tmp_path / "less-parse-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "variables.less").write_text(
        "@brand-color: #123456;\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "mixins.less").write_text(
        ".rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.less").write_text(
        '@import "variables.less";\n'
        '@import "mixins.less";\n'
        ".card {\n"
        "  color: @brand-color;\n"
        "  .rounded(4px);\n"
        "}\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["styles/variables.less", "styles/mixins.less", "styles/main.less"],
        root_path=repo_path,
    )
    text = (repo_path / "styles" / "main.less").read_text(encoding="utf-8")

    dependencies = repository_service.less_adapter.parse_dependencies_only(
        "styles/main.less",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.less_adapter.parse_file(
        "styles/main.less",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "styles/variables.less" for dependency in dependencies)
    assert any(dependency.target_file == "styles/mixins.less" for dependency in dependencies)
    assert any(symbol.symbol_name == "styles/main" for symbol in symbols)
    assert any(
        reference.target_file == "styles/variables.less" and "brand-color" in reference.target_names
        for reference in references
    )
    assert any(
        reference.target_file == "styles/mixins.less" and "rounded" in reference.target_names
        for reference in references
    )


def test_less_language_detection_supports_less_suffix() -> None:
    assert repository_service._language_for_path(
        Path("styles/main.less"),
        text='@import "theme.less";\n.card { color: @brand-color; }\n',
    ) == "less"


def test_less_profile_hints_reuse_loaded_text_per_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "less-profile-hints-cache-repo"
    (repo_path / "styles").mkdir(parents=True)
    variables_path = repo_path / "styles" / "variables.less"
    main_path = repo_path / "styles" / "main.less"
    variables_path.write_text("@brand-color: #123456;\n", encoding="utf-8")
    main_path.write_text(
        '@import "variables.less";\n.card { color: @brand-color; }\n',
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_counts: dict[Path, int] = {}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in {variables_path, main_path}:
            read_counts[self] = read_counts.get(self, 0) + 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    entrypoints, roots, configs = _less_profile_hints_from_candidates(
        repo_path,
        ["styles/variables.less", "styles/main.less"],
    )

    assert "styles/main.less" in entrypoints
    assert "styles" in roots
    assert configs == set()
    assert read_counts[variables_path] <= 1
    assert read_counts[main_path] <= 1


def test_operational_seed_plan_without_diagnostics_promotes_less_when_less_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "less-profile-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "variables.less").write_text(
        "@brand-color: #123456;\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "mixins.less").write_text(
        ".rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.less").write_text(
        '@import "variables.less";\n'
        '@import "mixins.less";\n'
        ".card {\n"
        "  color: @brand-color;\n"
        "  .rounded(4px);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"less-demo","scripts":{"dev":"vite","build":"vite build"}}\n',
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text("import '../styles/main.less';\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "less" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "less"
    assert "styles/main.less" in seed_plan["entrypoint_files"]
    assert "styles" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_does_not_force_less_first_in_ts_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "less-mixed-ts-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "theme.less").write_text(
        "@brand-color: #123456;\n.card { color: @brand-color; }\n",
        encoding="utf-8",
    )
    (repo_path / "package.json").write_text(
        '{"name":"mixed-less","scripts":{"dev":"vite","build":"vite build"}}\n',
        encoding="utf-8",
    )
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.ts").write_text("import '../styles/theme.less';\n", encoding="utf-8")
    for index in range(24):
        (repo_path / "src" / f"page_{index}.ts").write_text(
            f"export function page{index}() {{ return {index}; }}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "less" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "less"
    assert "typescript" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_less_dependency_and_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "less-graph-repo"
    (repo_path / "styles").mkdir(parents=True)
    (repo_path / "styles" / "variables.less").write_text(
        "@brand-color: #123456;\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "mixins.less").write_text(
        ".rounded(@radius) { border-radius: @radius; }\n",
        encoding="utf-8",
    )
    (repo_path / "styles" / "main.less").write_text(
        '@import "variables.less";\n'
        '@import "mixins.less";\n'
        ".card {\n"
        "  color: @brand-color;\n"
        "  .rounded(4px);\n"
        "  content: 'less-graph-contract-v1';\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["styles/*.less", "styles/**/*.less", "*.less"],
        ),
    )

    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:styles/main.less"
        and str(row["target_node"]) == "file:styles/mixins.less"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("styles/main.less", "styles/main")]
    mixin_symbol_id = symbol_ids[("styles/mixins.less", "rounded")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{mixin_symbol_id}"
        for row in graph_rows
    )
