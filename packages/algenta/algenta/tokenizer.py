"""Text in, token ids out: the checkpoint's own BPE tokenizer, implemented here.

This is parity gap 1 from the beat-llama.cpp campaign's end-to-end gap analysis (2026-08-09):
until this module the kernel path was token-ids-in only, and any text had to be tokenized by an
external `transformers` install. This module reads the checkpoint's OWN `tokenizer.json` (the
Hugging Face tokenizers format) and implements exactly what it declares -- nothing more, nothing
imported from a tokenizer library. Two tokenizer FAMILIES are supported, detected from the file's
own normalizer/pre-tokenizer shape:

Qwen3/Qwen2 byte-level BPE (normalizer NFC, the byte-level pre-tokenizer Sequence)
-----------------------------------------------------------------------------------
* **Normalizer**: NFC, because `tokenizer.json` says `{"type": "NFC"}`.
* **Pre-tokenizer**: the GPT-4-style regex split (contractions, letter runs, single digits,
  punctuation/newline chunks, whitespace runs) with `behavior: Isolated`, then the byte-level
  alphabet mapping, because `tokenizer.json` says exactly that Sequence.
* **Model**: byte-level BPE with the file's own vocab + merge list, greedy lowest-rank merging.
* **Added tokens**: the file's special tokens (e.g. ENDOFTEXT, id 151643) matched verbatim,
  unnormalized, before any other processing -- special: true, normalized: false in the file.
* **Decoder**: the inverse byte-level map, then UTF-8.

llama-family SentencePiece-style BPE (the Prepend/Replace marker normalizer, no pre-tokenizer)
----------------------------------------------------------------------------------------------
* **Normalizer**: the SentencePiece marker convention, because tokenizer.json says
  Sequence [ Prepend the U+2581 marker, Replace space with the marker ]. At encode time this
  module reproduces what the reference implementation ACTUALLY runs (transformers' unified
  LlamaTokenizer backend: a Metaspace marking of spaces), which differs from the declared
  normalizer in one documented corner: when the text starts with a space, the space's own marker
  takes the prepend's place instead of doubling -- encode(' x') == encode('x'). Which segments
  get the prepend depends on the checkpoint's tokenizer_config.json legacy flag: legacy=false
  (TinyLlama) marks only the segment at the start of the text; legacy=true marks every segment.
* **Pre-tokenizer**: none, because tokenizer.json says null -- the whole marked text is one BPE
  word. There is NO byte-level alphabet mapping: the pieces ARE the marker-prefixed strings.
* **Model**: BPE with the file's own vocab + merge list, same greedy lowest-rank merging as the
  byte-level path. A character with no vocab entry falls back BEFORE merging, in the file's
  declared order: byte-fallback pieces (uppercase-hex byte tokens in angle brackets) first, then
  the declared unk piece (fused across a run when fuse_unk says so).
* **Added tokens**: the file's specials (unk id 0, BOS id 1, EOS id 2) matched verbatim, plus
  the tokenizer_config.json superset like the Qwen3 path. BOS is prepended by encode only when
  add_special_tokens=True -- matching transformers' default-encode convention.
* **Decoder**: the file's declared chain -- marker back to space, byte-fallback runs back to
  bytes (UTF-8 with replacement characters), fuse, then strip exactly one leading space.
* **Post-processor**: the file's TemplateProcessing BOS is read to know which id
  add_special_tokens=True prepends; a post_processor of any other type is refused.

GGUF-embedded llama SentencePiece BPE (tokenizer.ggml.model == "llama")
-----------------------------------------------------------------------
A GGUF model file EMBEDS its tokenizer in its metadata (tokenizer.ggml.tokens /
tokenizer.ggml.scores / tokenizer.ggml.token_type plus the bos/eos/unknown ids);
`Tokenizer.from_gguf_metadata` builds this same llama family directly from those tables -- a GGUF
carries no tokenizer.json. Two conventions differ from the tokenizer.json path above, both because
the GGUF's reference consumer is llama.cpp and this module reproduces llama.cpp's tokenizer
exactly (verified against llama.cpp's llm_tokenizer_spm_session):
* **Merge order comes from the scores, not a merge list.** The GGUF carries no merge table; BPE
  runs llama.cpp's score-greedy loop: seed every adjacent character pair whose concatenation is a
  vocab piece, repeatedly merge the pair whose MERGED piece has the highest
  tokenizer.ggml.scores entry (ties -> the leftmost pair), until nothing merges. A final symbol
  with no vocab entry falls back to byte-fallback pieces per UTF-8 byte (per-character unk when
  the file carries no byte pieces).
* **The space prepend is llama.cpp's, not Metaspace.** Every fragment at the start of the text or
  right after a special token gets a literal space prepended (tokenizer.ggml.add_space_prefix,
  default true) and THEN spaces are escaped to the marker -- NO leading-space absorption, so
  encode(' x') == [marker] + encode('x'), and a fragment after a special always gains a marker.
  Decode strips the leading space only when add_space_prefix is on. The specials are the file's
  unknown/control/user-defined token types; BOS is prepended by encode(add_special_tokens=True)
  only when the file's tokenizer.ggml.add_bos says so (llama.cpp's SPM default: true).

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **Three tokenizer sources.** The two tokenizer.json shapes above, detected from the file's own
  normalizer / pre-tokenizer declarations, plus the GGUF-embedded llama SentencePiece BPE. A
  tokenizer.json of another shape (Unigram, WordPiece, a different normalizer or pre-tokenizer
  stack) raises TokenizerFormatError naming the unsupported piece rather than half-tokenizing; a
  GGUF whose tokenizer.ggml.model is not "llama" (e.g. "gpt2" byte-level BPE) is refused the same
  way.
* **No chat template here.** Chat-template rendering (messages -> prompt text) is the separate
  algenta.chat_template module; this module is BPE encode/decode only.
* **Cross-validated, not assumed.** tests/test_tokenizer_qwen3.py checks the Qwen3 encode AND
  decode against transformers.AutoTokenizer on the real checkpoints (the same byte-for-byte-
  against-the-original convention algenta.qwen3_decode.prepare_checkpoint established), and
  tests/test_tokenizer_llama.py checks the llama family the same way against a llama checkpoint.
  Without the checkpoint on disk those oracle tests skip; the structural unit tests always run.

Usage
-----
    from algenta.tokenizer import load_tokenizer

    tok = load_tokenizer("/path/to/qwen3-checkpoint")   # reads tokenizer.json
    ids = tok.encode("The capital of France is")
    text = tok.decode(ids)

    llama = load_tokenizer("/path/to/llama-checkpoint") # same loader, family detected
    ids = llama.encode("The capital of France is", add_special_tokens=True)  # BOS prepended
    text = llama.decode(ids)
"""

from __future__ import annotations

import heapq
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

__all__ = [
    "TokenizerFormatError",
    "Tokenizer",
    "load_tokenizer",
]

# The llama-family word-boundary marker (SentencePiece convention): spaces become this, and one
# is prepended at the start of the text. It is U+2581, NOT an underscore.
_SP_MARKER = "\u2581"  # '▁'

# The llama-family byte-fallback pieces (0x00..0xFF spelled uppercase-hex in angle brackets,
# exactly as the reference model formats them). A decode-time run of these turns back into bytes.
_SP_BYTE_TOKEN_RE = re.compile(r"^<0x([0-9A-F]{2})>$")

# The byte-level BPE alphabet (GPT-2's, which Qwen2/Qwen3 inherit): printable ASCII and Latin-1
# ranges keep their own code points; every other byte maps to 256+n so all 256 bytes have distinct,
# printable, whitespace-free symbols. Space (32) becomes chr(288) = 'Ġ', newline (10) chr(266).
_BYTE_TO_SYMBOL: dict[int, str] = {}
_SYMBOL_TO_BYTE: dict[str, int] = {}


def _init_byte_alphabet() -> None:
    kept = list(range(ord("!"), ord("~") + 1))
    kept += list(range(ord("¡"), ord("¬") + 1))
    kept += list(range(ord("®"), ord("ÿ") + 1))
    symbols = kept[:]
    extra = 0
    for byte in range(256):
        if byte not in kept:
            kept.append(byte)
            symbols.append(256 + extra)
            extra += 1
    for byte, symbol in zip(kept, symbols):
        _BYTE_TO_SYMBOL[byte] = chr(symbol)
        _SYMBOL_TO_BYTE[chr(symbol)] = byte


_init_byte_alphabet()


class TokenizerFormatError(ValueError):
    """The checkpoint's tokenizer.json is neither supported shape -- not the Qwen3-family
    byte-level BPE, not the llama-family SentencePiece-style BPE.

    Raised at load time, naming the unsupported piece -- never a half-tokenizer."""


def _unicode_category_class_contents(category_prefixes: tuple[str, ...]) -> str:
    """The CONTENTS (no surrounding brackets) of a Python-`re` character class covering every code
    point whose unicodedata category starts with one of `category_prefixes` -- the translation of
    `\\p{L}` / `\\p{N}` the pre-tokenizer regex uses (Python's `re` has no Unicode-property
    escapes, and this module takes no third-party regex dependency for one character class). Every
    member is re.escape'd, so the contents are safe to embed in ANY bracket expression. Built
    once per process (lru_cache below)."""
    ranges: list[tuple[int, int]] = []
    start = -1
    prev = -2
    for code in range(0x110000):
        if unicodedata.category(chr(code)).startswith(category_prefixes):
            if code != prev + 1:
                if start >= 0:
                    ranges.append((start, prev))
                start = code
            prev = code
    if start >= 0:
        ranges.append((start, prev))
    parts: list[str] = []
    for lo, hi in ranges:
        if lo == hi:
            parts.append(re.escape(chr(lo)))
        else:
            parts.append(f"{re.escape(chr(lo))}-{re.escape(chr(hi))}")
    return "".join(parts)


@lru_cache(maxsize=1)
def _letter_class_contents() -> str:
    return _unicode_category_class_contents(("L",))


@lru_cache(maxsize=1)
def _number_class_contents() -> str:
    return _unicode_category_class_contents(("N",))


# The Qwen3 pre-tokenizer split pattern, as declared by its tokenizer.json, with the two
# Unicode-property escapes resolved to explicit code-point ranges (see
# _unicode_category_class_contents). The shape is GPT-4's: contractions first, then optional-lead
# letter runs, lone digits, punctuation chunks (with trailing newlines), newline runs with leading
# space, dangling whitespace, and finally plain whitespace. __LRAW__/__NRAW__ stand for the raw
# class contents so the SAME template also renders the literal \p{L}/\p{N} source the file's
# pattern is compared against (see from_tokenizer_json).
_PRETOKENIZE_REGEX_TEMPLATE = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
    r"|[^\r\n__LRAW____NRAW__]?[__LRAW__]+"
    r"|[__NRAW__]"
    r"| ?[^\s__LRAW____NRAW__]+[\r\n]*"
    r"|\s*[\r\n]+"
    r"|\s+(?!\S)"
    r"|\s+"
)


def _render_pretokenize_pattern(letter_raw: str, number_raw: str) -> str:
    return _PRETOKENIZE_REGEX_TEMPLATE.replace("__LRAW__", letter_raw).replace(
        "__NRAW__", number_raw
    )


# The EXACT source form tokenizer.json carries (compared verbatim at load time). Same language as
# _PRETOKENIZE_REGEX_TEMPLATE, with \p{L}/\p{N} left as the file spells them.
_EXPECTED_PRETOKENIZE_PATTERN = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
    r"|[^\r\n\p{L}\p{N}]?\p{L}+"
    r"|\p{N}"
    r"| ?[^\s\p{L}\p{N}]+[\r\n]*"
    r"|\s*[\r\n]+"
    r"|\s+(?!\S)"
    r"|\s+"
)


class Tokenizer:
    """One checkpoint's tokenizer, loaded from its own tokenizer.json. Immutable after load.

    One class carries all three supported sources: the Qwen3 byte-level BPE (the default
    construction -- `sentencepiece=False`), the llama-family SentencePiece-style BPE from a
    tokenizer.json (`sentencepiece=True`, which switches encode/decode to the marker pipeline and
    leaves the byte-level fields unused), and the llama SentencePiece BPE EMBEDDED in a GGUF file
    (`sentencepiece=True` + `sp_gguf=True` -- the llama.cpp conventions: score-greedy merging from
    `sp_scores` and the llama.cpp space-prepend scheme, see the module docstring)."""

    def __init__(
        self,
        *,
        vocab: dict[str, int],
        merges: dict[tuple[str, str], int],
        special_tokens: dict[str, int],
        pretokenize_regex: re.Pattern | None,
        sentencepiece: bool = False,
        sp_legacy: bool = True,
        byte_fallback: bool = False,
        fuse_unk: bool = False,
        unk_token: str | None = None,
        bos_id: int | None = None,
        sp_gguf: bool = False,
        sp_scores: dict[str, float] | None = None,
        add_bos: bool = True,
        add_space_prefix: bool = True,
        eos_id: int | None = None,
    ) -> None:
        self._vocab = vocab
        self._id_to_token = {token_id: token for token, token_id in vocab.items()}
        self._merges = merges
        self._special_tokens = special_tokens
        self._special_by_id = {token_id: token for token, token_id in special_tokens.items()}
        self._pretokenize = pretokenize_regex
        # Longest-first so a shorter special string never shadows a longer one at the same spot.
        self._special_sorted = sorted(special_tokens, key=len, reverse=True)
        # The llama-family fields (unused by the Qwen3 byte-level path).
        self._sentencepiece = sentencepiece
        self._sp_legacy = sp_legacy
        self._byte_fallback = byte_fallback
        self._fuse_unk = fuse_unk
        self._unk_token = unk_token
        self._bos_id = bos_id
        # The GGUF-embedded fields (unused by the tokenizer.json paths). `sp_gguf` switches
        # encode/decode to the llama.cpp conventions; `sp_scores` carries the merge scores;
        # `add_bos` / `add_space_prefix` are the file's tokenizer.ggml flags; `eos_id` is the
        # file's declared end-of-sequence id (the GGUF says it outright; a tokenizer.json's is
        # looked up from the specials instead).
        self._sp_gguf = sp_gguf
        self._sp_scores = sp_scores or {}
        self._add_bos = add_bos
        self._add_space_prefix = add_space_prefix
        self._eos_id = eos_id

    @classmethod
    def from_tokenizer_json(cls, path: str | Path, *, legacy: bool = True) -> "Tokenizer":
        """Load one tokenizer.json. The FAMILY is detected from the file's own shape: the NFC /
        byte-level pre-tokenizer declarations load the Qwen3 byte-level BPE; the SentencePiece
        marker normalizer with NO pre-tokenizer loads the llama-family pipeline. `legacy` is the
        llama-family prepend scheme switch (the checkpoint's tokenizer_config.json `legacy`
        flag); the Qwen3 path ignores it."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))

        model = raw.get("model") or {}
        if model.get("type") != "BPE":
            raise TokenizerFormatError(
                f"unsupported tokenizer model type {model.get('type')!r}: this module implements "
                "the Qwen3-family byte-level BPE and the llama-family SentencePiece BPE only."
            )
        vocab = model.get("vocab")
        merge_rules = model.get("merges")
        if not isinstance(vocab, dict) or not isinstance(merge_rules, list):
            raise TokenizerFormatError(
                "tokenizer.json model is missing its vocab/merges tables; cannot load."
            )

        normalizer = raw.get("normalizer")
        if _is_sentencepiece_normalizer(normalizer) and raw.get("pre_tokenizer") is None:
            return cls._from_sentencepiece_json(raw, vocab, merge_rules, legacy=legacy)

        if normalizer not in (None, {"type": "NFC"}):
            raise TokenizerFormatError(
                f"unsupported normalizer {normalizer!r}: this module implements the Qwen3 NFC "
                "normalizer and the llama-family Prepend/Replace marker normalizer only."
            )

        pre_tokenizer = raw.get("pre_tokenizer") or {}
        stages = pre_tokenizer.get("pretokenizers")
        if pre_tokenizer.get("type") != "Sequence" or not isinstance(stages, list) or len(stages) != 2:
            raise TokenizerFormatError(
                f"unsupported pre_tokenizer {pre_tokenizer.get('type')!r}: expected the Qwen3 "
                "Sequence of [regex Split, ByteLevel]."
            )
        split_stage, byte_stage = stages
        if split_stage.get("type") != "Split" or split_stage.get("behavior") != "Isolated":
            raise TokenizerFormatError(
                f"unsupported pre-tokenizer split stage {split_stage.get('type')!r}: expected an "
                "Isolated regex Split."
            )
        pattern = (split_stage.get("pattern") or {}).get("Regex")
        if not isinstance(pattern, str):
            raise TokenizerFormatError("the pre-tokenizer split stage carries no Regex pattern.")
        _assert_byte_level_stage(byte_stage, "pre-tokenizer")

        decoder = raw.get("decoder")
        if decoder not in (None,):
            _assert_byte_level_stage(decoder, "decoder")
        post = raw.get("post_processor")
        if post is not None:
            _assert_byte_level_stage(post, "post_processor")

        # The file's regex is GPT-4's, with \p{L}/\p{N}; resolve those to explicit ranges and
        # VERIFY the source is EXACTLY the pattern this module implements -- a different split
        # regex would silently change tokenization, so it is refused instead.
        resolved = _render_pretokenize_pattern(
            _letter_class_contents(), _number_class_contents()
        )
        if pattern != _EXPECTED_PRETOKENIZE_PATTERN:
            raise TokenizerFormatError(
                "the pre-tokenizer regex is not the GPT-4-style pattern this module implements; "
                "refusing rather than tokenizing against a different split."
            )

        merges = _parse_merge_rules(merge_rules)
        special_tokens = _parse_added_tokens(raw)

        full_vocab = dict(vocab)
        for content, token_id in special_tokens.items():
            full_vocab.setdefault(content, token_id)

        return cls(
            vocab=full_vocab,
            merges=merges,
            special_tokens=special_tokens,
            pretokenize_regex=re.compile(resolved),
        )

    @classmethod
    def _from_sentencepiece_json(
        cls,
        raw: dict,
        vocab: dict,
        merge_rules: list,
        *,
        legacy: bool,
    ) -> "Tokenizer":
        """The llama-family shape: the marker normalizer (validated by the caller), NO
        pre-tokenizer, BPE directly on the marker-prefixed pieces. Every declared piece of the
        file is verified verbatim -- a different decoder/post-processor/model-flag set is refused
        rather than half-tokenized, exactly like the Qwen3 path does for its shape."""
        model = raw["model"]

        dropout = model.get("dropout")
        if dropout is not None:
            raise TokenizerFormatError(
                f"unsupported BPE dropout {dropout!r}: dropout randomizes merges; this module "
                "implements deterministic BPE only."
            )
        for key in ("continuing_subword_prefix", "end_of_word_suffix"):
            if model.get(key) not in (None, ""):
                raise TokenizerFormatError(
                    f"unsupported BPE {key} {model.get(key)!r}: the llama-family pipeline merges "
                    "the marked pieces with no extra prefix/suffix."
                )
        if model.get("ignore_merges"):
            raise TokenizerFormatError(
                "ignore_merges=true is unsupported: this pipeline is merge-driven BPE."
            )
        unk_token = model.get("unk_token")
        if unk_token is not None and not isinstance(unk_token, str):
            raise TokenizerFormatError(f"malformed unk_token {unk_token!r}.")
        if unk_token is not None and unk_token not in vocab:
            raise TokenizerFormatError(
                f"the declared unk_token {unk_token!r} has no vocab entry; cannot load."
            )
        byte_fallback = bool(model.get("byte_fallback"))
        fuse_unk = bool(model.get("fuse_unk"))

        decoder = raw.get("decoder")
        if not _is_sentencepiece_decoder(decoder):
            raise TokenizerFormatError(
                f"unsupported decoder {decoder!r}: the llama-family shape declares the Sequence "
                "[Replace marker->space, ByteFallback, Fuse, Strip one leading space]."
            )

        # The declared TemplateProcessing prepends the BOS special to a single sequence; that is
        # the id encode(add_special_tokens=True) prepends (the transformers default-encode
        # convention). No post-processor means no BOS to add.
        post = raw.get("post_processor")
        bos_id = None
        if post is not None:
            if not isinstance(post, dict) or post.get("type") != "TemplateProcessing":
                raise TokenizerFormatError(
                    f"unsupported post_processor {post!r}: the llama-family shape declares the "
                    "BOS-prepending TemplateProcessing."
                )
            single = post.get("single")
            if (
                not isinstance(single, list)
                or not single
                or not isinstance(single[0], dict)
                or not isinstance(single[0].get("SpecialToken"), dict)
            ):
                raise TokenizerFormatError(
                    f"unsupported post_processor single template {single!r}: expected a leading "
                    "SpecialToken (the BOS)."
                )
            bos_content = single[0]["SpecialToken"].get("id")
            if not isinstance(bos_content, str):
                raise TokenizerFormatError(
                    f"the post_processor BOS entry carries no token string: {single[0]!r}."
                )
            bos_id = vocab.get(bos_content)
            if bos_id is None:
                raise TokenizerFormatError(
                    f"the post_processor BOS {bos_content!r} has no vocab entry; cannot load."
                )

        merges = _parse_merge_rules(merge_rules)
        special_tokens = _parse_added_tokens(raw)

        full_vocab = dict(vocab)
        for content, token_id in special_tokens.items():
            full_vocab.setdefault(content, token_id)

        return cls(
            vocab=full_vocab,
            merges=merges,
            special_tokens=special_tokens,
            pretokenize_regex=None,
            sentencepiece=True,
            sp_legacy=legacy,
            byte_fallback=byte_fallback,
            fuse_unk=fuse_unk,
            unk_token=unk_token,
            bos_id=bos_id,
        )

    @classmethod
    def from_gguf_metadata(cls, metadata: dict) -> "Tokenizer":
        """The tokenizer EMBEDDED in a GGUF file's metadata (the `tokenizer.ggml.*` keys), built
        with llama.cpp's exact SentencePiece-BPE conventions (see the module docstring section).
        `metadata` is the parsed GGUF metadata kv dict (`algenta.inference._read_gguf_header`).
        Only `tokenizer.ggml.model == "llama"` is implemented; anything else raises
        TokenizerFormatError naming what the file carries -- never a half-tokenizer."""
        model = metadata.get("tokenizer.ggml.model")
        if model != "llama":
            raise TokenizerFormatError(
                f"unsupported GGUF tokenizer model {model!r}: this module implements the 'llama' "
                "SentencePiece BPE embedded tokenizers only."
            )

        def _require_list(key: str, item_check: Any) -> list:
            value = metadata.get(key)
            if (
                not isinstance(value, list)
                or not value
                or not all(item_check(item) for item in value)
            ):
                raise TokenizerFormatError(
                    f"the GGUF file carries no usable {key} array; cannot build a tokenizer "
                    "from it."
                )
            return value

        tokens = _require_list("tokenizer.ggml.tokens", lambda item: isinstance(item, str))
        scores = _require_list(
            "tokenizer.ggml.scores",
            lambda item: isinstance(item, int | float) and not isinstance(item, bool),
        )
        if len(scores) != len(tokens):
            raise TokenizerFormatError(
                f"the GGUF tokenizer arrays disagree: {len(tokens)} tokens vs {len(scores)} "
                "scores; cannot build a tokenizer from them."
            )
        token_types = metadata.get("tokenizer.ggml.token_type")
        if token_types is not None:
            if (
                not isinstance(token_types, list)
                or len(token_types) != len(tokens)
                or not all(
                    isinstance(item, int) and not isinstance(item, bool) for item in token_types
                )
            ):
                raise TokenizerFormatError(
                    f"the GGUF file's tokenizer.ggml.token_type array is malformed ({len(tokens)} "
                    "tokens declared); cannot build a tokenizer from it."
                )

        def _special_id(key: str) -> int | None:
            """One declared special id. GGUF version 3 allows an ARRAY of ids (multi-EOS models);
            the first element stands in -- encode prepends one BOS, and decode/stop care about
            identity, not multiplicity, here."""
            value = metadata.get(key)
            if isinstance(value, list):
                value = value[0] if value else None
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < len(tokens):
                raise TokenizerFormatError(
                    f"the GGUF file's {key} is {metadata.get(key)!r}; expected an in-vocab token "
                    "id (or a non-empty array of them)."
                )
            return value

        unk_id = _special_id("tokenizer.ggml.unknown_token_id")
        bos_id = _special_id("tokenizer.ggml.bos_token_id")
        eos_id = _special_id("tokenizer.ggml.eos_token_id")
        pad_id = _special_id("tokenizer.ggml.padding_token_id")

        def _flag(key: str, default: bool) -> bool:
            value = metadata.get(key)
            return value if isinstance(value, bool) else default

        # llama.cpp's SPM defaults: BOS added, space prefix prepended (the flags' documented
        # defaults in llama_vocab.cpp's LLAMA_VOCAB_TYPE_SPM branch).
        add_bos = _flag("tokenizer.ggml.add_bos", True)
        add_space_prefix = _flag("tokenizer.ggml.add_space_prefix", True)

        # The vocab and the score table: FIRST occurrence wins on a duplicated piece string, the
        # same convention llama.cpp's token_to_id map uses.
        vocab: dict[str, int] = {}
        sp_scores: dict[str, float] = {}
        for token_id, token in enumerate(tokens):
            vocab.setdefault(token, token_id)
            sp_scores.setdefault(token, float(scores[token_id]))

        # The specials: the file's own unknown/control/user-defined pieces (ggml token types 2,
        # 3, 4) -- matched verbatim, never BPE-split, rendered literally by decode. Without a
        # token_type array the declared special ids stand in.
        special_tokens: dict[str, int] = {}
        if token_types is not None:
            for token_id, token_type in enumerate(token_types):
                if token_type in (2, 3, 4):
                    special_tokens.setdefault(tokens[token_id], token_id)
        else:
            for token_id in (unk_id, bos_id, eos_id, pad_id):
                if token_id is not None:
                    special_tokens.setdefault(tokens[token_id], token_id)
        for token_id in (unk_id, bos_id, eos_id, pad_id):
            if token_id is not None:
                special_tokens.setdefault(tokens[token_id], token_id)

        unk_token = tokens[unk_id] if unk_id is not None else None
        if unk_token is not None and unk_token not in vocab:
            raise TokenizerFormatError(
                f"the GGUF file's declared unk piece {unk_token!r} has no vocab entry; cannot "
                "load."
            )
        # Byte fallback is a FACT of the vocab (all 256 uppercase-hex byte pieces present), the
        # same truth llama.cpp's byte_to_token consults at encode time.
        byte_fallback = all(f"<0x{byte:02X}>" in vocab for byte in range(256))

        return cls(
            vocab=vocab,
            merges={},
            special_tokens=special_tokens,
            pretokenize_regex=None,
            sentencepiece=True,
            sp_gguf=True,
            sp_scores=sp_scores,
            byte_fallback=byte_fallback,
            fuse_unk=False,
            unk_token=unk_token,
            bos_id=bos_id,
            add_bos=add_bos,
            add_space_prefix=add_space_prefix,
            eos_id=eos_id,
        )

    # ── encode ────────────────────────────────────────────────────────────────────────────────

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        """Text -> token ids, following the family's pipeline. Qwen3: added-token split
        (verbatim, unnormalized), NFC, the regex split, byte-level mapping, BPE. llama family:
        added-token split, the marker Metaspace, BPE on the marked pieces (see
        `_encode_sentencepiece`).

        `add_special_tokens` matches the transformers naming. The Qwen3 path wraps no specials,
        so True and False behave identically there unless the text itself contains a special
        string (which is mapped either way). The llama-family path prepends the BOS id declared
        by the file's post_processor when True -- the same convention
        `transformers.AutoTokenizer.encode` defaults to. The GGUF-embedded path additionally
        honors the file's tokenizer.ggml.add_bos flag (llama.cpp's SPM default: true)."""
        if self._sentencepiece:
            if self._sp_gguf:
                return self._encode_gguf_sentencepiece(text, add_special_tokens=add_special_tokens)
            return self._encode_sentencepiece(text, add_special_tokens=add_special_tokens)
        del add_special_tokens
        ids: list[int] = []
        for piece, is_special in self._split_specials(text):
            if is_special:
                ids.append(self._special_tokens[piece])
                continue
            normalized = unicodedata.normalize("NFC", piece)
            for chunk in self._pretokenize.findall(normalized):
                ids.extend(self._bpe_chunk(chunk))
        return ids

    def _split_specials(self, text: str) -> list[tuple[str, bool]]:
        if not self._special_sorted:
            return [(text, False)]
        pieces: list[tuple[str, bool]] = []
        remaining = text
        while remaining:
            best_pos = len(remaining)
            best_token: str | None = None
            for token in self._special_sorted:
                pos = remaining.find(token)
                if pos != -1 and pos < best_pos:
                    best_pos = pos
                    best_token = token
                    if pos == 0:
                        break
            if best_pos > 0:
                pieces.append((remaining[:best_pos], False))
            if best_token is None:
                break
            pieces.append((best_token, True))
            remaining = remaining[best_pos + len(best_token) :]
        return pieces

    # ── encode, llama family ──────────────────────────────────────────────────────────────────

    def _encode_sentencepiece(self, text: str, *, add_special_tokens: bool) -> list[int]:
        """The llama-family encode: specials split verbatim; every other segment gets its spaces
        turned into the U+2581 marker and ONE BPE run over the whole marked segment (the file
        declares no pre-tokenizer). The marker prepend follows the reference Metaspace scheme:
        with `legacy=false` (the checkpoint's tokenizer_config.json flag) only the segment at
        the very start of the text is prepend-eligible, with `legacy=true` every segment is; a
        segment whose replaced form already starts with the marker (the text began with a space)
        is never prepended -- the space's own marker takes its place."""
        ids: list[int] = []
        if add_special_tokens and self._bos_id is not None:
            ids.append(self._bos_id)
        for position, (piece, is_special) in enumerate(self._split_specials(text)):
            if is_special:
                ids.append(self._special_tokens[piece])
                continue
            if not piece:
                continue
            chunk = piece.replace(" ", _SP_MARKER)
            if not chunk.startswith(_SP_MARKER) and (position == 0 or self._sp_legacy):
                chunk = _SP_MARKER + chunk
            ids.extend(self._bpe_sentencepiece(chunk))
        return ids

    def _bpe_sentencepiece(self, chunk: str) -> list[int]:
        """BPE over the chunk's own characters -- no byte-level alphabet. A character with no
        vocab entry falls back BEFORE merging, in the order the file declares: byte_fallback
        turns it into its UTF-8 bytes as byte-fallback pieces (when every one of them is in the
        vocab), else the unk piece stands in -- fused into ONE piece across a run when fuse_unk
        says so. Then the same greedy lowest-rank merging as the byte-level path."""
        symbols: list[str] = []
        pending_unk = False

        def flush_unk() -> None:
            nonlocal pending_unk
            if pending_unk:
                symbols.append(self._unk_token)
                pending_unk = False

        for char in chunk:
            if char in self._vocab:
                flush_unk()
                symbols.append(char)
                continue
            if self._byte_fallback:
                byte_pieces = [f"<0x{byte:02X}>" for byte in char.encode("utf-8")]
                if all(piece in self._vocab for piece in byte_pieces):
                    flush_unk()
                    symbols.extend(byte_pieces)
                    continue
            if self._unk_token is None:
                raise TokenizerFormatError(
                    f"character {char!r} has no vocab entry and the model declares neither "
                    "usable byte_fallback pieces nor an unk_token; cannot encode."
                )
            if pending_unk and self._fuse_unk:
                continue  # one unk piece for the whole OOV run
            flush_unk()
            pending_unk = True
        flush_unk()

        while len(symbols) > 1:
            best_rank = len(self._merges)
            best_pair: tuple[str, str] | None = None
            for i in range(len(symbols) - 1):
                rank = self._merges.get((symbols[i], symbols[i + 1]))
                if rank is not None and rank < best_rank:
                    best_rank = rank
                    best_pair = (symbols[i], symbols[i + 1])
            if best_pair is None:
                break
            merged: list[str] = []
            i = 0
            while i < len(symbols):
                if (
                    i < len(symbols) - 1
                    and symbols[i] == best_pair[0]
                    and symbols[i + 1] == best_pair[1]
                ):
                    merged.append(best_pair[0] + best_pair[1])
                    i += 2
                else:
                    merged.append(symbols[i])
                    i += 1
            symbols = merged
        return [self._piece_id(symbol) for symbol in symbols]

    # ── encode, GGUF-embedded llama family (llama.cpp conventions) ──────────────────────────

    def _encode_gguf_sentencepiece(self, text: str, *, add_special_tokens: bool) -> list[int]:
        """The GGUF-embedded encode, llama.cpp's exact SPM pipeline (llama_vocab.cpp's
        LLAMA_VOCAB_TYPE_SPM branch + llm_tokenizer_spm_session): specials split verbatim; each
        remaining fragment gets a literal space prepended when it starts the text or follows a
        special (add_space_prefix, the file's tokenizer.ggml.add_space_prefix -- default true),
        then ALL spaces escape to the marker -- no Metaspace absorption, so a leading space
        doubles the marker instead of taking the prepend's place. BOS is prepended for
        add_special_tokens=True only when the file's add_bos says so."""
        ids: list[int] = []
        if add_special_tokens and self._add_bos and self._bos_id is not None:
            ids.append(self._bos_id)
        is_prev_special = True  # llama.cpp: "prefix with space if first token"
        for piece, is_special in self._split_specials(text):
            if is_special:
                ids.append(self._special_tokens[piece])
                is_prev_special = True
                continue
            if not piece:
                continue
            if self._add_space_prefix and is_prev_special:
                piece = " " + piece
            ids.extend(self._bpe_gguf_spm(piece.replace(" ", _SP_MARKER)))
            is_prev_special = False
        return ids

    def _bpe_gguf_spm(self, chunk: str) -> list[int]:
        """llama.cpp's score-greedy SentencePiece BPE over the chunk's own characters: every
        adjacent pair whose concatenation is a vocab piece is a merge candidate keyed by the
        merged piece's tokenizer.ggml.scores entry; repeatedly merge the HIGHEST-score candidate
        (ties -> leftmost), exactly the llm_tokenizer_spm_session work queue. A final symbol the
        vocab does not carry resolves to byte-fallback pieces per UTF-8 byte (per character the
        unk piece when the file has no byte pieces) -- llama.cpp's resegment byte fallback."""
        if not chunk:
            return []
        symbols: list[str | None] = list(chunk)
        count = len(symbols)
        prev = [index - 1 for index in range(count)]
        nxt = [index + 1 if index < count - 1 else -1 for index in range(count)]
        # (negative score, left index, insertion order, right index, merged text): heapq pops
        # highest score first, leftmost first on a score tie -- the llm_bigram_spm comparator.
        queue: list[tuple[float, int, int, int, str]] = []
        insertion = 0

        def try_add(left: int, right: int) -> None:
            nonlocal insertion
            if left == -1 or right == -1:
                return
            left_sym = symbols[left]
            right_sym = symbols[right]
            if left_sym is None or right_sym is None:
                return
            text = left_sym + right_sym
            score = self._sp_scores.get(text)
            if score is None:
                return
            heapq.heappush(queue, (-score, left, insertion, right, text))
            insertion += 1

        for index in range(1, count):
            try_add(index - 1, index)
        while queue:
            _, left, _, right, text = heapq.heappop(queue)
            left_sym = symbols[left]
            right_sym = symbols[right]
            # A stale candidate: either symbol already merged away, or the merge text changed.
            if left_sym is None or right_sym is None or left_sym + right_sym != text:
                continue
            symbols[left] = text
            symbols[right] = None
            nxt[left] = nxt[right]
            if nxt[left] != -1:
                prev[nxt[left]] = left
            try_add(prev[left], left)
            try_add(left, nxt[left])

        ids: list[int] = []
        index = 0
        while index != -1:
            symbol = symbols[index]
            assert symbol is not None
            token_id = self._vocab.get(symbol)
            if token_id is not None:
                ids.append(token_id)
            else:
                byte_ids = [
                    self._vocab.get(f"<0x{byte:02X}>") for byte in symbol.encode("utf-8")
                ]
                if all(byte_id is not None for byte_id in byte_ids):
                    ids.extend(byte_ids)  # type: ignore[arg-type]
                elif self._unk_token is not None:
                    unk_id = self._vocab[self._unk_token]
                    ids.extend(unk_id for _ in symbol)
                else:
                    raise TokenizerFormatError(
                        f"piece {symbol!r} has no vocab entry and the GGUF file carries neither "
                        "byte-fallback pieces nor an unk piece; cannot encode."
                    )
            index = nxt[index]
        return ids

    # ── encode, Qwen3 family ──────────────────────────────────────────────────────────────────

    def _bpe_chunk(self, chunk: str) -> list[int]:
        symbols = [_BYTE_TO_SYMBOL[b] for b in chunk.encode("utf-8")]
        if len(symbols) == 1:
            return [self._piece_id(symbols[0])]
        # Greedy lowest-rank merging: at every step merge ALL occurrences of the lowest-rank pair
        # present, exactly as the reference BPE does.
        while len(symbols) > 1:
            best_rank = len(self._merges)
            best_pair: tuple[str, str] | None = None
            for i in range(len(symbols) - 1):
                rank = self._merges.get((symbols[i], symbols[i + 1]))
                if rank is not None and rank < best_rank:
                    best_rank = rank
                    best_pair = (symbols[i], symbols[i + 1])
            if best_pair is None:
                break
            merged: list[str] = []
            i = 0
            while i < len(symbols):
                if (
                    i < len(symbols) - 1
                    and symbols[i] == best_pair[0]
                    and symbols[i + 1] == best_pair[1]
                ):
                    merged.append(best_pair[0] + best_pair[1])
                    i += 2
                else:
                    merged.append(symbols[i])
                    i += 1
            symbols = merged
        return [self._piece_id(symbol) for symbol in symbols]

    def _piece_id(self, piece: str) -> int:
        token_id = self._vocab.get(piece)
        if token_id is None:
            # Byte-level BPE is total over bytes (and the llama path resolves every OOV piece
            # before merging), so a merge product with no vocab entry means a malformed vocab --
            # refuse loudly rather than invent an id.
            raise TokenizerFormatError(f"piece {piece!r} has no vocab entry; cannot encode.")
        return token_id

    # ── decode ────────────────────────────────────────────────────────────────────────────────

    def decode(self, ids: list[int]) -> str:
        """Token ids -> text: piece lookup, inverse byte-level map, UTF-8. Special ids decode to
        their literal strings (e.g. 151643 -> '<|endoftext|>'). Byte sequences that are not valid
        UTF-8 decode with the Unicode replacement character -- a byte-level model can emit them."""
        if self._sentencepiece:
            return self._decode_sentencepiece(ids)
        parts: list[str] = []
        for token_id in ids:
            special = self._special_by_id.get(token_id)
            if special is not None:
                parts.append(special)
                continue
            piece = self._id_to_token.get(token_id)
            if piece is None:
                raise TokenizerFormatError(f"id {token_id} is not in this tokenizer's vocab.")
            parts.append(piece)
        joined = "".join(parts)
        raw = bytearray()
        for symbol in joined:
            byte = _SYMBOL_TO_BYTE.get(symbol)
            if byte is None:
                # A non-byte symbol (only possible for specials, handled above) -- keep verbatim.
                raw.extend(symbol.encode("utf-8"))
            else:
                raw.append(byte)
        return bytes(raw).decode("utf-8", errors="replace")

    # ── decode, llama family ──────────────────────────────────────────────────────────────────

    def _decode_sentencepiece(self, ids: list[int]) -> str:
        """The file's declared decoder chain, in order: marker back to space, byte-fallback runs
        back to raw bytes (UTF-8 with replacement characters for invalid runs), fuse (join),
        strip EXACTLY ONE leading space -- the marker at the start of the text decodes to a
        boundary, not a literal space. Special ids pass through as their literal strings (BOS ->
        '<s>', EOS -> '</s>'), exactly as the reference renders them.

        The leading-space strip is gated on add_space_prefix for the GGUF-embedded path
        (llama.cpp's `remove_space = add_space_prefix`); a tokenizer.json path always strips
        (its normalizer always prepends)."""
        parts: list[str] = []
        byte_buffer = bytearray()

        def flush_bytes() -> None:
            if byte_buffer:
                parts.append(bytes(byte_buffer).decode("utf-8", errors="replace"))
                byte_buffer.clear()

        for token_id in ids:
            piece = self._special_by_id.get(token_id)
            if piece is None:
                piece = self._id_to_token.get(token_id)
                if piece is None:
                    raise TokenizerFormatError(f"id {token_id} is not in this tokenizer's vocab.")
            byte_match = _SP_BYTE_TOKEN_RE.match(piece)
            if byte_match is not None:
                byte_buffer.append(int(byte_match.group(1), 16))
                continue
            flush_bytes()
            parts.append(piece.replace(_SP_MARKER, " "))
        flush_bytes()
        text = "".join(parts)
        if self._add_space_prefix and text.startswith(" "):
            return text[1:]
        return text

    # ── introspection ─────────────────────────────────────────────────────────────────────────

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    @property
    def special_ids(self) -> dict[str, int]:
        return dict(self._special_tokens)

    def eos_id(self) -> int | None:
        """The end-of-sequence special id: '<|endoftext|>' on Qwen3, '</s>' on the llama
        family; None when the checkpoint declares neither. A GGUF file states its EOS id outright
        (tokenizer.ggml.eos_token_id) and that declaration wins."""
        if self._eos_id is not None:
            return self._eos_id
        return self._special_tokens.get("<|endoftext|>", self._special_tokens.get("</s>"))

    def bos_id(self) -> int | None:
        """The llama-family BOS id declared by the file's post_processor (None on Qwen3 -- its
        prompts wrap no specials). `encode(text, add_special_tokens=True)` prepends it (on the
        GGUF path, only when the file's tokenizer.ggml.add_bos is on)."""
        return self._bos_id

    def merge_added_tokens(self, extra: dict[str, int]) -> int:
        """Merge added-token entries (content -> id) that tokenizer.json does not list.

        The Qwen3 `tokenizer_config.json` `added_tokens_decoder` carries four more entries than
        `tokenizer.json` `added_tokens` -- the tool_response/think markers the chat template
        renders (ids 151665-151668). Without them those strings would BPE-split instead of mapping
        to their single token, so chat-formatted prompts would tokenize wrong. tokenizer.json
        entries win any content collision. Returns the number of entries actually added."""
        added = 0
        for content, token_id in extra.items():
            if not isinstance(content, str) or not content:
                continue
            if isinstance(token_id, bool) or not isinstance(token_id, int):
                continue
            if content in self._special_tokens:
                continue
            self._special_tokens[content] = token_id
            self._vocab.setdefault(content, token_id)
            added += 1
        if added:
            self._special_by_id = {tid: tok for tok, tid in self._special_tokens.items()}
            # Longest-first so a shorter added string never shadows a longer one at the same spot.
            self._special_sorted = sorted(self._special_tokens, key=len, reverse=True)
        return added


def _assert_byte_level_stage(stage: object, role: str) -> None:
    if not isinstance(stage, dict) or stage.get("type") != "ByteLevel":
        raise TokenizerFormatError(
            f"unsupported {role} {stage!r}: this module implements the ByteLevel {role} only."
        )


def _is_sentencepiece_normalizer(normalizer: object) -> bool:
    """The llama-family normalizer shape, verified verbatim: Sequence [ Prepend the U+2581
    marker, Replace space with the marker ]. Anything else is not this family."""
    if not isinstance(normalizer, dict) or normalizer.get("type") != "Sequence":
        return False
    stages = normalizer.get("normalizers")
    if not isinstance(stages, list) or len(stages) != 2:
        return False
    prepend_stage, replace_stage = stages
    if (
        not isinstance(prepend_stage, dict)
        or prepend_stage.get("type") != "Prepend"
        or prepend_stage.get("prepend") != _SP_MARKER
    ):
        return False
    if not isinstance(replace_stage, dict) or replace_stage.get("type") != "Replace":
        return False
    if replace_stage.get("content") != _SP_MARKER:
        return False
    pattern = replace_stage.get("pattern")
    return isinstance(pattern, dict) and pattern.get("String") == " "


def _is_sentencepiece_decoder(decoder: object) -> bool:
    """The llama-family decoder shape, verified verbatim: Sequence [ Replace marker->space,
    ByteFallback, Fuse, Strip(content=space, exactly one from the left) ]."""
    if not isinstance(decoder, dict) or decoder.get("type") != "Sequence":
        return False
    stages = decoder.get("decoders")
    if not isinstance(stages, list) or len(stages) != 4:
        return False
    replace_stage, byte_stage, fuse_stage, strip_stage = stages
    if (
        not isinstance(replace_stage, dict)
        or replace_stage.get("type") != "Replace"
        or replace_stage.get("content") != " "
    ):
        return False
    pattern = replace_stage.get("pattern")
    if not isinstance(pattern, dict) or pattern.get("String") != _SP_MARKER:
        return False
    if not isinstance(byte_stage, dict) or byte_stage.get("type") != "ByteFallback":
        return False
    if not isinstance(fuse_stage, dict) or fuse_stage.get("type") != "Fuse":
        return False
    if (
        not isinstance(strip_stage, dict)
        or strip_stage.get("type") != "Strip"
        or strip_stage.get("content") != " "
        or strip_stage.get("start") != 1
        or strip_stage.get("stop") != 0
    ):
        return False
    return True


def _parse_merge_rules(merge_rules: list) -> dict[tuple[str, str], int]:
    """The file's merge list as {(a, b): rank}. Both spellings occur in real checkpoint files:
    "a b" strings (Qwen3 0.6B, llama) and ["a", "b"] lists (Qwen3 1.7B). Same rank order, same
    meaning."""
    merges: dict[tuple[str, str], int] = {}
    for rank, rule in enumerate(merge_rules):
        pair = rule.split(" ") if isinstance(rule, str) else rule
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or not all(isinstance(piece, str) for piece in pair)
        ):
            raise TokenizerFormatError(f"malformed merge rule {rule!r} at rank {rank}.")
        merges[(pair[0], pair[1])] = rank
    return merges


def _parse_added_tokens(raw: dict) -> dict[str, int]:
    """The tokenizer.json `added_tokens` as {content: id} -- the specials matched verbatim,
    unnormalized, before any other processing."""
    special_tokens: dict[str, int] = {}
    for added in raw.get("added_tokens") or []:
        content = added.get("content")
        token_id = added.get("id")
        if not isinstance(content, str) or not isinstance(token_id, int):
            raise TokenizerFormatError(f"malformed added token {added!r}.")
        special_tokens[content] = token_id
    return special_tokens


def _read_tokenizer_config(checkpoint_dir: Path) -> dict:
    """The checkpoint's `tokenizer_config.json` parsed, or {} when missing/unreadable -- both
    extractors below then contribute nothing (tokenizer.json alone still loads)."""
    config_path = checkpoint_dir / "tokenizer_config.json"
    if not config_path.is_file():
        return {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return config if isinstance(config, dict) else {}


def _added_tokens_from_tokenizer_config(config: dict) -> dict[str, int]:
    """The checkpoint config's `added_tokens_decoder` as {content: id}. The Qwen3 file lists four
    added tokens that `tokenizer.json` omits, so it is the superset source."""
    decoder = config.get("added_tokens_decoder") or {}
    if not isinstance(decoder, dict):
        return {}
    extra: dict[str, int] = {}
    for token_id, entry in decoder.items():
        if not isinstance(entry, dict):
            continue
        content = entry.get("content")
        if not isinstance(content, str) or not content:
            continue
        try:
            extra[content] = int(token_id)
        except (TypeError, ValueError):
            continue
    return extra


def _legacy_from_tokenizer_config(config: dict) -> bool:
    """The checkpoint's `legacy` flag, which fixes the llama-family marker prepend scheme (see
    `_encode_sentencepiece`). Missing means True -- the same default the reference applies."""
    legacy = config.get("legacy", True)
    if isinstance(legacy, bool):
        return legacy
    return True


def load_tokenizer(checkpoint_dir: str | Path) -> Tokenizer:
    """Load `<checkpoint_dir>/tokenizer.json` into a `Tokenizer`, then merge the added-token
    superset from `<checkpoint_dir>/tokenizer_config.json` (`added_tokens_decoder`). The checkpoint
    directory is the same Hugging Face snapshot `algenta.inference.decode` takes -- one directory
    serves both the weights and the tokenizer."""
    directory = Path(checkpoint_dir)
    path = directory / "tokenizer.json"
    if not path.is_file():
        raise TokenizerFormatError(
            f"{path} not found: load_tokenizer needs the checkpoint's own tokenizer.json."
        )
    config = _read_tokenizer_config(directory)
    tokenizer = Tokenizer.from_tokenizer_json(path, legacy=_legacy_from_tokenizer_config(config))
    tokenizer.merge_added_tokens(_added_tokens_from_tokenizer_config(config))
    return tokenizer
