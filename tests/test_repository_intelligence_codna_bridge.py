"""Tests for the algenta -> codna language bridge (repository_intelligence_codna_bridge).

The bridge is duck-typed against codna's codeunits seam, so these tests pin its contract with a
minimal stand-in registry — no installed codna required. The REAL adapters (mojo_language et al.)
do the extraction, so the regex side is exercised end-to-end on live sources.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from apps.api_server.services import repository_intelligence_codna_bridge as bridge


@dataclass(frozen=True)
class _CodeUnit:
    id: str
    text: str
    path: str
    language: str
    symbol_type: str
    qualname: str


class _FakeCodeunits:
    """The codna.codeunits surface the bridge consumes."""

    def __init__(self):
        self._EXTRACTORS: dict[str, object] = {}
        self.CodeUnit = _CodeUnit

    def register_extractor(self, extractor):
        for ext in extractor.extensions:
            self._EXTRACTORS[ext] = extractor


MOJO_SOURCE = """\
from utils import helper

fn test_attention_kernel():
    var x = helper()
    return x

struct Tile:
    var data: Float32

fn scale(tile: Tile, factor: Float32) -> Tile:
    return tile
"""


def _extract(codna, relpath: str, source: str, language: str):
    ext = next(e for e, x in codna._EXTRACTORS.items() if x.language == language)
    return list(codna._EXTRACTORS[ext].extract("repo", relpath, source))


def test_discover_finds_standard_contract_adapters():
    found = bridge.discover_adapters(languages=("mojo_language", "zig"))
    assert set(found) == {"mojo_language", "zig"}


def test_discover_records_unknown_language_not_raises():
    errors: dict[str, str] = {}
    found = bridge.discover_adapters(languages=("klingon",), record_error=errors.setdefault)
    assert found == {}
    assert "unknown adapter language" in errors["klingon"]


def test_register_mojo_extractor_extracts_structural_units():
    codna = _FakeCodeunits()
    live = bridge.register_algenta_adapters(codna, languages=("mojo_language",))
    assert live == {"mojo_language"}
    assert ".mojo" in codna._EXTRACTORS

    units = _extract(codna, "kernels/attn.mojo", MOJO_SOURCE, "mojo_language")
    by_qual = {u.qualname: u for u in units}
    assert set(by_qual) == {"test_attention_kernel", "Tile", "scale"}

    test_unit = by_qual["test_attention_kernel"]
    assert test_unit.symbol_type == "test"
    assert test_unit.id == "repo:kernels/attn.mojo:test_attention_kernel"
    assert test_unit.language == "mojo_language"
    assert test_unit.path == "kernels/attn.mojo"
    assert "var x = helper()" in test_unit.text          # source slice rides in the unit text
    assert len(test_unit.text) <= bridge._MAX_UNIT_CHARS

    assert by_qual["Tile"].symbol_type == "class"         # struct maps to the class vocabulary
    assert by_qual["scale"].symbol_type == "function"


def test_register_never_shadows_codna_owned_extensions():
    codna = _FakeCodeunits()
    codna._EXTRACTORS[".py"] = object()                   # codna's ast extractor owns .py
    for ext in (".js", ".jsx", ".mjs", ".ts", ".tsx"):    # installed grammars own all of js_like
        codna._EXTRACTORS[ext] = object()

    live = bridge.register_algenta_adapters(
        codna, languages=("python_language", "js_like", "mojo_language"))

    assert live == {"mojo_language"}                      # python/js fully shadowed -> not live
    assert isinstance(codna._EXTRACTORS[".py"], object)
    assert not hasattr(codna._EXTRACTORS[".py"], "language")   # untouched, still the original


def test_partial_shadow_registers_only_unowned_extensions():
    codna = _FakeCodeunits()
    codna._EXTRACTORS[".ts"] = object()                   # tree-sitter owns .ts but not .js

    live = bridge.register_algenta_adapters(codna, languages=("js_like",))

    assert live == {"js_like"}
    extractor = codna._EXTRACTORS[".js"]
    assert ".js" in extractor.extensions and ".tsx" in extractor.extensions
    assert ".ts" not in extractor.extensions              # the owned extension was filtered out


def test_broken_adapter_recorded_not_fatal():
    codna = _FakeCodeunits()
    errors: dict[str, str] = {}
    live = bridge.register_algenta_adapters(
        codna, languages=("mojo_language", "klingon"), record_error=errors.setdefault)
    assert live == {"mojo_language"}
    assert "klingon" in errors


def test_missing_codeunit_class_recorded_not_fatal():
    class _NoUnits:
        _EXTRACTORS: dict = {}

    errors: dict[str, str] = {}
    live = bridge.register_algenta_adapters(_NoUnits(), languages=("mojo_language",),
                                            record_error=errors.setdefault)
    assert live == set()
    assert "no CodeUnit class" in errors["codna"]


def test_adapter_table_covers_the_documented_contract_set():
    # The table is the v1 contract: guard against silent shrinkage (a removed entry would quietly
    # drop language coverage from every downstream codna index).
    assert len(bridge.ADAPTER_EXTENSIONS) >= 40
    for language in ("mojo_language", "zig", "rust_language", "go_language", "c_family"):
        assert language in bridge.ADAPTER_EXTENSIONS
