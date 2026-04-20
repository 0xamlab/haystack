"""
vector_kernels/ffi_layout.py — Python ctypes layout for the typed pipeline.

This file is REFERENCE ONLY — not imported at runtime.
It documents the ABI-stable types from types.mojo / table.mojo so that
Python can call into a compiled Mojo shared library via ctypes.

Mojo compilation target:
    mojo build mojo/engine/vector_kernels/table.mojo -o mojo_build/libranker.dylib

Or via a thin entry-point that exports C-linkage functions wrapping
CandidateTable.rank() and build_query().

────────────────────────────────────────────────────────────────────────────────
ABI-stable types (from types.mojo Layer 2)
────────────────────────────────────────────────────────────────────────────────

Mojo constants → Python ints (UInt16 / UInt8):

    SOURCE_UNKNOWN = 0    SOURCE_POS     = 1
    SOURCE_BACKLOG = 2
    SOURCE_INVOICE = 3

    ROLE_OTHER   = 0
    ROLE_UNIT    = 1   # unit_measure: unit price, unit cost
    ROLE_DERIVED = 2   # derived_measure: ext price, total

────────────────────────────────────────────────────────────────────────────────
ctypes struct definitions
────────────────────────────────────────────────────────────────────────────────
"""

import ctypes
from ctypes import c_float, c_uint8, c_uint16, c_uint32

# ── Integer constants ─────────────────────────────────────────────────────────

SOURCE_UNKNOWN = 0
SOURCE_POS     = 1
SOURCE_BACKLOG = 2
SOURCE_INVOICE = 3

ROLE_OTHER   = 0
ROLE_UNIT    = 1
ROLE_DERIVED = 2

VEC_DIM    = 64
RANK_TOP_K = 8


# ── TopKEntry: 16 bytes, C-compatible ─────────────────────────────────────────

class TopKEntry(ctypes.Structure):
    """
    Single ranked result from the typed pipeline.

    Mojo layout (types.mojo):
        column_id  UInt32   4 bytes — opaque column identifier
        score      Float32  4 bytes — final weighted score [0, 1]
        name_sim   Float32  4 bytes — cosine similarity component
        type_boost Float32  4 bytes — role + prior boost applied
        ─────────────────── 16 bytes total

    Usage:
        entry = result.entries[0]
        print(f"column {entry.column_id}: score={entry.score:.3f}")
    """
    _fields_ = [
        ("column_id",  c_uint32),   # 4
        ("score",      c_float),    # 4
        ("name_sim",   c_float),    # 4
        ("type_boost", c_float),    # 4  → 16 bytes
    ]

    def __repr__(self) -> str:
        return (
            f"TopKEntry(id={self.column_id}, score={self.score:.4f}, "
            f"sim={self.name_sim:.4f}, boost={self.type_boost:.4f})"
        )


# ── RankResult: 136 bytes ─────────────────────────────────────────────────────

class RankResult(ctypes.Structure):
    """
    Top-k ranking result from the typed pipeline.

    Mojo layout (types.mojo):
        count          UInt8          1 byte  — valid entry count (≤ 8)
        ambiguous      UInt8          1 byte  — 1 if confidence_gap < 0.08
        _pad           UInt8 × 2     2 bytes  — alignment padding
        confidence_gap Float32        4 bytes — score[0] − score[1]
        entries        TopKEntry × 8 128 bytes — 8 × 16-byte TopKEntry
        ─────────────────────────── 136 bytes total

    Note: Mojo's Bool maps to UInt8 for C compatibility (0=False, 1=True).

    Usage:
        result = lib.rank(table_ptr, byref(req))
        for i in range(result.count):
            print(result.entries[i])
        if result.ambiguous:
            print("ambiguous match — gap =", result.confidence_gap)
    """
    _fields_ = [
        ("count",          c_uint8),           # 1
        ("ambiguous",      c_uint8),           # 1
        ("_pad",           c_uint8 * 2),       # 2
        ("confidence_gap", c_float),           # 4
        ("entries",        TopKEntry * 8),     # 128 → 136 bytes
    ]

    def top(self) -> TopKEntry | None:
        """Return the highest-scored entry, or None if empty."""
        if self.count == 0:
            return None
        return self.entries[0]

    def results(self) -> list[TopKEntry]:
        """Return the valid entries as a Python list."""
        return [self.entries[i] for i in range(self.count)]

    def __repr__(self) -> str:
        entries_str = ", ".join(repr(self.entries[i]) for i in range(self.count))
        return (
            f"RankResult(count={self.count}, ambiguous={bool(self.ambiguous)}, "
            f"gap={self.confidence_gap:.4f}, [{entries_str}])"
        )


# ── RankRequest: typed query ──────────────────────────────────────────────────
#
# Python builds this, Mojo consumes it.
# query_vec_data is a 64-element Float32 array (pre-built with build_vec64).
#
# C layout (approximate — Mojo may add internal padding):
#   source_id      UInt16    2 bytes
#   role_id        UInt8     1 byte
#   top_k          UInt8     1 byte
#   query_norm_inv Float32   4 bytes
#   query_vec_data Float32×64 256 bytes
#   ─────────────────────────────── 264 bytes

class RankRequest(ctypes.Structure):
    """
    Typed query for CandidateTable.rank().

    Python populates this with:
      1. source_id / role_id from the SOURCE_* / ROLE_* constants
      2. top_k: how many results to return (≤ 8)
      3. query_vec_data: 64 Float32 bigram frequencies (see build_vec64)
      4. query_norm_inv: 1/||query_vec|| (see build_vec64)

    Usage:
        req = RankRequest()
        req.source_id = SOURCE_POS
        req.role_id   = ROLE_UNIT
        req.top_k     = 5
        req.query_norm_inv = build_vec64("unit_price", req.query_vec_data)
    """
    _fields_ = [
        ("source_id",      c_uint16),          # 2
        ("role_id",        c_uint8),           # 1
        ("top_k",          c_uint8),           # 1
        ("query_norm_inv", c_float),           # 4
        ("query_vec_data", c_float * VEC_DIM), # 256 → 264 bytes
    ]


# ── build_vec64: Python-side bigram encoder ───────────────────────────────────

def _norm_byte(c: int) -> int:
    """Normalise byte: separators → 32 (space), uppercase → lowercase."""
    if c in (95, 45, 46):  # _ - .
        return 32
    if 65 <= c <= 90:       # A-Z
        return c + 32
    return c


def build_vec64(name: str, out_vec: ctypes.Array) -> float:
    """
    Encode a column name as a 64-bucket bigram frequency vector.

    Fills `out_vec` (a Float32 × 64 ctypes array) and returns norm_inv.
    Mirrors the Mojo build_vec64_f32() implementation exactly.

    Args:
        name:    column name string (e.g. "unit_price")
        out_vec: ctypes (c_float * 64) array to fill in-place

    Returns:
        norm_inv: Float32 — 1/||vec||, or 0.0 for empty / zero vectors

    Example:
        req = RankRequest()
        req.query_norm_inv = build_vec64("unit_price", req.query_vec_data)
    """
    # Zero the output
    for i in range(VEC_DIM):
        out_vec[i] = 0.0

    bs = name.encode("utf-8")
    n = len(bs)
    if n == 0:
        return 0.0

    prev = _norm_byte(bs[0])
    for i in range(1, n):
        cur = _norm_byte(bs[i])
        h = (prev * 31 + cur) & (VEC_DIM - 1)
        out_vec[h] += 1.0
        prev = cur

    # L2 norm inverse
    mag_sq = sum(out_vec[i] * out_vec[i] for i in range(VEC_DIM))
    if mag_sq <= 0.0:
        return 0.0
    return 1.0 / (mag_sq ** 0.5)


# ── Convenience builder ───────────────────────────────────────────────────────

def make_rank_request(
    name:      str,
    source_id: int = SOURCE_UNKNOWN,
    role_id:   int = ROLE_OTHER,
    top_k:     int = 5,
) -> RankRequest:
    """
    Build a RankRequest from a raw column name.

    Example:
        req = make_rank_request("unit_price", SOURCE_POS, ROLE_UNIT, top_k=5)
        result = lib.rank_resident(table_handle, ctypes.byref(req))
    """
    req = RankRequest()
    req.source_id      = source_id
    req.role_id        = role_id
    req.top_k          = top_k
    req.query_norm_inv = build_vec64(name, req.query_vec_data)
    return req


# ── Future shared-library integration sketch ─────────────────────────────────
#
# When Mojo supports exported C-linkage functions, the integration will be:
#
#   lib = ctypes.CDLL("mojo_build/libranker.dylib")
#
#   # Build the table once at startup
#   lib.build_table_json.restype  = c_void_p
#   lib.build_table_json.argtypes = [ctypes.c_char_p]
#   table_handle = lib.build_table_json(candidates_json.encode())
#
#   # Query per request (hot path — zero Python GIL contention)
#   lib.rank_resident.restype  = RankResult
#   lib.rank_resident.argtypes = [c_void_p, POINTER(RankRequest)]
#   req    = make_rank_request("unit_price", SOURCE_POS, ROLE_UNIT)
#   result = lib.rank_resident(table_handle, ctypes.byref(req))
#
#   # Inspect results
#   for entry in result.results():
#       print(entry)
#
# Until shared-library export is available, use the subprocess JSON bridge:
#   from engines.column_ranker import run_column_rank_v2
#   (falls back to JSON pipeline — still 9x faster than pure Python)


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Verify struct sizes
    assert ctypes.sizeof(TopKEntry) == 16,  f"TopKEntry size={ctypes.sizeof(TopKEntry)}, expected 16"
    assert ctypes.sizeof(RankResult) == 136, f"RankResult size={ctypes.sizeof(RankResult)}, expected 136"

    # Test build_vec64 — exact match
    req = make_rank_request("unit_price", SOURCE_POS, ROLE_UNIT)
    assert req.source_id == SOURCE_POS
    assert req.role_id   == ROLE_UNIT
    assert req.top_k     == 5
    assert req.query_norm_inv > 0.0, "norm_inv should be positive for non-empty name"

    # Verify bigram hash for "un" → (117 * 31 + 110) & 63 = (3627 + 110) & 63 = 3737 & 63 = 25
    # "unit_price" should have a non-zero bucket at h=25
    assert req.query_vec_data[25] > 0.0, "bigram bucket for 'un' should be non-zero"

    print("[PASS] TopKEntry size = 16")
    print("[PASS] RankResult size = 136")
    print("[PASS] build_vec64('unit_price') norm_inv =", req.query_norm_inv)
    print("[PASS] ffi_layout.py self-test complete")
    sys.exit(0)
