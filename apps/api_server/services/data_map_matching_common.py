from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Any

ABBREVIATIONS: dict[str, str] = {
    "qty": "quantity",
    "qnty": "quantity",
    "amt": "amount",
    "amnt": "amount",
    "rev": "revenue",
    "revs": "revenue",
    "cst": "cost",
    "cts": "cost",
    "cus": "customer",
    "cust": "customer",
    "ord": "order",
    "prc": "price",
    "pr": "price",
    "no": "number",
    "num": "number",
    "nbr": "number",
    "dt": "date",
    "ts": "timestamp",
    "wo": "workorder",
    "ap": "airport",
}

GENERIC_MATCH_TOKENS = frozenset(
    {
        "action",
        "actions",
        "current",
        "data",
        "decision",
        "decisions",
        "event",
        "events",
        "first",
        "have",
        "highest",
        "how",
        "information",
        "last",
        "latest",
        "most",
        "need",
        "now",
        "record",
        "records",
        "recent",
        "result",
        "results",
        "right",
        "show",
        "status",
        "summary",
        "today",
        "top",
        "what",
        "where",
        "which",
    }
)

IDENTIFIER_TOKENS = frozenset({"id", "identifier", "key", "number", "ref"})
TABLE_CONTEXT_CUES = frozenset({"during", "for", "from", "in", "within"})
SCHEMA_MATCH_STOP_WORDS = frozenset(
    {
        "a",
        "about",
        "against",
        "across",
        "an",
        "and",
        "any",
        "are",
        "compare",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "me",
        "of",
        "on",
        "or",
        "show",
        "the",
        "to",
        "we",
        "what",
        "where",
        "which",
        "with",
    }
)
SCHEMA_MATCH_LOW_SIGNAL_TERMS = frozenset(
    {
        *GENERIC_MATCH_TOKENS,
        "day",
        "days",
        "month",
        "months",
        "past",
        "previous",
        "quarter",
        "quarters",
        "row",
        "rows",
        "week",
        "weeks",
        "year",
        "years",
        "yesterday",
    }
)
LOW_SIGNAL_LABEL_TOKENS = frozenset(
    {
        "comment",
        "comments",
        "description",
        "detail",
        "details",
        "message",
        "messages",
        "name",
        "names",
        "note",
        "notes",
        "remark",
        "remarks",
        "text",
        "title",
    }
)
SCHEMA_MATCH_METRIC_TOKENS = frozenset(
    {
        "amount",
        "avg",
        "average",
        "burn",
        "cost",
        "count",
        "delay",
        "duration",
        "fare",
        "ground",
        "hour",
        "hours",
        "kg",
        "l",
        "litre",
        "liter",
        "minute",
        "minutes",
        "pax",
        "price",
        "qty",
        "quantity",
        "rate",
        "revenue",
        "score",
        "time",
        "total",
        "usd",
        "value",
        "volume",
        "weight",
    }
)
SCHEMA_MATCH_DIMENSION_DISPLAY_TOKENS = frozenset(
    {
        "alias",
        "code",
        "display",
        "full",
        "label",
        "locator",
        "name",
        "number",
        "registration",
        "slug",
        "title",
    }
)
SCHEMA_MATCH_DIMENSION_PRIMARY_DISPLAY_TOKENS = frozenset(
    {
        "full",
        "label",
        "name",
        "registration",
        "title",
    }
)
SCHEMA_MATCH_DIMENSION_SECONDARY_DISPLAY_TOKENS = frozenset(
    {
        "alias",
        "code",
        "locator",
        "number",
        "slug",
    }
)
SCHEMA_MATCH_DIMENSION_NOISE_TOKENS = frozenset(
    {
        "backlog",
        "combination",
        "combinations",
        "group",
        "grouped",
        "highest",
        "largest",
        "linked",
        "open",
        "through",
        "total",
    }
)
SCHEMA_MATCH_AGGREGATION_HINT_TOKENS = frozenset(
    {
        "avg",
        "average",
        "count",
        "max",
        "maximum",
        "mean",
        "min",
        "minimum",
        "sum",
        "total",
    }
)
SCHEMA_MATCH_NO_PRUNE_TABLE_LIMIT = 64
SCHEMA_MATCH_SHORTLIST_MIN = 48
SCHEMA_MATCH_SHORTLIST_MAX = 72
SCHEMA_MATCH_SHORTLIST_PER_TERM = 12
SCHEMA_MATCH_SHORTLIST_FILLER_MAX = 12
SECONDARY_TABLE_QUERY_PENALTIES: tuple[tuple[frozenset[str], frozenset[str], float], ...] = (
    (
        frozenset({"audit", "audits", "change", "changes", "history", "log", "logs"}),
        frozenset({"audit", "audits", "change", "changes", "history", "log", "logs", "update"}),
        0.84,
    ),
    (
        frozenset({"request", "requests", "swap", "swaps"}),
        frozenset({"request", "requests", "swap", "swaps"}),
        0.86,
    ),
    (
        frozenset(
            {
                "forecast",
                "forecasts",
                "metric",
                "metrics",
                "run",
                "runs",
                "score",
                "scores",
                "snapshot",
                "snapshots",
            }
        ),
        frozenset(
            {
                "forecast",
                "forecasts",
                "kpi",
                "metric",
                "metrics",
                "optimi",
                "optimise",
                "optimization",
                "optimisation",
                "predict",
                "prediction",
                "score",
                "scores",
                "snapshot",
                "snapshots",
            }
        ),
        0.88,
    ),
)
SCHEMA_MATCH_TEMPORAL_COLUMN_TOKENS = frozenset(
    {
        "at",
        "created",
        "date",
        "detected",
        "ended",
        "opened",
        "recorded",
        "reported",
        "started",
        "time",
        "timestamp",
        "updated",
    }
)
SCHEMA_MATCH_STATUS_COLUMN_TOKENS = frozenset(
    {
        "severity",
        "stage",
        "state",
        "status",
    }
)
SCHEMA_MATCH_BOOLEAN_COLUMN_TOKENS = frozenset(
    {
        "can",
        "has",
        "is",
        "should",
        "was",
        "were",
    }
)
SCHEMA_MATCH_PARTIAL_NAME_TOKENS = frozenset(
    {
        "first",
        "given",
        "last",
        "middle",
    }
)
SCHEMA_MATCH_INCIDENTAL_DETAIL_TOKENS = frozenset(
    {
        "contact",
        "document",
        "email",
        "phone",
    }
)

SEMANTIC_CONCEPT_FAMILIES: dict[str, frozenset[str]] = {
    "backlog": frozenset(
        {"backlog", "open", "pending", "outstanding", "queue", "workorder", "workorders"}
    ),
    "cost": frozenset(
        {
            "cost",
            "costs",
            "expense",
            "expenses",
            "expenditure",
            "payment",
            "payments",
            "price",
            "prices",
            "amount",
        }
    ),
    "customer": frozenset({"customer", "client", "buyer", "account", "consumer"}),
    "date": frozenset({"date", "timestamp", "datetime", "period", "time"}),
    "id": frozenset({"id", "key", "identifier", "number", "code", "ref"}),
    "maintenance": frozenset(
        {"maintenance", "maint", "repair", "repairs", "defect", "defects", "mx"}
    ),
    "order": frozenset({"order", "orders", "workorder", "workorders"}),
    "overdue": frozenset({"overdue", "due", "aging", "aged", "late", "outstanding"}),
    "price": frozenset({"price", "prices", "rate", "unitprice", "unitcost", "tariff"}),
    "product": frozenset(
        {"product", "item", "items", "sku", "article", "good", "goods", "part", "parts"}
    ),
    "quantity": frozenset({"quantity", "qty", "count", "counts", "units", "volume", "amount"}),
    "revenue": frozenset({"revenue", "sales", "income", "receipts", "turnover", "topline"}),
    "variance": frozenset({"variance", "delta", "difference", "deviation"}),
}

TOKEN_TO_CONCEPTS: dict[str, frozenset[str]] = {}
for canonical, family in SEMANTIC_CONCEPT_FAMILIES.items():
    for term in family | {canonical}:
        TOKEN_TO_CONCEPTS[term] = frozenset({*TOKEN_TO_CONCEPTS.get(term, frozenset()), canonical})


@dataclass(frozen=True)
class PreparedSchemaLabel:
    kind: str
    value: str
    normalized: str
    token_sequence: tuple[str, ...]
    tokens: frozenset[str]
    concepts: frozenset[str]
    low_signal_only: bool


@dataclass(frozen=True)
class PreparedSchemaTable:
    source_table: str
    import_target_table: str
    domain: str | None
    imported_row_count: int
    primary_key: tuple[Any, ...]
    columns: tuple[str, ...]
    labels: tuple[PreparedSchemaLabel, ...]
    table_tokens: frozenset[str]
    label_tokens: frozenset[str]
    label_concepts: frozenset[str]
    table_name_phrases: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class PreparedSchemaCatalog:
    tables: tuple[PreparedSchemaTable, ...]
    token_hits: dict[str, frozenset[int]]
    concept_hits: dict[str, frozenset[int]]


def _singularize_token(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    if token.endswith("sses") and len(token) > 5:
        return token[:-2]
    if token.endswith("ses") and len(token) > 4:
        return token[:-1]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


@functools.lru_cache(maxsize=16384)
def _normalize_token(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", value.lower().strip())
    if not normalized:
        return ""
    return _singularize_token(ABBREVIATIONS.get(normalized, normalized))


def _normalize(value: str) -> str:
    """Normalize field name for comparison: lowercase, remove symbols, expand abbreviations."""
    tokens = _identifier_tokens(value)
    if not tokens:
        return ""
    return "".join(tokens)


@functools.lru_cache(maxsize=4096)
def _identifier_tokens(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    parts = re.split(r"[^a-zA-Z0-9]+", expanded)
    tokens: list[str] = []
    for part in parts:
        normalized = _normalize_token(part)
        if normalized:
            tokens.append(normalized)
    if not tokens:
        normalized = _normalize_token(value)
        return (normalized,) if normalized else ()
    return tuple(dict.fromkeys(tokens))


@functools.lru_cache(maxsize=4096)
def _identifier_concepts(value: str) -> frozenset[str]:
    concepts: set[str] = set()
    for token in _identifier_tokens(value):
        concepts.update(TOKEN_TO_CONCEPTS.get(token, ()))
    return frozenset(concepts)


def _format_token_reason(prefix: str, shared: set[str]) -> str:
    tokens = ", ".join(sorted(shared)[:3])
    return f"{prefix} ({tokens})"


def _is_identifier_dominant(tokens: set[str]) -> bool:
    informative_tokens = tokens - GENERIC_MATCH_TOKENS
    business_tokens = informative_tokens - IDENTIFIER_TOKENS
    return bool(informative_tokens & IDENTIFIER_TOKENS) and 0 < len(business_tokens) <= 1


@functools.lru_cache(maxsize=131072)
def _lexical_overlap_score(term: str, label: str) -> float:
    normalized_term = _normalize_token(term)
    normalized_label = _normalize_token(label)
    if len(normalized_term) < 3 or len(normalized_label) < 3:
        return 0.0
    if normalized_term == normalized_label:
        return 1.0

    label_parts = [token for token in _identifier_tokens(label) if len(token) >= 3]
    best_score = 0.0
    for part in label_parts:
        if normalized_term in part:
            if not part.startswith(normalized_term):
                continue
            overlap_ratio = len(normalized_term) / len(part)
            best_score = max(best_score, min(0.94, 0.52 + overlap_ratio * 0.42))
    return best_score


def _common_prefix_length(a: str, b: str) -> int:
    prefix_length = 0
    for char_a, char_b in zip(a, b, strict=False):
        if char_a != char_b:
            break
        prefix_length += 1
    return prefix_length


def _build_schema_query_term_entries(query: str) -> list[dict[str, Any]]:
    raw_tokens = re.findall(r"[a-z0-9]+", query.lower())
    filtered_tokens = [
        token
        for token in raw_tokens
        if len(token) >= 3 and token not in SCHEMA_MATCH_STOP_WORDS and not token.isdigit()
    ]
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []

    def add_entry(term: str, *, weight: float, generic: bool, derived: bool = False) -> None:
        normalized_term = _normalize_token(term)
        if not normalized_term or normalized_term in seen or len(normalized_term) < 3:
            return
        seen.add(normalized_term)
        entries.append(
            {
                "term": normalized_term,
                "weight": weight,
                "generic": generic,
                "derived": derived,
            }
        )

    for token in filtered_tokens:
        normalized_token = _normalize_token(token)
        is_generic = normalized_token in SCHEMA_MATCH_LOW_SIGNAL_TERMS
        add_entry(token, weight=0.2 if is_generic else 1.0, generic=is_generic)

    return entries


def _schema_source_labels(table: dict[str, Any]) -> list[tuple[str, str]]:
    labels: list[tuple[str, str]] = []
    source_table = str(table.get("sourceTable") or "").strip()
    import_target_table = str(table.get("importTargetTable") or "").strip()
    domain = str(table.get("domain") or "").strip()

    def add_table_label(value: str) -> None:
        labels.append(("table", value))
        labels.extend(("table", token) for token in _identifier_tokens(value) if len(token) >= 3)

    if source_table:
        add_table_label(source_table)
    if import_target_table and import_target_table != source_table:
        add_table_label(import_target_table)
    if domain:
        labels.append(("domain", domain))
    for column in table.get("columns") or []:
        if isinstance(column, str) and column.strip():
            labels.append(("column", column.strip()))
    return labels


def _prepare_schema_label(kind: str, value: str) -> PreparedSchemaLabel:
    token_sequence = tuple(token for token in _identifier_tokens(value) if len(token) >= 3)
    tokens = frozenset(token_sequence)
    low_signal_tokens = tokens - IDENTIFIER_TOKENS
    return PreparedSchemaLabel(
        kind=kind,
        value=value,
        normalized=_normalize(value),
        token_sequence=token_sequence,
        tokens=tokens,
        concepts=_identifier_concepts(value),
        low_signal_only=bool(low_signal_tokens) and low_signal_tokens <= LOW_SIGNAL_LABEL_TOKENS,
    )


def prepare_schema_table(table: dict[str, Any]) -> PreparedSchemaTable:
    labels = tuple(
        _prepare_schema_label(kind, value) for kind, value in _schema_source_labels(table)
    )
    source_table = str(table.get("sourceTable") or "").strip()
    import_target_table = str(table.get("importTargetTable") or "").strip()
    table_tokens = frozenset(
        {
            *(_identifier_tokens(source_table) if source_table else ()),
            *(_identifier_tokens(import_target_table) if import_target_table else ()),
        }
    )
    label_tokens = frozenset(token for label in labels for token in label.tokens)
    label_concepts = frozenset(concept for label in labels for concept in label.concepts)
    table_name_phrases = tuple(
        phrase_tokens
        for phrase_tokens in (
            tuple(token for token in _identifier_tokens(source_table) if token),
            tuple(token for token in _identifier_tokens(import_target_table) if token),
        )
        if phrase_tokens
    )
    return PreparedSchemaTable(
        source_table=source_table,
        import_target_table=import_target_table,
        domain=(str(table.get("domain")).strip() or None) if table.get("domain") else None,
        imported_row_count=int(table.get("importedRowCount") or 0),
        primary_key=tuple(table.get("primaryKey") or ()),
        columns=tuple(str(column) for column in (table.get("columns") or ())),
        labels=labels,
        table_tokens=table_tokens,
        label_tokens=label_tokens,
        label_concepts=label_concepts,
        table_name_phrases=table_name_phrases,
    )


def _build_prepared_schema_catalog(
    tables: tuple[PreparedSchemaTable, ...],
) -> PreparedSchemaCatalog:
    token_hits: dict[str, set[int]] = {}
    concept_hits: dict[str, set[int]] = {}
    for table_index, table in enumerate(tables):
        table_tokens: set[str] = set()
        table_concepts: set[str] = set()
        for label in table.labels:
            table_tokens.update(label.tokens)
            table_concepts.update(label.concepts)
        for token in table_tokens:
            token_hits.setdefault(token, set()).add(table_index)
        for concept in table_concepts:
            concept_hits.setdefault(concept, set()).add(table_index)
    return PreparedSchemaCatalog(
        tables=tables,
        token_hits={token: frozenset(indices) for token, indices in token_hits.items()},
        concept_hits={concept: frozenset(indices) for concept, indices in concept_hits.items()},
    )


def prepare_schema_catalog(catalog: list[dict[str, Any]]) -> PreparedSchemaCatalog:
    tables = tuple(prepare_schema_table(table) for table in catalog)
    return _build_prepared_schema_catalog(tables)


def _schema_catalog_signature(catalog: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            str(table.get("sourceTable") or "").strip(),
            str(table.get("importTargetTable") or "").strip(),
            (str(table.get("domain")).strip() or None) if table.get("domain") else None,
            int(table.get("importedRowCount") or 0),
            tuple(table.get("primaryKey") or ()),
            tuple(str(column) for column in (table.get("columns") or ())),
        )
        for table in catalog
    )


@functools.lru_cache(maxsize=32)
def _prepare_schema_catalog_cached(
    signature: tuple[tuple[Any, ...], ...],
) -> PreparedSchemaCatalog:
    tables = tuple(
        prepare_schema_table(
            {
                "sourceTable": source_table,
                "importTargetTable": import_target_table,
                "domain": domain,
                "importedRowCount": imported_row_count,
                "primaryKey": list(primary_key),
                "columns": list(columns),
            }
        )
        for (
            source_table,
            import_target_table,
            domain,
            imported_row_count,
            primary_key,
            columns,
        ) in signature
    )
    return _build_prepared_schema_catalog(tables)


@functools.lru_cache(maxsize=4096)
def _normalized_query_tokens(value: str) -> tuple[str, ...]:
    raw_tokens = re.findall(r"[a-z0-9]+", value.lower())
    normalized_tokens = [_normalize_token(token) for token in raw_tokens]
    return tuple(token for token in normalized_tokens if token)


def _contextual_table_phrase_bonus_from_names(query: str, table_names: tuple[str, ...]) -> float:
    query_tokens = _normalized_query_tokens(query)
    if not query_tokens:
        return 0.0

    table_name_phrases = tuple(
        phrase_tokens
        for phrase_tokens in (
            tuple(token for token in _identifier_tokens(table_name) if token)
            for table_name in table_names
        )
        if phrase_tokens
    )
    return _contextual_table_phrase_bonus_from_tokens(query_tokens, table_name_phrases)


def _contextual_table_phrase_bonus_from_tokens(
    query_tokens: tuple[str, ...],
    table_name_phrases: tuple[tuple[str, ...], ...],
) -> float:
    if not query_tokens:
        return 0.0

    best_bonus = 0.0
    for phrase_tokens in table_name_phrases:
        phrase_length = len(phrase_tokens)
        for index in range(len(query_tokens) - phrase_length + 1):
            if query_tokens[index : index + phrase_length] != phrase_tokens:
                continue
            cue_index = index - 1
            if cue_index >= 0 and query_tokens[cue_index] in TABLE_CONTEXT_CUES:
                if phrase_length >= 2:
                    best_bonus = max(best_bonus, 0.5)
                else:
                    best_bonus = max(best_bonus, 0.42)
    return best_bonus


def _column_phrase_bonus(
    query_tokens: tuple[str, ...],
    label: PreparedSchemaLabel,
) -> float:
    if label.kind != "column" or label.low_signal_only:
        return 0.0
    phrase_tokens = label.token_sequence
    if len(phrase_tokens) < 2:
        return 0.0
    if not set(phrase_tokens) - (GENERIC_MATCH_TOKENS | IDENTIFIER_TOKENS):
        return 0.0
    phrase_length = len(phrase_tokens)
    for index in range(len(query_tokens) - phrase_length + 1):
        if query_tokens[index : index + phrase_length] == phrase_tokens:
            if phrase_length >= 3:
                return 0.45
            return 0.32
    for start_index, query_token in enumerate(query_tokens):
        if query_token != phrase_tokens[0]:
            continue
        phrase_index = 1
        query_index = start_index + 1
        while query_index < len(query_tokens) and phrase_index < phrase_length:
            if query_tokens[query_index] == phrase_tokens[phrase_index]:
                phrase_index += 1
            query_index += 1
        if phrase_index == phrase_length and (query_index - start_index) <= phrase_length + 2:
            if phrase_length >= 3:
                return 0.36
            return 0.28
    return 0.0
