from __future__ import annotations

from benchmarks.python_manual_libs.text_tokenizer import (
    _substr,
    pad_sequence,
    sentence_tokenize,
    token_frequency,
    word_tokenize,
)


def test_manual_text_tokenizer_reference_matches_expected_outputs() -> None:
    assert _substr("hello", 1, 4) == "ell"
    assert word_tokenize("Hello, world!") == ["hello", "world"]
    assert sentence_tokenize("One. Two!") == ["One.", "Two!"]
    assert token_frequency(["a", "b", "a"]) == [["a", "2"], ["b", "1"]]
    assert pad_sequence(["a", "b"], 4, "<pad>") == ["a", "b", "<pad>", "<pad>"]
