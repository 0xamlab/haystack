from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_native_dispatch as repository_native_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    classic_visual_basic_analysis_support as repository_classic_visual_basic_analysis_support,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_freebasic_parser_dispatch_routes_to_native_basic_wrapper() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["freebasic"] is (
        repository_native_dispatch._parse_freebasic_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["freebasic"] is (
        repository_native_dispatch._parse_freebasic_dependencies_only
    )


def test_freebasic_language_detection_supports_source_and_header_units_without_overclaiming() -> None:
    assert ".bi" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/runtime.bi"),
            text=(
                '#include once "crt.bi"\n'
                "declare function fb_Init cdecl () as integer\n"
            ),
        )
        == "freebasic"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.bas"),
            text=(
                '#include once "runtime.bi"\n'
                "declare sub run ()\n"
                "sub run ()\n"
                "end sub\n"
            ),
        )
        == "freebasic"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/example.bi"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_freebasic_native_wrapper_extracts_symbols_and_include_dependencies() -> None:
    module_index = repository_service._build_module_index(
        ["src/runtime.bi", "src/main.bas"],
        root_path=Path("/tmp/freebasic-index"),
    )
    text = (
        '#include once "runtime.bi"\n'
        "declare sub run ()\n"
        "sub run ()\n"
        "end sub\n"
    )

    symbols, dependencies, references = repository_native_dispatch._parse_freebasic_file(
        "src/main.bas",
        text,
        module_index,
    )

    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(dependency.target_file == "src/runtime.bi" for dependency in dependencies)
    assert any(reference.target_file == "src/runtime.bi" for reference in references)


def test_freebasic_native_wrapper_reuses_stripped_text_within_each_parse_entrypoint(
    monkeypatch,
) -> None:
    module_index = repository_service._build_module_index(
        ["src/runtime.bi", "src/main.bas"],
        root_path=Path("/tmp/freebasic-index"),
    )
    source_text = (
        "' comment to force comment stripping\n"
        '#include once "runtime.bi"\n'
        "dim runtime as RuntimeType\n"
        "declare sub run ()\n"
        "sub run ()\n"
        "  runtime.execute()\n"
        "end sub\n"
    )
    original_strip_comments = repository_classic_visual_basic_analysis_support.strip_comments
    strip_comment_calls = 0

    def _counting_strip_comments(text: str) -> str:
        nonlocal strip_comment_calls
        strip_comment_calls += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_classic_visual_basic_analysis_support,
        "strip_comments",
        _counting_strip_comments,
    )

    repository_native_dispatch._parse_freebasic_dependencies_only(
        "src/main.bas",
        source_text,
        module_index,
    )
    assert strip_comment_calls == 1

    repository_native_dispatch._parse_freebasic_file(
        "src/main.bas",
        source_text,
        module_index,
    )
    assert strip_comment_calls == 2


def test_freebasic_native_wrapper_caches_repeated_target_resolution_within_parse(
    monkeypatch,
) -> None:
    module_index = repository_service._build_module_index(
        ["src/runtime.bi", "src/main.bas"],
        root_path=Path("/tmp/freebasic-index"),
    )
    source_text = (
        '#include once "runtime.bi"\n'
        "dim runtime as RuntimeType\n"
        "declare sub run ()\n"
        "sub run ()\n"
        "  runtime.execute()\n"
        "  runtime.execute()\n"
        "  runtime.execute()\n"
        "end sub\n"
    )
    original_resolve_target = repository_native_dispatch._resolve_classic_visual_basic_target
    resolve_calls = {"value": 0}

    def _counting_resolve_target(reference_target: str, module_index: dict[str, str]) -> str | None:
        resolve_calls["value"] += 1
        return original_resolve_target(reference_target, module_index)

    monkeypatch.setattr(
        repository_native_dispatch,
        "_resolve_classic_visual_basic_target",
        _counting_resolve_target,
    )

    repository_native_dispatch._parse_freebasic_file(
        "src/main.bas",
        source_text,
        module_index,
    )

    assert resolve_calls["value"] == 2


def test_operational_seed_plan_without_diagnostics_promotes_freebasic_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "freebasic-profile-repo"
    src_dir = repo_path / "src"
    inc_dir = repo_path / "inc"
    src_dir.mkdir(parents=True)
    inc_dir.mkdir(parents=True)
    for index in range(4):
        (inc_dir / f"runtime_{index}.bi").write_text(
            (
                "declare function fb_runtime_version () as integer\n"
                "type RuntimeContext\n"
                "end type\n"
            ),
            encoding="utf-8",
        )
    for index in range(4):
        (src_dir / f"module_{index}.bas").write_text(
            (
                f'#include once "../inc/runtime_{index}.bi"\n'
                f"declare sub module_{index}_run ()\n"
                f"sub module_{index}_run ()\nend sub\n"
            ),
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

    assert "freebasic" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "freebasic"
