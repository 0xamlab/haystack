from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    hcl_primitives as repository_hcl_primitives,
)


def test_hcl_strip_comments_reuse_cached_results() -> None:
    repository_hcl_primitives._strip_comments_cached.cache_clear()
    source_text = (
        'resource "aws_vpc" "main" {\n'
        "  # comment\n"
        '  cidr_block = "10.0.0.0/16"\n'
        "  /* block */\n"
        "}\n"
    )

    first_result = repository_hcl_primitives.strip_comments(source_text)
    first_cache_info = repository_hcl_primitives._strip_comments_cached.cache_info()
    second_result = repository_hcl_primitives.strip_comments(source_text)
    second_cache_info = repository_hcl_primitives._strip_comments_cached.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_hcl_line_offsets_reuse_cached_results() -> None:
    repository_hcl_primitives._line_offsets.cache_clear()
    source_text = (
        'resource "aws_vpc" "main" {\n'
        '  cidr_block = "10.0.0.0/16"\n'
        "}\n"
    )

    first_result = repository_hcl_primitives._line_offsets(source_text)
    first_cache_info = repository_hcl_primitives._line_offsets.cache_info()
    second_result = repository_hcl_primitives._line_offsets(source_text)
    second_cache_info = repository_hcl_primitives._line_offsets.cache_info()

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_hcl_block_entries_and_line_mappings_remain_stable() -> None:
    source_text = (
        'locals {\n'
        "  alpha = 1\n"
        "  beta = 2\n"
        "}\n"
        'module "network" {\n'
        '  source = "./modules/network"\n'
        "}\n"
    )

    block_entries = repository_hcl_primitives.iter_block_entries(source_text)

    assert len(block_entries) == 2
    assert block_entries[0].kind == "locals"
    assert block_entries[0].start_line == 1
    assert block_entries[0].end_line == 4
    assert repository_hcl_primitives.iter_local_assignments(block_entries[0]) == (
        ("alpha", 2),
        ("beta", 3),
    )
    assert repository_hcl_primitives.iter_module_source_statements(block_entries[1]) == (
        ("./modules/network", 6),
    )
