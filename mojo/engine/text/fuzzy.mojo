"""
fuzzy.mojo — Fuzzy string matching utilities. Zero Python imports.

Replaces Python's fuzzywuzzy / rapidfuzz with pure Mojo implementations.

Public API:
  levenshtein_distance    — Edit distance between two strings (DP, O(mn))
  normalized_levenshtein  — Normalized edit distance [0,1]
  jaro_similarity         — Jaro similarity score [0,1]
  jaro_winkler_similarity — Jaro-Winkler with prefix boost [0,1]
  hamming_distance        — Hamming distance (equal-length strings)
  longest_common_subsequence — LCS length via DP
  fuzzy_ratio             — 2*LCS / (len(a)+len(b)), range [0,1]
"""


# ── levenshtein_distance ──────────────────────────────────────────────────────


def levenshtein_distance(a: String, b: String) -> Int:
    """Edit distance between two strings using Wagner-Fischer DP algorithm.

    Time: O(m*n), Space: O(min(m,n)) using two-row optimisation.
    """
    var m = len(a)
    var n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()

    # Use two rows for space efficiency
    var prev = List[Int]()
    var curr = List[Int]()
    for j in range(n + 1):
        prev.append(j)
        curr.append(0)

    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            var cost = 0
            if a_bytes[i - 1] != b_bytes[j - 1]:
                cost = 1
            var del_cost = prev[j] + 1
            var ins_cost = curr[j - 1] + 1
            var sub_cost = prev[j - 1] + cost
            var best = del_cost
            if ins_cost < best:
                best = ins_cost
            if sub_cost < best:
                best = sub_cost
            curr[j] = best
        # Swap rows
        for j in range(n + 1):
            var tmp = prev[j]
            prev[j] = curr[j]
            curr[j] = tmp

    return prev[n]


# ── normalized_levenshtein ────────────────────────────────────────────────────


def normalized_levenshtein(a: String, b: String) -> Float64:
    """Normalized Levenshtein similarity: 1.0 - distance / max(len(a), len(b)).

    Returns value in [0, 1]. Returns 1.0 for identical strings.
    Returns 1.0 if both strings are empty.
    """
    var la = len(a)
    var lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    var max_len = la
    if lb > max_len:
        max_len = lb
    var dist = levenshtein_distance(a, b)
    return 1.0 - Float64(dist) / Float64(max_len)


# ── jaro_similarity ───────────────────────────────────────────────────────────


def jaro_similarity(a: String, b: String) -> Float64:
    """Jaro similarity score in [0, 1].

    Uses the classic Jaro algorithm:
      - match_window = max(len(a), len(b)) / 2 - 1
      - count matching characters and transpositions
      - jaro = (m/|a| + m/|b| + (m-t)/m) / 3
    """
    var la = len(a)
    var lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    if la == 0 or lb == 0:
        return 0.0

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()

    var max_len = la
    if lb > max_len:
        max_len = lb
    var match_window = max_len // 2 - 1
    if match_window < 0:
        match_window = 0

    # Track which characters in b have been matched
    var a_matched = List[Bool]()
    var b_matched = List[Bool]()
    for _ in range(la):
        a_matched.append(False)
    for _ in range(lb):
        b_matched.append(False)

    var matches = 0
    var transpositions = 0

    # Find matches
    for i in range(la):
        var low = i - match_window
        if low < 0:
            low = 0
        var high = i + match_window + 1
        if high > lb:
            high = lb
        for j in range(low, high):
            if not b_matched[j] and a_bytes[i] == b_bytes[j]:
                a_matched[i] = True
                b_matched[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    # Count transpositions
    var k = 0
    for i in range(la):
        if a_matched[i]:
            while not b_matched[k]:
                k += 1
            if a_bytes[i] != b_bytes[k]:
                transpositions += 1
            k += 1

    var t = Float64(transpositions) / 2.0
    var m = Float64(matches)
    return (m / Float64(la) + m / Float64(lb) + (m - t) / m) / 3.0


# ── jaro_winkler_similarity ──────────────────────────────────────────────────


def jaro_winkler_similarity(
    a: String, b: String, prefix_weight: Float64 = 0.1
) -> Float64:
    """Jaro-Winkler similarity: Jaro + prefix bonus.

    jw = jaro + l * p * (1 - jaro)
    where l = common prefix length (up to 4), p = prefix_weight.
    """
    var jaro = jaro_similarity(a, b)

    # Common prefix length (up to 4)
    var la = len(a)
    var lb = len(b)
    var max_prefix = 4
    if la < max_prefix:
        max_prefix = la
    if lb < max_prefix:
        max_prefix = lb

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()
    var prefix_len = 0
    for i in range(max_prefix):
        if a_bytes[i] == b_bytes[i]:
            prefix_len += 1
        else:
            break

    return jaro + Float64(prefix_len) * prefix_weight * (1.0 - jaro)


# ── hamming_distance ──────────────────────────────────────────────────────────


def hamming_distance(a: String, b: String) raises -> Int:
    """Hamming distance — number of positions where characters differ.

    Raises if strings have different lengths.
    """
    var la = len(a)
    var lb = len(b)
    if la != lb:
        raise Error("hamming_distance: strings must be equal length")

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()
    var dist = 0
    for i in range(la):
        if a_bytes[i] != b_bytes[i]:
            dist += 1
    return dist


# ── longest_common_subsequence ────────────────────────────────────────────────


def longest_common_subsequence(a: String, b: String) -> Int:
    """Length of the longest common subsequence via DP.

    Time: O(m*n), Space: O(min(m,n)) using two-row optimisation.
    """
    var m = len(a)
    var n = len(b)
    if m == 0 or n == 0:
        return 0

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()

    # Two-row DP
    var prev = List[Int]()
    var curr = List[Int]()
    for _ in range(n + 1):
        prev.append(0)
        curr.append(0)

    for i in range(1, m + 1):
        curr[0] = 0
        for j in range(1, n + 1):
            if a_bytes[i - 1] == b_bytes[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                var top = prev[j]
                var left = curr[j - 1]
                if top > left:
                    curr[j] = top
                else:
                    curr[j] = left
        for j in range(n + 1):
            prev[j] = curr[j]

    return prev[n]


# ── fuzzy_ratio ───────────────────────────────────────────────────────────────


def fuzzy_ratio(a: String, b: String) -> Float64:
    """Fuzzy match ratio: 2 * LCS / (len(a) + len(b)), range [0, 1].

    Returns 1.0 for identical strings. Returns 0.0 if both are empty.
    """
    var la = len(a)
    var lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    if la == 0 or lb == 0:
        return 0.0
    var lcs = longest_common_subsequence(a, b)
    return 2.0 * Float64(lcs) / Float64(la + lb)
