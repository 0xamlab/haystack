"""`algenta.tokenizer` llama-family increment: the SentencePiece-style BPE of llama-architecture
checkpoints (TinyLlama-1.1B is the campaign's llama checkpoint), implemented from scratch in the
same module -- the U+2581 marker convention, BPE directly on the marked pieces, byte-fallback /
unk handling, marker decode -- no tokenizer library imported. Same two halves as
`test_tokenizer_qwen3.py`:

* STRUCTURAL tests (always run): a synthetic SentencePiece-style BPE over a hand-built vocab
  (marker prepend + leading-space absorption, byte fallback, unk fusion, decode strip, BOS), and
  the format-refusal contract for the llama shape -- none need a real checkpoint.
* ORACLE tests (skip unless the machine has a real llama snapshot AND `transformers`): encode
  (with AND without the BOS convention) and decode (with AND without specials in the id list)
  must match `transformers.AutoTokenizer` EXACTLY across an edge-case corpus. Same
  skip-unless-present convention the Qwen3 oracle established: the checkpoint is a manual
  download, never fetched by a test.
"""

from __future__ import annotations

import json
import os
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
    load_tokenizer,
)

# The marker is U+2581, not an underscore; the specials are built by concatenation so no literal
# special-token string sits in this source file (same convention as test_tokenizer_qwen3.py).
_MARKER = "\u2581"  # '▁'
_BOS = "<" + "s>"
_EOS = "<" + "/s>"
_UNK = "<" + "unk>"


# ── structural: always run ─────────────────────────────────────────────────────────────────────


def _synthetic_sentencepiece(
    *, legacy: bool = False, byte_fallback: bool = True, fuse_unk: bool = True
) -> Tokenizer:
    """A hand-built llama-style BPE: pieces a/b/ab with the marker forms, the three specials,
    and the two byte-fallback pieces of UTF-8 'é'. Merges: (a,b)->ab rank 0, (marker,ab)->
    marker+ab rank 1 -- enough to check the marker pipeline without a checkpoint."""
    vocab = {
        _UNK: 0,
        "a": 1,
        "b": 2,
        f"{_MARKER}a": 3,
        f"{_MARKER}ab": 4,
        "ab": 5,
        "<0xC3>": 50,
        "<0xA9>": 51,
        _BOS: 10,
        _EOS: 11,
        _MARKER: 100,
    }
    merges = {("a", "b"): 0, (_MARKER, "ab"): 1}
    return Tokenizer(
        vocab=vocab,
        merges=merges,
        special_tokens={_UNK: 0, _BOS: 10, _EOS: 11},
        pretokenize_regex=None,
        sentencepiece=True,
        sp_legacy=legacy,
        byte_fallback=byte_fallback,
        fuse_unk=fuse_unk,
        unk_token=_UNK,
        bos_id=10,
    )


def test_synthetic_sentencepiece_marker_merges_and_round_trip() -> None:
    tok = _synthetic_sentencepiece()
    assert tok.encode("ab") == [4]  # prepend marker, then both merges fire
    assert tok.encode("ba") == [100, 2, 1]  # no (b,a) merge; marker stays its own piece
    assert tok.decode([4]) == "ab"  # leading marker decodes to the boundary, then strips
    assert tok.decode([100, 4]) == " ab"  # two markers -> two spaces -> strip ONE
    assert tok.decode([10]) == _BOS  # specials render literally
    assert tok.decode([10, 4]) == f"{_BOS} ab"  # literal special, then the marked piece
    assert tok.decode([11, 4]) == f"{_EOS} ab"  # the marker decodes to a space anywhere
    assert tok.eos_id() == 11 and tok.bos_id() == 10
    assert tok.vocab_size == 11


def test_synthetic_sentencepiece_leading_space_absorption() -> None:
    """The reference Metaspace corner: a single leading space's own marker takes the prepend's
    place -- encode(' x') == encode('x') -- while the second and later spaces stay pieces."""
    tok = _synthetic_sentencepiece()
    assert tok.encode(" ab") == tok.encode("ab") == [4]
    assert tok.encode("  ab") == [100, 4]  # extra space survives as its own marker piece
    assert tok.encode("") == []  # empty text carries no pieces at all
    assert tok.encode(" ") == [100]
    assert tok.decode(tok.encode(" ")) == ""  # one marker -> one space -> stripped


def test_synthetic_sentencepiece_bos_convention() -> None:
    """add_special_tokens=True prepends exactly the declared BOS id -- the transformers
    default-encode convention; False leaves the sequence bare."""
    tok = _synthetic_sentencepiece()
    assert tok.encode("ab", add_special_tokens=True) == [10, 4]
    assert tok.encode("", add_special_tokens=True) == [10]
    assert tok.encode("ab", add_special_tokens=False) == [4]


def test_synthetic_sentencepiece_special_split_and_offset_rule() -> None:
    """Specials split verbatim; with legacy=False the marker prepend is eligible ONLY for the
    segment at the start of the text, so a word right after a special gets no marker."""
    tok = _synthetic_sentencepiece()  # legacy=False
    assert tok.encode(_EOS + "ab") == [11, 5]  # 'ab' unmarked after the special
    assert tok.encode(f"a {_EOS} b") == [100, 1, 100, 11, 100, 2]
    legacy = _synthetic_sentencepiece(legacy=True)
    assert legacy.encode(_EOS + "ab") == [11, 4]  # legacy marks every segment
    assert tok.encode(_UNK) == [0]  # specials matched verbatim, never BPE-split


def test_synthetic_sentencepiece_byte_fallback_and_unk() -> None:
    """OOV characters resolve BEFORE merging: byte_fallback emits the UTF-8 byte pieces when the
    file declares it; without it the declared unk stands in, fused across a run when fuse_unk."""
    tok = _synthetic_sentencepiece()
    assert tok.encode("\u00e9") == [100, 50, 51]  # marker + the two UTF-8 bytes of 'é'
    assert tok.decode([50, 51]) == "\u00e9"  # a byte run decodes back through UTF-8
    assert tok.decode([50]) == "\ufffd"  # a lone continuation-less byte is invalid UTF-8

    no_bytes = _synthetic_sentencepiece(byte_fallback=False, fuse_unk=True)
    assert no_bytes.encode("\u00e9\u00e9") == [100, 0]  # fused: ONE unk for the run
    no_fuse = _synthetic_sentencepiece(byte_fallback=False, fuse_unk=False)
    assert no_fuse.encode("\u00e9\u00e9") == [100, 0, 0]  # one unk per OOV char
    assert no_bytes.decode([0]) == _UNK


def test_synthetic_sentencepiece_decode_marker_after_byte_run() -> None:
    """The strip takes exactly ONE leading space and only a leading one -- a marker decoded
    behind a byte run keeps its space (the reference decoder chain's exact behavior)."""
    tok = _synthetic_sentencepiece()
    assert tok.decode([50, 51, 100]) == "\u00e9 "
    assert tok.decode([100, 50, 51]) == "\u00e9"  # leading space stripped, bytes intact


def _llama_shape_payload(**model_overrides) -> dict:
    """A minimal llama-family tokenizer.json: the marker normalizer, no pre-tokenizer, the
    declared decoder chain, and the BOS-prepending TemplateProcessing."""
    vocab = {_UNK: 0, _BOS: 1, _EOS: 2, _MARKER: 3, "a": 4, f"{_MARKER}a": 5}
    vocab.update(model_overrides.pop("extra_vocab", {}))
    model = {
        "type": "BPE",
        "dropout": None,
        "unk_token": _UNK,
        "continuing_subword_prefix": None,
        "end_of_word_suffix": None,
        "fuse_unk": True,
        "byte_fallback": False,
        "vocab": vocab,
        "merges": [f"{_MARKER} a"],
    }
    model.update(model_overrides)
    return {
        "model": model,
        "normalizer": {
            "type": "Sequence",
            "normalizers": [
                {"type": "Prepend", "prepend": _MARKER},
                {"type": "Replace", "pattern": {"String": " "}, "content": _MARKER},
            ],
        },
        "pre_tokenizer": None,
        "decoder": {
            "type": "Sequence",
            "decoders": [
                {"type": "Replace", "pattern": {"String": _MARKER}, "content": " "},
                {"type": "ByteFallback"},
                {"type": "Fuse"},
                {"type": "Strip", "content": " ", "start": 1, "stop": 0},
            ],
        },
        "post_processor": {
            "type": "TemplateProcessing",
            "single": [
                {"SpecialToken": {"id": _BOS, "type_id": 0}},
                {"Sequence": {"id": "A", "type_id": 0}},
            ],
            "pair": [
                {"SpecialToken": {"id": _BOS, "type_id": 0}},
                {"Sequence": {"id": "A", "type_id": 0}},
                {"SpecialToken": {"id": _BOS, "type_id": 1}},
                {"Sequence": {"id": "B", "type_id": 1}},
            ],
            "special_tokens": {_BOS: {"id": _BOS, "ids": [1], "tokens": [_BOS]}},
        },
        "added_tokens": [
            {"id": 0, "content": _UNK, "special": True},
            {"id": 1, "content": _BOS, "special": True},
            {"id": 2, "content": _EOS, "special": True},
        ],
    }


def test_llama_shape_loads_and_detects_family(tmp_path: Path) -> None:
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(_llama_shape_payload(), ensure_ascii=False), encoding="utf-8"
    )
    tok = load_tokenizer(tmp_path)
    assert tok.vocab_size == 6
    assert tok.bos_id() == 1 and tok.eos_id() == 2
    assert tok.encode("a") == [5]  # marker prepended, merged piece
    assert tok.encode("a", add_special_tokens=True) == [1, 5]
    assert tok.decode([5]) == "a"


def test_sentencepiece_normalizer_with_pretokenizer_refused(tmp_path: Path) -> None:
    """The marker normalizer only identifies the llama family WITHOUT a pre-tokenizer; with one
    present the shape is neither family and must be refused."""
    payload = _llama_shape_payload()
    payload["pre_tokenizer"] = {"type": "Split", "pattern": {"String": " "}, "behavior": "Isolated"}
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(TokenizerFormatError):
        load_tokenizer(tmp_path)


def test_llama_shape_refuses_wrong_decoder(tmp_path: Path) -> None:
    payload = _llama_shape_payload()
    payload["decoder"] = {"type": "ByteLevel", "use_regex": False}
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "decoder" in str(excinfo.value)


def test_llama_shape_refuses_dropout(tmp_path: Path) -> None:
    payload = _llama_shape_payload(dropout=0.1)
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "dropout" in str(excinfo.value)


def test_llama_shape_refuses_foreign_post_processor(tmp_path: Path) -> None:
    payload = _llama_shape_payload()
    payload["post_processor"] = {"type": "ByteLevel"}
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "post_processor" in str(excinfo.value)


def test_llama_shape_refuses_unk_missing_from_vocab(tmp_path: Path) -> None:
    payload = _llama_shape_payload()
    payload["model"]["vocab"].pop(_UNK)
    (tmp_path / "tokenizer.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(TokenizerFormatError) as excinfo:
        load_tokenizer(tmp_path)
    assert "unk_token" in str(excinfo.value)


# ── oracle: real llama checkpoint + transformers, skip-unless-present ──────────────────────────

_CORPUS = [
    "The capital of France is Paris.",
    "Hello, world! It's a TEST of contractions: I'm, you're, we've, they'll.",
    "Digits: 0 1 2 3 45 678 90 12345678901234567890",
    "Punctuation ... !!! ??? --- ; : , . ( ) [ ] { } @ # $ % ^ & * _ ~ `",
    "MixedCase Word CAPS ALLCAPS and 42numbers glued99",
    "   Leading and trailing spaces   ",
    " single leading space",
    "  double leading",
    "trailing space ",
    "",
    " ",
    "  ",
    "\n",
    "Whitespace:\ttabs\n\nnewlines\r\nwindows",
    "Unicode: \u4e2d\u6587\u6d4b\u8bd5\uff0c\u65e5\u672c\u8a9e\u306e\u30c6\u30ad\u30b9\u30c8\u3001\ud55c\uad6d\uc5b4, \u0395\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac, \u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    "Emoji: \U0001f600 \U0001f389 \U0001f680 \u2764\ufe0f",
    "Combining: e\u0301 vs \u00e9, a\u0308o\u0308u\u0308",
    "Mixed \u4e2d\u6587 and English 123 with \u6570\u5b57 and \u00e9mojis \U0001f3a8 together.",
    "a",
    "\u5f88" * 60,
    "a" * 300,
    "\x00\x01\x7f control-ish bytes in a string",
    f"x {_EOS} y and {_UNK} and {_BOS} specials",
    "caf\u00e9 na\u00efve r\u00e9sum\u00e9",
]


def _llama_checkpoint_dir() -> Path | None:
    override = os.environ.get("ALGENTA_LLAMA_TEST_CHECKPOINT")
    candidate = Path(override) if override else Path("/private/tmp/tinyllama")
    return candidate if (candidate / "tokenizer.json").is_file() else None


def _transformers():
    return pytest.importorskip("transformers", reason="the oracle cross-check needs transformers")


@pytest.mark.skipif(
    _llama_checkpoint_dir() is None,
    reason="no llama snapshot with tokenizer.json on this machine (manual download, never fetched by a test)",
)
def test_llama_encode_decode_identical_to_transformers_oracle() -> None:
    """The honesty gate for the llama family: for every corpus text, the bare encode, the
    BOS-wrapped encode (transformers' default convention), and BOTH decodes (specials rendered
    and all) must match transformers.AutoTokenizer EXACTLY."""
    AutoTokenizer = _transformers().AutoTokenizer
    model_dir = _llama_checkpoint_dir()
    mine = load_tokenizer(model_dir)
    ref = AutoTokenizer.from_pretrained(str(model_dir))
    for text in _CORPUS:
        my_ids = mine.encode(text)
        ref_ids = ref.encode(text, add_special_tokens=False)
        assert my_ids == ref_ids, (
            f"encode mismatch on {text[:60]!r}: {my_ids[:12]}... vs {ref_ids[:12]}..."
        )
        my_bos = mine.encode(text, add_special_tokens=True)
        ref_bos = ref.encode(text)
        assert my_bos == ref_bos, (
            f"BOS-encode mismatch on {text[:60]!r}: {my_bos[:12]}... vs {ref_bos[:12]}..."
        )
        assert mine.decode(my_ids) == ref.decode(ref_ids), f"decode mismatch on {text[:60]!r}"
        assert mine.decode(my_bos) == ref.decode(ref_bos), (
            f"decode-with-specials mismatch on {text[:60]!r}"
        )


@pytest.mark.skipif(
    _llama_checkpoint_dir() is None,
    reason="no llama snapshot with tokenizer.json on this machine",
)
def test_llama_special_ids_match_reference() -> None:
    """BOS/EOS ids agree with the reference, and the EOS literal encodes to its single id --
    the exact id the engine's stop check carries in the manifest (2 on TinyLlama)."""
    AutoTokenizer = _transformers().AutoTokenizer
    model_dir = _llama_checkpoint_dir()
    mine = load_tokenizer(model_dir)
    ref = AutoTokenizer.from_pretrained(str(model_dir))
    assert mine.bos_id() == ref.bos_token_id
    assert mine.eos_id() == ref.eos_token_id
    assert mine.encode(_EOS) == [mine.eos_id()]
    assert mine.decode([mine.eos_id()]) == _EOS
    assert mine.decode([mine.bos_id()]) == _BOS
