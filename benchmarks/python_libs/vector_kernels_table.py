"""Manual Python reference for vector_kernels/table.mojo."""

from __future__ import annotations

import json
import math
from ctypes import c_float

VEC_DIM = 64
SOURCE_UNKNOWN = 0
SOURCE_POS = 1
SOURCE_BACKLOG = 2
SOURCE_INVOICE = 3
ROLE_OTHER = 0
ROLE_UNIT = 1
ROLE_DERIVED = 2


def _f32(value: float) -> float:
    return float(c_float(float(value)).value)


def _norm_byte(value: int) -> int:
    if value in {95, 45, 46}:
        return 32
    if 65 <= value <= 90:
        return value + 32
    return value


def _build_vec_inplace(value: str, buf: list[float]) -> float:
    for index in range(VEC_DIM):
        buf[index] = _f32(0.0)
    encoded = value.encode("utf-8")
    if not encoded:
        return _f32(0.0)
    prev = _norm_byte(encoded[0])
    for raw in encoded[1:]:
        cur = _norm_byte(raw)
        slot = (prev * 31 + cur) & (VEC_DIM - 1)
        buf[slot] = _f32(buf[slot] + 1.0)
        prev = cur
    mag = _f32(sum(_f32(item * item) for item in buf))
    if mag <= 0.0:
        return _f32(0.0)
    return _f32(1.0 / math.sqrt(mag))


def source_id_of(value: str) -> int:
    if value == "POS":
        return SOURCE_POS
    if value == "BACKLOG":
        return SOURCE_BACKLOG
    if value == "INVOICE":
        return SOURCE_INVOICE
    return SOURCE_UNKNOWN


def role_id_of(value: str) -> int:
    if value == "unit_measure":
        return ROLE_UNIT
    if value == "derived_measure":
        return ROLE_DERIVED
    return ROLE_OTHER


def build_query(name: str, source_id: int, role_id: int, top_k: int) -> dict[str, object]:
    vec_data = [_f32(0.0) for _ in range(VEC_DIM)]
    query_norm_inv = _build_vec_inplace(name, vec_data)
    return {
        "source_id": int(source_id),
        "role_id": int(role_id),
        "top_k": int(top_k),
        "query_norm_inv": _f32(query_norm_inv),
        "query_vec": {
            "data": vec_data,
            "norm_inv": _f32(0.0),
        },
    }


def build_table_json(candidates_json: str) -> dict[str, object]:
    try:
        candidates = json.loads(candidates_json)
    except Exception:
        candidates = []
    entries: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates):
        column_id = int(candidate.get("id", index + 1))
        source = str(candidate.get("source", ""))
        role = str(candidate.get("role", ""))
        name = str(candidate.get("name", ""))
        vec_data = [_f32(0.0) for _ in range(VEC_DIM)]
        norm_inv = _build_vec_inplace(name, vec_data)
        entries.append(
            {
                "column_id": column_id,
                "source_id": source_id_of(source),
                "role_id": role_id_of(role),
                "norm_inv": _f32(norm_inv),
                "vec": {
                    "data": vec_data,
                    "norm_inv": _f32(0.0),
                },
            }
        )
    return {"entries": entries}
