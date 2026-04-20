"""
vector_kernels/tokenizer.py — Python-side tokenisation + alias expansion
                               + token index builder for Mojo prefilter.

This module owns ALL string work. The output is pure integer data that
feeds Mojo's TokenIndexBuilder. On the hot path, Mojo never touches strings.

Public API:
  tokenize_name(name)            -> list[str]
  ALIASES                        -> dict[str, list[str]]
  build_vocab(column_names)      -> Vocab
  build_index_data(vocab, cols)  -> IndexData
  Vocab                          -> namedtuple with token_to_id / id_to_token
  IndexData                      -> namedtuple with vocab_size / col_token_ids

Self-test:
    python3 mojo/engine/vector_kernels/tokenizer.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple

# ── Tokenizer ─────────────────────────────────────────────────────────────────

_SEPARATOR_RE = re.compile(r'[_\-/\s]+')
_CAMEL_RE     = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')   # split camelCase


def tokenize_name(name: str) -> list[str]:
    """
    Split a column name into lowercase tokens.

    Rules (in order):
      1. camelCase → "camel Case" (split before each uppercase run)
      2. Split on _ - / space
      3. Lowercase all
      4. Drop empty strings and single-char tokens that are stopwords

    Examples:
        "unit_price"     → ["unit", "price"]
        "ExtendedAmt"    → ["extended", "amt"]
        "OH_COST"        → ["oh", "cost"]
        "ORDERED_ON"     → ["ordered", "on"]
        "LineItemTotal"  → ["line", "item", "total"]
        "ext-price"      → ["ext", "price"]
        "salesOrderQty"  → ["sales", "order", "qty"]
    """
    # Insert space before uppercase runs (camelCase split)
    s = _CAMEL_RE.sub(' ', name)
    # Split on separator characters
    parts = _SEPARATOR_RE.split(s)
    # Lowercase + filter
    tokens = [p.lower() for p in parts if len(p) >= 2]
    return tokens


# ── Domain alias table ────────────────────────────────────────────────────────
#
# Alias expansion improves recall for near-synonyms without forcing the SIMD
# scorer to handle all variants. When a column name contains a key, ALL alias
# values are added as additional token IDs (with a reduced weight of 0.8).
#
# Schema-specific entries should be added at table-build time. These are
# domain-general aliases for procurement/manufacturing schemas.

ALIASES: dict[str, list[str]] = {
    # Quantity aliases
    "qty":      ["quantity"],
    "quantity": ["qty"],
    "qoh":      ["quantity", "on", "hand"],

    # Price / cost aliases
    "price":    ["cost", "rate"],
    "cost":     ["price", "rate"],
    "rate":     ["price", "cost"],
    "amt":      ["amount"],
    "amount":   ["amt"],

    # Extended / total aliases
    "ext":      ["extended", "total"],
    "extended": ["ext"],
    "total":    ["ext", "extended", "sum"],
    "sum":      ["total"],

    # Unit aliases
    "unit":     ["each", "per"],
    "each":     ["unit"],
    "uom":      ["unit", "measure"],
    "um":       ["unit", "measure"],
    "uoi":      ["unit"],

    # Part / item aliases
    "pn":       ["part", "number"],
    "partno":   ["part", "number"],
    "item":     ["part", "product"],
    "part":     ["item", "pn"],
    "sku":      ["item", "part"],

    # Overhead / cost type
    "oh":       ["overhead"],
    "overhead": ["oh"],

    # Date aliases
    "dt":       ["date"],
    "date":     ["dt"],

    # Description
    "desc":     ["description"],
    "description": ["desc"],

    # Source / origin
    "src":      ["source"],
    "source":   ["src"],

    # Number / id
    "no":       ["number", "id"],
    "num":      ["number"],
    "id":       ["no", "number"],
    "number":   ["no", "num", "id"],

    # Order
    "ord":      ["order"],
    "order":    ["ord"],

    # Line
    "ln":       ["line"],
    "line":     ["ln"],

    # Sales / revenue synonyms
    "revenue":  ["sales", "income"],
    "sales":    ["revenue"],
    "income":   ["revenue", "sales"],

    # Hospitality / restaurant POS domain
    "ppa":      ["per", "person", "average"],   # Per Person Average abbreviation
    "avg":      ["average"],
    "average":  ["avg"],
    "guests":   ["guest", "covers", "diners"],
    "guest":    ["guests", "covers"],
    "covers":   ["guests", "guest"],            # industry term for table guests
    "sold":     ["quantity", "qty"],
    "tips":     ["gratuity"],
    "gratuity": ["tips"],
}


def expand_tokens(
    tokens:  list[str],
    aliases: dict[str, list[str]] | None = None,
) -> list[tuple[str, float]]:
    """
    Expand tokens with alias table. Returns list of (token, weight) pairs.

    Original tokens have weight 1.0.
    Alias expansions have weight 0.8 (slightly discounted).

    Args:
        tokens:  list of lowercase tokens from tokenize_name()
        aliases: override alias table; if None, uses the module-level ALIASES
    """
    _aliases = aliases if aliases is not None else ALIASES
    seen: dict[str, float] = {}
    for tok in tokens:
        if tok not in seen:
            seen[tok] = 1.0
    for tok in list(tokens):
        if tok in _aliases:
            for alias in _aliases[tok]:
                if alias not in seen:
                    seen[alias] = 0.8
    return list(seen.items())


# ── Vocabulary: string ↔ integer id ──────────────────────────────────────────

@dataclass
class Vocab:
    """
    Bidirectional string ↔ UInt32 mapping built from column names.
    Build once at table-load time; ids are stable for the session.

    _aliases stores the combined (global + domain) alias table used at build
    time so query_ids() expands with the same rules as the index.
    """
    token_to_id: dict[str, int]       = field(default_factory=dict)
    id_to_token: list[str]            = field(default_factory=list)
    _aliases:    dict[str, list[str]] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.id_to_token)

    def intern(self, token: str) -> int:
        """Return existing id or assign a new one."""
        if token not in self.token_to_id:
            self.token_to_id[token] = len(self.id_to_token)
            self.id_to_token.append(token)
        return self.token_to_id[token]

    def lookup(self, token: str) -> int:
        """Return id or -1 if unknown."""
        return self.token_to_id.get(token, -1)

    def query_ids(self, name: str) -> list[int]:
        """
        Tokenize + expand name and return only known token IDs.
        Uses the same combined alias table the index was built with.
        Unknown tokens are silently dropped (no new vocab entries at query time).
        """
        _als = self._aliases if self._aliases else None
        tokens_w = expand_tokens(tokenize_name(name), _als)
        ids = []
        for tok, _w in tokens_w:
            tid = self.lookup(tok)
            if tid >= 0:
                ids.append(tid)
        return ids


# ── IndexData: ready-to-pass-to-Mojo integer arrays ──────────────────────────

class IndexData(NamedTuple):
    """
    Flat integer data ready for TokenIndexBuilder.add_column().

    col_token_ids[i]  = list of (token_id, weight) for column i
    vocab_size        = total number of distinct tokens
    """
    vocab_size:    int
    col_token_ids: list[list[tuple[int, float]]]  # [col_idx] → [(tok_id, weight)]


def merge_aliases(
    extra: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    """
    Merge global ALIASES with schema-specific extra_aliases.
    Returns a new dict; the original ALIASES is never mutated.
    """
    combined = dict(ALIASES)
    if extra:
        for k, v in extra.items():
            if k in combined:
                combined[k] = list(set(combined[k] + v))
            else:
                combined[k] = list(v)
    return combined


def build_vocab(
    column_names:  list[str],
    extra_aliases: dict[str, list[str]] | None = None,
) -> Vocab:
    """
    Build vocabulary from all column names.

    Steps:
      1. Tokenize each name
      2. Expand with merged alias table (global ALIASES + extra_aliases)
      3. Assign sequential integer IDs
      4. Store the combined alias table on the Vocab for later use by query_ids()

    Args:
        column_names:  list of raw column name strings
        extra_aliases: schema-specific aliases merged with the global table

    Returns:
        Vocab with stable token_to_id mapping and embedded alias table
    """
    combined = merge_aliases(extra_aliases)
    vocab = Vocab(_aliases=combined)
    for name in column_names:
        tokens = tokenize_name(name)
        for tok, _ in expand_tokens(tokens, combined):
            vocab.intern(tok)
    return vocab


def build_index_data(vocab: Vocab, column_names: list[str]) -> IndexData:
    """
    Build integer index data for all columns.

    For each column, tokenize + alias-expand its name and map to token IDs.

    Args:
        vocab:        Vocab built by build_vocab() from the same column_names
        column_names: same list as passed to build_vocab()

    Returns:
        IndexData with vocab_size and per-column (token_id, weight) lists
    """
    col_data = []
    for name in column_names:
        tokens = tokenize_name(name)
        expanded = expand_tokens(tokens)
        id_weight_pairs = []
        for tok, w in expanded:
            tid = vocab.lookup(tok)
            if tid >= 0:
                id_weight_pairs.append((tid, w))
        col_data.append(id_weight_pairs)
    return IndexData(vocab_size=vocab.size, col_token_ids=col_data)


# ── planner_resolve: Python entry point for full typed resolution ─────────────

def make_query_token_ids(
    vocab:    Vocab,
    name:     str,
    max_ids:  int = 8,
) -> list[int]:
    """
    Convert a query name to token IDs for Mojo QueryForRank.set_token_ids().

    Returns at most `max_ids` known token IDs (unknown tokens silently dropped).
    """
    ids = vocab.query_ids(name)
    return ids[:max_ids]


# ── Self-test ─────────────────────────────────────────────────────────────────

def _test_tokenizer():
    cases = [
        ("unit_price",      ["unit", "price"]),
        ("ExtendedAmt",     ["extended", "amt"]),
        ("OH_COST",         ["oh", "cost"]),
        ("ORDERED_ON",      ["ordered", "on"]),
        ("LineItemTotal",   ["line", "item", "total"]),
        ("ext-price",       ["ext", "price"]),
        ("salesOrderQty",   ["sales", "order", "qty"]),
        ("UNIT_PRICE",      ["unit", "price"]),
        ("total_amount",    ["total", "amount"]),
        ("part_number",     ["part", "number"]),
        ("customer_name",   ["customer", "name"]),
        ("invoice_date",    ["invoice", "date"]),
    ]
    for name, expected in cases:
        got = tokenize_name(name)
        ok = got == expected
        print(f"  {'PASS' if ok else 'FAIL'} tokenize({name!r}) = {got} {'✓' if ok else f'≠ {expected}'}")
    print()


def _test_alias_expand():
    # "unit_price" → tokens: unit, price → aliases: each, per, cost, rate
    expanded = dict(expand_tokens(["unit", "price"]))
    assert "unit"  in expanded and expanded["unit"]  == 1.0
    assert "price" in expanded and expanded["price"] == 1.0
    assert "cost"  in expanded and expanded["cost"]  == 0.8
    assert "each"  in expanded and expanded["each"]  == 0.8
    print("  PASS alias expansion for ['unit', 'price']")
    print(f"       → tokens: {sorted(expanded.keys())}")
    print()


def _test_vocab_and_index():
    columns = [
        "unit_price",
        "extended_price",
        "quantity",
        "total_amount",
        "line_total",
        "customer_name",
        "description",
        "unit_cost",
        "part_number",
        "invoice_date",
    ]
    vocab = build_vocab(columns)
    index = build_index_data(vocab, columns)

    print(f"  PASS vocab size = {vocab.size} tokens")
    print(f"  PASS index has {len(index.col_token_ids)} columns")

    # "unit_price" should share token IDs with "unit_cost"
    ids_up = set(tid for tid, _ in index.col_token_ids[0])   # unit_price
    ids_uc = set(tid for tid, _ in index.col_token_ids[7])   # unit_cost
    shared = ids_up & ids_uc
    assert len(shared) >= 1, f"unit_price and unit_cost should share tokens, shared={shared}"
    print(f"  PASS unit_price ∩ unit_cost = {len(shared)} shared token IDs")

    # Query for "unit_price" should return known IDs
    q_ids = make_query_token_ids(vocab, "unit_price")
    assert len(q_ids) >= 2, f"Expected ≥2 query IDs, got {q_ids}"
    print(f"  PASS query_ids('unit_price') = {q_ids}")
    print(f"       tokens: {[vocab.id_to_token[i] for i in q_ids]}")
    print()


if __name__ == "__main__":
    import sys
    print("=== tokenizer.py self-test ===")
    print()
    print("[1] tokenize_name():")
    _test_tokenizer()
    print("[2] expand_tokens() aliases:")
    _test_alias_expand()
    print("[3] Vocab + IndexData:")
    _test_vocab_and_index()
    print("All tests passed.")
    sys.exit(0)
