"""`algenta.tokenizer` is parity gap 1's first increment: the checkpoint's own tokenizer.json
implemented from scratch (NFC, the GPT-4-style regex split, byte-level BPE, added tokens, byte-level
decode) -- no tokenizer library imported, no third-party regex dependency. "Implemented from
scratch" only means something if it is checked against the reference, so this file has two halves:

* STRUCTURAL tests (always run): the byte alphabet, BPE merging on a synthetic vocab, decode
  round-trips, and the format-refusal contract -- none need a real checkpoint.
* ORACLE tests (skip unless the machine has a real Qwen3 snapshot AND `transformers`): encode AND
  decode must be BYTE-IDENTICAL to `transformers.AutoTokenizer` across an edge-case corpus, on
  both checkpoints. Same skip-unless-present convention `test_qwen3_decode_checkpoint_conversion.py`
  established: the checkpoint is the README-documented manual download, never fetched by a test.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_ALGENTA = ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.tokenizer import (  # noqa: E402
    Tokenizer,
    TokenizerFormatError,
    _BYTE_TO_SYMBOL,
    _SYMBOL_TO_BYTE,
    load_tokenizer,
)


# ── structural: always run ─────────────────────────────────────────────────────────────────────


def test_byte_alphabet_is_a_total_bijection() -> None:
    """All 256 bytes map to distinct printable symbols and back -- the byte-level BPE invariant
    that makes the model total over arbitrary UTF-8 (and arbitrary invalid byte runs)."""
    assert len(_BYTE_TO_SYMBOL) == 256
    assert len(set(_BYTE_TO_SYMBOL.values())) == 256
    for byte in range(256):
        symbol = _BYTE_TO_SYMBOL[byte]
        assert _SYMBOL_TO_BYTE[symbol] == byte
        assert not symbol.isspace(), f"byte {byte} mapped to a whitespace symbol"
    # The two landmarks the merge tables are written against.
    assert _BYTE_TO_SYMBOL[32] == "Ġ"  # space
    assert _BYTE_TO_SYMBOL[10] == "Ċ"  # newline


def _synthetic_tokenizer() -> Tokenizer:
    """A hand-built byte-level BPE over ASCII: vocab a/b/space + merges (a,b)->ab and
    (Ġ,ab)->Ġab, so encode/merge behavior is checkable without any checkpoint. The pretokenize
    regex attaches a leading space to the following word, like the real one does."""
    vocab = {"a": 0, "b": 1, "Ġ": 3, "ab": 2, "Ġab": 4}
    merges = {("a", "b"): 0, ("Ġ", "ab"): 1}
    return Tokenizer(
        vocab=vocab,
        merges=merges,
        special_tokens={"<eos>": 9},
        pretokenize_regex=re.compile(r" ?\S+|\s+"),
    )


def test_synthetic_bpe_merges_and_round_trip() -> None:
    tok = _synthetic_tokenizer()
    assert tok.encode("ab") == [2]  # merged
    assert tok.encode("ba") == [1, 0]  # no (b,a) merge
    assert tok.encode(" ab") == [4]  # space symbol attaches, then both merges fire
    assert tok.decode([2]) == "ab"
    assert tok.decode([3, 2, 1, 0]) == " abba"  # Ġ ab b a
    assert tok.decode([9]) == "<eos>"
    # eos_id() looks up the Qwen3 endoftext special by name; the synthetic vocab has none.
    assert tok.eos_id() is None
    # Constructor-built: the 5 vocab pieces only (specials merge into the vocab in
    # from_tokenizer_json, which this synthetic path bypasses).
    assert tok.vocab_size == 5


def test_unknown_piece_and_unknown_id_refused() -> None:
    tok = _synthetic_tokenizer()
    with pytest.raises(TokenizerFormatError):
        tok.decode([77])  # id not in vocab
    # 'c' is not in the synthetic vocab: encoding must refuse, never invent an id.
    with pytest.raises(TokenizerFormatError):
        tok.encode("c")


def test_load_tokenizer_missing_file_refused(tmp_path: Path) -> None:
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "tokenizer.json" in str(excinfo.value)


def test_unsupported_model_type_refused(tmp_path: Path) -> None:
    (tmp_path / "tokenizer.json").write_text(
        json.dumps({"model": {"type": "Unigram", "vocab": {}, "merges": []}}),
        encoding="utf-8",
    )
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "Unigram" in str(excinfo.value)


def test_foreign_pretokenizer_regex_refused(tmp_path: Path) -> None:
    """A tokenizer.json with the right SHAPE but a different split regex must be refused --
    tokenizing against a different split would be silently wrong."""
    payload = {
        "model": {"type": "BPE", "vocab": {"a": 0}, "merges": []},
        "normalizer": {"type": "NFC"},
        "pre_tokenizer": {
            "type": "Sequence",
            "pretokenizers": [
                {"type": "Split", "pattern": {"Regex": r"\w+"}, "behavior": "Isolated"},
                {"type": "ByteLevel", "use_regex": False},
            ],
        },
        "decoder": {"type": "ByteLevel", "use_regex": False},
    }
    (tmp_path / "tokenizer.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "refusing" in str(excinfo.value)


def test_list_form_merge_rules_accepted(tmp_path: Path) -> None:
    """Real checkpoints spell merges both ways: "a b" strings and ["a","b"] lists."""
    payload = {
        "model": {"type": "BPE", "vocab": {"a": 0, "b": 1, "ab": 2}, "merges": [["a", "b"]]},
        "pre_tokenizer": {
            "type": "Sequence",
            "pretokenizers": [
                {
                    "type": "Split",
                    "pattern": {"Regex": _qwen3_pretokenizer_pattern()},
                    "behavior": "Isolated",
                },
                {"type": "ByteLevel", "use_regex": False},
            ],
        },
    }
    (tmp_path / "tokenizer.json").write_text(json.dumps(payload), encoding="utf-8")
    tok = load_tokenizer(tmp_path)
    assert tok.vocab_size == 3


def _qwen3_pretokenizer_pattern() -> str:
    from algenta.tokenizer import _EXPECTED_PRETOKENIZE_PATTERN

    return _EXPECTED_PRETOKENIZE_PATTERN


# ── oracle: real checkpoints + transformers, skip-unless-present ───────────────────────────────

# Built by concatenation so no literal special-token string sits in this source file.
_EOS = "<|" + "endoftext" + "|>"
_IM_START = "<|" + "im_start" + "|>"
_IM_END = "<|" + "im_end" + "|>"

_CORPUS = [
    "The capital of France is Paris.",
    "The capital of France is Paris. " * 36 + "The capital of France",
    "Hello, world! It's a TEST of contractions: I'm, you're, we've, they'll, he'd.",
    "Digits: 0 1 2 3 45 678 90 12345678901234567890",
    "Punctuation ... !!! ??? --- ; : , . ( ) [ ] { } < > / \\ | @ # $ % ^ & * _ ~ `",
    "Whitespace:    tabs\there\n\nnewlines\r\nwindows\rand  trailing  ",
    "Unicode: 中文测试，日本語のテキスト、한국어, Ελληνικά, Русский, العربية, עברית",
    "Emoji: 😀 🎉 🚀 ❤️ 🇫🇷 👨\u200d👩\u200d👧\u200d👦",
    "Combining: e\u0301 vs \u00e9, a\u0308o\u0308u\u0308",
    "Mixed 中文 and English 123 with 数字 and émojis 🎨 together.",
    "Leading and trailing spaces   ",
    "",
    " ",
    "\n",
    "a" * 500,
    "很" * 200,
    "𐀀 𠀀 𠀁",
    "\x00\x01\x7f control-ish bytes in a string",
    "Pre text " + _EOS + " post text",
    _IM_START + "system\nYou are helpful." + _IM_END,
]


def _checkpoint_dirs() -> list[Path]:
    dirs = []
    for env_name, default in (
        ("ALGENTA_QWEN3_TEST_CHECKPOINT", Path("/private/tmp/qwen3-0.6b-base")),
        ("ALGENTA_QWEN3_TEST_CHECKPOINT_17B", Path("/private/tmp/qwen3-1.7b")),
    ):
        override = os.environ.get(env_name)
        candidate = Path(override) if override else default
        if (candidate / "tokenizer.json").is_file():
            dirs.append(candidate)
    return dirs


def _transformers():
    return pytest.importorskip("transformers", reason="the oracle cross-check needs transformers")


@pytest.mark.skipif(
    not _checkpoint_dirs(),
    reason="no Qwen3 snapshot with tokenizer.json on this machine (manual download, never fetched by a test)",
)
def test_encode_decode_byte_identical_to_transformers_oracle() -> None:
    """The honesty gate for the whole module: for every corpus text, encode ids AND decoded text
    must match transformers.AutoTokenizer EXACTLY, on every checkpoint present."""
    AutoTokenizer = _transformers().AutoTokenizer
    for model_dir in _checkpoint_dirs():
        mine = load_tokenizer(model_dir)
        ref = AutoTokenizer.from_pretrained(str(model_dir), trust_remote_code=True)
        for text in _CORPUS:
            my_ids = mine.encode(text)
            ref_ids = ref.encode(text, add_special_tokens=False)
            assert my_ids == ref_ids, (
                f"{model_dir.name}: encode mismatch on {text[:60]!r}: "
                f"{my_ids[:12]}... vs {ref_ids[:12]}..."
            )
            assert mine.decode(my_ids) == ref.decode(ref_ids), (
                f"{model_dir.name}: decode mismatch on {text[:60]!r}"
            )


@pytest.mark.skipif(
    not _checkpoint_dirs(),
    reason="no Qwen3 snapshot with tokenizer.json on this machine",
)
def test_eos_round_trip_through_special_id() -> None:
    """The endoftext special decodes to its literal string and encodes back to its id -- the
    exact id the kernel path checks for stop (151643 on Qwen3)."""
    for model_dir in _checkpoint_dirs():
        tok = load_tokenizer(model_dir)
        eos = tok.eos_id()
        assert eos is not None and eos >= 151643
        assert tok.decode([eos]) == _EOS
        assert tok.encode(_EOS) == [eos]
        mixed = tok.encode("x " + _EOS + " y")
        assert eos in mixed
        assert _EOS in tok.decode(mixed)
