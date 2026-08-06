"""
column_scorer.mojo — Mojo-backed lexical + semantic column scoring.

Augments fuzzy.mojo with richer signals for matching a natural-language
hint (e.g. "unit cost") against a candidate column name (e.g. "UNIT_COST").

Public API:
  score_token_overlap  — Jaccard similarity on whitespace/underscore tokens
  score_ngram_overlap  — Dice coefficient on character n-grams
  score_prefix_match   — Fraction of hint covered by a shared prefix
  score_column_hint    — Weighted composite: token + ngram + prefix

Design constraints:
  - Zero domain knowledge hardcoded here.  Synonym tables live in the
    Python bridge so they can be extended without recompiling Mojo.
  - All inputs are already lower-cased and normalised by the Python caller.
  - Scores are in [0, 1].  score_column_hint caps at 1.0.
"""


# ── helpers ────────────────────────────────────────────────────────────────────


def _to_tokens(s: String) -> List[String]:
    """Split on underscores (95), spaces (32), and hyphens (45)."""
    var result = List[String]()
    var current = String("")

    var s_bytes = s.as_bytes()
    var n = len(s_bytes)

    for i in range(n):
        var b = s_bytes[i]
        if b == 95 or b == 32 or b == 45:
            if len(current) > 0:
                result.append(current)
                current = String("")
        else:
            current = current + chr(Int(b))

    if len(current) > 0:
        result.append(current)

    return result^


def _count_shared_tokens(a_tokens: List[String], b_tokens: List[String]) -> Int:
    """Count how many tokens from a appear in b (exact match)."""
    var count = 0
    for i in range(len(a_tokens)):
        for j in range(len(b_tokens)):
            if a_tokens[i] == b_tokens[j]:
                count += 1
                break
    return count


def _ngrams(s: String, n: Int) -> List[String]:
    """Extract all character n-grams of length n from s."""
    var result = List[String]()
    var s_len = len(s)
    if s_len < n:
        return result^
    var s_bytes = s.as_bytes()
    for i in range(s_len - n + 1):
        var gram = String("")
        for j in range(n):
            gram = gram + chr(Int(s_bytes[i + j]))
        result.append(gram^)
    return result^


def _count_shared_ngrams(a_grams: List[String], b_grams: List[String]) -> Int:
    """Count shared n-grams (each a-gram counted at most once)."""
    var count = 0
    var b_used = List[Bool]()
    for _ in range(len(b_grams)):
        b_used.append(False)

    for i in range(len(a_grams)):
        for j in range(len(b_grams)):
            if not b_used[j] and a_grams[i] == b_grams[j]:
                count += 1
                b_used[j] = True
                break
    return count


# ── score_token_overlap ────────────────────────────────────────────────────────


def score_token_overlap(hint: String, col: String) -> Float64:
    """
    Jaccard token overlap: |A ∩ B| / |A ∪ B|.

    Tokens are split on underscores, spaces, and hyphens.
    Both strings must already be lower-cased.

    Returns 1.0 when both inputs are empty. Returns 0.0 when one is empty.
    """
    var a_toks = _to_tokens(hint)
    var b_toks = _to_tokens(col)

    var a_n = len(a_toks)
    var b_n = len(b_toks)

    if a_n == 0 and b_n == 0:
        return 1.0
    if a_n == 0 or b_n == 0:
        return 0.0

    var shared = _count_shared_tokens(a_toks, b_toks)
    var union = a_n + b_n - shared
    if union == 0:
        return 0.0
    return Float64(shared) / Float64(union)


# ── score_ngram_overlap ────────────────────────────────────────────────────────


def score_ngram_overlap(hint: String, col: String, n: Int = 2) -> Float64:
    """
    Dice coefficient on character n-grams: 2 * |A ∩ B| / (|A| + |B|).

    Uses n=2 (bigrams) by default; pass n=3 for trigrams.
    Both strings must already be lower-cased.
    """
    var a_grams = _ngrams(hint, n)
    var b_grams = _ngrams(col, n)

    var a_n = len(a_grams)
    var b_n = len(b_grams)

    if a_n == 0 and b_n == 0:
        return 1.0
    if a_n == 0 or b_n == 0:
        return 0.0

    var shared = _count_shared_ngrams(a_grams, b_grams)
    return 2.0 * Float64(shared) / Float64(a_n + b_n)


# ── score_prefix_match ─────────────────────────────────────────────────────────


def score_prefix_match(hint: String, col: String) -> Float64:
    """
    Fraction of hint covered by the longest common prefix with col.

    score = common_prefix_length / len(hint)

    Useful for abbreviation matching: "unit" is a prefix of "unit_cost".
    Returns 1.0 when hint is empty. Returns 0.0 when col is empty.
    """
    var la = len(hint)
    var lb = len(col)
    if la == 0:
        return 1.0
    if lb == 0:
        return 0.0

    var a_bytes = hint.as_bytes()
    var b_bytes = col.as_bytes()

    var common = 0
    var max_compare = la
    if lb < max_compare:
        max_compare = lb

    for i in range(max_compare):
        if a_bytes[i] == b_bytes[i]:
            common += 1
        else:
            break

    return Float64(common) / Float64(la)


# ── score_column_hint ──────────────────────────────────────────────────────────


def score_column_hint(
    hint: String,
    col: String,
    token_weight: Float64 = 0.50,
    ngram_weight: Float64 = 0.30,
    prefix_weight: Float64 = 0.20,
) -> Float64:
    """
    Weighted composite lexical similarity between a hint and a column name.

    Components:
      token_overlap  (50 %) — Jaccard on underscore/space tokens
      ngram_overlap  (30 %) — Dice on character bigrams
      prefix_match   (20 %) — Shared prefix fraction (abbreviation signal)

    Both strings must already be lower-cased and normalised by the caller.
    Returns a score clamped to [0, 1].
    """
    if len(hint) == 0 and len(col) == 0:
        return 1.0
    if len(hint) == 0 or len(col) == 0:
        return 0.0

    var tok   = score_token_overlap(hint, col)
    var ngram = score_ngram_overlap(hint, col, 2)
    var pref  = score_prefix_match(hint, col)

    var score = token_weight * tok + ngram_weight * ngram + prefix_weight * pref

    if score > 1.0:
        return 1.0
    if score < 0.0:
        return 0.0
    return score
