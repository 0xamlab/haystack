"""
training/semantic/build_vocab.py — Build the token vocabulary for the semantic model.

Collects tokens from:
  1. All column names in a provided schema dict
  2. All query strings in the seed dataset (build_dataset.py)
  3. All alias expansions in the combined alias table

Produces:
  vocab.json   — {"token": id, ...} mapping (id = index in sorted list)
  id_to_token.json — ["token0", "token1", ...] (the reverse map)

Usage:
    python3 training/semantic/build_vocab.py \
        --schema  path/to/schema.json \
        --seed    training/semantic/seed_queries.json \
        --aliases path/to/domain_aliases.json \
        --out-dir training/semantic/artifacts/

Schema JSON format:
    {"POS": [["UNIT_PRICE","unit_measure"], ...], "Totals": [...]}

Domain aliases JSON (optional):
    {"ppa": ["per","person","average"], "arr": ["annual","recurring","revenue"]}

Self-test:
    python3 training/semantic/build_vocab.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mojo.engine.vector_kernels.tokenizer import (
    expand_tokens,
    merge_aliases,
    tokenize_name,
)

# ── Built-in seed tokens (always included regardless of schema) ───────────────

_SEED_TOKENS: list[str] = [
    # Aggregation keywords
    "count", "total", "sum", "average", "avg", "mean", "max", "min",
    "maximum", "minimum", "highest", "lowest",
    # Meta-query keywords
    "how", "many", "number", "of", "distinct", "unique", "different",
    # Modifier keywords
    "per", "by", "for", "each", "grouped", "group",
    # Common measure words
    "revenue", "sales", "cost", "price", "amount", "value", "rate",
    "quantity", "qty", "units", "volume",
    # Common dimension words
    "customer", "date", "time", "period", "region", "category", "type",
    "status", "name", "id", "code",
    # Entity nouns (row-level)
    "orders", "order", "customers", "servers", "server", "employees",
    "employee", "transactions", "transaction", "items", "products",
    # Hospitality domain
    "guests", "guest", "covers", "diners", "tips", "gratuity",
    "beverage", "food", "alcohol",
    # Special tokens
    "<PAD>", "<UNK>",
]


def build_vocab_from_sources(
    schema:       dict[str, list[list[str]]],
    extra_tokens: list[str] | None = None,
    domain_aliases: dict[str, list[str]] | None = None,
) -> tuple[dict[str, int], list[str]]:
    """
    Build token_to_id and id_to_token from schema + seed tokens.

    Returns (token_to_id, id_to_token).
    """
    combined = merge_aliases(domain_aliases)
    all_tokens: set[str] = set()

    # Add seed tokens
    for tok in _SEED_TOKENS:
        all_tokens.add(tok.lower())

    if extra_tokens:
        for tok in extra_tokens:
            all_tokens.add(tok.lower())

    # Add all tokens from schema column names (expanded with combined aliases)
    for _src, cols in schema.items():
        for col_entry in cols:
            col_name = col_entry[0] if isinstance(col_entry, list | tuple) else col_entry
            tokens = tokenize_name(col_name)
            for tok, _ in expand_tokens(tokens, combined):
                all_tokens.add(tok)

    # Add alias expansions
    for k, vs in combined.items():
        all_tokens.add(k.lower())
        for v in vs:
            all_tokens.add(v.lower())

    # Sort for stable ids; put special tokens first
    special = ["<PAD>", "<UNK>"]
    regular = sorted(t for t in all_tokens if t not in special)
    id_to_token = special + regular
    token_to_id = {tok: i for i, tok in enumerate(id_to_token)}

    return token_to_id, id_to_token


def main():
    parser = argparse.ArgumentParser(description="Build semantic model vocabulary")
    parser.add_argument("--schema",   type=Path, help="Schema JSON file")
    parser.add_argument("--seed",     type=Path, help="Extra seed query JSON list")
    parser.add_argument("--aliases",  type=Path, help="Domain aliases JSON")
    parser.add_argument("--out-dir",  type=Path, default=Path("training/semantic/artifacts"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _run_self_test()
        return

    schema: dict = {}
    if args.schema and args.schema.exists():
        schema = json.loads(args.schema.read_text())

    extra_tokens: list[str] = []
    if args.seed and args.seed.exists():
        seed_data = json.loads(args.seed.read_text())
        for item in seed_data:
            q = item.get("query", "")
            extra_tokens.extend(tokenize_name(q))

    domain_aliases: dict = {}
    if args.aliases and args.aliases.exists():
        domain_aliases = json.loads(args.aliases.read_text())

    token_to_id, id_to_token = build_vocab_from_sources(schema, extra_tokens, domain_aliases)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vocab.json").write_text(json.dumps(token_to_id, indent=2))
    (args.out_dir / "id_to_token.json").write_text(json.dumps(id_to_token, indent=2))

    print(f"Vocab size: {len(id_to_token)} tokens")
    print(f"Written to: {args.out_dir}")


def _run_self_test():
    schema = {
        "POS": [["UNIT_PRICE", "unit_measure"], ["EXT_PRICE", "derived_measure"],
                ["QTY", "base_measure"], ["ORDER_DATE", "other"], ["CUSTOMER_NAME", "other"]],
        "Totals": [["Net_Sales", "derived_measure"], ["Guests", "base_measure"], ["PPA", "ratio"]],
    }
    domain_aliases = {"ppa": ["per", "person", "average"]}

    tok_to_id, id_to_tok = build_vocab_from_sources(schema, domain_aliases=domain_aliases)

    assert "<PAD>" in tok_to_id and tok_to_id["<PAD>"] == 0
    assert "<UNK>" in tok_to_id and tok_to_id["<UNK>"] == 1
    assert "ppa"    in tok_to_id
    assert "per"    in tok_to_id
    assert "person" in tok_to_id
    assert "average" in tok_to_id
    assert "guests" in tok_to_id
    assert "count"  in tok_to_id
    assert len(id_to_tok) == len(tok_to_id)

    # No schema → should still work (seed tokens only)
    t2, i2 = build_vocab_from_sources({})
    assert len(i2) >= len(_SEED_TOKENS)

    print(f"Self-test PASSED  vocab_size={len(id_to_tok)}")


if __name__ == "__main__":
    main()
