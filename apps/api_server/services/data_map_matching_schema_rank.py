from __future__ import annotations

from typing import Any

from .data_map_matching_common import (
    IDENTIFIER_TOKENS,
    SCHEMA_MATCH_AGGREGATION_HINT_TOKENS,
    SCHEMA_MATCH_BOOLEAN_COLUMN_TOKENS,
    SCHEMA_MATCH_DIMENSION_DISPLAY_TOKENS,
    SCHEMA_MATCH_DIMENSION_NOISE_TOKENS,
    SCHEMA_MATCH_DIMENSION_PRIMARY_DISPLAY_TOKENS,
    SCHEMA_MATCH_DIMENSION_SECONDARY_DISPLAY_TOKENS,
    SCHEMA_MATCH_INCIDENTAL_DETAIL_TOKENS,
    SCHEMA_MATCH_METRIC_TOKENS,
    SCHEMA_MATCH_NO_PRUNE_TABLE_LIMIT,
    SCHEMA_MATCH_PARTIAL_NAME_TOKENS,
    SCHEMA_MATCH_SHORTLIST_FILLER_MAX,
    SCHEMA_MATCH_SHORTLIST_MAX,
    SCHEMA_MATCH_SHORTLIST_MIN,
    SCHEMA_MATCH_SHORTLIST_PER_TERM,
    SCHEMA_MATCH_STATUS_COLUMN_TOKENS,
    SCHEMA_MATCH_TEMPORAL_COLUMN_TOKENS,
    SECONDARY_TABLE_QUERY_PENALTIES,
    TOKEN_TO_CONCEPTS,
    PreparedSchemaCatalog,
    PreparedSchemaTable,
    _build_schema_query_term_entries,
    _column_phrase_bonus,
    _contextual_table_phrase_bonus_from_names,
    _contextual_table_phrase_bonus_from_tokens,
    _identifier_tokens,
    _lexical_overlap_score,
    _normalized_query_tokens,
    _prepare_schema_catalog_cached,
    _prepare_schema_label,
    _schema_catalog_signature,
    _schema_source_labels,
    prepare_schema_table,
)
from .data_map_matching_similarity import _semantic_similarity, _semantic_similarity_cached


def rank_schema_metric_columns(query: str, columns: list[str]) -> list[dict[str, Any]]:
    query_terms = [
        {
            **entry,
            "weight": float(entry["weight"])
            * (0.22 if str(entry["term"]) in SCHEMA_MATCH_AGGREGATION_HINT_TOKENS else 1.0),
        }
        for entry in _build_schema_query_term_entries(query)
    ]
    query_token_sequence = _normalized_query_tokens(query)
    query_business_tokens = frozenset(
        str(entry["term"]) for entry in query_terms if entry.get("generic") is False
    )
    ranked: list[dict[str, Any]] = []
    for column in columns:
        label = _prepare_schema_label("column", column)
        raw_column_tokens = frozenset(_identifier_tokens(column))
        best_score = 0.0
        top_scores: list[float] = []
        matched_terms: set[str] = set()
        for term_entry in query_terms:
            term = str(term_entry["term"])
            weight = float(term_entry["weight"])
            semantic_score = _semantic_similarity_cached(term, column)[0]
            lexical_score = _lexical_overlap_score(term, column)
            effective_score = max(float(semantic_score or 0.0), lexical_score) * weight
            if label.low_signal_only:
                effective_score *= 0.76
            if effective_score >= 0.34 and term_entry.get("generic") is False:
                matched_terms.add(term)
                top_scores.append(effective_score)
            best_score = max(best_score, effective_score)

        top_scores.sort(reverse=True)
        phrase_bonus = _column_phrase_bonus(query_token_sequence, label)
        metric_token_overlap = len(
            label.tokens & query_business_tokens & SCHEMA_MATCH_METRIC_TOKENS
        )
        specific_overlap = len(
            label.tokens & (query_business_tokens - SCHEMA_MATCH_AGGREGATION_HINT_TOKENS)
        )
        identifier_like = bool(raw_column_tokens & IDENTIFIER_TOKENS)
        metric_intent = bool(query_business_tokens & SCHEMA_MATCH_METRIC_TOKENS)
        if identifier_like and metric_intent:
            phrase_bonus *= 0.2
        identifier_penalty = 1.0
        if identifier_like:
            identifier_penalty = 0.38 if metric_intent else 0.78
        aggregate_score = round(
            (
                best_score * 0.58
                + (sum(top_scores[:2]) / min(len(top_scores[:2]), 2) if top_scores else 0.0) * 0.2
                + phrase_bonus * 0.16
                + min(metric_token_overlap, 2) * 0.05
                + min(specific_overlap, 3) * 0.04
                + min(len(matched_terms), 3) * 0.03
            )
            * identifier_penalty,
            4,
        )
        ranked.append(
            {
                "column": column,
                "score": aggregate_score,
                "matchedTermCount": len(matched_terms),
                "columnPhraseScore": round(phrase_bonus, 4),
            }
        )

    ranked.sort(
        key=lambda entry: (
            -float(entry["score"]),
            -int(entry["matchedTermCount"]),
            str(entry["column"]),
        )
    )
    return ranked


def rank_schema_dimension_columns(
    query: str,
    columns: list[str],
    *,
    table_name: str | None = None,
) -> list[dict[str, Any]]:
    query_terms = [
        {
            **entry,
            "weight": float(entry["weight"])
            * (
                0.18
                if str(entry["term"])
                in (SCHEMA_MATCH_METRIC_TOKENS | SCHEMA_MATCH_AGGREGATION_HINT_TOKENS)
                else 1.0
            ),
        }
        for entry in _build_schema_query_term_entries(query)
    ]
    query_token_sequence = _normalized_query_tokens(query)
    query_business_tokens = frozenset(
        str(entry["term"]) for entry in query_terms if entry.get("generic") is False
    )
    table_tokens = frozenset(_identifier_tokens(table_name or ""))
    query_entity_tokens = query_business_tokens - (
        SCHEMA_MATCH_METRIC_TOKENS
        | SCHEMA_MATCH_AGGREGATION_HINT_TOKENS
        | SCHEMA_MATCH_DIMENSION_NOISE_TOKENS
    )
    prepared_columns = [
        (
            column,
            _prepare_schema_label("column", column),
            frozenset(_identifier_tokens(column)),
        )
        for column in columns
    ]
    has_primary_display_candidate = any(
        raw_tokens & SCHEMA_MATCH_DIMENSION_PRIMARY_DISPLAY_TOKENS
        for _column, _label, raw_tokens in prepared_columns
    )
    has_secondary_display_candidate = any(
        raw_tokens & SCHEMA_MATCH_DIMENSION_SECONDARY_DISPLAY_TOKENS
        for _column, _label, raw_tokens in prepared_columns
    )
    has_canonical_secondary_display_candidate = any(
        raw_tokens & SCHEMA_MATCH_DIMENSION_SECONDARY_DISPLAY_TOKENS
        and not (raw_tokens & SCHEMA_MATCH_INCIDENTAL_DETAIL_TOKENS)
        for _column, _label, raw_tokens in prepared_columns
    )
    has_display_candidate = has_primary_display_candidate or has_secondary_display_candidate
    ranked: list[dict[str, Any]] = []
    for column, label, raw_column_tokens in prepared_columns:
        best_score = 0.0
        top_scores: list[float] = []
        matched_terms: set[str] = set()
        for term_entry in query_terms:
            term = str(term_entry["term"])
            weight = float(term_entry["weight"])
            semantic_score = _semantic_similarity_cached(term, column)[0]
            lexical_score = _lexical_overlap_score(term, column)
            effective_score = max(float(semantic_score or 0.0), lexical_score) * weight
            if label.low_signal_only:
                effective_score *= 0.72
            if effective_score >= 0.34 and term_entry.get("generic") is False:
                matched_terms.add(term)
                top_scores.append(effective_score)
            best_score = max(best_score, effective_score)

        top_scores.sort(reverse=True)
        phrase_bonus = _column_phrase_bonus(query_token_sequence, label)
        entity_overlap = len(label.tokens & query_entity_tokens)
        display_overlap = len(raw_column_tokens & SCHEMA_MATCH_DIMENSION_DISPLAY_TOKENS)
        primary_display = bool(raw_column_tokens & SCHEMA_MATCH_DIMENSION_PRIMARY_DISPLAY_TOKENS)
        secondary_display = bool(
            raw_column_tokens & SCHEMA_MATCH_DIMENSION_SECONDARY_DISPLAY_TOKENS
        )
        identifier_like = bool(raw_column_tokens & IDENTIFIER_TOKENS)
        metric_like = bool(raw_column_tokens & SCHEMA_MATCH_METRIC_TOKENS)
        temporal_like = bool(raw_column_tokens & SCHEMA_MATCH_TEMPORAL_COLUMN_TOKENS)
        status_like = bool(raw_column_tokens & SCHEMA_MATCH_STATUS_COLUMN_TOKENS)
        boolean_like = bool(
            raw_column_tokens & SCHEMA_MATCH_BOOLEAN_COLUMN_TOKENS
        ) or column.lower().startswith(("is_", "has_", "can_"))
        type_like = "type" in raw_column_tokens
        partial_name_like = bool(raw_column_tokens & SCHEMA_MATCH_PARTIAL_NAME_TOKENS)
        table_echo_overlap = len(raw_column_tokens & table_tokens)
        display_bonus = 0.0
        if primary_display:
            display_bonus += 0.42
        elif secondary_display:
            display_bonus += 0.26
        elif display_overlap:
            display_bonus += 0.16
        elif (
            type_like
            and not has_display_candidate
            and not any((identifier_like, metric_like, temporal_like, status_like, boolean_like))
        ):
            display_bonus += 0.34
        elif not any((identifier_like, metric_like, temporal_like, status_like, boolean_like)):
            display_bonus += 0.08
        if raw_column_tokens <= {"full", "name"}:
            display_bonus += 0.08

        aggregate_score = (
            best_score * 0.38
            + (sum(top_scores[:2]) / min(len(top_scores[:2]), 2) if top_scores else 0.0) * 0.16
            + phrase_bonus * 0.1
            + min(entity_overlap, 2) * 0.12
            + display_bonus
            + min(len(matched_terms), 3) * 0.04
        )
        if identifier_like:
            aggregate_score *= 0.26 if has_display_candidate else 0.34
        if metric_like and not display_overlap:
            aggregate_score *= 0.35 if has_display_candidate else 0.58
        if temporal_like:
            aggregate_score *= 0.42 if has_display_candidate else 0.68
        if status_like and "status" not in query_entity_tokens:
            aggregate_score *= 0.44 if has_display_candidate else 0.76
        if boolean_like:
            aggregate_score *= 0.24 if has_display_candidate else 0.58
        if type_like and not (primary_display or secondary_display):
            aggregate_score *= 0.46 if has_display_candidate else 0.76
        if secondary_display and has_primary_display_candidate and not primary_display:
            aggregate_score *= 0.82
        if partial_name_like and has_canonical_secondary_display_candidate:
            aggregate_score *= 0.42
        if (
            table_echo_overlap
            and secondary_display
            and has_primary_display_candidate
            and "number" not in raw_column_tokens
        ):
            aggregate_score *= 0.55
        if table_echo_overlap and type_like and has_display_candidate:
            aggregate_score *= 0.55

        ranked.append(
            {
                "column": column,
                "score": round(aggregate_score, 4),
                "matchedTermCount": len(matched_terms),
                "columnPhraseScore": round(phrase_bonus, 4),
                "displayColumnScore": round(display_bonus, 4),
            }
        )

    ranked.sort(
        key=lambda entry: (
            -float(entry["score"]),
            -int(entry["matchedTermCount"]),
            str(entry["column"]),
        )
    )
    return ranked


def _contextual_table_phrase_bonus(query: str, table: dict[str, Any]) -> float:
    return _contextual_table_phrase_bonus_from_names(
        query,
        (
            str(table.get("sourceTable") or "").strip(),
            str(table.get("importTargetTable") or "").strip(),
        ),
    )


def _term_hits_catalog(
    term_entry: dict[str, Any],
    catalog: list[dict[str, Any]] | PreparedSchemaCatalog,
) -> int:
    term = str(term_entry["term"])
    if isinstance(catalog, PreparedSchemaCatalog):
        matching_tables = set(catalog.token_hits.get(term, ()))
        for concept in TOKEN_TO_CONCEPTS.get(term, ()):
            matching_tables.update(catalog.concept_hits.get(concept, ()))
        return len(matching_tables)

    for_threshold = float(term_entry["weight"])
    hits = 0
    for table in catalog:
        for _, label in _schema_source_labels(table):
            semantic_score, _ = _semantic_similarity(term, label)
            lexical_score = _lexical_overlap_score(term, label)
            if max(float(semantic_score or 0.0), lexical_score) * for_threshold >= 0.34:
                hits += 1
                break
    return hits


def _query_term_specificity_weights(
    query_terms: list[dict[str, Any]],
    catalog: list[dict[str, Any]] | PreparedSchemaCatalog,
) -> dict[str, float]:
    hit_counts = {
        str(entry["term"]): _term_hits_catalog(entry, catalog)
        for entry in query_terms
        if entry.get("generic") is False
    }
    if not hit_counts:
        return {}

    max_hits = max(hit_counts.values())
    min_hits = min(hit_counts.values())
    if max_hits == min_hits:
        return dict.fromkeys(hit_counts, 1.0)

    return {
        term: round(1.0 + 0.4 * ((max_hits - hits) / max(max_hits - min_hits, 1)), 4)
        for term, hits in hit_counts.items()
    }


def _candidate_schema_tables(
    query: str,
    query_terms: list[dict[str, Any]],
    catalog: PreparedSchemaCatalog,
) -> tuple[PreparedSchemaTable, ...]:
    if len(catalog.tables) <= SCHEMA_MATCH_NO_PRUNE_TABLE_LIMIT:
        return catalog.tables

    business_terms = frozenset(
        str(entry["term"]) for entry in query_terms if entry.get("generic") is False
    )
    if not business_terms:
        return catalog.tables

    business_concepts = frozenset(
        concept for term in business_terms for concept in TOKEN_TO_CONCEPTS.get(term, ())
    )
    query_tokens = _normalized_query_tokens(query)
    shortlist_size = min(
        len(catalog.tables),
        max(
            SCHEMA_MATCH_SHORTLIST_MIN,
            min(SCHEMA_MATCH_SHORTLIST_MAX, len(business_terms) * SCHEMA_MATCH_SHORTLIST_PER_TERM),
        ),
    )

    positive_candidates: list[tuple[float, int, str, PreparedSchemaTable]] = []
    zero_candidates: list[tuple[int, str, PreparedSchemaTable]] = []
    for table in catalog.tables:
        context_bonus = _contextual_table_phrase_bonus_from_tokens(
            query_tokens,
            table.table_name_phrases,
        )
        table_token_overlap = len(table.table_tokens & business_terms)
        token_overlap = len(table.label_tokens & business_terms)
        concept_overlap = len(table.label_concepts & business_concepts)
        cheap_score = (
            table_token_overlap * 3.0
            + token_overlap * 2.0
            + concept_overlap * 1.0
            + context_bonus * 10.0
        )
        if cheap_score > 0.0:
            positive_candidates.append(
                (cheap_score, table.imported_row_count, table.source_table, table)
            )
        else:
            zero_candidates.append((table.imported_row_count, table.source_table, table))

    if not positive_candidates:
        return catalog.tables

    positive_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    shortlisted = [item[3] for item in positive_candidates[:shortlist_size]]
    remaining_slots = shortlist_size - len(shortlisted)
    if remaining_slots <= 0:
        return tuple(shortlisted)

    zero_candidates.sort(key=lambda item: (-item[0], item[1]))
    filler_limit = min(remaining_slots, SCHEMA_MATCH_SHORTLIST_FILLER_MAX)
    shortlisted.extend(item[2] for item in zero_candidates[:filler_limit])
    return tuple(shortlisted)


def score_schema_table_match(
    query: str,
    table: dict[str, Any] | PreparedSchemaTable,
    *,
    query_terms: list[dict[str, Any]] | None = None,
    query_token_sequence: tuple[str, ...] | None = None,
    query_business_tokens: frozenset[str] | None = None,
) -> dict[str, Any]:
    prepared_table = (
        table if isinstance(table, PreparedSchemaTable) else prepare_schema_table(table)
    )
    if query_terms is None:
        query_terms = _build_schema_query_term_entries(query)
    if query_token_sequence is None:
        query_token_sequence = _normalized_query_tokens(query)
    if query_business_tokens is None:
        query_business_tokens = frozenset(
            str(entry["term"]) for entry in query_terms if entry.get("generic") is False
        )
    best_table_score = 0.0
    best_domain_score = 0.0
    column_scores: list[tuple[float, str]] = []
    matched_columns: list[str] = []
    matched_column_terms: set[str] = set()
    matched_business_terms: set[str] = set()
    matched_generic_terms: set[str] = set()

    for label in prepared_table.labels:
        best_label_score = 0.0
        best_term_entry: dict[str, Any] | None = None
        for term_entry in query_terms:
            term = str(term_entry["term"])
            weight = float(term_entry["weight"])
            semantic_score = _semantic_similarity_cached(term, label.value)[0]
            lexical_score = _lexical_overlap_score(term, label.value)
            effective_score = max(float(semantic_score or 0.0), lexical_score) * weight
            if label.low_signal_only:
                effective_score *= 0.76
            phrase_bonus = _column_phrase_bonus(query_token_sequence, label)
            if phrase_bonus > 0.0:
                effective_score = max(effective_score, min(1.0, effective_score + phrase_bonus))
            if effective_score > best_label_score:
                best_label_score = effective_score
                best_term_entry = term_entry

        if best_label_score >= 0.34 and best_term_entry is not None:
            if best_term_entry.get("generic") is True:
                matched_generic_terms.add(str(best_term_entry["term"]))
            else:
                matched_business_terms.add(str(best_term_entry["term"]))
                if label.kind == "column" and label.value not in matched_columns:
                    matched_columns.append(label.value)
                    matched_column_terms.add(str(best_term_entry["term"]))

        if label.kind == "table":
            best_table_score = max(best_table_score, best_label_score)
        elif label.kind == "domain":
            best_domain_score = max(best_domain_score, best_label_score)
        else:
            column_scores.append((best_label_score, label.value))

    top_column_scores = sorted((score for score, _ in column_scores), reverse=True)[:3]
    column_score = sum(top_column_scores) / len(top_column_scores) if top_column_scores else 0.0
    coverage_score = min(1.0, len(matched_business_terms))
    generic_only_penalty = (
        1.0 if matched_business_terms else (0.45 if matched_generic_terms else 1.0)
    )
    table_tokens = set(prepared_table.table_tokens)
    context_bonus = _contextual_table_phrase_bonus_from_tokens(
        query_token_sequence,
        prepared_table.table_name_phrases,
    )
    best_table_score = min(1.0, best_table_score + context_bonus)
    secondary_table_penalty = 1.0
    for secondary_tokens, allowed_query_tokens, penalty in SECONDARY_TABLE_QUERY_PENALTIES:
        if table_tokens & secondary_tokens and not (query_business_tokens & allowed_query_tokens):
            secondary_table_penalty = min(secondary_table_penalty, penalty)

    total_score = round(
        (
            best_table_score * 0.52
            + column_score * 0.28
            + best_domain_score * 0.08
            + min(1.0, len(matched_column_terms) / 2) * 0.08
            + min(1.0, len(matched_business_terms) / 3) * 0.04
            + context_bonus * 0.08
        )
        * generic_only_penalty
        * secondary_table_penalty,
        4,
    )

    return {
        "sourceTable": prepared_table.source_table,
        "importTargetTable": prepared_table.import_target_table,
        "domain": prepared_table.domain,
        "importedRowCount": prepared_table.imported_row_count,
        "primaryKey": list(prepared_table.primary_key),
        "columns": list(prepared_table.columns),
        "matchedColumns": matched_columns[:5],
        "score": total_score,
        "businessTermCount": len(matched_business_terms),
        "coverageScore": coverage_score,
        "sourceAnchorScore": round(context_bonus, 4),
    }


def rank_schema_table_matches(
    query: str,
    catalog: list[dict[str, Any]] | PreparedSchemaCatalog,
) -> list[dict[str, Any]]:
    prepared_catalog = (
        catalog
        if isinstance(catalog, PreparedSchemaCatalog)
        else _prepare_schema_catalog_cached(_schema_catalog_signature(catalog))
    )
    query_terms = _build_schema_query_term_entries(query)
    specificity_weights = _query_term_specificity_weights(query_terms, prepared_catalog)
    weighted_query_terms = [
        {
            **entry,
            "weight": float(entry["weight"]) * specificity_weights.get(str(entry["term"]), 1.0),
        }
        for entry in query_terms
    ]
    query_token_sequence = _normalized_query_tokens(query)
    query_business_tokens = frozenset(
        str(entry["term"]) for entry in weighted_query_terms if entry.get("generic") is False
    )
    candidate_tables = _candidate_schema_tables(query, query_terms, prepared_catalog)
    ranked = [
        score_schema_table_match(
            query,
            table,
            query_terms=weighted_query_terms,
            query_token_sequence=query_token_sequence,
            query_business_tokens=query_business_tokens,
        )
        for table in candidate_tables
    ]
    ranked.sort(
        key=lambda entry: (
            -float(entry.get("sourceAnchorScore") or 0.0),
            -float(entry["score"]),
            -int(entry["importedRowCount"] or 0),
            str(entry["sourceTable"] or ""),
        )
    )
    return ranked
