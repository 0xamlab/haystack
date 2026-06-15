"""Tests for repository_intelligence_service: languages_a.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    assembly as repository_assembly_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    systemverilog_analysis_support as repository_systemverilog_analysis_support,
)
from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_c_family_operational_reference_name_filters_macro_like_noise() -> None:
    assert repository_service._is_c_family_operational_reference_name("format_value")
    assert not repository_service._is_c_family_operational_reference_name("FMT_ENABLE_IF")
    assert not repository_service._is_c_family_operational_reference_name("__attribute__")
    assert not repository_service._is_c_family_operational_reference_name("va_end")


def test_visual_basic_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "visual-basic-alias-repo"
    (repo_path / "src" / "Acme").mkdir(parents=True)
    (repo_path / "src" / "Acme" / "Services.vb").write_text(
        "Namespace Acme.Core\n"
        "Public Class Mediator\n"
        "End Class\n"
        "End Namespace\n",
        encoding="utf-8",
    )

    aliases = repository_service.visual_basic_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Acme/Services.vb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme/services.vb" in aliases
    assert "src/acme/services" in aliases
    assert "src.acme.services" in aliases
    assert "acme.core" in aliases
    assert "acme.core.services" in aliases
    assert "acme.core.mediator" in aliases


def test_fortran_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "fortran-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "math_utils.f90").write_text(
        "module math_utils\n"
        "implicit none\n"
        "contains\n"
        "subroutine helper()\n"
        "end subroutine helper\n"
        "end module math_utils\n",
        encoding="utf-8",
    )

    aliases = repository_service.fortran_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/math_utils.f90",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math_utils" in aliases
    assert "math_utils.helper" in aliases
    assert "helper" in aliases


def test_d_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "d-alias-repo"
    (repo_path / "source" / "acme").mkdir(parents=True)
    (repo_path / "source" / "acme" / "util.d").write_text(
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.d_language_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="source/acme/util.d",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "acme.util" in aliases
    assert "util" in aliases
    assert "Worker" in aliases
    assert "acme.util.Worker" in aliases
    assert "acme.util.helper" in aliases


def test_d_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "d-inline-text-repo"
    (repo_path / "source" / "acme").mkdir(parents=True)
    source_text = (
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n"
    )
    file_path = repo_path / "source" / "acme" / "util.d"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.d_language_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="source/acme/util.d",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.d_language_adapter.strip_comments(source_text),
    )

    assert "acme.util" in aliases
    assert "util" in aliases
    assert "Worker" in aliases
    assert "acme.util.Worker" in aliases
    assert "acme.util.helper" in aliases


def test_d_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_service.d_language_adapter._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_service.d_language_adapter.strip_comments(
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n"
    )

    first_result = repository_service.d_language_adapter._iter_symbol_entries_from_stripped_text(
        stripped_text
    )
    first_cache_info = (
        repository_service.d_language_adapter._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_service.d_language_adapter._iter_symbol_entries_from_stripped_text(
        stripped_text
    )
    second_cache_info = (
        repository_service.d_language_adapter._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_build_module_index_reuses_preloaded_text_for_d_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "d-module-index-repo"
    (repo_path / "source" / "acme").mkdir(parents=True)
    source_file = repo_path / "source" / "acme" / "util.d"
    source_file.write_text(
        "module acme.util;\n"
        "struct Worker {}\n"
        "void helper() {}\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_count = {"value": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    module_index = repository_service._build_module_index(
        ["source/acme/util.d"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert module_index["acme.util.helper"] == "source/acme/util.d"


def test_d_adapter_parse_file_extracts_import_dependencies_and_references() -> None:
    file_path = "source/acme/util.d"
    text = (
        "module acme.util;\n"
        "import acme.helper;\n"
        "struct Worker {\n"
        "    void run() {\n"
        "        helper.doThing();\n"
        "    }\n"
        "}\n"
    )
    module_index = {
        "acme.helper": "source/acme/helper.d",
        "helper": "source/acme/helper.d",
        "source/acme/helper.d": "source/acme/helper.d",
    }

    symbols, dependencies, references = repository_service.d_language_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: (
            repository_service.d_language_adapter.resolve_import(
                import_target,
                module_index=module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
        ),
    )

    assert any(symbol["symbol_name"] == "Worker" for symbol in symbols)
    assert any(
        dependency["target_file"] == "source/acme/helper.d"
        and dependency["target_symbol"] == "acme.helper"
        for dependency in dependencies
    )
    assert any(
        reference["target_file"] == "source/acme/helper.d"
        and reference["target_names"] == ("doThing",)
        for reference in references
    )


def test_d_adapter_collect_symbol_entries_bounds_non_module_symbol_ranges() -> None:
    text = (
        "module acme.util;\n"
        "void first() {\n"
        "}\n"
        "void second() {\n"
        "}\n"
    )

    symbol_entries = repository_service.d_language_adapter.collect_symbol_entries(
        text,
        file_path="source/acme/util.d",
        stable_identifier=repository_service._stable_identifier,
    )

    first_symbol = next(
        symbol for symbol in symbol_entries if symbol["symbol_name"] == "first"
    )
    second_symbol = next(
        symbol for symbol in symbol_entries if symbol["symbol_name"] == "second"
    )
    module_symbol = next(
        symbol for symbol in symbol_entries if symbol["symbol_kind"] == "module"
    )

    assert first_symbol["start_line"] == 2
    assert first_symbol["end_line"] == 3
    assert second_symbol["start_line"] == 4
    assert second_symbol["end_line"] == 5
    assert module_symbol["end_line"] == 5


def test_d_adapter_parse_file_prefers_function_scope_for_references() -> None:
    file_path = "source/acme/util.d"
    text = (
        "module acme.util;\n"
        "import acme.helper;\n"
        "void run() {\n"
        "    helper.doThing();\n"
        "}\n"
        "void noop() {\n"
        "}\n"
    )
    module_index = {
        "acme.helper": "source/acme/helper.d",
        "helper": "source/acme/helper.d",
        "source/acme/helper.d": "source/acme/helper.d",
    }

    symbols, _dependencies, references = repository_service.d_language_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: (
            repository_service.d_language_adapter.resolve_import(
                import_target,
                module_index=module_index,
                resolve_suffix_match=repository_service._resolve_suffix_match,
            )
        ),
    )

    run_symbol_id = next(
        symbol["symbol_id"] for symbol in symbols if symbol["symbol_name"] == "run"
    )
    module_symbol_id = next(
        symbol["symbol_id"] for symbol in symbols if symbol["symbol_kind"] == "module"
    )

    do_thing_references = [
        reference
        for reference in references
        if reference["target_file"] == "source/acme/helper.d"
        and reference["target_names"] == ("doThing",)
    ]

    assert any(reference["source_symbol_id"] == run_symbol_id for reference in do_thing_references)
    assert all(
        reference["source_symbol_id"] != module_symbol_id for reference in do_thing_references
    )


def test_d_adapter_parse_file_returns_stable_ids_across_repeated_parses() -> None:
    file_path = "source/acme/util.d"
    text = (
        "module acme.util;\n"
        "import acme.helper;\n"
        "struct Worker {\n"
        "    void run() {\n"
        "        helper.doThing();\n"
        "    }\n"
        "}\n"
    )
    module_index = {
        "acme.helper": "source/acme/helper.d",
        "helper": "source/acme/helper.d",
        "source/acme/helper.d": "source/acme/helper.d",
    }

    def _parse_once() -> tuple[list[dict[str, object]], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
        return repository_service.d_language_adapter.parse_file(
            file_path,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            resolve_import=lambda import_target, module_index: (
                repository_service.d_language_adapter.resolve_import(
                    import_target,
                    module_index=module_index,
                    resolve_suffix_match=repository_service._resolve_suffix_match,
                )
            ),
        )

    first_symbols, first_dependencies, first_references = _parse_once()
    second_symbols, second_dependencies, second_references = _parse_once()

    assert [symbol["symbol_id"] for symbol in first_symbols]
    assert [symbol["symbol_id"] for symbol in first_symbols] == [
        symbol["symbol_id"] for symbol in second_symbols
    ]
    assert [dependency["dependency_edge_id"] for dependency in first_dependencies] == [
        dependency["dependency_edge_id"] for dependency in second_dependencies
    ]
    assert [reference["reference_edge_id"] for reference in first_references] == [
        reference["reference_edge_id"] for reference in second_references
    ]


def test_ada_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "ada-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "acme-util.adb").write_text(
        "package body Acme.Util is\n"
        "   procedure Helper is\n"
        "   begin\n"
        "      null;\n"
        "   end Helper;\n"
        "end Acme.Util;\n",
        encoding="utf-8",
    )

    aliases = repository_service.ada_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/acme-util.adb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/acme-util.adb" in aliases
    assert "src/acme-util" in aliases
    assert "acme.util" in aliases
    assert "util" in aliases
    assert "acme.util.helper" in aliases


def test_ada_adapter_preserves_unresolved_binding_targets_as_none() -> None:
    file_path = "src/main.adb"
    text = (
        "with Missing.Util;\n"
        "procedure Main is\n"
        "begin\n"
        "   Missing.Util.Helper;\n"
        "end Main;\n"
    )

    dependencies = repository_service.ada_adapter.parse_dependencies_only(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )
    _, _, references = repository_service.ada_adapter.parse_file(
        file_path,
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_import=lambda import_target, module_index: None,
    )

    assert len(dependencies) == 1
    assert dependencies[0]["dependency_type"] == "imports"
    assert dependencies[0]["target_file"] is None
    assert references == ()


def test_assembly_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "assembly-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "boot.asm").write_text(
        "global start\n"
        "start:\n"
        "    call print_string\n"
        "    ret\n"
        "print_string:\n"
        "    ret\n",
        encoding="utf-8",
    )

    aliases = repository_service.assembly_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/boot.asm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/boot.asm" in aliases
    assert "src/boot" in aliases
    assert "src.boot" in aliases
    assert "boot" in aliases
    assert "start" in aliases
    assert "boot.start" in aliases
    assert "print_string" in aliases


def test_assembly_adapter_module_aliases_can_skip_symbol_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "assembly-module-only-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "global start\n"
        "start:\n"
        "    call print_string\n"
        "    ret\n"
        "print_string:\n"
        "    ret\n"
    )
    (repo_path / "src" / "boot.asm").write_text(source_text, encoding="utf-8")

    def _unexpected_collect_symbol_entries(*args: object, **kwargs: object) -> object:
        raise AssertionError("module-only assembly aliases should skip symbol collection")

    monkeypatch.setattr(
        repository_assembly_adapter,
        "collect_symbol_entries",
        _unexpected_collect_symbol_entries,
    )

    aliases = repository_service.assembly_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/boot.asm",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        include_symbol_aliases=False,
    )

    assert "src/boot.asm" in aliases
    assert "src/boot" in aliases
    assert "src.boot" in aliases
    assert "boot" in aliases
    assert "start" not in aliases
    assert "boot.start" not in aliases
    assert "print_string" not in aliases


def test_build_module_index_reuses_preloaded_text_for_assembly_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "assembly-module-index-repo"
    (repo_path / "src").mkdir(parents=True)
    source_file = repo_path / "src" / "boot.asm"
    source_text = (
        "global start\n"
        "start:\n"
        "    call print_string\n"
        "    ret\n"
        "print_string:\n"
        "    ret\n"
    )
    source_file.write_text(source_text, encoding="utf-8")

    original_read_text = Path.read_text
    read_count = {"value": 0}
    observed_texts: list[str | None] = []
    observed_include_symbol_aliases: list[bool | None] = []
    loaded_adapter = repository_root_scoped_aliases.assembly_adapter._load()
    original_module_aliases_for_path = loaded_adapter.module_aliases_for_path

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    def _recording_module_aliases_for_path(**kwargs) -> set[str]:
        observed_texts.append(kwargs.get("text"))
        observed_include_symbol_aliases.append(kwargs.get("include_symbol_aliases"))
        return original_module_aliases_for_path(**kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)
    monkeypatch.setattr(
        loaded_adapter,
        "module_aliases_for_path",
        _recording_module_aliases_for_path,
    )

    module_index = repository_service._build_module_index(
        ["src/boot.asm"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert observed_texts == [source_text]
    # The preloaded-text reuse (one read, text threaded into the adapter) is the
    # optimization under test. Symbol-level aliases must still be built, though:
    # assembly resolves call/extern references through the module index, so dropping
    # them would drop the references_symbol graph edges.
    assert observed_include_symbol_aliases == [True]
    assert module_index["src/boot.asm"] == "src/boot.asm"
    assert module_index["src.boot"] == "src/boot.asm"
    assert module_index["boot"] == "src/boot.asm"
    assert module_index["print_string"] == "src/boot.asm"


def test_prolog_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "prolog-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "family.pl").write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )

    aliases = repository_service.prolog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/family.pl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/family.pl" in aliases
    assert "src/family" in aliases
    assert "src.family" in aliases
    assert "family" in aliases
    assert "ancestor" in aliases
    assert "family.ancestor" in aliases
    assert "family:ancestor" in aliases


def test_prolog_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "prolog-preloaded-text-repo"
    (repo_path / "src").mkdir(parents=True)
    target_path = repo_path / "src" / "family.pl"
    target_path.write_text(
        ":- module(family, [ancestor/2, parent/2]).\n"
        "parent(alice, bob).\n"
        "ancestor(X, Y) :- parent(X, Y).\n",
        encoding="utf-8",
    )
    text = target_path.read_text(encoding="utf-8")
    target_path.unlink()

    aliases = repository_service.prolog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/family.pl",
        stable_identifier=repository_service._stable_identifier,
        text=text,
    )

    assert "family" in aliases
    assert "ancestor" in aliases
    assert "family.ancestor" in aliases


def test_prolog_marker_detection_ignores_empty_directives() -> None:
    assert repository_prolog_primitives.has_prolog_markers("\t\t:-\n") is False


def test_prolog_adapter_parse_file_reuses_single_clause_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = "src/related.pl"
    text = (
        ":- module(related, [related/2]).\n"
        ":- use_module('family.pl', [ancestor/2]).\n"
        "related(X, Y) :- ancestor(X, Y).\n"
    )
    module_index = {
        "family": "src/family.pl",
        "family.pl": "src/family.pl",
        "src/family.pl": "src/family.pl",
        "ancestor": "src/family.pl",
        "family.ancestor": "src/family.pl",
        "family:ancestor": "src/family.pl",
    }
    original_split_clauses = repository_prolog_analysis_support._split_clauses
    split_calls = {"value": 0}

    def _counting_split_clauses(
        source_text: str,
        *,
        stripped_text: str | None = None,
    ) -> tuple[tuple[int, str], ...]:
        split_calls["value"] += 1
        return original_split_clauses(source_text, stripped_text=stripped_text)

    monkeypatch.setattr(
        repository_prolog_analysis_support,
        "_split_clauses",
        _counting_split_clauses,
    )

    symbols, dependencies, references = repository_service.prolog_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=repository_native_resolution._resolve_prolog_import,
        resolve_target=repository_native_resolution._resolve_prolog_target,
    )

    assert split_calls["value"] == 1
    assert any(symbol["symbol_name"] == "related" for symbol in symbols)
    assert any(
        dependency["target_file"] == "src/family.pl"
        and dependency["dependency_type"] == "imports"
        for dependency in dependencies
    )
    assert any(
        reference["target_file"] == "src/family.pl"
        and reference["target_names"] == ("ancestor",)
        for reference in references
    )


def test_foxpro_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "foxpro-alias-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "report.prg").write_text(
        "DEFINE CLASS JsonRunner AS Custom\n"
        "ENDDEFINE\n"
        "FUNCTION Helper()\n"
        "    RETURN 1\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    aliases = repository_service.foxpro_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="programs/report.prg",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "programs/report.prg" in aliases
    assert "programs/report" in aliases
    assert "programs.report" in aliases
    assert "report" in aliases
    assert "helper" in aliases
    assert "report.helper" in aliases
    assert "jsonrunner" in aliases


def test_foxpro_adapter_module_aliases_reuse_single_stripped_text(tmp_path: Path) -> None:
    from apps.api_server.services.repository_intelligence_adapters import foxpro as repository_foxpro

    repo_path = tmp_path / "foxpro-strip-reuse-repo"
    (repo_path / "programs").mkdir(parents=True)
    (repo_path / "programs" / "report.prg").write_text(
        "DEFINE CLASS JsonRunner AS Custom && comment\n"
        "ENDDEFINE\n"
        "FUNCTION Helper()\n"
        "    RETURN 1 && comment\n"
        "ENDFUNC\n",
        encoding="utf-8",
    )

    strip_comment_calls = {"value": 0}
    original_strip_comments = repository_foxpro.strip_comments

    def _counting_strip_comments(source_text: str) -> str:
        strip_comment_calls["value"] += 1
        return original_strip_comments(source_text)

    repository_foxpro.strip_comments = _counting_strip_comments
    try:
        aliases = repository_service.foxpro_adapter.module_aliases_for_path(
            root_path=repo_path,
            file_path="programs/report.prg",
            stable_identifier=repository_service._stable_identifier,
        )
    finally:
        repository_foxpro.strip_comments = original_strip_comments

    assert strip_comment_calls["value"] == 1
    assert "helper" in aliases


def test_foxpro_adapter_parse_file_reuses_single_stripped_text() -> None:
    from apps.api_server.services.repository_intelligence_adapters import foxpro as repository_foxpro

    source_text = (
        "DEFINE CLASS JsonRunner AS Custom && comment\n"
        "ENDDEFINE\n"
        "FUNCTION Helper()\n"
        "    RETURN 1 && comment\n"
        "ENDFUNC\n"
    )
    strip_comment_calls = {"value": 0}
    original_strip_comments = repository_foxpro.strip_comments

    def _counting_strip_comments(value: str) -> str:
        strip_comment_calls["value"] += 1
        return original_strip_comments(value)

    repository_foxpro.strip_comments = _counting_strip_comments
    try:
        symbols, dependencies, references = repository_service.foxpro_adapter.parse_file(
            "programs/report.prg",
            source_text,
            {},
            stable_identifier=repository_service._stable_identifier,
            resolve_target_fn=lambda _target: None,
        )
    finally:
        repository_foxpro.strip_comments = original_strip_comments

    assert strip_comment_calls["value"] == 1
    assert any(entry["symbol_name"] == "Helper" for entry in symbols)
    assert dependencies == ()
    assert references == ()


def test_autoit_strip_comments_preserves_strings_and_block_comment_boundaries() -> None:
    stripped = repository_autoit_primitives.strip_comments(
        'Func Demo()\n'
        '    Local $value = "keep;semi"; trailing comment\n'
        '#cs hidden block\n'
        'ignored();\n'
        '#ce\n'
        '    Return $value\n'
        'EndFunc\n'
    )

    assert 'Local $value = "keep;semi"' in stripped
    assert "trailing comment" not in stripped
    assert "ignored()" not in stripped
    assert stripped.splitlines() == [
        "Func Demo()",
        '    Local $value = "keep;semi"',
        "",
        "",
        "",
        "    Return $value",
        "EndFunc",
    ]


def test_solidity_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "solidity-alias-repo"
    (repo_path / "src" / "access").mkdir(parents=True)
    (repo_path / "package.json").write_text(
        '{"name":"solidity-alias-repo"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "access" / "Ownable.sol").write_text(
        "pragma solidity ^0.8.20;\n"
        "abstract contract Ownable {\n"
        "    function owner() public view returns (address) {}\n"
        "}\n"
        "interface IOwnable {\n"
        "    function owner() external view returns (address);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.solidity_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/access/Ownable.sol",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/access/Ownable.sol" in aliases
    assert "src/access/Ownable" in aliases
    assert "src.access.Ownable" in aliases
    assert "access/Ownable.sol" in aliases
    assert "access/Ownable" in aliases
    assert "solidity-alias-repo/access/Ownable.sol" in aliases
    assert "Ownable" in aliases
    assert "IOwnable" in aliases
    assert "owner" in aliases


def test_systemverilog_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.sv").write_text(
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.systemverilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.sv",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.sv" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases


def test_systemverilog_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "systemverilog-preloaded-text-repo"
    (repo_path / "rtl").mkdir(parents=True)
    source_path = repo_path / "rtl" / "top.sv"
    source_path.write_text(
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    text = source_path.read_text(encoding="utf-8")
    source_path.unlink()

    aliases = repository_service.systemverilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.sv",
        stable_identifier=repository_service._stable_identifier,
        text=text,
    )

    assert "top" in aliases
    assert "module:top" in aliases
    assert "util_pkg" in aliases
    assert "package:util_pkg" in aliases


def test_systemverilog_adapter_module_aliases_can_skip_primary_symbols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "systemverilog-module-only-repo"
    (repo_path / "rtl").mkdir(parents=True)
    source_text = (
        "package util_pkg;\n"
        "endpackage\n"
        "module top;\n"
        "endmodule\n"
    )
    (repo_path / "rtl" / "top.sv").write_text(source_text, encoding="utf-8")

    def _unexpected_collect_primary_symbols(*args: object, **kwargs: object) -> object:
        raise AssertionError("module-only systemverilog aliases should skip primary symbol collection")

    monkeypatch.setattr(
        repository_systemverilog_analysis_support,
        "_collect_primary_symbols",
        _unexpected_collect_primary_symbols,
    )

    aliases = repository_service.systemverilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.sv",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        include_symbol_aliases=False,
    )

    assert "rtl/top.sv" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" not in aliases
    assert "util_pkg" not in aliases
    assert "package:util_pkg" not in aliases


def test_verilog_adapter_module_aliases_include_module_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "verilog-alias-repo"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "top.v").write_text(
        "module top;\n"
        "  function helper;\n"
        "  endfunction\n"
        "endmodule\n",
        encoding="utf-8",
    )

    aliases = repository_service.verilog_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rtl/top.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rtl/top.v" in aliases
    assert "rtl/top" in aliases
    assert "rtl.top" in aliases
    assert "top" in aliases
    assert "module:top" in aliases


def test_actionscript_adapter_module_aliases_include_package_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "actionscript-alias-repo"
    (repo_path / "src" / "demo" / "app").mkdir(parents=True)
    (repo_path / "src" / "demo" / "app" / "Main.as").write_text(
        "package demo.app {\n"
        "    public class Main {\n"
        "        public function boot():void {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.actionscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/app/Main.as",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/app/Main.as" in aliases
    assert "src/demo/app/Main" in aliases
    assert "src.demo.app.Main" in aliases
    assert "Main" in aliases
    assert "demo.app" in aliases
    assert "package:demo.app" in aliases
    assert "demo.app.Main" in aliases
    assert "class:Main" in aliases
    assert "class:demo.app.Main" in aliases
    assert "boot" in aliases
    assert "Main.boot" in aliases
    assert "demo.app.Main.boot" in aliases


def test_awk_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "awk-alias-repo"
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "lib" / "math.awk").write_text(
        "function add(a, b) {\n"
        "    return a + b\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.awk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/math.awk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/math.awk" in aliases
    assert "lib/math" in aliases
    assert "lib.math" in aliases
    assert "math" in aliases
    assert "add" in aliases
    assert "math.add" in aliases


def test_awk_module_aliases_skip_irrelevant_non_awk_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "awk-non-source-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.json").write_text('{"targets":[]}\n', encoding="utf-8")

    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("non-Awk files should bypass Awk comment stripping")

    monkeypatch.setattr(
        repository_awk_primitives,
        "strip_comments",
        _unexpected_strip_comments,
    )
    monkeypatch.setattr(
        repository_awk_analysis_support,
        "strip_comments",
        _unexpected_strip_comments,
    )

    aliases = repository_service.awk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.json",
        stable_identifier=repository_service._stable_identifier,
    )

    assert aliases == set()


def test_coffeescript_adapter_module_aliases_include_class_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.coffee").write_text(
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n"
        "\n"
        "exports.compile = ->\n"
        "  true\n",
        encoding="utf-8",
    )

    aliases = repository_service.coffeescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.coffee",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.coffee" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "App" in aliases
    assert "boot" in aliases
    assert "renderJson" in aliases
    assert "compile" in aliases
    assert "main.boot" in aliases
    assert "main.renderJson" in aliases
    assert "main.compile" in aliases


def test_coffeescript_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coffeescript-inline-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n"
    )
    file_path = repo_path / "src" / "main.coffee"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.coffeescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.coffee",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.coffeescript_adapter.strip_comments(source_text),
    )

    assert "App" in aliases
    assert "boot" in aliases
    assert "renderJson" in aliases
    assert "main.boot" in aliases


def test_coffeescript_adapter_module_aliases_skip_stable_ids_for_raw_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coffeescript-stable-id-repo"
    (repo_path / "src").mkdir(parents=True)
    file_path = repo_path / "src" / "main.coffee"
    file_path.write_text(
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n",
        encoding="utf-8",
    )

    def _no_symbol_ids(kind: str, payload: object) -> str:
        if kind == "sym":
            raise AssertionError(f"module_aliases_for_path should not request stable ids: {payload}")
        return repository_service._stable_identifier(kind, payload)

    aliases = repository_service.coffeescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.coffee",
        stable_identifier=_no_symbol_ids,
    )

    assert "App" in aliases
    assert "renderJson" in aliases


def test_coffeescript_adapter_parse_file_reuses_single_stripped_text() -> None:
    file_path = "src/main.coffee"
    text = (
        "Helper = require './helper'\n"
        "\n"
        "class App\n"
        "  boot: ->\n"
        "    helper = new Helper\n"
        "    helper.run()\n"
    )
    module_index = {"src/helper.coffee": "src/helper.coffee"}
    strip_comment_calls = {"value": 0}
    original_analysis_strip_comments = repository_coffeescript_analysis_support.strip_comments
    original_primitive_strip_comments = repository_coffeescript_primitives.strip_comments

    def _counting_strip_comments(source_text: str) -> str:
        strip_comment_calls["value"] += 1
        return original_primitive_strip_comments(source_text)

    repository_coffeescript_analysis_support.strip_comments = _counting_strip_comments
    repository_coffeescript_primitives.strip_comments = _counting_strip_comments
    try:
        symbols, dependencies, references = repository_service.coffeescript_adapter.parse_file(
            file_path,
            text,
            module_index,
            stable_identifier=repository_service._stable_identifier,
            normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
            resolve_suffix_match=repository_service._resolve_suffix_match,
        )
    finally:
        repository_coffeescript_analysis_support.strip_comments = original_analysis_strip_comments
        repository_coffeescript_primitives.strip_comments = original_primitive_strip_comments

    assert strip_comment_calls["value"] == 1
    assert any(symbol.symbol_name == "App" for symbol in symbols)
    assert any(dependency.target_file == "src/helper.coffee" for dependency in dependencies)
    assert any(reference.target_names == ("run",) for reference in references)


def test_coffeescript_strip_comments_uses_cache_for_repeat_inputs() -> None:
    repository_coffeescript_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "class App\n"
        "  boot: ->\n"
        "    true # comment\n"
    )

    first_result = repository_service.coffeescript_adapter.strip_comments(source_text)
    first_cache_info = repository_coffeescript_primitives._strip_comments_cached.cache_info()
    second_result = repository_service.coffeescript_adapter.strip_comments(source_text)
    second_cache_info = repository_coffeescript_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_build_module_index_reuses_preloaded_text_for_coffeescript_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coffeescript-module-index-repo"
    (repo_path / "src").mkdir(parents=True)
    source_file = repo_path / "src" / "main.coffee"
    source_file.write_text(
        "class App\n"
        "  boot: ->\n"
        "    true\n"
        "\n"
        "renderJson = ->\n"
        "  '{}'\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_count = {"value": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    module_index = repository_service._build_module_index(
        ["src/main.coffee"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert module_index["main.renderJson"] == "src/main.coffee"


def test_vala_adapter_module_aliases_include_namespace_type_and_method_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "vala-alias-repo"
    (repo_path / "src" / "App").mkdir(parents=True)
    (repo_path / "src" / "App" / "MainWindow.vala").write_text(
        "namespace Demo.App {\n"
        "    public class MainWindow : Object {\n"
        "        public void present_window () {\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.vala_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/App/MainWindow.vala",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/App/MainWindow.vala" in aliases
    assert "src/App/MainWindow" in aliases
    assert "src.app.mainwindow" in aliases
    assert "MainWindow" in aliases
    assert "demo.app" in aliases
    assert "Demo.App.MainWindow" in aliases
    assert "present_window" in aliases
    assert "Demo.App.MainWindow.present_window" in aliases


def test_mql5_adapter_module_aliases_include_type_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mql5-alias-repo"
    (repo_path / "Experts").mkdir(parents=True)
    (repo_path / "Experts" / "Main.mq5").write_text(
        "class Helper\n"
        "{\n"
        "public:\n"
        "   string RenderJson()\n"
        "     {\n"
        '      return "{}";\n'
        "     }\n"
        "};\n"
        "\n"
        "void OnStart()\n"
        "{\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.mql5_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Experts/Main.mq5",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Experts/Main.mq5" in aliases
    assert "Experts/Main" in aliases
    assert "Experts.Main" in aliases
    assert "Main" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "OnStart" in aliases
    assert "Helper.RenderJson" in aliases
    assert "Main.OnStart" in aliases


def test_gams_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "gams-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "main.gms").write_text(
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. cost('a') =e= 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.gams_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/main.gms",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/main.gms" in aliases
    assert "models/main" in aliases
    assert "models.main" in aliases
    assert "main" in aliases
    assert "i" in aliases
    assert "cost" in aliases
    assert "balance" in aliases
    assert "main.balance" in aliases


def test_gams_adapter_parse_file_assigns_reference_to_equation_symbol() -> None:
    module_index = {
        "common.inc": "include/common.inc",
        "include/common.inc": "include/common.inc",
        "demand": "include/common.inc",
        "main": "models/main.gms",
        "models/main": "models/main.gms",
    }
    text = (
        "$include ../include/common.inc\n"
        "set i /a,b/;\n"
        "parameter cost(i);\n"
        "equation balance;\n"
        "balance.. demand('a') =e= cost('a');\n"
    )

    symbols, dependencies, references = repository_service.gams_adapter.parse_file(
        "models/main.gms",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    balance_symbol_id = next(
        symbol.symbol_id
        for symbol in symbols
        if symbol.symbol_name == "balance" and symbol.start_line == 5
    )
    assert any(dependency.target_file == "include/common.inc" for dependency in dependencies)
    assert any(
        reference.source_symbol_id == balance_symbol_id
        and reference.target_file == "include/common.inc"
        and reference.target_names == ("demand",)
        for reference in references
    )


def test_nix_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "nix-alias-repo"
    (repo_path / "nix").mkdir(parents=True)
    (repo_path / "nix" / "formatter.nix").write_text(
        "{ pkgs }:\n"
        "let\n"
        "  mkFormatter = package: package;\n"
        "in {\n"
        "  mkFormatter = mkFormatter;\n"
        "  formatter = mkFormatter pkgs.alejandra;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nix_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="nix/formatter.nix",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "nix/formatter.nix" in aliases
    assert "nix/formatter" in aliases
    assert "nix.formatter" in aliases
    assert "formatter" in aliases
    assert "mkFormatter" in aliases
    assert "formatter.mkFormatter" in aliases


def test_openscad_adapter_module_aliases_include_module_and_function_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    (repo_path / "models" / "helpers.scad").write_text(
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n",
        encoding="utf-8",
    )

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "models/helpers.scad" in aliases
    assert "models/helpers" in aliases
    assert "models.helpers" in aliases
    assert "shelf" in aliases
    assert "render_profile" in aliases
    assert "helpers.shelf" in aliases
    assert "helpers.render_profile" in aliases


def test_openscad_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "openscad-inline-text-repo"
    (repo_path / "models").mkdir(parents=True)
    source_text = (
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n"
    )
    file_path = repo_path / "models" / "helpers.scad"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.openscad_adapter.strip_comments(source_text),
    )

    assert "models/helpers.scad" in aliases
    assert "models/helpers" in aliases
    assert "models.helpers" in aliases
    assert "shelf" in aliases
    assert "render_profile" in aliases


def test_openscad_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "openscad-module-only-alias-repo"
    (repo_path / "models").mkdir(parents=True)
    source_text = (
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n"
        "function render_profile(value) = value + 1;\n"
    )
    (repo_path / "models" / "helpers.scad").write_text(source_text, encoding="utf-8")

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.openscad_adapter.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "models/helpers.scad" in aliases
    assert "models/helpers" in aliases
    assert "models.helpers" in aliases
    assert "shelf" not in aliases
    assert "render_profile" not in aliases
    assert "helpers.shelf" not in aliases


def test_openscad_strip_comments_reuses_cached_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = repository_openscad_primitives._strip_comments_preserving_lines
    call_count = {"value": 0}

    def counting_strip(text: str) -> str:
        call_count["value"] += 1
        return original(text)

    repository_openscad_primitives.strip_comments.cache_clear()
    monkeypatch.setattr(
        repository_openscad_primitives,
        "_strip_comments_preserving_lines",
        counting_strip,
    )

    source_text = "module shelf() { /* comment */ cube([1, 1, 1]); }\n"

    assert repository_service.openscad_adapter.strip_comments(source_text)
    assert repository_service.openscad_adapter.strip_comments(source_text)
    assert call_count["value"] == 1

    repository_openscad_primitives.strip_comments.cache_clear()


def test_openscad_parse_dependencies_only_skips_import_scan_without_directives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class GuardedImportPattern:
        def finditer(self, text: str) -> object:
            raise AssertionError("parse_dependencies_only should skip import scanning")

    monkeypatch.setattr(
        repository_openscad_analysis_support,
        "_IMPORT_RE",
        GuardedImportPattern(),
    )

    dependencies = repository_service.openscad_adapter.parse_dependencies_only(
        "models/helpers.scad",
        "module shelf(width) {\n  cube([width, width, width]);\n}\n",
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert dependencies == ()


def test_openscad_module_aliases_skip_file_read_for_module_only_indexing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openscad-module-only-repo"
    (repo_path / "models").mkdir(parents=True)
    file_path = repo_path / "models" / "helpers.scad"
    file_path.write_text(
        "module shelf(width) {\n"
        "  cube([width, width, width]);\n"
        "}\n",
        encoding="utf-8",
    )

    def _fail_strip(text: str) -> str:
        raise AssertionError("module-only aliases should not strip comments")

    monkeypatch.setattr(
        repository_openscad_primitives,
        "strip_comments",
        _fail_strip,
    )

    aliases = repository_service.openscad_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="models/helpers.scad",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "models/helpers.scad" in aliases
    assert "models.helpers" in aliases
    assert "helpers" in aliases


def test_openscad_has_import_directives_detects_indented_directive_lines() -> None:
    assert repository_openscad_primitives.has_import_directives(
        "module shelf() {\n  cube([1, 1, 1]);\n}\n",
    ) is False
    assert repository_openscad_primitives.has_import_directives(
        "  use <lib/helpers.scad>;\nmodule shelf() { cube([1, 1, 1]); }\n",
    ) is True


def test_purescript_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-alias-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        "module Control.Helper where\n"
        "\n"
        "data Helper = Helper\n"
        "\n"
        "renderJson :: String\n"
        "renderJson = \"{}\"\n",
        encoding="utf-8",
    )

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Control/Helper.purs" in aliases
    assert "src/Control/Helper" in aliases
    assert "src.Control.Helper" in aliases
    assert "Control.Helper" in aliases
    assert "renderJson" in aliases
    assert "Helper" in aliases
    assert "Control.Helper.renderJson" in aliases


def test_purescript_adapter_module_aliases_can_skip_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "purescript-module-only-alias-repo"
    (repo_path / "src" / "Control").mkdir(parents=True)
    source_text = (
        "module Control.Helper where\n"
        "\n"
        "data Helper = Helper\n"
        "\n"
        "renderJson :: String\n"
        "renderJson = \"{}\"\n"
    )
    (repo_path / "src" / "Control" / "Helper.purs").write_text(
        source_text,
        encoding="utf-8",
    )

    aliases = repository_service.purescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Control/Helper.purs",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "src/Control/Helper.purs" in aliases
    assert "src/Control/Helper" in aliases
    assert "src.Control.Helper" in aliases
    assert "Control.Helper" in aliases
    assert "renderJson" not in aliases
    assert "Helper" not in aliases
    assert "Control.Helper.renderJson" not in aliases


def test_gleam_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "gleam-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "helper.gleam").write_text(
        "pub type Helper {\n  Helper\n}\n\npub fn render_json() {\n  Nil\n}\n",
        encoding="utf-8",
    )

    aliases = repository_service.gleam_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/helper.gleam",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/helper.gleam" in aliases
    assert "src/demo/helper" in aliases
    assert "src.demo.helper" in aliases
    assert "demo/helper" in aliases
    assert "demo.helper" in aliases
    assert "render_json" in aliases
    assert "Helper" in aliases
    assert "demo.helper.render_json" in aliases


def test_janet_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "janet-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "init.janet").write_text(
        "(defn render-json [] @{})\n(def helper-state @{})\n",
        encoding="utf-8",
    )

    aliases = repository_service.janet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/init.janet",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/init.janet" in aliases
    assert "src/demo/init" in aliases
    assert "src.demo.init" in aliases
    assert "init" in aliases
    assert "demo" in aliases
    assert "render-json" in aliases
    assert "helper-state" in aliases
    assert "demo/render-json" in aliases
    assert "demo.render-json" in aliases


def test_dhall_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "dhall-alias-repo"
    (repo_path / "schemas" / "Step").mkdir(parents=True)
    (repo_path / "schemas" / "Step" / "package.dhall").write_text(
        "{ Type = \"step\", default = \"run\" }\n",
        encoding="utf-8",
    )

    aliases = repository_service.dhall_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="schemas/Step/package.dhall",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "schemas/Step/package.dhall" in aliases
    assert "schemas/Step/package" in aliases
    assert "schemas.Step.package" in aliases
    assert "schemas/Step" in aliases
    assert "schemas.Step" in aliases
    assert "Step" in aliases
    assert "Type" in aliases
    assert "default" in aliases
    assert "schemas/Step.Type" in aliases
    assert "schemas.Step.Type" in aliases


def test_puppet_adapter_module_aliases_include_manifest_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-alias-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.puppet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="manifests/params.pp",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "manifests/params.pp" in aliases
    assert "manifests/params" in aliases
    assert "manifests::params" in aliases
    assert "params" in aliases
    assert "apache::params" in aliases
    assert "apache/params" in aliases
    assert "apache.params" in aliases


def test_puppet_module_aliases_skip_irrelevant_non_puppet_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "puppet-non-source-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.json").write_text('{"name":"demo"}\n', encoding="utf-8")

    def _unexpected_strip_comments(_text: str) -> str:
        raise AssertionError("non-Puppet files should bypass Puppet comment stripping")

    monkeypatch.setattr(
        repository_puppet_primitives,
        "strip_comments",
        _unexpected_strip_comments,
    )
    monkeypatch.setattr(
        repository_puppet_analysis_support,
        "strip_comments",
        _unexpected_strip_comments,
    )

    aliases = repository_service.puppet_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.json",
        stable_identifier=repository_service._stable_identifier,
    )

    assert aliases == set()


def test_coq_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-alias-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )

    aliases = repository_service.coq_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="theories/Helper.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "theories/Helper.v" in aliases
    assert "theories.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_coq_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "coq-module-only-alias-repo"
    (repo_path / "theories").mkdir(parents=True)
    source_text = "Definition helper : nat := 0.\n"
    (repo_path / "theories" / "Helper.v").write_text(source_text, encoding="utf-8")

    aliases = repository_service.coq_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="theories/Helper.v",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "theories/Helper.v" in aliases
    assert "theories.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" not in aliases


def test_coq_module_aliases_path_only_mode_skips_text_loading_and_symbol_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-path-only-fast-path-repo"
    (repo_path / "theories").mkdir(parents=True)
    file_path = repo_path / "theories" / "Helper.v"
    file_path.write_text("Definition helper : nat := 0.\n", encoding="utf-8")

    def _unexpected_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"path-only coq aliases should not reread {self}")

    def _unexpected_collect_symbols(*args: object, **kwargs: object) -> object:
        raise AssertionError("path-only coq aliases should skip symbol collection")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)
    monkeypatch.setattr(
        repository_coq_analysis_support,
        "_collect_symbols",
        _unexpected_collect_symbols,
    )

    aliases = repository_service.coq_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="theories/Helper.v",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "theories/Helper.v" in aliases
    assert "theories.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" not in aliases


def test_coq_parse_require_modules_reuses_cached_stripped_text_results() -> None:
    source_text = (
        "(* comment *)\n"
        "From Coq Require Import Arith.\n"
        "Require Import Foo Bar.\n"
    )
    stripped_text = repository_coq_primitives.strip_comments(source_text)

    first = repository_service.coq_adapter.parse_require_modules(
        source_text,
        stripped_text=stripped_text,
    )
    second = repository_service.coq_adapter.parse_require_modules(
        source_text,
        stripped_text=stripped_text,
    )

    assert first == (("Coq.Arith", 2), ("Foo", 3), ("Bar", 3))
    assert first is second


def test_coq_project_parsers_reuse_cached_stripped_text_results() -> None:
    manifest_text = (
        "(* project comment *)\n"
        "-R theories Demo\n"
        "-I plugins\n"
        "theories/Main.v\n"
        "theories/Helper.v\n"
    )
    stripped_text = repository_coq_primitives.strip_comments(manifest_text)

    first_roots = repository_service.coq_adapter.parse_project_roots(
        manifest_text,
        stripped_text=stripped_text,
    )
    second_roots = repository_service.coq_adapter.parse_project_roots(
        manifest_text,
        stripped_text=stripped_text,
    )
    first_sources = repository_service.coq_adapter.parse_project_sources(
        manifest_text,
        stripped_text=stripped_text,
    )
    second_sources = repository_service.coq_adapter.parse_project_sources(
        manifest_text,
        stripped_text=stripped_text,
    )

    assert first_roots == ("theories", "plugins")
    assert first_sources == ("theories/Main.v", "theories/Helper.v")
    assert first_roots is second_roots
    assert first_sources is second_sources


def test_lean_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-alias-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_lean_adapter_module_aliases_can_use_preloaded_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-alias-preloaded-text-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    source_text = "def helper : Nat := 0\n"
    (repo_path / "Batteries" / "Helper.lean").write_text(
        source_text,
        encoding="utf-8",
    )

    def _fail_read_text(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("module_aliases_for_path should reuse preloaded lean text")

    monkeypatch.setattr(Path, "read_text", _fail_read_text)

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.lean_adapter.strip_comments(source_text),
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases


def test_lean_adapter_module_aliases_can_skip_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-module-only-alias-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    source_text = "def helper : Nat := 0\n"
    (repo_path / "Batteries" / "Helper.lean").write_text(
        source_text,
        encoding="utf-8",
    )

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.lean_adapter.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" not in aliases


def test_lean_module_aliases_skip_symbol_collection_in_module_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "lean-module-only-fast-path-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    source_text = "def helper : Nat := 0\n"
    (repo_path / "Batteries" / "Helper.lean").write_text(
        source_text,
        encoding="utf-8",
    )

    def _unexpected_collect_symbols(**kwargs: object) -> object:
        raise AssertionError("module-only lean aliases should skip symbol collection")

    monkeypatch.setattr(
        repository_lean_analysis_support,
        "_collect_symbols",
        _unexpected_collect_symbols,
    )

    aliases = repository_service.lean_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Batteries/Helper.lean",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.lean_adapter.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "Batteries/Helper.lean" in aliases
    assert "Batteries.Helper" in aliases
    assert "Helper" in aliases
    assert "helper" not in aliases


def test_rego_adapter_module_aliases_include_package_and_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-alias-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.rego_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="policy/lib/helpers.rego",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "policy/lib/helpers.rego" in aliases
    assert "policy/lib/helpers" in aliases
    assert "policy.lib.helpers" in aliases
    assert "policy/lib/helpers" in aliases
    assert "data.policy.lib.helpers" in aliases
    assert "render_json" in aliases
    assert "policy.lib.helpers.render_json" in aliases
    assert "data.policy.lib.helpers.render_json" in aliases


def test_yara_adapter_module_aliases_include_rule_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-alias-repo"
    (repo_path / "rules").mkdir(parents=True)
    (repo_path / "rules" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.yara_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="rules/helper.yar",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "rules/helper.yar" in aliases
    assert "rules/helper" in aliases
    assert "helper_rule" in aliases
