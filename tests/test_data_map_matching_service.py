from apps.api_server.services.data_map_matching import (
    _build_schema_query_term_entries,
    _detect_derived_relationships,
    _lexical_overlap_score,
    _query_term_specificity_weights,
    _semantic_similarity,
    prepare_schema_catalog,
    rank_schema_dimension_columns,
    rank_schema_metric_columns,
    rank_schema_table_matches,
    score_schema_table_match,
)


def test_semantic_similarity_normalizes_common_abbreviations() -> None:
    score, reasons = _semantic_similarity("qty", "quantity")

    assert score == 1.0
    assert reasons == ["exact name match"]


def test_semantic_similarity_prefers_full_compound_token_coverage() -> None:
    exact_score, _ = _semantic_similarity(
        "which crew bases have the highest fatigue scores",
        "crew_bases",
    )
    partial_score, _ = _semantic_similarity(
        "which crew bases have the highest fatigue scores",
        "crew_assignments",
    )

    assert exact_score > partial_score
    assert exact_score >= 0.9


def test_semantic_similarity_downweights_generic_action_terms() -> None:
    entity_score, _ = _semantic_similarity(
        "gates crews turnaround decisions need action first today",
        "gate_assignments",
    )
    generic_score, _ = _semantic_similarity(
        "gates crews turnaround decisions need action first today",
        "recovery_actions",
    )

    assert entity_score > generic_score


def test_semantic_similarity_caps_generic_substring_matches() -> None:
    score, _ = _semantic_similarity("action", "recovery_actions")

    assert score < 0.4


def test_semantic_similarity_rejects_embedded_partial_word_matches() -> None:
    score, _ = _semantic_similarity("network", "work")

    assert score < 0.4


def test_semantic_similarity_rejects_loose_description_collisions() -> None:
    score, _ = _semantic_similarity("disruption", "description")

    assert score < 0.4


def test_lexical_overlap_score_rejects_internal_substring_collisions() -> None:
    assert _lexical_overlap_score("diversion", "version") == 0.0


def test_semantic_similarity_downweights_identifier_only_matches() -> None:
    query_score, _ = _semantic_similarity(
        "which crew bases have the highest fatigue scores",
        "crew_id",
    )
    label_score, _ = _semantic_similarity(
        "which crew bases have the highest fatigue scores",
        "crew_bases",
    )

    assert label_score > query_score


def test_score_schema_table_match_downweights_generic_action_tables() -> None:
    query = "Which gates, crews, or turnaround decisions need action first today?"
    recovery = score_schema_table_match(
        query,
        {
            "sourceTable": "recovery_actions",
            "importTargetTable": "recovery_actions",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["action_type", "action_target", "crew_id"],
        },
    )
    gate = score_schema_table_match(
        query,
        {
            "sourceTable": "gate_assignments",
            "importTargetTable": "gate_assignments",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["gate_code", "flight_id", "airport_id"],
        },
    )

    assert gate["score"] > recovery["score"]


def test_score_schema_table_match_downweights_secondary_metric_tables() -> None:
    query = "Which gates, crews, or turnaround decisions need action first today?"
    operational = score_schema_table_match(
        query,
        {
            "sourceTable": "gate_assignments",
            "importTargetTable": "gate_assignments",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["gate_code", "flight_id", "airport_id"],
        },
    )
    analytic = score_schema_table_match(
        query,
        {
            "sourceTable": "crew_fatigue_scores",
            "importTargetTable": "crew_fatigue_scores",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["crew_id", "fatigue_score", "recorded_at_utc"],
        },
    )

    assert operational["score"] > analytic["score"]


def test_score_schema_table_match_prefers_primary_disruption_tables() -> None:
    query = "Where are the highest-risk disruptions across the airport network right now?"
    disruption = score_schema_table_match(
        query,
        {
            "sourceTable": "disruption_event_flights",
            "importTargetTable": "disruption_event_flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "flight_id", "impact_type"],
        },
    )
    generic = score_schema_table_match(
        query,
        {
            "sourceTable": "maintenance_work_orders",
            "importTargetTable": "maintenance_work_orders",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "description", "status"],
        },
    )

    assert disruption["score"] > generic["score"]


def test_score_schema_table_match_boosts_context_named_source_table() -> None:
    query = (
        "Which disruption events and flights combinations have the highest total "
        "delay minutes attributable in disruption event flights?"
    )
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "disruption_event_flights",
            "importTargetTable": "disruption_event_flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "flight_id", "delay_minutes_attributable"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "delay_assignments",
            "importTargetTable": "delay_assignments",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["flight_id", "delay_minutes", "delay_code"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_score_schema_table_match_boosts_single_token_context_table_name() -> None:
    query = "Which flights have the highest average ground time minutes in diversions?"
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "diversions",
            "importTargetTable": "diversions",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "ground_handling_tasks",
            "importTargetTable": "ground_handling_tasks",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["flight_id", "delay_minutes", "status"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_score_schema_table_match_prefers_explicitly_anchored_bridge_fact_over_flights() -> None:
    query = (
        "Which disruption events and flights combinations have the highest total "
        "delay minutes attributable in disruption event flights?"
    )
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "disruption_event_flights",
            "importTargetTable": "disruption_event_flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "flight_id", "delay_minutes_attributable"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "flights",
            "importTargetTable": "flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "dep_delay_minutes", "arr_delay_minutes"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_score_schema_table_match_prefers_explicitly_anchored_fact_over_uplifts() -> None:
    query = "Which airports and suppliers combinations have the highest total price usd per l in fuel prices?"
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "fuel_prices",
            "importTargetTable": "fuel_prices",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "supplier_id", "price_usd_per_l"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "fuel_uplifts",
            "importTargetTable": "fuel_uplifts",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "supplier_id", "fuel_uplift_kg"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_score_schema_table_match_prefers_explicitly_anchored_diversions_over_flights() -> None:
    query = "Which flights have the highest average ground time minutes in diversions?"
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "diversions",
            "importTargetTable": "diversions",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "flights",
            "importTargetTable": "flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["dep_delay_minutes", "arr_delay_minutes", "pax_count"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_score_schema_table_match_prefers_exact_metric_phrase_over_related_plan_table() -> None:
    query = "Which flights have the highest average cost estimate usd in diversions?"
    primary = score_schema_table_match(
        query,
        {
            "sourceTable": "diversions",
            "importTargetTable": "diversions",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
        },
    )
    sibling = score_schema_table_match(
        query,
        {
            "sourceTable": "flight_plans",
            "importTargetTable": "flight_plans",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["trip_fuel_kg", "cost_index", "payload_kg"],
        },
    )

    assert primary["score"] > sibling["score"]


def test_build_schema_query_term_entries_omits_context_prepositions() -> None:
    entries = _build_schema_query_term_entries(
        "Where are the highest-risk disruptions across the airport network right now?"
    )

    assert {entry["term"] for entry in entries} == {
        "highest",
        "risk",
        "disruption",
        "airport",
        "network",
        "right",
        "now",
    }


def test_query_term_specificity_weights_favor_rarer_terms() -> None:
    query = "Where are the highest-risk disruptions across the airport network right now?"
    catalog = [
        {
            "sourceTable": "airports",
            "importTargetTable": "airports",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_type"],
        },
        {
            "sourceTable": "airport_slots",
            "importTargetTable": "airport_slots",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "slot_status"],
        },
        {
            "sourceTable": "airport_weather_alerts",
            "importTargetTable": "airport_weather_alerts",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "alert_level"],
        },
        {
            "sourceTable": "airport_network_nodes",
            "importTargetTable": "airport_network_nodes",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "node_code"],
        },
        {
            "sourceTable": "airport_runway_events",
            "importTargetTable": "airport_runway_events",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "status"],
        },
        {
            "sourceTable": "disruption_event_flights",
            "importTargetTable": "disruption_event_flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "flight_id", "impact_type"],
        },
        {
            "sourceTable": "maintenance_work_orders",
            "importTargetTable": "maintenance_work_orders",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_id", "description", "status"],
        },
    ]

    weights = _query_term_specificity_weights(
        _build_schema_query_term_entries(query),
        catalog,
    )

    assert weights["disruption"] > weights["airport"]


def test_query_term_specificity_weights_match_prepared_catalog() -> None:
    query = "Where are the highest-risk disruptions across the airport network right now?"
    catalog = [
        {
            "sourceTable": "airports",
            "importTargetTable": "airports",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["airport_type"],
        },
        {
            "sourceTable": "disruption_event_flights",
            "importTargetTable": "disruption_event_flights",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["disruption_event_id", "flight_id", "impact_type"],
        },
    ]

    query_terms = _build_schema_query_term_entries(query)
    raw_weights = _query_term_specificity_weights(query_terms, catalog)
    prepared_weights = _query_term_specificity_weights(
        query_terms,
        prepare_schema_catalog(catalog),
    )

    assert prepared_weights == raw_weights


def test_rank_schema_table_matches_matches_prepared_catalog() -> None:
    query = "Which flights have the highest average ground time minutes in diversions?"
    catalog = [
        {
            "sourceTable": "diversions",
            "importTargetTable": "diversions",
            "domain": None,
            "importedRowCount": 10,
            "primaryKey": [],
            "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
        },
        {
            "sourceTable": "ground_handling_tasks",
            "importTargetTable": "ground_handling_tasks",
            "domain": None,
            "importedRowCount": 5,
            "primaryKey": [],
            "columns": ["flight_id", "delay_minutes", "status"],
        },
    ]

    raw_ranked = rank_schema_table_matches(query, catalog)
    prepared_ranked = rank_schema_table_matches(query, prepare_schema_catalog(catalog))

    assert prepared_ranked == raw_ranked


def test_rank_schema_table_matches_preserves_relevant_table_with_large_catalog() -> None:
    query = "Which flights have the highest average ground time minutes in diversions?"
    catalog = [
        {
            "sourceTable": f"airport_ops_{index}",
            "importTargetTable": f"airport_ops_{index}",
            "domain": None,
            "importedRowCount": 1000 - index,
            "primaryKey": [],
            "columns": ["airport_id", "status", "delay_minutes"],
        }
        for index in range(70)
    ]
    catalog.extend(
        [
            {
                "sourceTable": "diversions",
                "importTargetTable": "diversions",
                "domain": None,
                "importedRowCount": 10,
                "primaryKey": [],
                "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
            },
            {
                "sourceTable": "flights",
                "importTargetTable": "flights",
                "domain": None,
                "importedRowCount": 500,
                "primaryKey": [],
                "columns": ["flight_number", "status", "aircraft_id"],
            },
        ]
    )

    ranked = rank_schema_table_matches(query, catalog)

    assert ranked[0]["sourceTable"] == "diversions"


def test_rank_schema_table_matches_prefers_explicit_source_anchor_over_unanchored_sibling() -> None:
    query = "Which flights have the highest average ground time minutes in diversions?"
    ranked = rank_schema_table_matches(
        query,
        [
            {
                "sourceTable": "flights",
                "importTargetTable": "flights",
                "domain": None,
                "importedRowCount": 100,
                "primaryKey": [],
                "columns": ["dep_delay_minutes", "arr_delay_minutes", "pax_count"],
            },
            {
                "sourceTable": "diversions",
                "importTargetTable": "diversions",
                "domain": None,
                "importedRowCount": 10,
                "primaryKey": [],
                "columns": ["flight_id", "ground_time_minutes", "cost_estimate_usd"],
            },
        ],
    )

    assert ranked[0]["sourceTable"] == "diversions"
    assert ranked[0]["sourceAnchorScore"] > ranked[1]["sourceAnchorScore"]


def test_rank_schema_table_matches_keeps_full_catalog_when_no_positive_shortlist_hits() -> None:
    query = "Which entities need calibration alignment remediation?"
    catalog = [
        {
            "sourceTable": f"table_{index}",
            "importTargetTable": f"table_{index}",
            "domain": None,
            "importedRowCount": index,
            "primaryKey": [],
            "columns": ["id", "description"],
        }
        for index in range(80)
    ]

    ranked = rank_schema_table_matches(query, catalog)

    assert len(ranked) == len(catalog)


def test_rank_schema_metric_columns_prefers_exact_metric_phrase() -> None:
    ranked = rank_schema_metric_columns(
        "Which flights have the highest average cost estimate usd in diversions?",
        ["flight_id", "ground_time_minutes", "cost_estimate_usd", "cost_index"],
    )

    assert ranked[0]["column"] == "cost_estimate_usd"


def test_rank_schema_metric_columns_matches_phrase_with_short_stop_word_gap() -> None:
    ranked = rank_schema_metric_columns(
        "Which aircraft types have the highest average hours on type in crew type ratings?",
        ["aircraft_type_id", "hours_on_type", "rating_level"],
    )

    assert ranked[0]["column"] == "hours_on_type"


def test_rank_schema_metric_columns_downweights_aggregation_token_dominance() -> None:
    ranked = rank_schema_metric_columns(
        "Which flights and passengers combinations have the highest total taxes usd in tickets?",
        ["total_usd", "taxes_usd", "base_fare_usd"],
    )

    assert ranked[0]["column"] == "taxes_usd"


def test_rank_schema_metric_columns_penalizes_identifier_for_metric_intent() -> None:
    ranked = rank_schema_metric_columns(
        "Which flights and loyalty members combinations have the highest total score in nps scores?",
        ["loyalty_member_id", "score", "comment_length"],
    )

    assert ranked[0]["column"] == "score"


def test_rank_schema_dimension_columns_prefers_display_column_over_identifier() -> None:
    ranked = rank_schema_dimension_columns(
        "Which flights and loyalty members combinations have the highest total score in nps scores?",
        ["loyalty_member_id", "member_number", "full_name", "created_at_utc"],
        table_name="loyalty_members",
    )

    assert ranked[0]["column"] == "full_name"


def test_rank_schema_dimension_columns_prefers_name_like_column_for_entity_query() -> None:
    ranked = rank_schema_dimension_columns(
        "Which airports have the highest total fuel price in fuel prices?",
        ["airport_id", "name", "created_at", "price_usd_per_l"],
        table_name="airports",
    )

    assert ranked[0]["column"] == "name"


def test_rank_schema_dimension_columns_falls_back_to_descriptive_type_without_display_name() -> (
    None
):
    ranked = rank_schema_dimension_columns(
        "Which airports and routes combinations have the highest total bags mishandled in bag handling metrics?",
        ["destination_airport_id", "preferred_body_type", "estimated_block_minutes"],
        table_name="routes",
    )

    assert ranked[0]["column"] == "preferred_body_type"


def test_rank_schema_dimension_columns_prefers_name_over_table_echo_code() -> None:
    ranked = rank_schema_dimension_columns(
        "Which suppliers have the highest average bags processed in bag handling metrics?",
        ["supplier_code", "name", "supplier_type"],
        table_name="suppliers",
    )

    assert ranked[0]["column"] == "name"


def test_rank_schema_dimension_columns_prefers_member_number_over_partial_name() -> None:
    ranked = rank_schema_dimension_columns(
        "Which flights and loyalty members combinations have the highest total score in nps scores?",
        ["member_number", "first_name", "last_name"],
        table_name="loyalty_members",
    )

    assert ranked[0]["column"] == "member_number"


def test_rank_schema_dimension_columns_prefers_partial_name_when_only_incidental_numbers_exist() -> (
    None
):
    ranked = rank_schema_dimension_columns(
        "Which flights and passengers combinations have the highest total base fare usd in tickets?",
        ["first_name", "last_name", "document_number", "passenger_type"],
        table_name="passengers",
    )

    assert ranked[0]["column"] == "first_name"


def test_score_schema_table_match_rewards_multi_term_business_coverage() -> None:
    query = "which crew bases have the highest fatigue scores"
    dimension = score_schema_table_match(
        query,
        {
            "sourceTable": "crew_bases",
            "importTargetTable": "crew_bases",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["base_code", "name"],
        },
    )
    bridge = score_schema_table_match(
        query,
        {
            "sourceTable": "crew_assignments",
            "importTargetTable": "crew_assignments",
            "domain": None,
            "importedRowCount": 1,
            "primaryKey": [],
            "columns": ["crew_id", "flight_id"],
        },
    )

    assert dimension["score"] > bridge["score"]


def test_detect_derived_relationships_finds_multiplication_formula() -> None:
    relationships = _detect_derived_relationships(
        [
            {"quantity": 2, "unit_price": 3, "extended_price": 6},
            {"quantity": 4, "unit_price": 5, "extended_price": 20},
            {"quantity": 6, "unit_price": 7, "extended_price": 42},
        ],
        ["extended_price", "quantity", "unit_price"],
        source="orders",
    )

    assert relationships == [
        {
            "formula": "extended_price = quantity × unit_price",
            "source": "orders",
            "field_result": "extended_price",
            "field_a": "quantity",
            "field_b": "unit_price",
            "operation": "multiply",
            "confidence": 1.0,
        }
    ]
