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
    repository_intelligence_dm_parser_dispatch as repository_intelligence_dm_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    dm_analysis_support as repository_dm_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dm_primitives as repository_dm_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _dm_profile_hints,
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


def test_repository_intelligence_dm_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["dm"] is (
        repository_intelligence_dm_parser_dispatch._parse_dm_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["dm"] is (
        repository_intelligence_dm_parser_dispatch._parse_dm_dependencies_only
    )


def test_repository_intelligence_dm_helpers_are_modularized() -> None:
    assert repository_service.dm_adapter.has_dm_path_hints is (
        repository_dm_primitives.has_dm_path_hints
    )
    assert repository_service.dm_adapter.is_probable_dm_source is (
        repository_dm_analysis_support.is_probable_dm_source
    )
    assert repository_service.dm_adapter.parse_include_entries is (
        repository_dm_primitives.parse_include_entries
    )
    assert repository_service.dm_adapter.module_aliases_for_path is (
        repository_dm_analysis_support.module_aliases_for_path
    )
    assert repository_service.dm_adapter.parse_file is (
        repository_dm_analysis_support.parse_file
    )


def test_dm_adapter_module_aliases_include_type_and_proc_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "dm-alias-repo"
    (repo_path / "code").mkdir(parents=True)
    (repo_path / "code" / "main.dm").write_text(
        "/obj/item\n"
        "spawn_item()\n"
        "    return new /obj/item\n",
        encoding="utf-8",
    )

    aliases = repository_service.dm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="code/main.dm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "code/main.dm" in aliases
    assert "main" in aliases
    assert "/obj/item" in aliases
    assert "spawn_item" in aliases


def test_dm_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "dm-module-only-alias-repo"
    (repo_path / "code").mkdir(parents=True)
    source_text = "/obj/item\nspawn_item()\n    return new /obj/item\n"
    (repo_path / "code" / "main.dm").write_text(source_text, encoding="utf-8")

    aliases = repository_service.dm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="code/main.dm",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_dm_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "code/main.dm" in aliases
    assert "code.main" in aliases
    assert "main" in aliases
    assert "/obj/item" not in aliases
    assert "spawn_item" not in aliases


def test_dm_module_aliases_path_only_mode_skips_text_loading_and_symbol_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dm-path-only-fast-path-repo"
    (repo_path / "code").mkdir(parents=True)
    file_path = repo_path / "code" / "main.dm"
    file_path.write_text("/obj/item\nspawn_item()\n    return new /obj/item\n", encoding="utf-8")

    def _unexpected_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"path-only dm aliases should not reread {self}")

    def _unexpected_collect_symbols(*args: object, **kwargs: object) -> object:
        raise AssertionError("path-only dm aliases should skip symbol collection")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)
    monkeypatch.setattr(
        repository_dm_analysis_support,
        "_collect_symbols",
        _unexpected_collect_symbols,
    )

    aliases = repository_service.dm_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="code/main.dm",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "code/main.dm" in aliases
    assert "code.main" in aliases
    assert "main" in aliases
    assert "/obj/item" not in aliases
    assert "spawn_item" not in aliases


def test_dm_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_dm_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_dm_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_dm_analysis_support, "strip_comments", counting_strip_comments)

    module_index = {
        "code/shared.dm": "code/shared.dm",
        "shared.dm": "code/shared.dm",
    }
    source_text = (
        '#include "shared.dm"\n'
        "/obj/item\n"
        "spawn_item()\n"
        "    return new /obj/item\n"
        "run()\n"
        "    spawn_item()\n"
    )

    repository_service.dm_adapter.parse_dependencies_only(
        "code/main.dm",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.dm_adapter.parse_file(
        "code/main.dm",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_dm_strip_comments_returns_original_text_when_no_comment_markers() -> None:
    source_text = (
        "/obj/item\n"
        "spawn_item()\n"
        "    return new /obj/item\n"
    )

    assert repository_dm_primitives.strip_comments(source_text) == source_text


def test_dm_strip_comments_reuses_cached_results() -> None:
    repository_dm_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "#define GAME \"Demo\"\n"
        "// comment\n"
        '#include "code/main.dm"\n'
    )

    first_result = repository_dm_primitives.strip_comments(source_text)
    first_cache_info = repository_dm_primitives._strip_comments_cached.cache_info()
    second_result = repository_dm_primitives.strip_comments(source_text)
    second_cache_info = repository_dm_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_dm_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = {
        "code/shared.dm": "code/shared.dm",
        "shared.dm": "code/shared.dm",
    }
    text = (
        '#include "shared.dm"\n'
        "/obj/item\n"
        "spawn_item()\n"
        "    return new /obj/item\n"
        "run()\n"
        "    spawn_item()\n"
    )

    symbols, dependencies, references = repository_service.dm_adapter.parse_file(
        "code/main.dm",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "code/shared.dm" for dependency in dependencies)
    assert any(symbol.symbol_name == "/obj/item" for symbol in symbols)
    assert any(symbol.symbol_name == "spawn_item" for symbol in symbols)
    assert any(reference.target_names == ("spawn_item",) for reference in references)
    assert any(reference.target_names == ("/obj/item",) for reference in references)


def test_dm_adapter_resolve_include_normalizes_windows_separators() -> None:
    module_index = {
        "code/main.dm": "code/main.dm",
        "code/nested/system.dm": "code/nested/system.dm",
    }

    assert repository_service.dm_adapter.resolve_include(
        current_file="game.dme",
        include_target="code\\main.dm",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "code/main.dm"
    assert repository_service.dm_adapter.resolve_include(
        current_file="game.dme",
        include_target="code\\nested\\system",
        module_index=module_index,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    ) == "code/nested/system.dm"


def test_dm_language_detection_supports_dm_and_dme_without_overclaiming() -> None:
    assert ".dm" in repository_service._TEXT_FILE_SUFFIXES
    assert ".dme" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("code/main.dm"),
        text="/obj/item\nspawn_item()\n    return new /obj/item\n",
    ) == "dm"
    assert repository_service._language_for_path(
        Path("project/demo.dme"),
        text='#define GAME "Demo"\n#include "code/main.dm"\n',
    ) == "dm"
    assert repository_service._language_for_path(
        Path("notes.dm"),
        text="plain notes without Dream Maker constructs\n",
    ) == "unknown"


def test_dm_profile_hints_follow_dme_manifest_without_loading_dm_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "dm-manifest-hints-repo"
    (repo_path / "code" / "systems").mkdir(parents=True)
    (repo_path / "maps").mkdir(parents=True)
    (repo_path / "game.dme").write_text(
        '#define GAME "Demo"\n'
        '#include "code\\\\main.dm"\n'
        '#include "code\\\\systems\\\\inventory.dm"\n'
        '#include "maps\\\\station.dm"\n',
        encoding="utf-8",
    )
    (repo_path / "code" / "main.dm").write_text("/world\n", encoding="utf-8")
    (repo_path / "code" / "systems" / "inventory.dm").write_text(
        "/datum/inventory\n",
        encoding="utf-8",
    )
    (repo_path / "maps" / "station.dm").write_text("/area/station\n", encoding="utf-8")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.suffix.lower() == ".dm":
            raise AssertionError(f"dm profile hints should not read source file {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    entrypoints, support_roots, config_paths = _dm_profile_hints(repo_path, "game.dme")

    assert config_paths == {"game.dme"}
    assert "code/main.dm" in entrypoints
    assert "code" in support_roots
    assert "code/systems" in support_roots
    assert "maps" in support_roots


def test_operational_seed_plan_without_diagnostics_promotes_dm_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dm-profile-repo"
    (repo_path / "code").mkdir(parents=True)
    for index in range(8):
        (repo_path / "code" / f"module_{index}.dm").write_text(
            f"/obj/item_{index}\nspawn_{index}()\n    return new /obj/item_{index}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"host_{index}.py").write_text(
            "def main():\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "dm" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dm"
    assert any(path.endswith(".dm") for path in seed_plan["candidate_file_paths"])


def test_operational_seed_plan_without_diagnostics_uses_dme_manifest_roots_for_dm(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dm-dme-seed-plan-repo"
    (repo_path / "code" / "systems").mkdir(parents=True)
    (repo_path / "web" / "src").mkdir(parents=True)
    (repo_path / "game.dme").write_text(
        '#define GAME "Demo"\n'
        '#include "code\\\\main.dm"\n'
        '#include "code\\\\systems\\\\inventory.dm"\n',
        encoding="utf-8",
    )
    (repo_path / "code" / "main.dm").write_text(
        "/world\n"
        "boot()\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (repo_path / "code" / "systems" / "inventory.dm").write_text(
        "/datum/inventory\n"
        "build()\n"
        "    return 1\n",
        encoding="utf-8",
    )
    for index in range(24):
        (repo_path / "web" / "src" / f"host_{index}.ts").write_text(
            "export const host = 1;\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=96,
    )

    assert "game.dme" in seed_plan["config_paths"]
    assert any(path.startswith("code/") for path in seed_plan["entrypoint_files"])
    assert any(root.startswith("code") for root in seed_plan["support_roots"])
    assert "dm" in seed_plan["detected_ecosystems"]


def test_operational_seed_plan_without_diagnostics_does_not_force_dm_first_in_host_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dm-mixed-host-repo"
    (repo_path / "code").mkdir(parents=True)
    for index in range(6):
        (repo_path / "code" / f"module_{index}.dm").write_text(
            f"/obj/item_{index}\nspawn_{index}()\n    return new /obj/item_{index}\n",
            encoding="utf-8",
        )
    (repo_path / "src").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / f"host_{index}.cs").write_text(
            "public static class Host { public static int Run() => 1; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "dm" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "dm"
    assert "cs" in seed_plan["operational_ecosystems"]


def test_operational_seed_plan_without_diagnostics_preserves_repo_root_support_scan_for_dm(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dm-root-support-repo"
    (repo_path / "code").mkdir(parents=True)
    (repo_path / "tgui" / "src").mkdir(parents=True)
    (repo_path / "tools" / "bridge").mkdir(parents=True)
    (repo_path / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (repo_path / "package.json").write_text('{"name":"dm-root-support"}\n', encoding="utf-8")
    for index in range(8):
        (repo_path / "code" / f"module_{index}.dm").write_text(
            f"/obj/item_{index}\nspawn_{index}()\n    return new /obj/item_{index}\n",
            encoding="utf-8",
        )
    for index in range(3):
        (repo_path / "tgui" / "src" / f"widget_{index}.ts").write_text(
            "export const widget = 1;\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "tools" / "bridge" / f"host_{index}.cs").write_text(
            "public static class Host { public static int Run() => 1; }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert any(path.endswith(".dm") for path in seed_plan["candidate_file_paths"])
    assert "dm" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "dm"


def test_repository_snapshot_graph_contains_dm_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "dm-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.dm").write_text(
        "/obj/item\n"
        "spawn_item()\n"
        "    return new /obj/item\n"
        "run()\n"
        "    spawn_item()\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.dm"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["file_path"] == "main.dm" and row["symbol_name"] in {"spawn_item", "/obj/item"}
    }
    assert target_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in target_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
