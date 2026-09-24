"""The transport template's flat-list fast paths (REPUBLISH-006): one C-level pass for a list
of primitives, the per-element path for everything else — same accepted values, same refusals.

The template imports `._contract` and `._native` relatively, so it is exercised inside a stub
package built here (no native library needed: only the pure-Python glue is under test)."""

from __future__ import annotations

import importlib.util
import math
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "hf_kernels" / "templates" / "_transport.py"
STRUCTS = {"Pair": {"fields": [{"name": "a", "type": "Int"}, {"name": "b", "type": "Float64"}]}}


@pytest.fixture
def transport(tmp_path: Path):
    pkg = tmp_path / "stubpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "_contract.py").write_text("CONTRACT = {'modules': {}}\n")
    (pkg / "_native.py").write_text(
        "class KernelError(Exception):\n"
        "    def __init__(self, code, message, details=None):\n"
        "        super().__init__(message)\n"
        "        self.code, self.message, self.details = code, message, details or {}\n"
    )
    shutil.copy(TEMPLATE, pkg / "_transport.py")
    name = f"stubpkg_{tmp_path.name}"
    spec = importlib.util.spec_from_file_location(
        name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(f"{name}._transport")


def _slow(transport, monkeypatch):
    """The same module with the fast path switched off: the per-element reference."""
    monkeypatch.setattr(transport, "_normalize_flat_list", lambda value, inner: None)


ACCEPTED = {
    "List[Float64]": [[1, 2.5, -3, 0.0, 1e300], [], [7]],
    "List[Float32]": [[1, 2.5]],
    "List[Int]": [[1, -2, 2**63 - 1, -(2**63)], []],
    "List[UInt8]": [[0, 255, 7]],
    "List[UInt64]": [[0, 2**64 - 1]],
    "List[String]": [["a", "", "ünïcödé"]],
    "List[Bool]": [[True, False]],
}
REJECTED = {
    "List[Float64]": [[1, True], [float("nan")], [float("inf")], [2**1030], ["1"], [None]],
    "List[Int]": [[1, True], [2**63], [-(2**63) - 1], [1.0], ["1"]],
    "List[UInt8]": [[-1], [256], [True], [1.5]],
    "List[String]": [["a", 1], ["\ud800"], [None]],
    "List[Bool]": [[1], ["true"], [None]],
}


def test_fast_path_returns_exactly_what_the_per_element_path_returns(transport, monkeypatch):
    for type_name, samples in ACCEPTED.items():
        for value in samples:
            inner = type_name[len("List[") : -1]
            assert transport._normalize_flat_list(list(value), inner) is not None, (
                type_name,
                value,
            )
            fast = transport.normalize_value(list(value), type_name, STRUCTS, "x")
            with monkeypatch.context() as m:
                _slow(transport, m)
                slow = transport.normalize_value(list(value), type_name, STRUCTS, "x")
            assert fast == slow, (type_name, value)
            assert [type(v) for v in fast] == [type(v) for v in slow], (type_name, value)
            # decode of the kernel's own list of primitives: the same equality
            fast_d = transport.decode_value(list(value), type_name, STRUCTS, "result")
            with monkeypatch.context() as m:
                _slow(transport, m)
                slow_d = transport.decode_value(list(value), type_name, STRUCTS, "result")
            assert fast_d == slow_d and [type(v) for v in fast_d] == [type(v) for v in slow_d]
    # ints are widened to floats on the float path, exactly as before
    assert transport.normalize_value([1, 2], "List[Float64]", STRUCTS, "x") == [1.0, 2.0]
    assert all(
        isinstance(v, float) for v in transport.normalize_value([1], "List[Float64]", STRUCTS, "x")
    )


def test_fast_path_refuses_what_the_per_element_path_refuses_with_the_same_words(
    transport, monkeypatch
):
    kernel_error = sys.modules[transport.__name__.rsplit(".", 1)[0]]._native.KernelError
    for type_name, samples in REJECTED.items():
        for value in samples:
            with pytest.raises(kernel_error) as fast:
                transport.normalize_value(list(value), type_name, STRUCTS, "x")
            with monkeypatch.context() as m:
                _slow(transport, m)
                with pytest.raises(kernel_error) as slow:
                    transport.normalize_value(list(value), type_name, STRUCTS, "x")
            assert (fast.value.code, fast.value.message) == (slow.value.code, slow.value.message), (
                type_name,
                value,
            )
    # a struct list never takes the fast path (structs are dicts, walked field by field)
    pairs = [{"a": 1, "b": 2.0}]
    assert transport.normalize_value(pairs, "List[Pair]", STRUCTS, "x") == [
        {transport.STRUCT_TYPE_KEY: "Pair", transport.STRUCT_VALUES_KEY: [1, 2.0]}
    ]


def test_to_plain_leaves_a_flat_plain_list_alone_and_still_converts_the_rest(transport):
    flat = [1, 2.5, "s", True, None]
    assert transport.to_plain(flat) is flat
    assert transport.to_plain([(1, 2), [b"\x01"]]) == [[1, 2], [[1]]]
    assert transport.to_plain({"a": (1, 2), "b": [b"\x01"]}) == {"a": [1, 2], "b": [[1]]}

    class Tensorish:
        def tolist(self):
            return [1.0, 2.0]

    assert transport.to_plain([Tensorish()]) == [[1.0, 2.0]]
    assert transport._normalize_flat_list([], "Float64") == []
    assert transport._normalize_flat_list([1, "x"], "Int") is None
    assert math.isfinite(transport._normalize_flat_list([1e308], "Float64")[0])
