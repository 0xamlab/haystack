---
icon: spell-check
description: Fuzzy string distance, a hand-rolled regex engine, generic string utilities, word/sentence tokenization and a lexical column-name scorer, all zero-Python-import Mojo.
---

# Text processing kernels

Five small, dependency-free modules for the text operations everything else in the engine
leans on: how similar are two strings, does this string match that pattern, split/join/pad/trim,
turn a sentence into tokens, and — a narrower, more specific problem — how well does a
natural-language hint like "unit cost" name a candidate column like `UNIT_COST`. None of these
call into `re`, `difflib`, or `fuzzywuzzy`; each is a from-scratch Mojo implementation that
operates on raw bytes (`as_bytes()` / `byte_length()`), which is why several of them carry an
explicit ASCII-only caveat rather than pretending to be codepoint-aware.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("text.fuzzy", "jaro_winkler_similarity", ["authhandler", "auth_handler"])["result"]
# 0.9833333333333333 -- the same kernel apps/api_server/services/repository_intelligence_sdk_ranking.py
# dispatches to catch camelCase/snake_case aliases an exact-substring heuristic would miss

runtime.execute("text.tokenizer", "word_tokenize", ["Check OH_COST instead."])["result"]
# ['check', 'oh', 'cost', 'instead'] -- underscore is punctuation here, so OH_COST splits in two
```

## The modules

| Module | What it does |
| --- | --- |
| `text.fuzzy` | edit-distance and character-overlap similarity — Levenshtein, Jaro/Jaro-Winkler, Hamming, longest common subsequence and the ratios built on them — replacing `fuzzywuzzy`/`rapidfuzz` |
| `text.regex` | a hand-rolled backtracking matcher for `. * + ? ^ $ \| [...]` and the `\d \w \s` escapes, plus find-all/replace/split built on it — not a full PCRE engine, sized for data-validation patterns |
| `text.string_utils` | split/join/replace/contains/pad/trim/count/reverse/truncate/center — the `str.*` methods a Mojo module can't just inherit |
| `text.tokenizer` | word/sentence tokenization, character and word n-grams, stopword removal, a suffix stemmer, vocabulary size, token frequency and sequence padding |
| `text.column_scorer` | Jaccard token overlap, Dice bigram overlap and prefix coverage between a lower-cased hint and a lower-cased column name, combined into one weighted score for schema/column-name resolution |

## Fuzzy matching: five ways to say "how different"

`levenshtein_distance` is the textbook Wagner-Fischer DP (`O(mn)` time, two-row `O(min(m,n))`
space); `normalized_levenshtein` divides it by the longer string's length so two strings of very
different length don't automatically score as dissimilar. `jaro_similarity` and
`jaro_winkler_similarity` (prefix bonus over the first 4 shared characters, `prefix_weight` default
`0.1`) implement the classic algorithms directly — the textbook `MARTHA`/`MARHTA` example checks
out against this source exactly:

```python
runtime.execute("text.fuzzy", "jaro_similarity", ["MARTHA", "MARHTA"])["result"]
# 0.9444444444444445
runtime.execute("text.fuzzy", "jaro_winkler_similarity", ["MARTHA", "MARHTA"])["result"]
# 0.9611111111111111  -- shared 2-char prefix ("MA") gets a small boost over the plain Jaro score
```

`longest_common_subsequence` is a second `O(mn)` DP, reused by `fuzzy_ratio` (`2*LCS /
(len(a)+len(b))`, the same shape as a Dice coefficient) as an alternative to edit distance that
doesn't penalize transpositions and reordering as harshly. `hamming_distance` is the odd one out:
it only makes sense between equal-length strings, so it is the one function in this family
declared `raises` — call it with `a` and `b` of different lengths and it raises `Error
("hamming_distance: strings must be equal length")` instead of returning a number, rather than
silently truncating or padding.

Every similarity function in `text.fuzzy` and `text.column_scorer` shares the same two-line
empty-string convention: both inputs empty is a perfect match (`1.0`), exactly one empty is no
match (`0.0`). `normalized_levenshtein("", "")`, `jaro_similarity("", "")` and `fuzzy_ratio("", "")`
all return `1.0`; pair either with a non-empty string and the result is `0.0` — there's no attempt
to fall back to "distance equals the non-empty string's length" once one side is nothing.

## Column scoring: three lexical signals, one weighted composite

`text.column_scorer` is the lexical half of the engine's column-resolution pipeline (see
`plans/COLUMN_SCORING_DESIGN.md`): given a hint like `"unit cost"` and a column name like
`unit_cost`, produce a `[0, 1]` similarity that a resolver can combine with statistical signals
(magnitude, fill rate, source priors) to pick the right column without a hardcoded synonym table.
Both inputs must already be lower-cased and normalized by the caller — the module itself does no
case-folding.

Three independent signals feed the composite:

- **`score_token_overlap`** — Jaccard similarity (`|A ∩ B| / |A ∪ B|`) on tokens split at
  underscore, space and hyphen.
- **`score_ngram_overlap`** — Dice coefficient (`2|A ∩ B| / (|A| + |B|)`) on character bigrams
  by default (`n=2`; pass `n=3` for trigrams).
- **`score_prefix_match`** — the length of the shared prefix divided by `len(hint)`, so `"unit"`
  scores as a strong (if partial) match against `"unit_cost"` — the abbreviation case token/ngram
  overlap alone would miss.

`score_column_hint` combines them `0.50 * token + 0.30 * ngram + 0.20 * prefix`, clamped to
`[0, 1]`. Against a hint of `"unit cost"` and three real candidate columns from the design doc's
own worked scenario:

```python
runtime.execute("text.column_scorer", "score_column_hint", ["unit cost", "unit_cost"])["result"]
# 0.8138888888888889  (token=1.0, ngram=0.75, prefix=0.444)
runtime.execute("text.column_scorer", "score_column_hint", ["unit cost", "oh_cost"])["result"]
# 0.2952380952380952  (token=0.333, ngram=0.429, prefix=0.0)
runtime.execute("text.column_scorer", "score_column_hint", ["unit cost", "ext_cost"])["result"]
# 0.2866666666666666  (token=0.333, ngram=0.4, prefix=0.0)
```

`unit_cost` wins by roughly 3x over either distractor — both distractors share the `cost` token
(hence the identical `0.333` token score) but neither shares `unit`'s prefix, which is exactly the
signal `score_prefix_match` exists to add. All three component functions and the composite are
registered in the runtime dispatch table (`mojo/engine/runtime_library_dispatch_generated.mojo`),
so they're callable individually when a caller wants just the token or ngram signal rather than
the fixed 50/30/20 blend.

## Regex: an atom list with backtracking, not a compiled NFA

`text.regex`'s docstring is explicit about scope: literal match, `* + ? .`, character classes
(`[abc]`, `[a-z]`, `[0-9]`, negation with `[^...]`), anchors (`^ $`), alternation (`|`), and the
escapes `\d \w \s` (plus their negations `\D \W \S`) and backslash-escaped literals. It compiles a
pattern into a flat list of atoms and matches by recursive backtracking — greedy quantifiers try
the longest run first and shrink on failure — rather than building a state machine, which keeps
the implementation small at the cost of worst-case exponential blowup on adversarial patterns (the
same tradeoff every non-compiled backtracking engine makes).

```python
runtime.execute("text.regex", "regex_find_all", [r"\d+", "order 42 ships in 7 days"])["result"]
# ['42', '7']
runtime.execute("text.regex", "regex_replace", [r"\d+", "sku-104 qty-8", "#"])["result"]
# 'sku-# qty-#'
runtime.execute("text.regex", "regex_match", [r"^unit_[a-z]+$", "unit_cost"])["result"]
# True
runtime.execute("text.regex", "regex_match", [r"^unit_[a-z]+$", "ext_cost"])["result"]
# False
```

{% hint style="warning" %}
**`\d \w \s` only work outside `[...]`.** The character-class parser reads bytes between `[` and
`]` literally — it does not re-enter the escape logic, so a backslash inside a class is just
another literal character. `[,\s]+` therefore does **not** mean "comma or whitespace, one or
more"; it means "comma, backslash, or the letter `s`, one or more" (three literal alternatives).
Splitting on comma-or-space needs the class spelled out literally, `[, ]+`:

```python
runtime.execute("text.regex", "regex_split", [r"[, ]+", "a, b,  c,d"])["result"]
# ['a', 'b', 'c', 'd']
```

The mistaken `[,\s]+` pattern still runs without error — it just only ever matches the literal
comma, so it does not collapse the runs of spaces the way the class was meant to.
{% endhint %}

`regex_search` returns the first match's start index or `-1`; `is_match_literal` is a fast path
that skips the compiler entirely — it is exact string equality (`pattern == text`), intended for
callers who already know the pattern has no metacharacters, not a check that it doesn't. Its
neighbor `is_match_simple` is documented as ". `*` `+` `?` support (no character classes)" but
actually reuses the same atom compiler as `regex_match`, so `[a-z]` and `\d`/`\w`/`\s` work through
it too; what it genuinely drops is alternation (`_compile_branch` never calls the alternation
splitter, so a bare `|` is read as a literal pipe character, not "or") and true anchoring (`^`/`$`
are silently consumed as no-ops rather than enforced) — harmless in practice, since
`is_match_simple` already requires the match to consume the entire input.

## Tokenizer and string utilities

`text.tokenizer`'s `word_tokenize` splits on whitespace and a fixed 32-character ASCII
punctuation set (``,.!?;:'"()[]{}-/@#$%&*+=<>`~^|_`` — note underscore is in that set, so
`unit_cost` becomes two tokens, `unit` and `cost`, the same splitting rule `text.column_scorer`
uses for its token-overlap signal) and lowercases everything as it goes:

```python
runtime.execute("text.tokenizer", "word_tokenize",
                ["The UNIT_COST field is not populated; check OH_COST instead."])["result"]
# ['the', 'unit', 'cost', 'field', 'is', 'not', 'populated', 'check', 'oh', 'cost', 'instead']
```

`is_stopword` checks a fixed 35-word English list (`a, an, and, are, ...`); `stem_simple` strips
at most one trailing suffix per call, in priority order `ing > ed > ly > s` (and only on words
longer than 4 characters, so `"is"` and `"was"` pass through untouched) — `"populated"` stems to
`"populat"`, `"cost"` and `"field"` are unaffected. `token_frequency` returns `[[token,
count_str], ...]` sorted by count descending with ties broken by first appearance (a stable
insertion sort, not a hash-order shuffle); `vocabulary_size` and `word_ngrams` / `char_ngrams`
round out the set, and `pad_sequence` truncates or right-pads a token list to an exact length —
useful for building fixed-width batches:

```python
runtime.execute("text.tokenizer", "pad_sequence", [["a", "b"], 5, "<pad>"])["result"]
# ['a', 'b', '<pad>', '<pad>', '<pad>']
runtime.execute("text.tokenizer", "pad_sequence", [["a", "b", "c", "d"], 2, "<pad>"])["result"]
# ['a', 'b']  -- truncates, does not error, when the sequence is already longer than max_len
```

`text.string_utils` is the generic layer underneath: `str_split`/`str_join`/`str_replace`/
`str_contains`/`str_count` are non-overlapping byte-substring operations; `str_pad_left`/
`str_pad_right`/`str_center` are no-ops (return `s` unchanged) once `s` is already at or past the
target width rather than truncating it to fit; `str_truncate` appends its `suffix` only when
truncation actually happens, keeping `keep + len(suffix) == max_len` in the ordinary case:

```python
runtime.execute("text.string_utils", "str_truncate", ["unit_cost_extended", 12, "..."])["result"]
# 'unit_cost...'  -- 9 kept characters + 3-character suffix = 12
runtime.execute("text.string_utils", "str_center", ["cost", 10, "-"])["result"]
# '---cost---'
```

{% hint style="info" %}
`str_truncate`'s docstring promises the result is always `<= max_len`, but when `max_len` is
smaller than `len(suffix)` the clamp (`keep = max(0, max_len - len(suffix))`) floors the kept
portion at zero and the full suffix still gets appended — `str_truncate("unit_cost_extended", 2,
"...")` returns `"..."`, three characters, not two. The guarantee holds whenever `max_len >=
len(suffix)`; below that the suffix alone can exceed the requested width.
{% endhint %}

{% hint style="info" %}
**Byte-level, not codepoint-level.** `str_reverse`, `str_upper` and `str_lower` operate on ASCII
bytes (`str_upper`/`str_lower` only remap `A`-`Z` / `a`-`z`; everything else, including any
multi-byte UTF-8 sequence, passes through byte-for-byte). Reversing a string containing a
multi-byte character reverses its bytes individually, which does not reverse the character — it
corrupts it. These functions are for ASCII identifiers, column names and similar machine-generated
text, not arbitrary user-facing strings.
{% endhint %}

## Verification

The generated test suite for these five modules (`mojo/tests/libs/test_text_fuzzy.mojo`,
`test_text_regex.mojo`, `test_text_string_utils.mojo`, `test_text_tokenizer.mojo`,
`test_text_column_scorer.mojo`) is a smoke suite: it calls every function once with the literal
input `"test"` (or a small fixed list) and asserts the numeric outputs are finite and the
collection outputs have non-negative length — it catches a signature mismatch or a NaN, not a
wrong answer. The worked numbers above (`MARTHA`/`MARHTA`, the `unit_cost` scoring comparison, the
`\d+`/`[,\s]+` regex behavior) were checked by hand-tracing this page's exact algorithm against
the real source in `mojo/engine/text/{fuzzy,column_scorer,regex,string_utils,tokenizer}.mojo` —
the Jaro/Jaro-Winkler values reproduce the standard published `MARTHA`/`MARHTA` reference values
exactly, which is the closest thing this family has to an independent check.

**Next:** see how `text.fuzzy` earns a place in a real ranking pipeline in
[Retrieval & ranking](retrieval.md), or browse the [engine catalog](catalog.md).
