from __future__ import annotations

from apps.api_server.services import (
    data_map_matching,
    data_map_matching_common,
    data_map_matching_schema_rank,
    data_map_matching_similarity,
)


def test_data_map_matching_wrapper_reexports_common_helpers() -> None:
    assert data_map_matching._normalize is data_map_matching_common._normalize
    assert (
        data_map_matching.prepare_schema_catalog is data_map_matching_common.prepare_schema_catalog
    )
    assert data_map_matching.PreparedSchemaCatalog is data_map_matching_common.PreparedSchemaCatalog


def test_data_map_matching_wrapper_reexports_schema_rank_helpers() -> None:
    assert (
        data_map_matching.rank_schema_dimension_columns
        is data_map_matching_schema_rank.rank_schema_dimension_columns
    )
    assert (
        data_map_matching.rank_schema_table_matches
        is data_map_matching_schema_rank.rank_schema_table_matches
    )
    assert (
        data_map_matching._query_term_specificity_weights
        is data_map_matching_schema_rank._query_term_specificity_weights
    )


def test_data_map_matching_wrapper_reexports_similarity_helpers() -> None:
    assert (
        data_map_matching._semantic_similarity is data_map_matching_similarity._semantic_similarity
    )
    assert (
        data_map_matching._detect_derived_relationships
        is data_map_matching_similarity._detect_derived_relationships
    )
    assert (
        data_map_matching._build_match_reasons is data_map_matching_similarity._build_match_reasons
    )
