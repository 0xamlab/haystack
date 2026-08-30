---
icon: language
description: Corpus-linguistics readability and diversity statistics, a small from-scratch IR toolkit (TF-IDF, cosine, Jaccard), lexicon-based sentiment scoring, and the arithmetic primitives behind BPE/SentencePiece subword tokenization.
---

# Text processing and tokenization kernels

Four small, independent modules for the layer of an NLP pipeline that sits above raw string
operations and below a real trained tokenizer or language model: how readable is this text and how
lexically diverse, what are its terms worth relative to a corpus, whether a sentence reads as
positive or negative against a fixed lexicon, and the scoring formulas a BPE/SentencePiece
tokenizer's training and inference loop runs internally (merge-candidate ranking, vocabulary-size
estimation, compression ratio, out-of-vocabulary rate). None of the four build an actual tokenizer,
vocabulary, or language model — each is a set of `Float64`-in/`Float64`-out (or small `List[String]`)
formulas a caller wires into one, the same "replace the Python library with a from-scratch Mojo
formula" shape as the rest of this corpus.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("nlp", "tokenize", ["Hello World!"])["result"]
# ['hello', 'world'] -- lowercased, punctuation stripped (but NOT underscore -- see below)

runtime.execute("sentiment", "sentiment_score", ["This is great and wonderful"])["result"]
# 0.875 -- average of the two lexicon hits ("great"=0.9, "wonderful"=0.85);
# "this", "is", and "and" aren't in the lexicon and don't count toward the average
```

## The modules

| Module | What it does |
| --- | --- |
| `linguistics` | corpus-linguistics text statistics: type-token ratio, hapax legomena ratio, Yule's K, Heaps' law vocabulary growth, Zipf's frequency law, five readability indices (Flesch Reading Ease, Flesch-Kincaid Grade, Gunning Fog, Automated Readability Index, Coleman-Liau), lexical density, and mean word length |
| `nlp` | a small from-scratch information-retrieval toolkit: whitespace/punctuation tokenization, n-grams, term frequency, IDF, TF-IDF, cosine similarity, Jaccard similarity, word/char counts, and unique-token extraction — "replaces nltk / sklearn.feature\_extraction" per its own docstring |
| `sentiment` | lexicon-based sentiment scoring: a hardcoded ~60-word polarity lexicon, per-text polarity/subjectivity, positive/negative word counts, and the single most positive or most negative word in a text |
| `bpe_tokenizer` | the scoring arithmetic underneath BPE / SentencePiece subword tokenization: merge-candidate scoring, pair frequency, subword log-probability, vocabulary-size estimation for a target character coverage, compression ratio, fertility, OOV rate, and streaming token-boundary detection |

## `nlp` is not the already-documented `text.tokenizer`

[Text processing kernels](text-processing-kernels.md) documents five `text.*`-namespaced modules,
including `text.tokenizer`, whose `word_tokenize` splits on whitespace plus a 32-character ASCII
punctuation set that explicitly includes underscore — that page's own worked example is
`"unit_cost"` → `["unit", "cost"]`. `nlp` is a different, bare-named module
(`mojo/engine/nlp.mojo`, not `mojo/engine/text/tokenizer.mojo`) with a *similar but not identical*
byte-level tokenizer: `nlp.tokenize`'s own `_is_punct` set is 30 characters (`. , ! ? ; : ( ) [ ] { }
" ' - / \ @ # $ % & * + = < > | ~ \``) and — unlike `text.tokenizer`'s — does **not** include
underscore. Tracing both functions against the same input:

```python
runtime.execute("nlp", "tokenize", ["unit_cost"])["result"]
# ['unit_cost'] -- one token; underscore isn't in nlp's punctuation set
runtime.execute("text.tokenizer", "word_tokenize", ["unit_cost"])["result"]
# ['unit', 'cost'] -- two tokens; underscore IS in text.tokenizer's punctuation set
```

Past tokenization the two modules diverge in purpose, not just character sets. `text.tokenizer` is
general-purpose text splitting — sentence splitting, stopword removal, suffix stemming, sequence
padding — with no similarity or statistical scoring. `nlp` has none of those, but adds the small
information-retrieval toolkit `text.tokenizer` never had: `tf`/`idf`/`tfidf`, `cosine_similarity_vec`,
and `jaccard_similarity`. A caller doing schema/column-name matching wants `text.tokenizer` (or
`text.column_scorer`, built on the same underscore-splitting convention); a caller scoring document
relevance against a small corpus wants `nlp`. Nothing in either module imports the other, and using
the wrong one silently changes tokenization behavior on any string containing an underscore rather
than raising an error.

## `linguistics`: readability and lexical diversity, worked by hand

Every formula in `linguistics` is a closed-form scalar expression — no corpus state, no fitted
parameters — so each can be checked against its own docstring formula directly. `mojo/tests/libs/test_linguistics.mojo`
is the usual auto-generated smoke suite (calls every function once with `0.5`s and checks the result
is finite), but `tests/mojo/test_wave67.mojo` carries real, hand-computed pinned values for this
module. Reproducing a few of them:

- **Yule's K** — `yules_k(n_tokens=100.0, freq_spectrum_sum=200.0)`, i.e. `10000 * (M2 - N) / N²` =
  `10000 * (200 - 100) / 100² = 100.0`.
- **Heaps' law** — `heaps_law(k=10.0, beta=0.5, n_tokens=10000.0)` = `10 * 10000^0.5 = 10 * 100 =
  1000.0` expected vocabulary size.
- **Zipf's frequency** — `zipfs_frequency(rank=1.0, max_freq=1000.0, s=1.0) = 1000.0`;
  `zipfs_frequency(rank=2.0, ...) = 500.0` — frequency halves as rank doubles, at `s=1`.
- **Flesch Reading Ease** — 200 words, 10 sentences, 300 syllables:
  `206.835 - 1.015*(200/10) - 84.6*(300/200) = 206.835 - 20.3 - 126.9 = 59.635`.
- **Flesch-Kincaid Grade** — same inputs: `0.39*20 + 11.8*1.5 - 15.59 = 7.8 + 17.7 - 15.59 = 9.91`.
- **Gunning Fog** — 200 words, 10 sentences, 30 complex words:
  `0.4 * (20 + 100*30/200) = 0.4 * 35 = 14.0`.
- **Automated Readability Index** — 1000 chars, 200 words, 10 sentences:
  `4.71*(1000/200) + 0.5*(200/10) - 21.43 = 23.55 + 10 - 21.43 = 12.12`.
- **Coleman-Liau** — `L=500` letters/100w, `S=4` sentences/100w:
  `0.0588*500 - 0.296*4 - 15.8 = 29.4 - 1.184 - 15.8 = 12.416`.

```python
runtime.execute("linguistics", "flesch_reading_ease", [200.0, 10.0, 300.0])["result"]
# 59.635
runtime.execute("linguistics", "heaps_law", [10.0, 0.5, 10000.0])["result"]
# 1000.0
```

None of the five readability formulas guard against a zero denominator — `flesch_reading_ease`,
`gunning_fog_index`, and `automated_readability_index` all divide by `total_words` or
`total_sentences` directly, so a caller passing `total_sentences=0.0` (an empty document, or one
with no sentence-terminating punctuation) gets back `+inf`/`-inf`/`NaN` rather than a guarded
sentinel — unlike the `<= 0.0` guards common elsewhere in this corpus (`bpe_tokenizer`'s functions,
for instance, all guard their divisors). Callers need to check `total_words`/`total_sentences`
themselves before calling in.

## `sentiment`: a fixed ~60-word lexicon, not a trained model

`sentiment_score` (and its alias `polarity`) tokenizes with the module's own `tokenize_lower`
(alphabetic runs plus `'`/`-`, lowercased — a third, distinct tokenization rule from both `nlp` and
`text.tokenizer`), looks each token up in a hardcoded parallel-list lexicon of positive and negative
words, and averages the scores of the words that were found — words absent from the lexicon
(`this`, `is`, `and`, `the`, ...) don't participate in the average at all, they aren't scored as
`0.0` alongside the hits. `tests/mojo/test_wave34.mojo` pins real assertions against this behavior
(`mojo/tests/libs/test_sentiment.mojo` is otherwise the usual finite-check smoke suite):

```python
runtime.execute("sentiment", "word_sentiment", ["good"])["result"]
# 0.7
runtime.execute("sentiment", "sentiment_score", ["This is great and wonderful"])["result"]
# 0.875  -- (0.9 + 0.85) / 2; only "great" and "wonderful" are in the lexicon
runtime.execute("sentiment", "sentiment_label", [0.03])["result"]
# 'neutral'  -- the +-0.05 band around 0 is neutral, not just exactly 0.0
runtime.execute("sentiment", "count_negative_words", ["bad terrible"])["result"]
# 2
runtime.execute("sentiment", "most_positive_word", ["bad good excellent"])["result"]
# 'excellent'
```

`subjectivity` reuses the same lookup to report the *fraction* of tokens found in the lexicon at
all (regardless of sign) — `subjectivity("good great")` is pinned at exactly `1.0` (both words known),
while `subjectivity("the cat is good")` lands strictly between `0` and `1` (one hit out of four
tokens). This makes `subjectivity` a coverage statistic over the lexicon, not a measure of opinion
strength — a text entirely made of mild lexicon hits (`"ok fine nice"`, all positive but weak) scores
the same `1.0` subjectivity as one entirely made of extreme hits (`"perfect excellent amazing"`).

{% hint style="info" %}
**The lexicon lists `"horrible"` twice, but only the first copy is reachable.** `_lexicon_words()`
appends `"horrible"` at index 3 (score `-0.95`) and again later, with the source's own comment
marking it `# duplicate, skip in scores` — but `word_sentiment` returns on the *first* matching
index it finds, so the second entry (also scored `-0.95` in the parallel list, to keep the two lists
the same length) is simply dead data, never read. The lexicon still behaves correctly — both copies
carry the same score — but it is redundant rather than a doubled weight.
{% endhint %}

## `bpe_tokenizer`: the scoring math, not the tokenizer itself

None of `bpe_tokenizer`'s ten functions build a merge table, run a byte-pair-encoding loop, or hold
a vocabulary — each is a standalone formula a real BPE/SentencePiece implementation's training or
inference loop would call. There is no wave test for this module — `mojo/tests/libs/test_bpe_tokenizer.mojo`
is the auto-generated smoke suite only (every function called once with `0.5`s, checked for
finiteness), so the worked numbers below were hand-computed independently against the real source in
`mojo/engine/bpe_tokenizer.mojo` and checked with a separate calculation, not read off a pinned test:

```python
# pair (a, b) co-occurs 120 times; token a has corpus frequency 500, token b has 300
runtime.execute("bpe_tokenizer", "bpe_merge_score", [120.0, 500.0, 300.0])["result"]
# 0.0008  -- pair_frequency / (freq_a * freq_b); higher score merges earlier

runtime.execute("bpe_tokenizer", "tokenization_compression_ratio", [4000.0, 1000.0])["result"]
# 4.0  -- characters per token; the module's own docstring cites "GPT-4 ~= 4" as the reference point

runtime.execute("bpe_tokenizer", "vocab_fertility", [1200.0, 1000.0])["result"]
# 1.2  -- 1200 tokens over 1000 whitespace-split words: each word splits into 1.2 subword tokens on average
```

`subword_log_probability` and `sentencepiece_vocab_size_est` both guard their edge cases explicitly:
`subword_log_probability(token_count<=0, ...)` or a non-positive `total_tokens` returns the sentinel
`-1e300` rather than calling `log` on a non-positive number; `sentencepiece_vocab_size_est` returns
`corpus_chars` unchanged once `char_coverage >= target_coverage` (target already met, no larger
vocabulary needed) instead of dividing by a near-zero `(1 - target_coverage)`.

{% hint style="warning" %}
**`streaming_token_boundary` only implements one of the four punctuation ranges its own comment
names.** The function's docstring says "Punctuation range (simplified: 33-47, 58-64, 91-96,
123-126)", but the body (`mojo/engine/bpe_tokenizer.mojo`, lines 191-196) only tests
`char_code >= 33.0 and char_code <= 47.0` — the second, third, and fourth named ranges (`58-64`:
`:;<=>?@`; `91-96`: `[\]^_\``; `123-126`: `` {|}~ ``) are never checked. Concretely,
`streaming_token_boundary(58.0, 0.0)` (a colon, ASCII 58) returns `0.0` — "not a boundary" — even
though the function's own comment lists 58 as inside the punctuation range it means to detect.
`prev_char_code`, the function's second parameter, is also accepted but never read anywhere in the
body; only `char_code` drives the return value.
{% endhint %}

`byte_fallback_encode` is the identity function — `return text_bytes`, one output token per input
byte — which matches how SentencePiece's actual byte-fallback scheme works (each UTF-8 byte a
piece-vocabulary can't represent becomes exactly one `<0xNN>` token); the docstring's own
parenthetical, `"(3 per byte in some SPM)"`, doesn't describe what this function computes and reads
like a stray note rather than a spec the code follows.

## Verification

`linguistics` and `sentiment` both have real, hand-computed pinned assertions in
`tests/mojo/test_wave67.mojo` and `tests/mojo/test_wave34.mojo` respectively (the worked examples
above are drawn directly from those files' own comments and expected values); `nlp` has the same in
`tests/mojo/test_wave25.mojo` (`tokenize`, `tf`, `idf`, `tfidf`, `cosine_similarity_vec`, and
`jaccard_similarity` are all pinned there — `jaccard_similarity(["a","b"], ["b","c"]) ≈ 0.3333`
matches `1/3` exactly). `bpe_tokenizer` has no such wave suite; its four
`mojo/tests/libs/test_*.mojo` companions across all four modules are otherwise the standard
auto-generated smoke tests (call every function once, assert the result is finite or the returned
list has non-negative length) and none of them pin a specific numeric output.

**Next:** see the disambiguated sibling module `text.tokenizer` in
[Text processing kernels](text-processing-kernels.md), or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
