from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from tests.csv_invariant_helpers import (
    TEST_FILES,
    discover_csv_paths,
    identifier_preservation_issues,
    load_regression_csv,
    register_csv_and_query_count,
    reset_runtime_state,
    temporary_registry_dir,
    unique_auth,
)


def test_csv_regression_corpus_defaults_to_root_files_only() -> None:
    default_paths = discover_csv_paths(include_processed_variants=False)
    full_paths = discover_csv_paths(include_processed_variants=True)

    assert TEST_FILES / "Backlog.csv" in default_paths
    assert all(path.parent == TEST_FILES for path in default_paths)
    assert any(path.parent == TEST_FILES / "Processed" for path in full_paths)
    assert len(full_paths) > len(default_paths)


def test_root_csv_regression_corpus_is_stable_across_repeated_loads() -> None:
    for path in discover_csv_paths(include_processed_variants=False):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        first = load_regression_csv(text)
        second = load_regression_csv(text)

        assert first.columns == second.columns, path.name
        assert first.schema_columns == second.schema_columns, path.name
        assert first.schema_hash == second.schema_hash, path.name
        assert first.row_order_hash == second.row_order_hash, path.name
        assert first.row_count == second.row_count, path.name

        issues = identifier_preservation_issues(text, first)
        assert issues == [], f"{path.name}: {issues}"


@pytest.mark.anyio
async def test_root_csv_regression_corpus_registers_or_fails_explicitly() -> None:
    with temporary_registry_dir() as tmp_dir:
        registry_dir = Path(tmp_dir) / "registry"
        await reset_runtime_state(registry_dir)

        for path in discover_csv_paths(include_processed_variants=False):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            loaded = load_regression_csv(text)

            try:
                registration = await register_csv_and_query_count(
                    csv_text=text,
                    source_name=f"Regression::{path.stem}",
                    auth=unique_auth("csv_regression"),
                )
            except HTTPException as exc:
                if loaded.row_count == 0:
                    assert exc.status_code == 400, path.name
                    assert exc.detail["error"]["code"] == "empty_source", path.name
                    continue
                raise

            assert registration.loader_count == loaded.row_count, path.name
            assert registration.query_count == loaded.row_count, path.name
            assert registration.schema_hash == loaded.schema_hash, path.name
            assert registration.registered_schema_hash == loaded.schema_hash, path.name
