"""Text in, token ids out: the Qwen3-family BPE tokenizer, implemented here.

This is parity gap 1 from the beat-llama.cpp campaign's end-to-end gap analysis (2026-08-09):
until this module the kernel path was token-ids-in only, and any text had to be tokenized by an
external `transformers` install. This module reads the checkpoint's OWN `tokenizer.json` (the
Hugging Face tokenizers format) and implements exactly what it declares -- nothing more, nothing
imported from a tokenizer library:

* **Normalizer**: NFC, because `tokenizer.json` says `{"type": "NFC"}`.
* **Pre-tokenizer**: the GPT-4-style regex split (contractions, letter runs, single digits,
  punctuation/newline chunks, whitespace runs) with `behavior: Isolated`, then the byte-level
  alphabet mapping, because `tokenizer.json` says exactly that Sequence.
* **Model**: byte-level BPE with the file's own vocab + merge list, greedy lowest-rank merging.
* **Added tokens**: the file's special tokens (e.g. `<|endoftext|>` = 151643) matched verbatim,
  unnormalized, before any other processing -- `special: true, normalized: false` in the file.
* **Decoder**: the inverse byte-level map, then UTF-8.

Scope, stated precisely so nothing here overclaims
---------------------------------------------------
* **One tokenizer family.** The Qwen3/Qwen2 byte-level BPE shape above. A `tokenizer.json` of
  another shape (Unigram, WordPiece, a different pre-tokenizer stack) raises
  `TokenizerFormatError` naming the unsupported piece rather than half-tokenizing.
* **No chat template.** Base models ship none; the instruct-template half of parity gap 1 is a
  later increment.
* **Cross-validated, not assumed.** `tests/test_tokenizer_qwen3.py` checks encode AND decode
  against `transformers.AutoTokenizer` on the real checkpoints (the same byte-for-byte-against-
  the-original convention `algenta.qwen3_decode.prepare_checkpoint` established). Without the
  checkpoint on disk those oracle tests skip; the structural unit tests always run.

Usage
-----
    from algenta.tokenizer import load_tokenizer

    tok = load_tokenizer("/path/to/qwen3-checkpoint")   # reads tokenizer.json
    ids = tok.encode("The capital of France is")
    text = tok.decode(ids)
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

__all__ = [
    "TokenizerFormatError",
    "Tokenizer",
    "load_tokenizer",
]

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
    """The checkpoint's tokenizer.json is not the supported Qwen3-family byte-level BPE shape.

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
    """One checkpoint's tokenizer, loaded from its own tokenizer.json. Immutable after load."""

    def __init__(
        self,
        *,
        vocab: dict[str, int],
        merges: dict[tuple[str, str], int],
        special_tokens: dict[str, int],
        pretokenize_regex: re.Pattern,
    ) -> None:
        self._vocab = vocab
        self._id_to_token = {token_id: token for token, token_id in vocab.items()}
        self._merges = merges
        self._special_tokens = special_tokens
        self._special_by_id = {token_id: token for token, token_id in special_tokens.items()}
        self._pretokenize = pretokenize_regex
        # Longest-first so a shorter special string never shadows a longer one at the same spot.
        self._special_sorted = sorted(special_tokens, key=len, reverse=True)

    @classmethod
    def from_tokenizer_json(cls, path: str | Path) -> "Tokenizer":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))

        model = raw.get("model") or {}
        if model.get("type") != "BPE":
            raise TokenizerFormatError(
                f"unsupported tokenizer model type {model.get('type')!r}: this module implements "
                "the Qwen3-family byte-level BPE only."
            )
        vocab = model.get("vocab")
        merge_rules = model.get("merges")
        if not isinstance(vocab, dict) or not isinstance(merge_rules, list):
            raise TokenizerFormatError(
                "tokenizer.json model is missing its vocab/merges tables; cannot load."
            )

        normalizer = raw.get("normalizer")
        if normalizer not in (None, {"type": "NFC"}):
            raise TokenizerFormatError(
                f"unsupported normalizer {normalizer!r}: this module implements NFC only."
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

        merges: dict[tuple[str, str], int] = {}
        for rank, rule in enumerate(merge_rules):
            # Both spellings occur in real checkpoint files: "a b" strings (0.6B) and
            # ["a", "b"] lists (1.7B). Same rank order, same meaning.
            pair = rule.split(" ") if isinstance(rule, str) else rule
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(piece, str) for piece in pair)
            ):
                raise TokenizerFormatError(f"malformed merge rule {rule!r} at rank {rank}.")
            merges[(pair[0], pair[1])] = rank

        special_tokens: dict[str, int] = {}
        for added in raw.get("added_tokens") or []:
            content = added.get("content")
            token_id = added.get("id")
            if not isinstance(content, str) or not isinstance(token_id, int):
                raise TokenizerFormatError(f"malformed added token {added!r}.")
            special_tokens[content] = token_id

        full_vocab = dict(vocab)
        for content, token_id in special_tokens.items():
            full_vocab.setdefault(content, token_id)

        return cls(
            vocab=full_vocab,
            merges=merges,
            special_tokens=special_tokens,
            pretokenize_regex=re.compile(resolved),
        )

    # ── encode ────────────────────────────────────────────────────────────────────────────────

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        """Text -> token ids, exactly the pipeline tokenizer.json declares: added-token split
        (verbatim, unnormalized), NFC, the regex split, byte-level mapping, BPE.

        `add_special_tokens` matches the transformers naming, but Qwen3 base prompts use no
        wrapping specials, so True and False behave identically here unless the text itself
        contains a special string (which is mapped either way)."""
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
            # Byte-level BPE is total over bytes, so this can only happen for a vocab whose
            # single-byte pieces were pruned -- refuse loudly rather than invent an id.
            raise TokenizerFormatError(f"piece {piece!r} has no vocab entry; cannot encode.")
        return token_id

    # ── decode ────────────────────────────────────────────────────────────────────────────────

    def decode(self, ids: list[int]) -> str:
        """Token ids -> text: piece lookup, inverse byte-level map, UTF-8. Special ids decode to
        their literal strings (e.g. 151643 -> '<|endoftext|>'). Byte sequences that are not valid
        UTF-8 decode with the Unicode replacement character -- a byte-level model can emit them."""
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

    # ── introspection ─────────────────────────────────────────────────────────────────────────

    @property
    def vocab_size(self) -> int:
        return len(self._vocab)

    @property
    def special_ids(self) -> dict[str, int]:
        return dict(self._special_tokens)

    def eos_id(self) -> int | None:
        return self._special_tokens.get("<|endoftext|>")


def _assert_byte_level_stage(stage: object, role: str) -> None:
    if not isinstance(stage, dict) or stage.get("type") != "ByteLevel":
        raise TokenizerFormatError(
            f"unsupported {role} {stage!r}: this module implements the ByteLevel {role} only."
        )


def load_tokenizer(checkpoint_dir: str | Path) -> Tokenizer:
    """Load `<checkpoint_dir>/tokenizer.json` into a `Tokenizer`. The checkpoint directory is the
    same Hugging Face snapshot `algenta.inference.decode` takes -- one directory serves both the
    weights and the tokenizer."""
    path = Path(checkpoint_dir) / "tokenizer.json"
    if not path.is_file():
        raise TokenizerFormatError(
            f"{path} not found: load_tokenizer needs the checkpoint's own tokenizer.json."
        )
    return Tokenizer.from_tokenizer_json(path)
