from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_aiken_parser_dispatch as repository_aiken_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aiken_analysis_support as repository_aiken_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    aiken_primitives as repository_aiken_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_aiken_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["aiken"] is (
        repository_aiken_parser_dispatch._parse_aiken_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["aiken"] is (
        repository_aiken_parser_dispatch._parse_aiken_dependencies_only
    )


def test_repository_intelligence_aiken_helpers_are_modularized() -> None:
    assert repository_service.aiken_adapter.strip_comments is (
        repository_aiken_primitives.strip_comments
    )
    assert repository_service.aiken_adapter.has_aiken_path_hints is (
        repository_aiken_primitives.has_aiken_path_hints
    )
    assert repository_service.aiken_adapter.is_probable_aiken_source is (
        repository_aiken_analysis_support.is_probable_aiken_source
    )
    assert repository_service.aiken_adapter.module_aliases_for_path is (
        repository_aiken_analysis_support.module_aliases_for_path
    )
    assert repository_service.aiken_adapter.parse_dependencies_only is (
        repository_aiken_analysis_support.parse_dependencies_only
    )
    assert repository_service.aiken_adapter.parse_file is (
        repository_aiken_analysis_support.parse_file
    )


def test_aiken_adapter_module_aliases_include_module_and_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "aiken-alias-repo"
    (repo_path / "lib" / "cardano").mkdir(parents=True)
    (repo_path / "lib" / "cardano" / "transaction.ak").write_text(
        "use aiken/math\n"
        "pub type Transaction {\n"
        "  amount: Int,\n"
        "}\n"
        "pub fn total(x: Int) -> Int {\n"
        "  x\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.aiken_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/cardano/transaction.ak",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/cardano/transaction.ak" in aliases
    assert "cardano/transaction" in aliases
    assert "cardano.transaction" in aliases
    assert "transaction" in aliases
    assert "Transaction" in aliases
    assert "total" in aliases


def test_aiken_adapter_parse_file_resolves_use_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "lib/aiken/math.ak",
            "lib/cardano/assets.ak",
            "lib/cardano/tx.ak",
        ],
        root_path=Path("/tmp/aiken-index"),
    )
    text = (
        "use aiken/math.{add}\n"
        "use cardano/assets as assets\n"
        "pub type Amount {\n"
        "  quantity: Int,\n"
        "}\n"
        "pub fn double(x: Int) -> Int {\n"
        "  add(x, x)\n"
        "}\n"
        "test uses_assets() {\n"
        "  assets.zero == double(1)\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.aiken_adapter.parse_file(
        "lib/cardano/tx.ak",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "Amount" and symbol.symbol_kind == "type" for symbol in symbols)
    assert any(symbol.symbol_name == "double" and symbol.symbol_kind == "function" for symbol in symbols)
    assert any(
        dependency.target_file == "lib/aiken/math.ak" and dependency.dependency_type == "uses"
        for dependency in dependencies
    )
    assert any(
        dependency.target_file == "lib/cardano/assets.ak" and dependency.dependency_type == "uses"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("aiken/math",) for reference in references)
    assert any(reference.target_names == ("add",) for reference in references)
    assert any(reference.target_names == ("zero",) for reference in references)
    assert any(reference.target_names == ("double",) for reference in references)


def test_aiken_language_detection_supports_sources_and_config_without_overclaiming() -> None:
    assert ".ak" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("lib/cardano/tx.ak"),
            text="use aiken/math\npub fn double(x: Int) -> Int { x }\n",
        )
        == "aiken"
    )
    assert (
        repository_service._language_for_path(
            Path("aiken.toml"),
            text='name = "demo/project"\nversion = "0.0.1"\ncompiler = "v1.1.21"\n',
        )
        == "aiken"
    )
    assert (
        repository_service._language_for_path(
            Path("lib/cardano/tx.ak"),
            text="plain notes without aiken constructs\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_aiken_with_repo_context(tmp_path: Path) -> None:
    repo_path = tmp_path / "aiken-candidate-repo"
    (repo_path / "lib" / "cardano").mkdir(parents=True)
    (repo_path / "lib" / "cardano" / "tx.ak").write_text(
        "use aiken/math\npub fn spend(x: Int) -> Int { x }\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "lib/cardano/tx.ak",
        repo_path=repo_path,
    ) == {"aiken"}


def test_operational_seed_plan_without_diagnostics_promotes_aiken_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "aiken-profile-repo"
    (repo_path / "lib" / "cardano").mkdir(parents=True)
    (repo_path / "lib" / "aiken").mkdir(parents=True)
    (repo_path / "aiken.toml").write_text(
        'name = "demo/project"\nversion = "0.0.1"\ncompiler = "v1.1.21"\n',
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "lib" / "cardano" / f"contract_{index}.ak").write_text(
            "use aiken/math\n"
            f"pub fn contract_{index}(x: Int) -> Int {{\n"
            "  x\n"
            "}\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "lib" / "aiken" / f"math_{index}.ak").write_text(
            f"pub fn helper_{index}(x: Int) -> Int {{\n"
            "  x\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "aiken" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "aiken"
    assert any(path.endswith(".ak") for path in seed_plan["entrypoint_files"])


def test_aiken_strip_comments_reuses_cached_results() -> None:
    repository_aiken_primitives.strip_comments.cache_clear()
    source_text = (
        "use aiken/math\n"
        "// comment\n"
        'pub fn total(x: Int) -> Int {\n'
        '  trace @"demo"\n'
        "  x\n"
        "}\n"
    )

    first_result = repository_aiken_primitives.strip_comments(source_text)
    first_cache_info = repository_aiken_primitives.strip_comments.cache_info()
    second_result = repository_aiken_primitives.strip_comments(source_text)
    second_cache_info = repository_aiken_primitives.strip_comments.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_aiken_symbol_match_reuses_cached_results() -> None:
    repository_aiken_primitives._iter_symbol_matches.cache_clear()
    stripped_text = (
        "pub type Amount {\n"
        "  quantity: Int,\n"
        "}\n"
        "pub fn total(x: Int) -> Int {\n"
        "  x\n"
        "}\n"
    )

    first_result = repository_aiken_primitives._iter_symbol_matches(stripped_text)
    first_cache_info = repository_aiken_primitives._iter_symbol_matches.cache_info()
    second_result = repository_aiken_primitives._iter_symbol_matches(stripped_text)
    second_cache_info = repository_aiken_primitives._iter_symbol_matches.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1
