"""
string_distance.mojo — Advanced string distance & similarity metrics. Zero Python imports.

Extends text/fuzzy.mojo. Replaces jellyfish / phonetics / python-Levenshtein
with pure Mojo implementations.

Public API:
  damerau_levenshtein   — Damerau-Levenshtein distance (transpositions as single edit)
  soundex               — American Soundex code (4 chars)
  edit_similarity       — 1 - lev(a,b)/max(len(a),len(b))
  common_prefix_length  — length of shared prefix
  common_suffix_length  — length of shared suffix
  dice_coefficient      — Sørensen-Dice on bigrams
  overlap_coefficient   — overlap coefficient on bigrams
  bigrams               — extract character bigrams
  string_reverse        — reverse a string
  is_palindrome         — case-insensitive palindrome check (ignoring spaces)
"""


# ── damerau_levenshtein ──────────────────────────────────────────────────────


def damerau_levenshtein(a: String, b: String) -> Int:
    """Damerau-Levenshtein distance allowing transpositions as a single edit.

    Uses the optimal string alignment (restricted edit distance) variant.
    Time: O(m*n), Space: O(m*n).
    """
    var m = len(a)
    var n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m

    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()

    # Build (m+1) x (n+1) DP table stored flat
    var dp = List[Int]()
    for _ in range((m + 1) * (n + 1)):
        dp.append(0)

    # Helper to index into flat array
    # dp[i*(n+1) + j]
    for i in range(m + 1):
        dp[i * (n + 1)] = i
    for j in range(n + 1):
        dp[j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            var cost = 0
            if a_bytes[i - 1] != b_bytes[j - 1]:
                cost = 1
            var del_cost = dp[(i - 1) * (n + 1) + j] + 1
            var ins_cost = dp[i * (n + 1) + (j - 1)] + 1
            var sub_cost = dp[(i - 1) * (n + 1) + (j - 1)] + cost
            var best = del_cost
            if ins_cost < best:
                best = ins_cost
            if sub_cost < best:
                best = sub_cost
            # Transposition
            if i > 1 and j > 1 and a_bytes[i - 1] == b_bytes[j - 2] and a_bytes[i - 2] == b_bytes[j - 1]:
                var trans_cost = dp[(i - 2) * (n + 1) + (j - 2)] + cost
                if trans_cost < best:
                    best = trans_cost
            dp[i * (n + 1) + j] = best

    return dp[m * (n + 1) + n]


# ── soundex ──────────────────────────────────────────────────────────────────


def _sx_code(c: UInt8) -> UInt8:
    """Map character to soundex digit. 48='0' means skip."""
    var ch = c
    if ch >= 97 and ch <= 122:
        ch = ch - 32
    # B=66,F=70,P=80,V=86 -> 1
    if ch == 66 or ch == 70 or ch == 80 or ch == 86:
        return 49  # '1'
    # C=67,G=71,J=74,K=75,Q=81,S=83,X=88,Z=90 -> 2
    if ch == 67 or ch == 71 or ch == 74 or ch == 75 or ch == 81 or ch == 83 or ch == 88 or ch == 90:
        return 50  # '2'
    # D=68,T=84 -> 3
    if ch == 68 or ch == 84:
        return 51  # '3'
    # L=76 -> 4
    if ch == 76:
        return 52  # '4'
    # M=77,N=78 -> 5
    if ch == 77 or ch == 78:
        return 53  # '5'
    # R=82 -> 6
    if ch == 82:
        return 54  # '6'
    return 48  # '0' for vowels, H, W, Y


def soundex(word: String) -> String:
    """American Soundex code (4 characters).

    Maps letters to digits: B,F,P,V→1  C,G,J,K,Q,S,X,Z→2  D,T→3
    L→4  M,N→5  R→6.  Vowels and H,W,Y→0 (ignored).
    H and W do not separate two identical codes.
    Returns e.g. 'R163' for 'Robert'.
    """
    if len(word) == 0:
        return "0000"

    var w_bytes = word.as_bytes()

    # Uppercase first letter
    var first = Int(w_bytes[0])
    if first >= 97 and first <= 122:
        first = first - 32

    var result = chr(first)

    var last_code = _sx_code(w_bytes[0])
    var count = 1

    for i in range(1, len(word)):
        if count >= 4:
            break
        var ch = w_bytes[i]
        # Uppercase for H/W check
        var uch = ch
        if uch >= 97 and uch <= 122:
            uch = uch - 32
        # H(72) and W(87) are transparent - don't update last_code
        if uch == 72 or uch == 87:
            continue
        var code = _sx_code(ch)
        if code != 48 and code != last_code:
            result += chr(Int(code))
            count += 1
        # Vowels reset the last_code so identical consonants
        # separated by a vowel are coded twice
        last_code = code

    while count < 4:
        result += "0"
        count += 1

    return result


# ── edit_similarity ──────────────────────────────────────────────────────────


def _levenshtein(a: String, b: String) -> Int:
    """Internal Levenshtein distance."""
    var m = len(a)
    var n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()
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
            var d = prev[j] + 1
            var ins = curr[j - 1] + 1
            var sub = prev[j - 1] + cost
            var best = d
            if ins < best:
                best = ins
            if sub < best:
                best = sub
            curr[j] = best
        for j in range(n + 1):
            var tmp = prev[j]
            prev[j] = curr[j]
            curr[j] = tmp
    return prev[n]


def edit_similarity(a: String, b: String) -> Float64:
    """Edit similarity: 1.0 - levenshtein(a,b) / max(len(a), len(b)).

    Range [0, 1]. Returns 1.0 for identical or both-empty strings.
    """
    var la = len(a)
    var lb = len(b)
    if la == 0 and lb == 0:
        return 1.0
    var mx = la
    if lb > mx:
        mx = lb
    var dist = _levenshtein(a, b)
    return 1.0 - Float64(dist) / Float64(mx)


# ── common_prefix_length ─────────────────────────────────────────────────────


def common_prefix_length(a: String, b: String) -> Int:
    """Length of the common prefix of two strings."""
    var la = len(a)
    var lb = len(b)
    var n = la if la < lb else lb
    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()
    var count = 0
    for i in range(n):
        if a_bytes[i] == b_bytes[i]:
            count += 1
        else:
            break
    return count


# ── common_suffix_length ─────────────────────────────────────────────────────


def common_suffix_length(a: String, b: String) -> Int:
    """Length of the common suffix of two strings."""
    var la = len(a)
    var lb = len(b)
    var n = la if la < lb else lb
    var a_bytes = a.as_bytes()
    var b_bytes = b.as_bytes()
    var count = 0
    for i in range(n):
        if a_bytes[la - 1 - i] == b_bytes[lb - 1 - i]:
            count += 1
        else:
            break
    return count


# ── bigrams ──────────────────────────────────────────────────────────────────


def bigrams(s: String) -> List[String]:
    """Extract character bigrams from string. E.g. 'abc' -> ['ab', 'bc']."""
    var result = List[String]()
    var n = len(s)
    if n < 2:
        return result^
    var s_bytes = s.as_bytes()
    for i in range(n - 1):
        var bg = chr(Int(s_bytes[i])) + chr(Int(s_bytes[i + 1]))
        result.append(bg^)
    return result^


# ── dice_coefficient ─────────────────────────────────────────────────────────


def dice_coefficient(a: String, b: String) -> Float64:
    """Sørensen-Dice coefficient on bigram multisets: 2*|A∩B|/(|A|+|B|).

    Range [0, 1]. Returns 1.0 if both strings have length < 2 and are equal.
    """
    var bg_a = bigrams(a)
    var bg_b = bigrams(b)
    var na = len(bg_a)
    var nb = len(bg_b)
    if na == 0 and nb == 0:
        return 1.0 if a == b else 0.0
    if na == 0 or nb == 0:
        return 0.0

    # Count matches (multiset intersection)
    var used = List[Bool]()
    for _ in range(nb):
        used.append(False)
    var matches = 0
    for i in range(na):
        for j in range(nb):
            if not used[j] and bg_a[i] == bg_b[j]:
                used[j] = True
                matches += 1
                break
    return 2.0 * Float64(matches) / Float64(na + nb)


# ── overlap_coefficient ──────────────────────────────────────────────────────


def overlap_coefficient(a: String, b: String) -> Float64:
    """|A∩B| / min(|A|, |B|) on bigram multisets.

    Range [0, 1]. Returns 1.0 if both strings have length < 2 and are equal.
    """
    var bg_a = bigrams(a)
    var bg_b = bigrams(b)
    var na = len(bg_a)
    var nb = len(bg_b)
    if na == 0 and nb == 0:
        return 1.0 if a == b else 0.0
    if na == 0 or nb == 0:
        return 0.0
    var mn = na if na < nb else nb
    var used = List[Bool]()
    for _ in range(nb):
        used.append(False)
    var matches = 0
    for i in range(na):
        for j in range(nb):
            if not used[j] and bg_a[i] == bg_b[j]:
                used[j] = True
                matches += 1
                break
    return Float64(matches) / Float64(mn)


# ── string_reverse ───────────────────────────────────────────────────────────


def string_reverse(s: String) -> String:
    """Reverse a string (byte-level reversal, ASCII safe)."""
    var n = len(s)
    if n == 0:
        return String("")
    var s_bytes = s.as_bytes()
    var result = String("")
    var i = n - 1
    while i >= 0:
        result += chr(Int(s_bytes[i]))
        i -= 1
    return result


# ── is_palindrome ────────────────────────────────────────────────────────────


def is_palindrome(s: String) -> Bool:
    """Check if string is a palindrome (case-insensitive, ignoring spaces)."""
    # Build cleaned lowercase version
    var s_bytes = s.as_bytes()
    var cleaned = List[UInt8]()
    for i in range(len(s)):
        var c = s_bytes[i]
        if c == 32:  # space
            continue
        if c >= 65 and c <= 90:
            c = c + 32
        cleaned.append(c)
    var n = len(cleaned)
    if n <= 1:
        return True
    var left = 0
    var right = n - 1
    while left < right:
        if cleaned[left] != cleaned[right]:
            return False
        left += 1
        right -= 1
    return True
