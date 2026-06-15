"""Tests for repository_intelligence_service: languages_b.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_bicep_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "main.bicep").write_text(
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n",
        encoding="utf-8",
    )

    aliases = repository_service.bicep_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/main.bicep",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/main.bicep" in aliases
    assert "modules/main" in aliases
    assert "modules" in aliases
    assert "modules.main" in aliases
    assert "name" in aliases
    assert "prefix" in aliases
    assert "fullName" in aliases
    assert "modules.fullName" in aliases


def test_bicep_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "bicep-inline-text-repo"
    (repo_path / "modules").mkdir(parents=True)
    source_text = (
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n"
    )
    file_path = repo_path / "modules" / "main.bicep"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.bicep_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/main.bicep",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_bicep_primitives.strip_comments(source_text),
    )

    assert "modules/main.bicep" in aliases
    assert "modules/main" in aliases
    assert "modules" in aliases
    assert "modules.main" in aliases
    assert "name" in aliases
    assert "prefix" in aliases
    assert "fullName" in aliases
    assert "modules.fullName" in aliases


def test_bicep_adapter_module_aliases_can_skip_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-module-only-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    source_text = (
        "param name string\n\n"
        "var prefix = name\n\n"
        "output fullName string = prefix\n"
    )
    (repo_path / "modules" / "main.bicep").write_text(source_text, encoding="utf-8")

    aliases = repository_service.bicep_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/main.bicep",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_bicep_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "modules/main.bicep" in aliases
    assert "modules/main" in aliases
    assert "modules" in aliases
    assert "modules.main" in aliases
    assert "name" not in aliases
    assert "prefix" not in aliases
    assert "fullName" not in aliases
    assert "modules.fullName" not in aliases


def test_bicep_strip_comments_preserves_strings_and_newlines() -> None:
    source_text = (
        "param literal string = '// keep'\n"
        "/*block\n"
        "comment*/\n"
        "var value = 1 // drop\n"
        "var nested = '/* keep */'\n"
    )

    stripped_text = repository_bicep_primitives.strip_comments(source_text)

    assert stripped_text == (
        "param literal string = '// keep'\n"
        "       \n"
        "         \n"
        "var value = 1        \n"
        "var nested = '/* keep */'\n"
    )


def test_tlaplus_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "tlaplus-alias-repo"
    (repo_path / "specs").mkdir(parents=True)
    (repo_path / "specs" / "Spec.tla").write_text(
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n\n"
        "Foo == 1\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n",
        encoding="utf-8",
    )

    aliases = repository_service.tlaplus_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="specs/Spec.tla",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "specs/Spec.tla" in aliases
    assert "specs/Spec" in aliases
    assert "Spec" in aliases
    assert "Foo" in aliases
    assert "Spec.Foo" in aliases
    assert "Spec!Foo" in aliases
    assert "x" in aliases
    assert "Y" in aliases


def test_tlaplus_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "tlaplus-alias-inline-text-repo"
    (repo_path / "specs").mkdir(parents=True)
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n\n"
        "Foo == 1\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n"
    )
    file_path = repo_path / "specs" / "Spec.tla"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.tlaplus_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="specs/Spec.tla",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_tlaplus_primitives.strip_comments(source_text),
    )

    assert "Spec" in aliases
    assert "Foo" in aliases
    assert "Spec.Foo" in aliases


def test_tlaplus_adapter_parse_file_reuses_cached_strip_comments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_tlaplus_primitives.clear_strip_comments_cache()
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n\n"
        "Foo == 1\n"
        "Bar == Foo\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n"
    )
    module_index = {
        "Spec": "specs/Spec.tla",
        "specs/Spec.tla": "specs/Spec.tla",
    }
    call_count = 0
    original_strip_comments = repository_tlaplus_primitives._strip_comments_uncached

    def _counting_strip_comments(source: str) -> str:
        nonlocal call_count
        call_count += 1
        return original_strip_comments(source)

    monkeypatch.setattr(
        repository_tlaplus_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments,
    )

    repository_service.tlaplus_adapter.parse_dependencies_only(
        "specs/Spec.tla",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.tlaplus_adapter.parse_file(
        "specs/Spec.tla",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert call_count == 1


def test_tlaplus_adapter_parse_file_reuses_prestripped_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_tlaplus_primitives.clear_strip_comments_cache()
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n"
        "(* repeated preprocessing used to restrip this line block *)\n"
        "\\* single-line comment\n"
        "Foo == 1\n"
        "Bar == Foo\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n"
    )
    module_index = {
        "Spec": "specs/Spec.tla",
        "specs/Spec.tla": "specs/Spec.tla",
    }
    call_count = 0
    original_strip_comments = repository_tlaplus_primitives._strip_comments_uncached

    def _counting_strip_comments(source: str) -> str:
        nonlocal call_count
        call_count += 1
        return original_strip_comments(source)

    monkeypatch.setattr(
        repository_tlaplus_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments,
    )

    repository_service.tlaplus_adapter.parse_file(
        "specs/Spec.tla",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert call_count == 1


def test_tlaplus_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_tlaplus_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n"
        "VARIABLES x\n"
        "CONSTANTS Y\n"
        "Foo == 1\n"
    )
    stripped_text = repository_tlaplus_primitives.strip_comments(source_text)

    first_result = repository_tlaplus_primitives.iter_symbol_entries(
        source_text,
        file_path="specs/Spec.tla",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_tlaplus_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_tlaplus_primitives.iter_symbol_entries(
        source_text,
        file_path="specs/Spec.tla",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_tlaplus_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_tlaplus_parse_instance_statements_reuse_cached_stripped_text_entries() -> None:
    repository_tlaplus_primitives._parse_instance_statements_from_stripped_text.cache_clear()
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n"
        "Inst == INSTANCE Helper\n"
        "LOCAL INSTANCE Tools\n"
    )
    stripped_text = repository_tlaplus_primitives.strip_comments(source_text)

    first_result = repository_tlaplus_primitives.parse_instance_statements(
        source_text,
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_tlaplus_primitives._parse_instance_statements_from_stripped_text.cache_info()
    )
    second_result = repository_tlaplus_primitives.parse_instance_statements(
        source_text,
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_tlaplus_primitives._parse_instance_statements_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_tlaplus_parse_instance_statements_reuse_cached_line_offsets() -> None:
    repository_tlaplus_primitives._parse_instance_statements_from_stripped_text.cache_clear()
    repository_tlaplus_primitives.line_start_offsets.cache_clear()
    source_text = (
        "---- MODULE Spec ----\n"
        "EXTENDS Naturals\n"
        "Inst == INSTANCE Helper\n"
        "LOCAL INSTANCE Tools\n"
    )
    stripped_text = repository_tlaplus_primitives.strip_comments(source_text)

    entries = repository_tlaplus_primitives.parse_instance_statements(
        source_text,
        stripped_text=stripped_text,
    )
    cache_info = repository_tlaplus_primitives.line_start_offsets.cache_info()

    assert [entry[2] for entry in entries] == [3, 4]
    assert cache_info.hits >= 1
    assert cache_info.misses == 1


def test_logtalk_adapter_module_aliases_include_entity_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "logtalk-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.lgt").write_text(
        ":- object(main).\n"
        "    :- public(run/0).\n"
        "    run :- helper::answer(_).\n"
        ":- end_object.\n",
        encoding="utf-8",
    )

    aliases = repository_service.logtalk_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.lgt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.lgt" in aliases
    assert "src/main" in aliases
    assert "main" in aliases
    assert "run" in aliases
    assert "main.run" in aliases


def test_chapel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Main.chpl").write_text(
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Main.chpl" in aliases
    assert "src/Main" in aliases
    assert "Main" in aliases
    assert "run" in aliases
    assert "Main.run" in aliases


def test_chapel_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "chapel-inline-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n"
    )
    file_path = repo_path / "src" / "Main.chpl"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_chapel_primitives.strip_comments(source_text),
    )

    assert "src/Main.chpl" in aliases
    assert "src/Main" in aliases
    assert "Main" in aliases
    assert "run" in aliases
    assert "Main.run" in aliases


def test_chapel_adapter_module_aliases_do_not_build_stable_ids_for_raw_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-raw-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "proc helper() { return 1; }\n"
        "}\n"
    )
    (repo_path / "src" / "Main.chpl").write_text(source_text, encoding="utf-8")

    def _unexpected_stable_identifier(_prefix: str, _payload: object) -> str:
        raise AssertionError("module_aliases_for_path should not build stable identifiers")

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=_unexpected_stable_identifier,
        text=source_text,
        stripped_text=repository_chapel_primitives.strip_comments(source_text),
    )

    assert "Main" in aliases
    assert "run" in aliases
    assert "Main.run" in aliases
    assert "helper" in aliases
    assert "Main.helper" in aliases


def test_chapel_adapter_module_aliases_can_skip_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "chapel-module-only-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n"
    )
    (repo_path / "src" / "Main.chpl").write_text(source_text, encoding="utf-8")

    aliases = repository_service.chapel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Main.chpl",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_chapel_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "src/Main.chpl" in aliases
    assert "src/Main" in aliases
    assert "Main" in aliases
    assert "run" not in aliases
    assert "Main.run" not in aliases


def test_chapel_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_chapel_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_chapel_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_chapel_analysis_support, "strip_comments", counting_strip_comments)

    source_text = (
        "module Main {\n"
        "use Utils;\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n"
    )
    module_index = {
        "Utils": "src/Utils.chpl",
        "Utils.chpl": "src/Utils.chpl",
        "Main": "main.chpl",
        "main.chpl": "main.chpl",
    }

    repository_service.chapel_adapter.parse_dependencies_only(
        "main.chpl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.chapel_adapter.parse_file(
        "main.chpl",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_chapel_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_chapel_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_chapel_primitives.strip_comments(
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "proc helper() { return 1; }\n"
        "}\n",
    )

    first_result = repository_chapel_primitives.iter_symbol_entries(
        "",
        file_path="src/Main.chpl",
        stripped_text=stripped_text,
        module_name="Main",
    )
    first_cache_info = (
        repository_chapel_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_chapel_primitives.iter_symbol_entries(
        "",
        file_path="src/Main.chpl",
        stripped_text=stripped_text,
        module_name="Main",
    )
    second_cache_info = (
        repository_chapel_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_build_module_index_reuses_preloaded_text_for_chapel_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "chapel-module-index-repo"
    (repo_path / "src").mkdir(parents=True)
    source_file = repo_path / "src" / "Main.chpl"
    source_file.write_text(
        "module Main {\n"
        "proc run() { return helper(); }\n"
        "}\n",
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
        ["src/Main.chpl"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert module_index["Main"] == "src/Main.chpl"
    assert "Main.run" not in module_index


def test_chapel_strip_comments_returns_original_text_when_no_comment_markers() -> None:
    source_text = (
        "module Main {\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n"
    )

    assert repository_chapel_primitives.strip_comments(source_text) == source_text


def test_chapel_strip_comments_preserve_strings_and_line_structure() -> None:
    source_text = (
        'module Main {\n'
        'proc run() {\n'
        '  var url = "https://example.com//kept"; // remove this comment\n'
        "  /* block\n"
        "     comment */\n"
        "  return url;\n"
        "}\n"
        "}\n"
    )

    stripped_text = repository_chapel_primitives.strip_comments(source_text)

    assert '"https://example.com//kept"' in stripped_text
    assert "remove this comment" not in stripped_text
    assert "block" not in stripped_text
    assert stripped_text.count("\n") == source_text.count("\n")
    assert "return url;" in stripped_text


def test_chapel_parse_use_import_statements_skips_sources_without_import_keywords() -> None:
    source_text = (
        "module Main {\n"
        "proc run() {\n"
        "  return helper();\n"
        "}\n"
        "}\n"
    )

    assert (
        repository_chapel_primitives.parse_use_import_statements(
            source_text,
            stripped_text=source_text,
        )
        == ()
    )


def test_chapel_parse_use_import_statements_preserve_line_numbers() -> None:
    source_text = (
        "module Main {\n"
        "use Alpha;\n"
        "\n"
        "import Beta as B;\n"
        "use Gamma only Delta;\n"
        "}\n"
    )

    assert repository_chapel_primitives.parse_use_import_statements(
        source_text,
        stripped_text=source_text,
    ) == (
        ("use", "Alpha", None, 2),
        ("import", "Beta", "B", 4),
        ("use", "Gamma", None, 5),
    )


def test_eiffel_adapter_module_aliases_include_class_and_feature_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/application.e" in aliases
    assert "src/application" in aliases
    assert "application" in aliases
    assert "APPLICATION" in aliases
    assert "make" in aliases
    assert "APPLICATION.make" in aliases


def test_eiffel_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-inline-text-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n"
    )
    file_path = repo_path / "src" / "application.e"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.eiffel_adapter.strip_comments(source_text),
    )

    assert "src/application.e" in aliases
    assert "APPLICATION" in aliases
    assert "make" in aliases
    assert "APPLICATION.make" in aliases


def test_eiffel_adapter_module_aliases_can_skip_feature_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "eiffel-module-only-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n"
    )
    (repo_path / "src" / "application.e").write_text(source_text, encoding="utf-8")

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.eiffel_adapter.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "src/application.e" in aliases
    assert "src/application" in aliases
    assert "application" in aliases
    assert "APPLICATION" in aliases
    assert "make" not in aliases
    assert "APPLICATION.make" not in aliases


def test_eiffel_module_aliases_skip_symbol_collection_in_module_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-module-only-fast-path-repo"
    (repo_path / "src").mkdir(parents=True)
    source_text = (
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n"
    )
    (repo_path / "src" / "application.e").write_text(source_text, encoding="utf-8")

    def _unexpected_collect_symbols(**kwargs):
        raise AssertionError("module-only eiffel aliases should skip symbol collection")

    monkeypatch.setattr(
        repository_eiffel_analysis_support,
        "_collect_symbols",
        _unexpected_collect_symbols,
    )

    aliases = repository_service.eiffel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/application.e",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_service.eiffel_adapter.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "src/application.e" in aliases
    assert "src/application" in aliases
    assert "application" in aliases
    assert "APPLICATION" in aliases
    assert "make" not in aliases


def test_raku_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-alias-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() { }\nclass Builder { }\n",
        encoding="utf-8",
    )

    aliases = repository_service.raku_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="lib/Demo/Helper.rakumod",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "lib/Demo/Helper.rakumod" in aliases
    assert "lib/Demo/Helper" in aliases
    assert "Demo::Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "render-json" in aliases
    assert "Builder" in aliases
    assert "Demo::Helper::render-json" in aliases


def test_raku_strip_comments_reuses_cached_results() -> None:
    source_text = "use Demo::Helper; # comment\nsub render-json() { }\n"

    repository_raku_primitives.strip_comments.cache_clear()
    first_result = repository_raku_primitives.strip_comments(source_text)
    second_result = repository_raku_primitives.strip_comments(source_text)
    cache_info = repository_raku_primitives.strip_comments.cache_info()

    assert second_result == first_result
    assert cache_info.hits >= 1
    assert cache_info.misses == 1


def test_agda_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-alias-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    aliases = repository_service.agda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Data/Helper.agda",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Data/Helper.agda" in aliases
    assert "src/Data/Helper" in aliases
    assert "src.Data.Helper" in aliases
    assert "Data.Helper" in aliases
    assert "Data/Helper" in aliases
    assert "Helper" in aliases
    assert "helper" in aliases
    assert "Data.Helper.helper" in aliases


def test_agda_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "agda-inline-text-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    source_text = (
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n"
    )
    file_path = repo_path / "src" / "Data" / "Helper.agda"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.agda_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Data/Helper.agda",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_agda_primitives.strip_comments(source_text),
    )

    assert "Data.Helper" in aliases
    assert "helper" in aliases
    assert "Data.Helper.helper" in aliases


def test_build_module_index_skips_dart_package_scan_when_no_dart_files_are_selected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "agda-module-index-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "pkgs" / "app").mkdir(parents=True)
    (repo_path / "pkgs" / "app" / "pubspec.yaml").write_text(
        "name: app\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )

    def _unexpected_build_workspace_dart_package_index(
        _root_path: Path,
    ) -> dict[str, tuple[str, ...]]:
        raise AssertionError("dart package scan should be skipped when no Dart files are selected")

    monkeypatch.setattr(
        repository_config,
        "_build_workspace_dart_package_index",
        _unexpected_build_workspace_dart_package_index,
    )

    module_index = repository_service._build_module_index(
        ["src/Data/Helper.agda"],
        root_path=repo_path,
    )

    assert module_index["Data.Helper"] == "src/Data/Helper.agda"


def test_agda_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_agda_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(repository_agda_primitives, "strip_comments", counting_strip_comments)
    monkeypatch.setattr(repository_agda_analysis_support, "strip_comments", counting_strip_comments)

    source_text = (
        "module Data.Helper where\n\n"
        "open import Data.Unit\n\n"
        "helper : Set\n"
        "helper = Set\n"
    )
    module_index = {
        "Data.Unit": "src/Data/Unit.agda",
        "src/Data/Unit.agda": "src/Data/Unit.agda",
    }

    repository_service.agda_adapter.parse_dependencies_only(
        "src/Data/Helper.agda",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.agda_adapter.parse_file(
        "src/Data/Helper.agda",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_agda_strip_comments_fast_path_preserves_line_structure_for_line_comments() -> None:
    source_text = (
        "-- module Fake where\n"
        "module Data.Helper where -- trailing comment\n"
        "helper : Set\n"
        "helper = Set -- trailing value\n"
    )

    stripped_text = repository_agda_primitives.strip_comments(source_text)

    assert stripped_text.count("\n") == source_text.count("\n")
    assert "module Data.Helper where" in stripped_text
    assert "helper = Set " in stripped_text
    assert "--" not in stripped_text


def test_agda_strip_comments_keeps_double_dash_inside_strings() -> None:
    source_text = (
        'message = "-- not a comment"\n'
        "module Data.Helper where\n"
    )

    stripped_text = repository_agda_primitives.strip_comments(source_text)

    assert stripped_text == source_text


def test_idris_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-alias-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "record Builder where\n"
        "  constructor MkBuilder\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )

    aliases = repository_service.idris_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Demo/Helper.idr",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Demo/Helper.idr" in aliases
    assert "src/Demo/Helper" in aliases
    assert "src.Demo.Helper" in aliases
    assert "Demo.Helper" in aliases
    assert "Demo/Helper" in aliases
    assert "Helper" in aliases
    assert "Builder" in aliases
    assert "renderJson" in aliases
    assert "Demo.Helper.renderJson" in aliases


def test_nushell_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-alias-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.nushell_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="modules/helper.nu",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "modules/helper.nu" in aliases
    assert "modules/helper" in aliases
    assert "helper" in aliases
    assert "render-json" in aliases
    assert "helper render-json" in aliases


def test_fish_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-alias-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper --description 'render data'\n"
        "    render_json\n"
        "end\n",
        encoding="utf-8",
    )

    aliases = repository_service.fish_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="functions/helper.fish",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "functions/helper.fish" in aliases
    assert "functions/helper" in aliases
    assert "functions.helper" in aliases
    assert "helper" in aliases
    assert "helper.helper" in aliases


def test_batchfile_adapter_module_aliases_include_script_and_label_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "batchfile-alias-repo"
    (repo_path / "scripts").mkdir(parents=True)
    (repo_path / "scripts" / "build.bat").write_text(
        "@echo off\n"
        ":setup\n"
        "call :done\n"
        ":done\n"
        "exit /b 0\n",
        encoding="utf-8",
    )

    aliases = repository_service.batchfile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/build.bat",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/build.bat" in aliases
    assert "scripts/build" in aliases
    assert "scripts.build" in aliases
    assert "build" in aliases
    assert "setup" in aliases
    assert "done" in aliases


def test_makefile_adapter_module_aliases_include_makefile_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "makefile-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Makefile").write_text(
        "build: clean\n"
        "\t$(MAKE) helper\n"
        "clean:\n"
        "\t@echo clean\n",
        encoding="utf-8",
    )

    aliases = repository_service.makefile_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Makefile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Makefile" in aliases
    assert "build" in aliases
    assert "clean" in aliases


def test_cmake_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "project(acme)\n"
        "add_library(acme_core INTERFACE)\n"
        "function(configure_runtime target)\n"
        "endfunction()\n",
        encoding="utf-8",
    )

    aliases = repository_service.cmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="CMakeLists.txt",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "CMakeLists.txt" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "configure_runtime" in aliases


def test_meson_adapter_module_aliases_include_project_and_target_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "meson.build").write_text(
        "project('acme', 'c')\n"
        "library('acme_core', 'src/core.c')\n"
        "custom_target('codegen')\n",
        encoding="utf-8",
    )

    aliases = repository_service.meson_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="meson.build",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "meson.build" in aliases
    assert "acme" in aliases
    assert "acme_core" in aliases
    assert "codegen" in aliases


def test_just_adapter_module_aliases_include_recipe_and_alias_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "just-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "Justfile").write_text(
        "alias ci := check\n"
        "check:\n"
        "  just build\n"
        "build:\n"
        "  echo build\n",
        encoding="utf-8",
    )

    aliases = repository_service.just_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Justfile",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Justfile" in aliases
    assert "ci" in aliases
    assert "check" in aliases
    assert "build" in aliases


def test_qmake_adapter_module_aliases_include_target_and_subdir_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qmake-alias-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "project.pro").write_text(
        "TEMPLATE = subdirs\n"
        "TARGET = acme\n"
        "SUBDIRS += core app\n"
        "app.depends = core\n",
        encoding="utf-8",
    )

    aliases = repository_service.qmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.pro",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "project.pro" in aliases
    assert "acme" in aliases
    assert "core" in aliases
    assert "app" in aliases


def test_qmake_adapter_module_aliases_use_supplied_text_without_rereading_target_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "qmake-alias-text-repo"
    repo_path.mkdir(parents=True)
    source_text = (
        "TEMPLATE = subdirs\n"
        "TARGET = acme\n"
        "SUBDIRS += core app\n"
        "app.depends = core\n"
    )
    target_file = repo_path / "project.pro"
    target_file.write_text(source_text, encoding="utf-8")
    original_read_text = Path.read_text

    def _guarded_read_text(self: Path, *args, **kwargs) -> str:
        if self == target_file:
            raise AssertionError("supplied qmake text should bypass rereading the target file")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guarded_read_text)

    aliases = repository_service.qmake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="project.pro",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "project.pro" in aliases
    assert "acme" in aliases
    assert "core" in aliases
    assert "app" in aliases


def test_qml_adapter_module_aliases_include_qmldir_module_component_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "qml-alias-repo"
    (repo_path / "controls").mkdir(parents=True)
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 controls/Button.qml\n",
        encoding="utf-8",
    )
    (repo_path / "controls" / "Button.qml").write_text(
        "Rectangle {\n"
        "    id: buttonRoot\n"
        "    function press() {\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.qml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="controls/Button.qml",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "controls/Button.qml" in aliases
    assert "Button" in aliases
    assert "Demo.Controls.Button" in aliases
    assert "buttonRoot" in aliases
    assert "press" in aliases


def test_qml_adapter_module_aliases_use_supplied_text_without_rereading_target_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "qml-alias-text-repo"
    (repo_path / "controls").mkdir(parents=True)
    source_text = (
        "Rectangle {\n"
        "    id: buttonRoot\n"
        "    function press() {\n"
        "    }\n"
        "}\n"
    )
    (repo_path / "qmldir").write_text(
        "module Demo.Controls\n"
        "Button 1.0 controls/Button.qml\n",
        encoding="utf-8",
    )
    target_file = repo_path / "controls" / "Button.qml"
    target_file.write_text(source_text, encoding="utf-8")
    original_read_text = Path.read_text

    def _guarded_read_text(self: Path, *args, **kwargs) -> str:
        if self == target_file:
            raise AssertionError("supplied QML text should bypass rereading the target file")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guarded_read_text)

    aliases = repository_service.qml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="controls/Button.qml",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "controls/Button.qml" in aliases
    assert "Button" in aliases
    assert "Demo.Controls.Button" in aliases
    assert "buttonRoot" in aliases
    assert "press" in aliases


def test_bitbake_adapter_module_aliases_include_recipe_class_and_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-alias-repo"
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        'require ../base/base.inc\n'
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python image_do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "recipes-core/images/core-image-minimal" in aliases
    assert "recipes-core.images.core-image-minimal" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_bitbake_adapter_module_aliases_use_supplied_text_without_rereading(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-inline-text-repo"
    recipe_text = (
        'DESCRIPTION = "demo"\n'
        "python do_install() {\n"
        "    pass\n"
        "}\n"
    )

    aliases = repository_service.bitbake_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="recipes-core/images/core-image-minimal.bb",
        stable_identifier=repository_service._stable_identifier,
        text=recipe_text,
    )

    assert "recipes-core/images/core-image-minimal.bb" in aliases
    assert "core-image-minimal" in aliases
    assert "recipe:core-image-minimal" in aliases
    assert "do_install" in aliases


def test_cue_adapter_module_aliases_include_module_prefix_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cue-alias-repo"
    (repo_path / "cue.mod").mkdir(parents=True)
    (repo_path / "pkg" / "schema").mkdir(parents=True)
    (repo_path / "cue.mod" / "module.cue").write_text(
        'module: "example.com/demo"\n',
        encoding="utf-8",
    )
    (repo_path / "pkg" / "schema" / "schema.cue").write_text(
        "package schema\n\n#Answer: 42\nconfig: #Answer\n",
        encoding="utf-8",
    )

    aliases = repository_service.cue_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="pkg/schema/schema.cue",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "pkg/schema/schema.cue" in aliases
    assert "pkg/schema" in aliases
    assert "example.com/demo/pkg/schema" in aliases
    assert "schema" in aliases
    assert "#Answer" in aliases
    assert "schema.#Answer" in aliases


def test_factor_adapter_module_aliases_include_vocabulary_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "factor-alias-repo"
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "math" / "math.factor").write_text(
        "IN: math\n\n: square ( n -- n ) dup * ;\n",
        encoding="utf-8",
    )

    aliases = repository_service.factor_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="math/math.factor",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "math/math.factor" in aliases
    assert "math/math" in aliases
    assert "math" in aliases
    assert "square" in aliases
    assert "math.square" in aliases


def test_haxe_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "haxe-alias-repo"
    (repo_path / "src" / "demo").mkdir(parents=True)
    (repo_path / "src" / "demo" / "Helper.hx").write_text(
        "package demo;\n"
        "\n"
        "class Helper {\n"
        "    public static function renderJson():String {\n"
        '        return "{}";\n'
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.haxe_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/demo/Helper.hx",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/demo/Helper.hx" in aliases
    assert "src/demo/Helper" in aliases
    assert "src.demo.Helper" in aliases
    assert "demo.Helper" in aliases
    assert "Helper" in aliases
    assert "renderJson" in aliases
    assert "demo.renderJson" not in aliases
    assert "demo.Helper.renderJson" in aliases


def test_glsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "noise.glsl").write_text(
        "struct Params {\n"
        "  float gain;\n"
        "};\n"
        "\n"
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.glsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/noise.glsl",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/noise.glsl" in aliases
    assert "shaders/noise" in aliases
    assert "noise" in aliases
    assert "Params" in aliases


def test_hlsl_adapter_module_aliases_include_shader_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-alias-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "shaders" / "lighting.hlsli").write_text(
        "struct LightingParams {\n"
        "  float intensity;\n"
        "};\n"
        "\n"
        "float4 ShadeMain(float3 normal) : SV_Target {\n"
        "  return float4(normal, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hlsl_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="shaders/lighting.hlsli",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "shaders/lighting.hlsli" in aliases
    assert "shaders/lighting" in aliases
    assert "lighting" in aliases
    assert "LightingParams" in aliases
    assert "ShadeMain" in aliases


def test_hack_adapter_module_aliases_include_namespace_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hack-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Ref.php").write_text(
        "<?hh\n"
        "namespace Demo;\n"
        "\n"
        "final class Ref<T> {}\n",
        encoding="utf-8",
    )

    aliases = repository_service.hack_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Ref.php",
    )

    assert "src/Ref.php" in aliases
    assert "src/Ref" in aliases
    assert "src.Ref" in aliases
    assert "Ref" in aliases
    assert "Demo\\Ref" in aliases


def test_odin_adapter_module_aliases_include_package_and_declared_symbols(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-alias-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "common" / "helper.odin").write_text(
        "package common\n"
        "\n"
        "Config :: struct {\n"
        "    value: int,\n"
        "}\n"
        "\n"
        "helper :: proc() -> int {\n"
        "    return 1\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.odin_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/common/helper.odin",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/common/helper.odin" in aliases
    assert "src/common/helper" in aliases
    assert "helper" in aliases
    assert "src:common" in aliases
    assert "common" in aliases
    assert "common.Config" in aliases
    assert "common.helper" in aliases


def test_autohotkey_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autohotkey-alias-repo"
    (repo_path / "Lib").mkdir(parents=True)
    (repo_path / "Lib" / "Helper.ahk").write_text(
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.autohotkey_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Lib/Helper.ahk",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Lib/Helper.ahk" in aliases
    assert "Lib/Helper" in aliases
    assert "Lib.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_autohotkey_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "autohotkey-inline-text-repo"
    (repo_path / "Lib").mkdir(parents=True)
    source_text = (
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n"
    )
    file_path = repo_path / "Lib" / "Helper.ahk"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.autohotkey_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Lib/Helper.ahk",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_autohotkey_primitives.strip_comments(source_text),
    )

    assert "Lib/Helper.ahk" in aliases
    assert "Lib/Helper" in aliases
    assert "Lib.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_autohotkey_strip_comments_returns_original_text_when_no_comment_markers() -> None:
    source_text = (
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n"
    )

    assert repository_autohotkey_primitives.strip_comments(source_text) == source_text


def test_autohotkey_strip_comments_reuse_cached_results() -> None:
    repository_autohotkey_primitives._strip_comments_cached.cache_clear()
    source_text = (
        "; comment\n"
        "#include <Helper>\n"
        "RenderJson(value) {\n"
        "    return value\n"
        "}\n"
    )

    first_result = repository_autohotkey_primitives.strip_comments(source_text)
    first_cache_info = repository_autohotkey_primitives._strip_comments_cached.cache_info()
    second_result = repository_autohotkey_primitives.strip_comments(source_text)
    second_cache_info = repository_autohotkey_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_build_module_index_reuses_preloaded_text_for_autohotkey_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "autohotkey-module-index-repo"
    (repo_path / "Lib").mkdir(parents=True)
    source_file = repo_path / "Lib" / "Helper.ahk"
    source_file.write_text(
        "class Helper {\n"
        "    RenderJson(value) {\n"
        "        return value\n"
        "    }\n"
        "}\n",
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
        ["Lib/Helper.ahk"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert module_index["Helper.RenderJson"] == "Lib/Helper.ahk"


def test_autoit_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-alias-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    aliases = repository_service.autoit_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Includes/Helper.au3",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Includes/Helper.au3" in aliases
    assert "Includes/Helper" in aliases
    assert "Includes.Helper" in aliases
    assert "Helper" in aliases
    assert "RenderJson" in aliases
    assert "Helper.RenderJson" in aliases


def test_autoit_adapter_parse_file_resolves_include_dependencies_and_call_references(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "autoit-parse-repo"
    (repo_path / "Includes").mkdir(parents=True)
    (repo_path / "Includes" / "Helper.au3").write_text(
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n",
        encoding="utf-8",
    )
    main_path = repo_path / "Main.au3"
    main_path.write_text(
        '#include "Includes/Helper.au3"\n'
        "Func Main()\n"
        "    Return Helper.RenderJson(\"ok\")\n"
        "EndFunc\n",
        encoding="utf-8",
    )

    module_index = repository_service._build_module_index(
        ["Includes/Helper.au3", "Main.au3"],
        root_path=repo_path,
    )
    text = main_path.read_text(encoding="utf-8")
    dependencies = repository_service.autoit_adapter.parse_dependencies_only(
        "Main.au3",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    symbols, _, references = repository_service.autoit_adapter.parse_file(
        "Main.au3",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Includes/Helper.au3" for dependency in dependencies)
    assert any(symbol.symbol_name == "Main" for symbol in symbols)
    assert any(
        reference.target_file == "Includes/Helper.au3"
        and reference.target_names == ("RenderJson",)
        for reference in references
    )


def test_autoit_adapter_iter_symbol_entries_preserve_line_numbers_after_block_comments() -> None:
    entries = repository_service.autoit_adapter.iter_symbol_entries(
        "#cs\n"
        "comment block\n"
        "#ce\n"
        "Func RenderJson($value)\n"
        "    Return $value\n"
        "EndFunc\n"
    )

    assert ("RenderJson", "function", 4) in entries


def test_squirrel_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-alias-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    (repo_path / "scripts" / "vscripts" / "ppmod.nut").write_text(
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n",
        encoding="utf-8",
    )

    aliases = repository_service.squirrel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/vscripts/ppmod.nut",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "scripts/vscripts/ppmod.nut" in aliases
    assert "scripts/vscripts/ppmod" in aliases
    assert "scripts.vscripts.ppmod" in aliases
    assert "ppmod" in aliases


def test_squirrel_adapter_module_aliases_accept_preloaded_text_without_file_read(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "squirrel-preloaded-text-repo"
    (repo_path / "scripts" / "vscripts").mkdir(parents=True)
    file_text = (
        "::ppmod <- {\n"
        "  run = function () {\n"
        '    return "ok";\n'
        "  }\n"
        "};\n"
    )
    file_path = repo_path / "scripts" / "vscripts" / "ppmod.nut"
    file_path.write_text(file_text, encoding="utf-8")
    file_path.unlink()

    aliases = repository_service.squirrel_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="scripts/vscripts/ppmod.nut",
        stable_identifier=repository_service._stable_identifier,
        text=file_text,
    )

    assert "scripts/vscripts/ppmod.nut" in aliases
    assert "scripts/vscripts/ppmod" in aliases
    assert "scripts.vscripts.ppmod" in aliases
    assert "ppmod" in aliases
