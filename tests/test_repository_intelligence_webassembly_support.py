from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_webassembly_parser_dispatch as repository_webassembly_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    webassembly_analysis_support as repository_webassembly_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    webassembly_primitives as repository_webassembly_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_webassembly_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["webassembly"] is (
        repository_webassembly_parser_dispatch._parse_webassembly_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["webassembly"] is (
        repository_webassembly_parser_dispatch._parse_webassembly_dependencies_only
    )


def test_repository_intelligence_webassembly_helpers_are_modularized() -> None:
    assert repository_service.webassembly_adapter.strip_comments is (
        repository_webassembly_primitives.strip_comments
    )
    assert repository_service.webassembly_adapter.has_webassembly_path_hints is (
        repository_webassembly_primitives.has_webassembly_path_hints
    )
    assert repository_service.webassembly_adapter.is_probable_webassembly_source is (
        repository_webassembly_analysis_support.is_probable_webassembly_source
    )
    assert repository_service.webassembly_adapter.module_aliases_for_path is (
        repository_webassembly_analysis_support.module_aliases_for_path
    )
    assert repository_service.webassembly_adapter.parse_dependencies_only is (
        repository_webassembly_analysis_support.parse_dependencies_only
    )
    assert repository_service.webassembly_adapter.parse_file is (
        repository_webassembly_analysis_support.parse_file
    )


def test_webassembly_adapter_parse_file_extracts_imports_and_symbol_references() -> None:
    text = (
        '(module\n'
        '  (import "env" "log" (func $log (param i32)))\n'
        '  (func $main\n'
        '    call $log)\n'
        ')\n'
    )

    aliases = repository_service.webassembly_adapter.module_aliases_for_path(
        root_path=Path("/tmp/webassembly-alias-root"),
        file_path="spec/main.wat",
        stable_identifier=repository_service._stable_identifier,
    )
    symbols, dependencies, references = repository_service.webassembly_adapter.parse_file(
        "spec/main.wat",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
    )

    assert "spec/main.wat" in aliases
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(dependency.target_symbol == "env::log" for dependency in dependencies)
    assert any(reference.target_names == ("log",) for reference in references)


def test_webassembly_language_detection_supports_text_format_suffixes_without_overclaiming() -> None:
    assert ".wat" in repository_service._TEXT_FILE_SUFFIXES
    assert repository_service._language_for_path(
        Path("spec/main.wat"),
        text="(module (func $main))\n",
    ) == "webassembly"
    assert repository_service._language_for_path(
        Path("spec/main.wast"),
        text='(module (import "env" "log" (func $log)))\n',
    ) == "webassembly"
    assert repository_service._language_for_path(
        Path("spec/notes.wat"),
        text="plain notes\n",
    ) == "unknown"


def test_operational_seed_plan_without_diagnostics_promotes_webassembly_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "webassembly-profile-repo"
    (repo_path / "test" / "core").mkdir(parents=True)
    for index in range(4):
        (repo_path / "test" / "core" / f"case_{index}.wat").write_text(
            '(module\n'
            '  (import "env" "log" (func $log (param i32)))\n'
            f'  (func $main{index}\n'
            '    call $log)\n'
            ')\n',
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

    assert "webassembly" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "webassembly"
    assert any(path.endswith(".wat") for path in seed_plan["entrypoint_files"])
