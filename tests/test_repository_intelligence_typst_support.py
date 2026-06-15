from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    typst_analysis_support as repository_typst_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    typst_primitives as repository_typst_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe_docs_support import (
    _typst_profile_hints_from_candidates,
)


def test_typst_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "typst-inline-text-repo"
    (repo_path / "docs").mkdir(parents=True)
    source_text = "#let add(x, y) = x + y\n#let scale(x) = x * 2\n"
    file_path = repo_path / "docs" / "math.typ"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    stripped_text = repository_typst_primitives.strip_comments(source_text)
    symbol_entries = repository_typst_primitives.iter_symbol_entries(
        source_text,
        stripped_text=stripped_text,
    )
    aliases = repository_service.typst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/math.typ",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=stripped_text,
        symbol_entries=symbol_entries,
    )

    assert "docs/math.typ" in aliases
    assert "docs.math" in aliases
    assert "add" in aliases
    assert "scale" in aliases


def test_typst_adapter_module_aliases_can_skip_symbol_aliases(tmp_path: Path) -> None:
    repo_path = tmp_path / "typst-module-only-alias-repo"
    (repo_path / "docs").mkdir(parents=True)
    source_text = "#let add(x, y) = x + y\n#let scale(x) = x * 2\n"
    (repo_path / "docs" / "math.typ").write_text(source_text, encoding="utf-8")

    aliases = repository_service.typst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/math.typ",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_typst_primitives.strip_comments(source_text),
        include_symbol_aliases=False,
    )

    assert "docs/math.typ" in aliases
    assert "docs.math" in aliases
    assert "math" in aliases
    assert "add" not in aliases
    assert "scale" not in aliases


def test_typst_module_aliases_path_only_mode_skips_text_loading_and_symbol_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "typst-path-only-fast-path-repo"
    (repo_path / "docs").mkdir(parents=True)
    file_path = repo_path / "docs" / "math.typ"
    file_path.write_text("#let add(x, y) = x + y\n#let scale(x) = x * 2\n", encoding="utf-8")

    def _unexpected_read_text(self: Path, *args: object, **kwargs: object) -> str:
        raise AssertionError(f"path-only typst aliases should not reread {self}")

    def _unexpected_iter_symbol_entries(*args: object, **kwargs: object) -> object:
        raise AssertionError("path-only typst aliases should skip symbol scans")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)
    monkeypatch.setattr(
        repository_typst_primitives,
        "iter_symbol_entries",
        _unexpected_iter_symbol_entries,
    )

    aliases = repository_service.typst_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="docs/math.typ",
        stable_identifier=repository_service._stable_identifier,
        include_symbol_aliases=False,
    )

    assert "docs/math.typ" in aliases
    assert "docs.math" in aliases
    assert "math" in aliases
    assert "add" not in aliases
    assert "scale" not in aliases


def test_typst_adapter_reuses_single_stripped_text_per_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_strip_comments = repository_typst_primitives.strip_comments
    strip_call_count = {"value": 0}

    def counting_strip_comments(text: str) -> str:
        strip_call_count["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_typst_primitives,
        "strip_comments",
        counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_typst_analysis_support,
        "strip_comments",
        counting_strip_comments,
    )

    source_text = (
        '#import "lib/math.typ": add\n'
        '#import "lib/math.typ" as math\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "  math.scale(3)\n"
        "}\n"
    )
    module_index = {
        "src/main.typ": "src/main.typ",
        "src/lib/math.typ": "src/lib/math.typ",
        "src/lib/math": "src/lib/math.typ",
        "lib/math.typ": "src/lib/math.typ",
        "math": "src/lib/math.typ",
    }

    repository_service.typst_adapter.parse_dependencies_only(
        "src/main.typ",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )
    repository_service.typst_adapter.parse_file(
        "src/main.typ",
        source_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_call_count["value"] == 2


def test_typst_profile_hints_reuse_loaded_text_per_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "typst-profile-hints-cache-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    math_path = repo_path / "content" / "math.typ"
    common_path = repo_path / "partials" / "common.typ"
    main_path = repo_path / "main.typ"
    config_path = repo_path / "typst.toml"
    math_path.write_text("#let add(x, y) = x + y\n", encoding="utf-8")
    common_path.write_text("#let title() = [Demo]\n", encoding="utf-8")
    main_path.write_text(
        '#import "content/math.typ": add\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    config_path.write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_counts: dict[Path, int] = {}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in {math_path, common_path, main_path, config_path}:
            read_counts[self] = read_counts.get(self, 0) + 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    entrypoints, roots, configs = _typst_profile_hints_from_candidates(
        repo_path,
        ["content/math.typ", "partials/common.typ", "main.typ", "typst.toml"],
    )

    assert "main.typ" in entrypoints
    assert "content" in roots
    assert "partials" in roots
    assert configs == {"typst.toml"}
    assert read_counts[math_path] <= 1
    assert read_counts[common_path] <= 1
    assert read_counts[main_path] <= 1
    assert read_counts[config_path] <= 1


def test_typst_profile_hints_skip_duplicate_source_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "typst-profile-hints-validation-repo"
    (repo_path / "content").mkdir(parents=True)
    (repo_path / "partials").mkdir(parents=True)
    (repo_path / "content" / "math.typ").write_text("#let add(x, y) = x + y\n", encoding="utf-8")
    (repo_path / "partials" / "common.typ").write_text(
        "#let title() = [Demo]\n",
        encoding="utf-8",
    )
    (repo_path / "main.typ").write_text(
        '#import "content/math.typ": add\n'
        '#include "partials/common.typ"\n'
        "#let render() = {\n"
        "  add(1, 2)\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "typst.toml").write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )

    original_is_probable_typst_source = repository_typst_primitives.is_probable_typst_source
    probable_source_calls = {"value": 0}

    def _counting_is_probable_typst_source(*args: object, **kwargs: object) -> bool:
        probable_source_calls["value"] += 1
        return original_is_probable_typst_source(*args, **kwargs)

    monkeypatch.setattr(
        repository_typst_primitives,
        "is_probable_typst_source",
        _counting_is_probable_typst_source,
    )
    monkeypatch.setattr(
        repository_typst_analysis_support,
        "is_probable_typst_source",
        _counting_is_probable_typst_source,
    )
    monkeypatch.setattr(
        repository_service.typst_adapter,
        "is_probable_typst_source",
        _counting_is_probable_typst_source,
    )

    _typst_profile_hints_from_candidates(
        repo_path,
        ["content/math.typ", "partials/common.typ", "main.typ", "typst.toml"],
    )

    assert probable_source_calls["value"] == 3


def test_typst_strip_comments_uses_bounded_cache() -> None:
    repository_typst_primitives.strip_comments.cache_clear()
    source_text = (
        "// heading comment\n"
        "#let render() = {\n"
        "  /* inline block */\n"
        "  [hello]\n"
        "}\n"
    )

    first = repository_typst_primitives.strip_comments(source_text)
    second = repository_typst_primitives.strip_comments(source_text)
    cache_info = repository_typst_primitives.strip_comments.cache_info()

    assert first == second
    assert cache_info.hits >= 1
    assert cache_info.maxsize == 512


def test_typst_reference_entries_reuse_cached_line_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_line_start_offsets = repository_typst_primitives.line_start_offsets
    call_count = {"value": 0}

    def counting_line_start_offsets(text: str) -> tuple[int, ...]:
        call_count["value"] += 1
        return original_line_start_offsets(text)

    monkeypatch.setattr(
        repository_typst_primitives,
        "line_start_offsets",
        counting_line_start_offsets,
    )

    source_text = (
        "#let render() = {\n"
        "  chart.draw(1)\n"
        "  helper(2)\n"
        "}\n"
    )
    stripped_text = repository_typst_primitives.strip_comments(source_text)

    entries = repository_typst_primitives.iter_reference_entries(
        source_text,
        stripped_text=stripped_text,
    )

    assert ("call", "chart", "draw", 2) in entries
    assert ("call", None, "helper", 3) in entries
    assert call_count["value"] == 1
