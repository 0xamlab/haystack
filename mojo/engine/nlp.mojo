"""
nlp.mojo — Basic NLP utilities. Zero Python imports.

Replaces nltk / sklearn.feature_extraction with pure Mojo implementations
for tokenization, TF-IDF, n-grams, cosine similarity, and Jaccard similarity.

Public API:
  tokenize              — Split text on whitespace/punctuation, lowercase
  ngrams                — Generate n-grams as joined strings
  term_frequency        — Pairs [term, count_as_string] sorted by frequency
  tf                    — Term frequency: count(term)/len(tokens)
  idf                   — Inverse document frequency: log(N / (1 + df))
  tfidf                 — TF × IDF
  cosine_similarity_vec — Cosine similarity of two float vectors
  jaccard_similarity    — Jaccard similarity of two token sets
  word_count            — Count words in text
  char_count            — Count non-whitespace characters
  unique_tokens         — Unique tokens in order of first appearance
"""
from std.math import sqrt, log


# ── Internal helpers (byte-level) ─────────────────────────────────────────────


@always_inline
def _is_ws(c: UInt8) -> Bool:
    """Check if byte is whitespace."""
    return c == 32 or c == 9 or c == 10 or c == 13  # space, tab, nl, cr


@always_inline
def _is_punct(c: UInt8) -> Bool:
    """Check if byte is common ASCII punctuation."""
    return (c == 46 or c == 44 or c == 33 or c == 63 or c == 59   # . , ! ? ;
            or c == 58 or c == 40 or c == 41 or c == 91 or c == 93   # : ( ) [ ]
            or c == 123 or c == 125 or c == 34 or c == 39 or c == 45  # { } " ' -
            or c == 47 or c == 92 or c == 64 or c == 35 or c == 36   # / \ @ # $
            or c == 37 or c == 38 or c == 42 or c == 43 or c == 61   # % & * + =
            or c == 60 or c == 62 or c == 124 or c == 126 or c == 96  # < > | ~ `
            or c == 94)  # ^


@always_inline
def _to_lower_byte(c: UInt8) -> UInt8:
    """Lowercase a single ASCII byte."""
    if c >= 65 and c <= 90:
        return c + 32
    return c


def _contains_str(haystack: List[String], needle: String) -> Bool:
    """Check if needle is in the list."""
    for i in range(len(haystack)):
        if haystack[i] == needle:
            return True
    return False


# ── Tokenize ─────────────────────────────────────────────────────────────────


def tokenize(text: String) -> List[String]:
    """Split text on whitespace and common punctuation. Lowercase all tokens."""
    var tokens = List[String]()
    var bs = text.as_bytes()
    var n = len(text)
    var start = -1
    for i in range(n):
        var c = bs[i]
        if _is_ws(c) or _is_punct(c):
            if start >= 0:
                var tok = String("")
                for j in range(start, i):
                    tok += chr(Int(_to_lower_byte(bs[j])))
                tokens.append(tok^)
                start = -1
        else:
            if start < 0:
                start = i
    if start >= 0:
        var tok = String("")
        for j in range(start, n):
            tok += chr(Int(_to_lower_byte(bs[j])))
        tokens.append(tok^)
    return tokens^


# ── N-grams ──────────────────────────────────────────────────────────────────


def ngrams(tokens: List[String], n: Int) -> List[String]:
    """Generate n-grams as joined strings (e.g., 'the_cat' for bigram)."""
    var result = List[String]()
    var sz = len(tokens)
    if n <= 0 or sz < n:
        return result^
    for i in range(sz - n + 1):
        var gram = tokens[i]
        for j in range(1, n):
            gram += "_" + tokens[i + j]
        result.append(gram^)
    return result^


# ── Term Frequency (as list of pairs) ────────────────────────────────────────


def term_frequency(tokens: List[String]) -> List[List[String]]:
    """Returns pairs [term, count_as_string] sorted by frequency descending."""
    var terms = List[String]()
    var counts = List[Int]()
    for i in range(len(tokens)):
        var t = tokens[i]
        var found = False
        for j in range(len(terms)):
            if terms[j] == t:
                counts[j] += 1
                found = True
                break
        if not found:
            terms.append(t)
            counts.append(1)
    # Sort by count descending (insertion sort)
    for i in range(1, len(terms)):
        var kc = counts[i]
        var kt = terms[i]
        var j = i - 1
        while j >= 0 and counts[j] < kc:
            counts[j + 1] = counts[j]
            terms[j + 1] = terms[j]
            j -= 1
        counts[j + 1] = kc
        terms[j + 1] = kt
    var result = List[List[String]]()
    for i in range(len(terms)):
        var pair = List[String]()
        pair.append(terms[i])
        pair.append(String(counts[i]))
        result.append(pair^)
    return result^


# ── TF ───────────────────────────────────────────────────────────────────────


def tf(term: String, tokens: List[String]) -> Float64:
    """Term frequency: count(term) / len(tokens)."""
    var n = len(tokens)
    if n == 0:
        return 0.0
    var count: Int = 0
    for i in range(n):
        if tokens[i] == term:
            count += 1
    return Float64(count) / Float64(n)


# ── IDF ──────────────────────────────────────────────────────────────────────


def idf(term: String, documents: List[List[String]]) -> Float64:
    """Inverse document frequency: log(N / (1 + df))."""
    var n_docs = len(documents)
    if n_docs == 0:
        return 0.0
    var df: Int = 0
    for i in range(n_docs):
        var doc_len = len(documents[i])
        for j in range(doc_len):
            if documents[i][j] == term:
                df += 1
                break
    return log(Float64(n_docs) / Float64(1 + df))


# ── TF-IDF ───────────────────────────────────────────────────────────────────


def tfidf(term: String, tokens: List[String],
         documents: List[List[String]]) -> Float64:
    """TF × IDF."""
    return tf(term, tokens) * idf(term, documents)


# ── Cosine Similarity ────────────────────────────────────────────────────────


def cosine_similarity_vec(a: List[Float64], b: List[Float64]) -> Float64:
    """Cosine similarity of two vectors."""
    var n = len(a)
    if n == 0 or len(b) != n:
        return 0.0
    var dot: Float64 = 0.0
    var na: Float64 = 0.0
    var nb: Float64 = 0.0
    for i in range(n):
        dot += a[i] * b[i]
        na += a[i] * a[i]
        nb += b[i] * b[i]
    var denom = sqrt(na) * sqrt(nb)
    if denom < 1e-15:
        return 0.0
    return dot / denom


# ── Jaccard Similarity ───────────────────────────────────────────────────────


def jaccard_similarity(a: List[String], b: List[String]) -> Float64:
    """|A∩B| / |A∪B| on token sets."""
    # Build union and count intersection
    var union_set = List[String]()
    var intersection_count: Int = 0
    # Add all unique from a
    for i in range(len(a)):
        if not _contains_str(union_set, a[i]):
            union_set.append(a[i])
    # Check b against a-set for intersection, add new to union
    var a_unique = List[String]()
    for i in range(len(a)):
        if not _contains_str(a_unique, a[i]):
            a_unique.append(a[i])
    for i in range(len(b)):
        if not _contains_str(union_set, b[i]):
            union_set.append(b[i])
    # Count intersection: items in both a and b
    for i in range(len(a_unique)):
        for j in range(len(b)):
            if a_unique[i] == b[j]:
                intersection_count += 1
                break
    var union_size = len(union_set)
    if union_size == 0:
        return 0.0
    return Float64(intersection_count) / Float64(union_size)


# ── Word Count ───────────────────────────────────────────────────────────────


def word_count(text: String) -> Int:
    """Count words in text (split by whitespace)."""
    var count: Int = 0
    var in_word = False
    var bs = text.as_bytes()
    var n = len(text)
    for i in range(n):
        if _is_ws(bs[i]):
            if in_word:
                count += 1
                in_word = False
        else:
            in_word = True
    if in_word:
        count += 1
    return count


# ── Char Count ───────────────────────────────────────────────────────────────


def char_count(text: String) -> Int:
    """Count non-whitespace characters."""
    var count: Int = 0
    var bs = text.as_bytes()
    var n = len(text)
    for i in range(n):
        if not _is_ws(bs[i]):
            count += 1
    return count


# ── Unique Tokens ────────────────────────────────────────────────────────────


def unique_tokens(tokens: List[String]) -> List[String]:
    """Unique tokens in order of first appearance."""
    var result = List[String]()
    for i in range(len(tokens)):
        if not _contains_str(result, tokens[i]):
            result.append(tokens[i])
    return result^
