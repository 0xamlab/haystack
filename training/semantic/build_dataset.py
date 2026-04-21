"""
training/semantic/build_dataset.py — Generate labeled training examples.

Produces train.jsonl where each line is:
    {"query": "...", "tokens": [ids...], "intent": 0, "agg": 0, "family": 0}

Label enumerations (must match semantic_types.mojo constants):
    intent:  0=column_like  1=meta_query  2=weak_semantic  3=unsupported
    agg:     0=none  1=count  2=sum  3=avg  4=min  5=max
    family:  0=measure  1=dimension  2=date  3=entity

Sources of training examples:
  1. Hardcoded seed set covering known resolution patterns
  2. Augmentation: prefix/suffix variants of each seed
  3. Schema-derived: column names → column_like + inferred family
  4. Optional: import from existing test files (--from-tests flag)

Usage:
    python3 training/semantic/build_dataset.py \
        --vocab  training/semantic/artifacts/vocab.json \
        --schema path/to/schema.json \
        --out    training/semantic/train.jsonl

Self-test:
    python3 training/semantic/build_dataset.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mojo.engine.vector_kernels.tokenizer import expand_tokens, merge_aliases, tokenize_name

# ── Intent / Agg / Family label constants (mirror semantic_types.mojo) ────────

INTENT_COLUMN_LIKE   = 0
INTENT_META_QUERY    = 1
INTENT_WEAK_SEMANTIC = 2
INTENT_UNSUPPORTED   = 3

AGG_NONE  = 0
AGG_COUNT = 1
AGG_SUM   = 2
AGG_AVG   = 3
AGG_MIN   = 4
AGG_MAX   = 5

FAMILY_MEASURE   = 0
FAMILY_DIMENSION = 1
FAMILY_DATE      = 2
FAMILY_ENTITY    = 3


# ── Hardcoded seed examples ───────────────────────────────────────────────────
# (query, intent, agg, family)

_SEED: list[tuple[str, int, int, int]] = [
    # ── Meta-query / count intent ──────────────────────────────────────────
    ("how many orders",         INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("how many customers",      INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("how many servers",        INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("how many guests",         INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("number of orders",        INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("number of servers",       INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("number of customers",     INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("count of orders",         INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("row count",               INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("total count",             INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("server count",            INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("order count",             INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("customer count",          INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("unique customers",        INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),
    ("distinct orders",         INTENT_META_QUERY,  AGG_COUNT, FAMILY_ENTITY),

    # ── Measure columns — SUM intent ──────────────────────────────────────
    ("total revenue",           INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("total net sales",         INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("total sales",             INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("total extended price",    INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("total cost",              INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("food revenue",            INTENT_COLUMN_LIKE, AGG_SUM,   FAMILY_MEASURE),
    ("beverage sales",          INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("alcohol net sales",       INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("items sold",              INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("quantity sold",           INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("extended price",          INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("unit price",              INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("tips",                    INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("gratuity",                INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),
    ("food tips",               INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_MEASURE),

    # ── Measure columns — AVG intent ──────────────────────────────────────
    ("average order time",      INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("avg order time",          INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("average price",           INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("per person average",      INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("ppa",                     INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("food per person average", INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),
    ("average sold per guest",  INTENT_COLUMN_LIKE, AGG_AVG,   FAMILY_MEASURE),

    # ── Measure columns — MIN/MAX ─────────────────────────────────────────
    ("max order value",         INTENT_COLUMN_LIKE, AGG_MAX,   FAMILY_MEASURE),
    ("maximum price",           INTENT_COLUMN_LIKE, AGG_MAX,   FAMILY_MEASURE),
    ("min cost",                INTENT_COLUMN_LIKE, AGG_MIN,   FAMILY_MEASURE),
    ("minimum order time",      INTENT_COLUMN_LIKE, AGG_MIN,   FAMILY_MEASURE),
    ("highest revenue",         INTENT_COLUMN_LIKE, AGG_MAX,   FAMILY_MEASURE),
    ("lowest price",            INTENT_COLUMN_LIKE, AGG_MIN,   FAMILY_MEASURE),

    # ── Dimension columns ─────────────────────────────────────────────────
    ("customer name",           INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),
    ("order status",            INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),
    ("customer id",             INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),
    ("product name",            INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),
    ("category",                INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),
    ("region",                  INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DIMENSION),

    # ── Date columns ──────────────────────────────────────────────────────
    ("order date",              INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),
    ("transaction date",        INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),
    ("date",                    INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),
    ("period",                  INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),
    ("year",                    INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),
    ("month",                   INTENT_COLUMN_LIKE, AGG_NONE,  FAMILY_DATE),

    # ── Weak / unsupported ────────────────────────────────────────────────
    ("show me",                 INTENT_UNSUPPORTED, AGG_NONE,  FAMILY_MEASURE),
    ("compare",                 INTENT_UNSUPPORTED, AGG_NONE,  FAMILY_MEASURE),
    ("trend",                   INTENT_WEAK_SEMANTIC, AGG_NONE, FAMILY_MEASURE),
    ("breakdown",               INTENT_WEAK_SEMANTIC, AGG_NONE, FAMILY_DIMENSION),
    ("analysis",                INTENT_WEAK_SEMANTIC, AGG_NONE, FAMILY_MEASURE),
]


# ── Augmentation: simple prefix/suffix variants ───────────────────────────────

_PREFIXES = ["food ", "beverage ", "alcohol ", "total ", "daily ", "weekly ", "monthly "]
_COUNT_VARIANTS = ["how many {}", "number of {}", "count of {}", "{} count"]


_Example = tuple[str, int, int, int, "list[str] | None"]


def _augment(seed: list[_Example]) -> list[_Example]:
    augmented = list(seed)
    for query, intent, agg, family, col_tokens in seed:
        # Count variants for entity-like queries
        if intent == INTENT_META_QUERY and "how many" not in query and "number of" not in query:
            for tmpl in _COUNT_VARIANTS:
                for tok in tokenize_name(query):
                    if len(tok) > 3:
                        aug = tmpl.format(tok + "s")
                        augmented.append((aug, INTENT_META_QUERY, AGG_COUNT, FAMILY_ENTITY, None))
                        break
        # Prefix variants for column-like measure queries
        if intent == INTENT_COLUMN_LIKE and family == FAMILY_MEASURE:
            for pfx in _PREFIXES[:3]:
                # Preserve col_tokens so augmented variants still align to the same column
                augmented.append((pfx + query, intent, agg, family, col_tokens))
    return augmented


def _schema_examples(
    schema: dict[str, list],
    domain_aliases: dict[str, list[str]] | None = None,
    max_per_family: int | None = None,
) -> list[tuple[str, int, int, int, list[str]]]:
    """
    Generate column_like examples from every column in the schema.

    Returns 5-tuples: (query, intent, agg, family, col_name_tokens)

    col_name_tokens — raw tokens of the original column name.
    Used as contrastive alignment target: train the model to embed
    "total revenue" close to "net_sales" in the same vector space.

    Parameters
    ----------
    max_per_family : int | None
        If set, cap the number of examples per family label.  Use for large
        schemas (millions of columns) to keep training time bounded — the model
        learns an embedding space, not a per-column classifier, so representative
        sampling is sufficient.  Column embeddings for ALL columns are computed
        at registration time via fast_resolver.embed(), which is O(tokens × D)
        and needs no training.
    """
    examples: list[tuple[str, int, int, int, list[str]]] = []
    family_counts: dict[int, int] = {}
    combined = merge_aliases(domain_aliases)
    date_tokens = {"date", "time", "period", "year", "month", "day"}
    measure_roles = {"derived_measure", "base_measure", "unit_measure", "ratio"}
    for _src, cols in schema.items():
        for col_entry in cols:
            col_name = col_entry[0] if isinstance(col_entry, list | tuple) else col_entry
            role = (
                col_entry[1]
                if isinstance(col_entry, list | tuple) and len(col_entry) > 1
                else "other"
            )
            tokens = tokenize_name(col_name)
            # Build natural query form by expanding the column name
            expanded = [token for token, _ in expand_tokens(tokens, combined)]
            query = " ".join(expanded)
            # Infer family from role and tokens
            tset = set(tokens)
            if tset & date_tokens:
                family = FAMILY_DATE
            elif role in measure_roles:
                family = FAMILY_MEASURE
            elif role == "other":
                family = FAMILY_DIMENSION
            else:
                family = FAMILY_MEASURE
            # Honour per-family cap for large schemas
            if max_per_family is not None:
                if family_counts.get(family, 0) >= max_per_family:
                    continue
                family_counts[family] = family_counts.get(family, 0) + 1
            # col_name_tokens is the contrastive alignment target
            examples.append((query, INTENT_COLUMN_LIKE, AGG_NONE, family, tokens))
    return examples


def tokenize_example(
    query: str,
    token_to_id: dict[str, int],
    domain_aliases: dict[str, list[str]] | None = None,
) -> list[int]:
    """Tokenize a query and return known token IDs (UNK id=1 for unknowns)."""
    combined = merge_aliases(domain_aliases)
    unk = token_to_id.get("<UNK>", 1)
    tokens = tokenize_name(query)
    ids: list[int] = []
    for tok, _ in expand_tokens(tokens, combined):
        ids.append(token_to_id.get(tok, unk))
    return ids or [unk]


def _tokenize_col_tokens(
    col_tokens: list[str],
    token_to_id: dict[str, int],
) -> list[int]:
    """Map raw column-name token strings to vocab IDs."""
    unk = token_to_id.get("<UNK>", 1)
    return [token_to_id.get(t, unk) for t in col_tokens] or [unk]


def build_dataset(
    vocab:           dict[str, int],
    schema:          dict | None = None,
    domain_aliases:  dict[str, list[str]] | None = None,
    augment:         bool = True,
    max_per_family:  int | None = 500,
) -> list[dict]:
    """
    Build the full training dataset.

    Returns list of dicts:
        {"query", "tokens", "intent", "agg", "family",
         "col_tokens": list[int] | None}

    col_tokens — vocab IDs for the target column name.  Present only for
    schema-derived examples; None for seed/augmented examples that have
    no specific column alignment target.  Used by the training loop to
    compute contrastive cosine loss between query and column embeddings.

    Parameters
    ----------
    max_per_family : int | None
        Cap on schema-derived examples per family label (default 500).
        For schemas with millions of columns this prevents the dataset from
        growing unbounded — the model learns an embedding space, not a
        per-column classifier, so representative sampling is sufficient.
        Column embeddings for all columns are computed at registration time
        via fast_resolver.embed(), which requires no training examples.
        Set to None to include every column (for small schemas only).
    """
    # Normalize _SEED 4-tuples → 5-tuples with col_tokens=None
    examples: list[_Example] = [(q, i, a, f, None) for q, i, a, f in _SEED]

    if schema:
        examples += _schema_examples(schema, domain_aliases, max_per_family=max_per_family)

    if augment:
        examples = _augment(examples)

    # Deduplicate by query string, keeping first occurrence
    seen_queries: set[str] = set()
    unique: list[_Example] = []
    for ex in examples:
        qn = ex[0].strip().lower()
        if qn not in seen_queries:
            seen_queries.add(qn)
            unique.append(ex)

    records = []
    for query, intent, agg, family, col_tokens in unique:
        tids = tokenize_example(query, vocab, domain_aliases)
        ctids = _tokenize_col_tokens(col_tokens, vocab) if col_tokens is not None else None
        records.append({
            "query":      query,
            "tokens":     tids,
            "intent":     intent,
            "agg":        agg,
            "family":     family,
            "col_tokens": ctids,
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="Build semantic training dataset")
    parser.add_argument("--vocab",   type=Path, default=None, help="vocab.json from build_vocab.py")
    parser.add_argument("--schema",  type=Path, help="Schema JSON file")
    parser.add_argument("--aliases", type=Path, help="Domain aliases JSON")
    parser.add_argument("--out",     type=Path, default=Path("training/semantic/train.jsonl"))
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--self-test",  action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    if not args.vocab:
        parser.error("--vocab is required")
    vocab = json.loads(args.vocab.read_text())
    schema: dict = {}
    if args.schema and args.schema.exists():
        schema = json.loads(args.schema.read_text())
    domain_aliases: dict = {}
    if args.aliases and args.aliases.exists():
        domain_aliases = json.loads(args.aliases.read_text())

    records = build_dataset(vocab, schema, domain_aliases, augment=not args.no_augment)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    intent_counts = [0] * 4
    for r in records:
        intent_counts[r["intent"]] += 1
    print(f"Dataset: {len(records)} examples")
    print(f"  column_like={intent_counts[0]}  meta_query={intent_counts[1]}"
          f"  weak={intent_counts[2]}  unsupported={intent_counts[3]}")
    print(f"Written to: {args.out}")


def _run_self_test():
    from training.semantic.build_vocab import build_vocab_from_sources
    schema = {
        "POS": [["UNIT_PRICE", "unit_measure"], ["EXT_PRICE", "derived_measure"],
                ["ORDER_DATE", "other"], ["CUSTOMER_NAME", "other"]],
    }
    domain_aliases = {"ppa": ["per", "person", "average"]}
    tok_to_id, _ = build_vocab_from_sources(schema, domain_aliases=domain_aliases)

    records = build_dataset(tok_to_id, schema, domain_aliases, augment=True)
    assert len(records) > 0

    # Check at least one meta-query example
    meta_examples = [r for r in records if r["intent"] == INTENT_META_QUERY]
    assert len(meta_examples) >= 5, f"Expected ≥5 meta examples, got {len(meta_examples)}"

    # Check tokens are valid ids (all non-negative ints)
    for r in records:
        assert all(isinstance(t, int) and t >= 0 for t in r["tokens"]), \
            f"Bad query token ids in: {r['query']}"
        if r["col_tokens"] is not None:
            assert all(isinstance(t, int) and t >= 0 for t in r["col_tokens"]), \
                f"Bad col_tokens in: {r['query']}"

    # Schema-derived examples must carry col_tokens
    schema_examples = [r for r in records if r["col_tokens"] is not None]
    assert len(schema_examples) >= len(schema["POS"]), (
        f"Expected ≥{len(schema['POS'])} schema examples with col_tokens, "
        f"got {len(schema_examples)}"
    )

    print(
        f"Self-test PASSED  {len(records)} examples  "
        f"{len(meta_examples)} meta-query  "
        f"{len(schema_examples)} with col_tokens"
    )


if __name__ == "__main__":
    main()
