from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    sql as repository_sql_support,
)


def test_sql_line_start_offsets_reuse_cached_results() -> None:
    repository_sql_support._line_start_offsets.cache_clear()
    source_text = (
        "create table dbo.users (\n"
        "  id int,\n"
        "  name varchar(255)\n"
        ");\n"
    )

    first_result = repository_sql_support._line_start_offsets(source_text)
    first_cache_info = repository_sql_support._line_start_offsets.cache_info()
    second_result = repository_sql_support._line_start_offsets(source_text)
    second_cache_info = repository_sql_support._line_start_offsets.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_sql_reference_targets_preserve_line_numbers() -> None:
    source_text = (
        "create table dbo.users (\n"
        "  id int\n"
        ");\n"
        "select * from dbo.users;\n"
        "{{ ref('orders') }}\n"
        "call dbo.refresh_users();\n"
    )

    targets = repository_sql_support.iter_reference_targets(source_text)

    assert ("relation" in {kind for _, kind, _ in targets}) is True
    assert (4, "relation", "dbo.users") in targets
    assert (5, "dbt_ref", "orders") in targets
    assert (6, "call", "dbo.refresh_users") in targets
