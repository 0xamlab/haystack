---
icon: magnifying-glass
description: A second, broader string-distance library, a minimal backtracking regex engine distinct from the corpus's other one, and vector-similarity formulas that operate on pre-reduced scalars rather than raw vectors.
---

# Text similarity and pattern matching kernels

Three modules that look, from their names, like they should overlap with kernels documented
elsewhere in this corpus — and in each case the overlap is real but narrower than the name
suggests. `string_distance` is a second string-metric library, layered *on top of* the
already-documented `text.fuzzy` rather than duplicating it: its own docstring says so directly
("Extends text/fuzzy.mojo"). `regex_engine` is a second regex matcher with a deliberately smaller
feature set than `text.regex`, not a shared implementation. `vector_similarity` answers a
different question than `vector_kernels.dot` altogether: instead of taking raw vectors and doing
the SIMD reduction itself, every function here takes the *already-reduced* scalars (a dot product,
an L2 norm, a sum of squared differences) and applies the final formula — the caller supplies its
own reduction, over vectors of any width, in exchange for `vector_kernels.dot`'s fixed 64-lane
Float32 SIMD path.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("string_distance", "damerau_levenshtein", ["ab", "ba"])["result"]
# 1 -- a single transposition; plain Levenshtein would need a delete and an insert to score 2

runtime.execute("regex_engine", "regex_match", ["unit_[a-z]+", "unit_cost"])["result"]
# True -- literal prefix, then a bracket class quantified with '+', anchored to the full string
```

## The modules

| Module | What it does |
| --- | --- |
| `string_distance` | Damerau-Levenshtein (transposition-aware edit distance), Soundex, edit similarity, common prefix/suffix length, bigram Dice/overlap coefficients, string reversal and palindrome checking |
| `regex_engine` | a small backtracking matcher for literals, `.`, `*`, `+`, `?`, `^`, `$`, and `[abc]`/`[a-z]` classes, plus literal count/split/find-first helpers and a pattern validator |
| `vector_similarity` | cosine, Euclidean, Manhattan, Chebyshev, Minkowski and angular distance/similarity, Hamming distance for bit vectors, Jaccard similarity, and Pearson correlation — all as formulas over pre-computed scalar reductions |

## `string_distance`: a second metric library, layered on `text.fuzzy`

`string_distance.mojo`'s own docstring is explicit about its relationship to the corpus's other
string-metric module: "Extends text/fuzzy.mojo. Replaces jellyfish / phonetics / python-Levenshtein
with pure Mojo implementations." [Text processing kernels](text-processing-kernels.md) already
documents `text.fuzzy`'s Levenshtein, Jaro/Jaro-Winkler, Hamming and LCS-based ratios; nothing in
`string_distance` re-implements any of those five. Instead it adds algorithms `text.fuzzy` doesn't
have at all — a transposition-aware edit distance, a phonetic code, and bigram-set similarity —
plus small string utilities (`string_reverse`, `is_palindrome`) that don't belong in either module's
existing scope. The two modules are meant to be used together, not chosen between.

**`damerau_levenshtein` counts an adjacent transposition as one edit, where plain Levenshtein counts
two.** `"ab"` → `"ba"` is a single adjacent swap: `text.fuzzy.levenshtein_distance("ab", "ba")` — a
substitution-only edit distance — has to spend two edits (say, delete `a`, then insert `a` at the
end) to get there, but `damerau_levenshtein("ab", "ba")` returns `1`, because the DP table's extra
transposition case (`a[i-1] == b[j-2] and a[i-2] == b[j-1]`) recognizes the swap directly and takes
`dp[i-2][j-2] + cost` instead of the usual three-way min. This implementation is the *optimal string
alignment* variant (a transposed pair can't itself be edited again afterward), not full unrestricted
Damerau-Levenshtein — the common, cheaper approximation most libraries actually ship. A larger worked
example: `damerau_levenshtein("kitten", "sitting")` returns `3`, the same distance plain Levenshtein
gives for this pair (there's no adjacent transposition available between them), which is exactly
what should happen — the transposition rule only ever helps, never hurts, relative to the ordinary
three-edit DP.

**`soundex` reproduces the textbook `"Robert"` → `"R163"` example exactly**, tracing the real
per-character logic in `mojo/engine/string_distance.mojo`: `R` is kept as the leading letter
unchanged; `o` is a vowel and contributes no digit; `b` maps to `1`; `e` is a vowel (resets
`last_code` so a repeated consonant after it codes again); `r` maps to `6`; `t` maps to `3` — giving
`R`, `1`, `6`, `3`. `H` and `W` are transparent (they don't update `last_code`, so `A` in `"Ashcraft"`
and the following `h` don't let `S`/`C` re-code as if separated by a vowel), while true vowels do
reset it, which is why a doubled letter split by a vowel (`"Bootle"` → `b-oo-t-l-e`) codes each
occurrence but a doubled letter split by `H`/`W` doesn't.

**`edit_similarity` is a plain Levenshtein ratio, unrelated to `text.fuzzy.fuzzy_ratio`'s LCS-based
formula.** `edit_similarity(a, b) = 1 - levenshtein(a, b) / max(len(a), len(b))`, using this module's
own internal `_levenshtein` (the ordinary substitution-only DP, no transposition rule).
`edit_similarity("kitten", "sitting")` — the classic Wagner-Fischer textbook pair, edit distance `3`
— returns `1 - 3/7 = 0.5714285714285714`. The two both-empty/one-empty conventions match the rest of
the corpus: `edit_similarity("", "")` is `1.0` by an explicit early return, not a `0/0` divide.

**`dice_coefficient` and `overlap_coefficient` reproduce the standard Sørensen-Dice reference pair.**
Both operate on character-bigram multisets with greedy (non-reused) matching. The Wikipedia textbook
example — `"night"` vs `"nacht"` — checks out exactly against this source: `bigrams("night") =
["ni","ig","gh","ht"]`, `bigrams("nacht") = ["na","ac","ch","ht"]`, one shared bigram (`"ht"`), so
`dice_coefficient("night", "nacht") = 2*1/(4+4) = 0.25`. `overlap_coefficient` on the same pair is
also `0.25` here only because both bigram counts happen to be equal (`4` and `4`, so `min` and the
sum behave the same way at this one data point) — for unequal-length strings the two diverge, since
overlap divides by the *smaller* set size instead of the sum.

```python
runtime.execute("string_distance", "dice_coefficient", ["night", "nacht"])["result"]
# 0.25
runtime.execute("string_distance", "common_prefix_length", ["unit_price", "unit_cost"])["result"]
# 5 -- "unit_" is shared; the 6th byte ('p' vs 'c') is where they diverge
runtime.execute("string_distance", "common_suffix_length", ["unit_price", "unit_cost"])["result"]
# 0 -- the last bytes ('e' vs 't') already differ, so no suffix is shared at all
```

`is_palindrome` lowercases ASCII letters and strips plain space characters (byte `32`) before a
two-pointer compare — it does not strip punctuation, so `is_palindrome("A man a plan a canal
Panama")` returns `True` (no punctuation in that phrase to trip it up) but a punctuated palindrome
sentence would not clear the same bar untouched.

## `regex_engine`: a smaller, separate matcher — not `text.regex`

[Text processing kernels](text-processing-kernels.md) already documents `text.regex`, a backtracking
matcher supporting alternation (`|`), the escapes `\d \w \s` (and their negations), and a full
find-all/replace/split API. `regex_engine` is a genuinely different, smaller implementation — not a
thin wrapper or a shared core. Its own docstring lists the supported syntax plainly: "literal chars,
`.` (any), `*` (0+), `+` (1+), `?` (0 or 1), `^` (start), `$` (end), `[abc]` (char class), `[a-z]`
(range)" — there is no alternation and no `\d`/`\w`/`\s` character-class escapes anywhere in
`regex_engine.mojo`. The two modules are dispatched under entirely separate contract names
(`regex_engine` vs. `text.regex`) and neither imports the other.

{% hint style="warning" %}
**A backslash escape in `regex_engine` matches only that literal character — it never becomes a
character class.** `_match_one`'s escape branch reads the byte after `\` and compares it straight
against the text byte; there is no dispatch table mapping `d`/`w`/`s` to digit/word/whitespace
classes the way `text.regex` has. `regex_match("\\d", "5")` returns `False` and `regex_match("\\d",
"d")` returns `True` — the exact opposite of what `\d` means in `text.regex` or in standard regex
syntax. A pattern written for `text.regex` and dispatched to `regex_engine` by mistake compiles and
runs without error; it just matches something else.
{% endhint %}

`regex_match` always enforces a full-string match, even without an explicit `$`: if the pattern
doesn't already end in `$`, the function appends one before matching, so `regex_match("a*",
"aaa")` (no anchors at all) still requires all of `"aaa"` to be consumed. Working the
`"unit_[a-z]+"` / `"unit_cost"` example from the top of this page by hand against the real
`_match_here` recursion: the five literal bytes of `"unit_"` match one at a time, then the `+`
quantifier over `[a-z]` counts the greedy maximum run of lowercase letters starting at position 5
(`"cost"`, 4 bytes) and tries backtracking down from 4 copies — the first try (all 4) already lands
exactly on the appended `$` at end-of-text, so it accepts immediately without ever needing to
retreat. Against `"unit_123"` the same class-count loop stops at `0` (digits aren't in `a-z`), and
since `+` requires at least one match, the whole pattern fails — `regex_match("unit_[a-z]+",
"unit_123")` is `False`.

{% hint style="danger" %}
**`regex_find_first` returns the shortest match at the leftmost start, not the longest — a real,
verifiable surprise for anything quantified with `*` or `+`.** Its implementation is a brute-force
double loop: for each `start`, try `end` values from `start` up to the text's length, in increasing
order, and return as soon as `regex_match(pattern, text[start:end])` succeeds against that exact
substring. Because `regex_match` enforces a full-string match, the *shortest* substring that
already satisfies the quantifier's minimum wins, and the loop never gets to try a longer one.
Tracing `regex_find_first("[0-9]+", "sku-104 qty-8")` against the real source: every `start` before
index 4 fails outright (no substring beginning there is all-digits), and at `start=4` the
single-character substring `"1"` already fully matches `"[0-9]+"` (one digit satisfies "one or
more"), so the function returns `[4, 5]` — not `[4, 7]`, which would be the full `"104"` run. The
same shape shows up on `regex_find_first("a+", "aaa")`, which returns `[0, 1]`, not `[0, 3]`. Anyone
expecting "the whole matched run," the way `text.regex.regex_find_all` or Python's `re.search`
behaves, needs to know this function structurally can't deliver that for a `*`/`+`-quantified
pattern — it finds *a* match, not the longest one.
{% endhint %}

`count_matches` and `split_by_literal` are both literal-only (no regex metacharacters at all,
despite living in this module) and non-overlapping: `count_matches("aa", "aaaa")` returns `2` (it
consumes each match and advances past it, `i += plen`, rather than re-checking overlapping
positions), and `split_by_literal("a,b,,c", ",")` returns `["a", "b", "", "c"]` — consecutive
delimiters produce an empty string in the output rather than being collapsed, unlike `text.regex`'s
character-class-based `regex_split` shown on the text-processing page. `is_valid_pattern` is a
lightweight syntax check (balanced brackets, no quantifier at the very start or doubled on the same
atom) rather than a real compile — `is_valid_pattern("*abc")` is `False` (a quantifier can't be the
first token), and `is_valid_pattern("[abc")` is `False` (an unclosed bracket), but it never runs the
pattern, so it says nothing about whether the pattern will actually match anything useful.

## `vector_similarity`: formulas over reductions, not over vectors

`vector_kernels.dot` (documented on [Vector ranking kernels](vector-ranking-kernels.md)) is a fixed
64-lane Float32 SIMD pipeline purpose-built for the bigram-hash name vectors behind column and
repository-file ranking: it takes two raw 64-element vectors and does the multiply-accumulate
itself. `vector_similarity` solves a more general version of the same problem by *not* doing that
reduction at all — every function takes `Float64` scalars that are already the result of summing
across whichever vector width the caller has (`dot`, `norm_a`, `norm_b`, `sum_sq_diff`,
`sum_abs_diff`, and so on), and applies only the final formula. That trade means `vector_similarity`
never has to know a vector's length or dtype — it works identically for a 3-dimensional feature
vector or a 4096-dimensional embedding — at the cost of leaving the (potentially expensive) act of
computing those sums entirely up to the caller. Neither module imports the other, and they solve
different halves of the same overall computation: one produces the reduced scalars, the other turns
reduced scalars into a similarity or distance number.

A worked chain for two small, easy-to-check vectors `a = [1, 2, 3]` and `b = [2, 3, 4]`:

```python
# a·b = 1*2 + 2*3 + 3*4 = 20; ||a|| = sqrt(14); ||b|| = sqrt(29) -- computed by the caller
dot, norm_a, norm_b = 20.0, 3.7416573867739413, 5.385164807134504

runtime.execute("vector_similarity", "cosine_similarity", [dot, norm_a, norm_b])["result"]
# 0.9925833339709303
runtime.execute("vector_similarity", "angular_distance", [dot, norm_a, norm_b])["result"]
# 0.007416666029069652  -- exactly 1 - cosine_similarity, reusing that same function internally

# sum((a_i - b_i)^2) = 1 + 1 + 1 = 3 -- also computed by the caller
runtime.execute("vector_similarity", "euclidean_distance", [3.0])["result"]
# 1.7320508075688772
runtime.execute("vector_similarity", "minkowski_distance", [3.0, 3.0])["result"]
# 1.4422495703074083  -- p=3; sum(|diff|^p) = 3 for this pair, same as sum_sq_diff by coincidence
```

`minkowski_distance` is implemented as `exp(log(sum_abs_p + 1e-300) / p)` rather than a direct
`sum_abs_p ** (1/p)` — mathematically the same value, but routed through `log`/`exp` so that `p` can
be any positive `Float64`, not just an integer a native power operator would require, and the
`1e-300` epsilon keeps `log(0)` from producing `-inf` when every dimension matches exactly. Passing
`p=1` reproduces `manhattan_distance`'s formula and `p=2` reproduces `euclidean_distance`'s, though
neither of those two simpler functions is implemented by calling `minkowski_distance` — each is its
own one-line pass-through of its pre-reduced scalar.

**Every guard clause returns a defined, non-crashing sentinel rather than propagating a division
error.** `cosine_similarity` and `pearson_correlation` return `0.0` if their denominator is `<= 0.0`
(a zero-norm vector, or a constant series with no variance to correlate); `jaccard_similarity` and
`hamming_distance_bits` return `0.0` for a zero-sized union or bit count. `dot_product`,
`manhattan_distance`, and `chebyshev_distance` are plain pass-throughs of their single pre-reduced
argument with no guard at all — there is nothing to divide by, so nothing can fail.

A Pearson correlation worked by hand, for two five-point series `x = [1,2,3,4,5]` and `y =
[5,3,4,2,1]` (a rough but not perfect negative relationship): `n=5`, `Σxy=36`, `Σx=15`, `Σy=15`,
`Σx²=55`, `Σy²=55`. `num = 5*36 - 15*15 = -45`; `denom_sq = (5*55-15²)*(5*55-15²) = 50*50 = 2500`;
`pearson_correlation(5, 36, 15, 15, 55, 55) = -45 / sqrt(2500) = -0.9` — strongly, but not perfectly,
inverse.

## Verification

All three modules' shipped test files (`test_string_distance.mojo`, `test_regex_engine.mojo`,
`test_vector_similarity.mojo`) are the corpus's auto-generated smoke suite: each calls every function
once with the literal argument `"test"` (string functions) or `0.5` (numeric functions) and checks
only that the result is finite or the call doesn't abort — none of them pin a real expected value.
`mojo/tests/libs/` and `tests/mojo/test_wave*.mojo` contain no hand-written suite for any of these
three modules. Every specific number on this page — `damerau_levenshtein`, `soundex`,
`edit_similarity`, `dice_coefficient`, the prefix/suffix lengths, every `regex_engine` trace
including the two `regex_find_first` surprises, and the `vector_similarity` cosine/Euclidean/
Minkowski/Pearson chain — was independently hand-traced against the real algorithms in
`mojo/engine/string_distance.mojo`, `mojo/engine/regex_engine.mojo`, and
`mojo/engine/vector_similarity.mojo`, and cross-checked with a plain-Python re-implementation of
each function's exact control flow rather than assumed from the docstrings alone.

**Next:** see `text.fuzzy` and `text.regex`, the modules these two string/regex kernels sit beside
without duplicating, on [Text processing kernels](text-processing-kernels.md); or see the raw-vector
SIMD path `vector_similarity` leaves to the caller on [Vector ranking kernels](vector-ranking-kernels.md).
