from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from apps.api_server.services.repository_intelligence_adapters import (
    lisp_analysis_support as repository_lisp_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    lisp_support as repository_lisp_support,
)


def test_lisp_tokenize_form_reuses_cached_result() -> None:
    repository_lisp_support._tokenize_form.cache_clear()
    form_text = '(defun run () (helper "value"))'

    first_result = repository_lisp_support._tokenize_form(form_text)
    first_cache_info = repository_lisp_support._tokenize_form.cache_info()
    second_result = repository_lisp_support._tokenize_form(form_text)
    second_cache_info = repository_lisp_support._tokenize_form.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_lisp_extract_top_level_forms_reuses_cached_result() -> None:
    repository_lisp_support._extract_top_level_forms.cache_clear()
    source_text = (
        "(defpackage :demo (:use :cl))\n"
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (helper))\n"
    )

    first_result = repository_lisp_support._extract_top_level_forms(source_text)
    first_cache_info = repository_lisp_support._extract_top_level_forms.cache_info()
    second_result = repository_lisp_support._extract_top_level_forms(source_text)
    second_cache_info = repository_lisp_support._extract_top_level_forms.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_lisp_top_level_form_records_reuse_cached_result() -> None:
    repository_lisp_analysis_support._top_level_form_records.cache_clear()
    source_text = (
        "(defpackage :demo (:use :cl))\n"
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (helper))\n"
    )

    first_result = repository_lisp_analysis_support._top_level_form_records(source_text)
    first_cache_info = repository_lisp_analysis_support._top_level_form_records.cache_info()
    second_result = repository_lisp_analysis_support._top_level_form_records(source_text)
    second_cache_info = repository_lisp_analysis_support._top_level_form_records.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_lisp_candidate_import_keys_reuse_cached_result() -> None:
    repository_lisp_analysis_support._candidate_import_keys.cache_clear()

    first_result = repository_lisp_analysis_support._candidate_import_keys(
        "util",
        current_file="src/demo.lisp",
    )
    first_cache_info = repository_lisp_analysis_support._candidate_import_keys.cache_info()
    second_result = repository_lisp_analysis_support._candidate_import_keys(
        "util",
        current_file="src/demo.lisp",
    )
    second_cache_info = repository_lisp_analysis_support._candidate_import_keys.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_lisp_module_aliases_for_path_stays_stable_with_cached_form_records(
    tmp_path: Path,
) -> None:
    repository_lisp_analysis_support._top_level_form_records.cache_clear()
    repository_lisp_analysis_support._current_package_name.cache_clear()
    file_path = "src/demo.lisp"
    source_text = (
        "(defpackage :demo (:use :cl))\n"
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (helper))\n"
    )
    target_path = tmp_path / file_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(source_text, encoding="utf-8")

    aliases = repository_lisp_analysis_support.module_aliases_for_path(
        root_path=tmp_path,
        file_path=file_path,
        stable_identifier=lambda prefix, payload: f"{prefix}:{payload['file_path']}",
    )

    assert "demo" in aliases
    assert "demo.run" in aliases


def test_lisp_parse_file_reuses_cached_line_offsets_for_references() -> None:
    repository_lisp_analysis_support._line_start_offsets.cache_clear()
    source_text = (
        "(defpackage :demo (:use :cl :util))\n"
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (util:helper)\n"
        "  (util:helper))\n"
    )

    _symbols, _dependencies, references = repository_lisp_analysis_support.parse_file(
        "src/demo.lisp",
        source_text,
        {"util": "src/util.lisp", "util:helper": "src/util.lisp"},
        stable_identifier=lambda prefix, payload: f"{prefix}:{payload}",
        normalize_repository_relative_path=lambda value: value.strip().lstrip("./"),
        resolve_suffix_match=lambda **_kwargs: None,
    )
    cache_info = repository_lisp_analysis_support._line_start_offsets.cache_info()

    assert references
    assert cache_info.hits >= 1
    assert cache_info.misses == 1


def test_lisp_parse_file_caches_repeated_reference_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = (
        "(defpackage :demo (:use :cl :util))\n"
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (util:helper)\n"
        "  (util:helper)\n"
        "  (util:helper))\n"
    )
    resolved_reference_names: list[str] = []
    original_resolve_reference_binding = (
        repository_lisp_analysis_support._resolve_reference_binding
    )

    def _counting_resolve_reference_binding(**kwargs: Any) -> tuple[str | None, tuple[str, ...]]:
        resolved_reference_names.append(str(kwargs["reference_name"]))
        return original_resolve_reference_binding(**kwargs)

    monkeypatch.setattr(
        repository_lisp_analysis_support,
        "_resolve_reference_binding",
        _counting_resolve_reference_binding,
    )

    _symbols, _dependencies, references = repository_lisp_analysis_support.parse_file(
        "src/demo.lisp",
        source_text,
        {
            "util": "src/util.lisp",
            "util:helper": "src/util.lisp",
        },
        stable_identifier=lambda prefix, payload: f"{prefix}:{payload}",
        normalize_repository_relative_path=lambda value: value.strip().lstrip("./"),
        resolve_suffix_match=lambda **_kwargs: None,
    )

    assert references
    assert resolved_reference_names.count("util:helper") == 1


def test_lisp_parse_file_caches_repeated_package_import_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_text = (
        "(in-package :demo)\n"
        "(defun run ()\n"
        "  (util:alpha)\n"
        "  (util:beta)\n"
        "  (util:gamma))\n"
    )
    resolved_import_targets: list[str] = []
    original_resolve_import = repository_lisp_analysis_support.resolve_import

    def _counting_resolve_import(**kwargs: Any) -> str | None:
        resolved_import_targets.append(str(kwargs["import_target"]))
        return original_resolve_import(**kwargs)

    monkeypatch.setattr(
        repository_lisp_analysis_support,
        "resolve_import",
        _counting_resolve_import,
    )

    _symbols, _dependencies, references = repository_lisp_analysis_support.parse_file(
        "src/demo.lisp",
        source_text,
        {
            "util": "src/util.lisp",
        },
        stable_identifier=lambda prefix, payload: f"{prefix}:{payload}",
        normalize_repository_relative_path=lambda value: value.strip().lstrip("./"),
        resolve_suffix_match=lambda **_kwargs: None,
    )

    assert references
    assert resolved_import_targets.count("util") == 1
