from __future__ import annotations

from apps.api_server.services import source_join_policy, source_join_scan_policy


def test_source_join_policy_reexports_scan_policy_helpers() -> None:
    schema_meta = {"columns": [{"name": f"c{i}"} for i in range(64)]}

    def _build_join_blocks(_schema_meta):  # type: ignore[no-untyped-def]
        return [{"name": "order_id"}] * 4

    assert source_join_policy._estimated_join_pair_cost(
        row_count=5_000,
        join_block_count=4,
        entry={"row_count": 2_000, "join_blocks": [{"name": "order_id"}] * 3},
    ) == source_join_scan_policy.estimated_join_pair_cost(
        row_count=5_000,
        join_block_count=4,
        entry={"row_count": 2_000, "join_blocks": [{"name": "order_id"}] * 3},
    )
    assert source_join_policy._should_use_scored_join_scan(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=12,
        existing_sources=[],
        build_join_blocks_fn=_build_join_blocks,
    ) == source_join_scan_policy.should_use_scored_join_scan(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=12,
        existing_sources=[],
        build_join_blocks_fn=_build_join_blocks,
    )
    assert source_join_policy._join_candidate_limit(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=24,
    ) == source_join_scan_policy.join_candidate_limit(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=24,
    )
    assert source_join_policy._join_candidate_min_score(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=24,
        build_join_blocks_fn=_build_join_blocks,
    ) == source_join_scan_policy.join_candidate_min_score(
        row_count=5_000,
        schema_meta=schema_meta,
        existing_total=24,
        build_join_blocks_fn=_build_join_blocks,
    )
