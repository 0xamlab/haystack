"""Manual Python reference for vector_kernels/ranker.mojo."""

from __future__ import annotations

import json
import math
from ctypes import c_float

VEC_DIM = 64
AMBIG_GAP = 0.08
W_NAME = 0.55
W_TOKEN = 0.25


def _f32(value: float) -> float:
    return float(c_float(float(value)).value)


def _contains_lower(text: str, sub: str) -> bool:
    return sub.lower() in text.lower()


def _split_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    current = []
    for ch in value:
        if ch in {"_", "-", ".", " "}:
            if current:
                tokens.append("".join(current))
                current.clear()
            continue
        current.append(ch.lower())
    if current:
        tokens.append("".join(current))
    return tokens


def _build_vec(value: str) -> tuple[list[float], float]:
    buf = [_f32(0.0) for _ in range(VEC_DIM)]
    if not value:
        return buf, _f32(0.0)
    normalized = []
    for ch in value:
        if ch in {"_", "-", "."}:
            normalized.append(" ")
        else:
            normalized.append(ch.lower())
    prev = ord(normalized[0])
    for ch in normalized[1:]:
        cur = ord(ch)
        index = (prev * 31 + cur) & (VEC_DIM - 1)
        buf[index] = _f32(buf[index] + 1.0)
        prev = cur
    mag = _f32(sum(_f32(item * item) for item in buf))
    if mag <= 0.0:
        return buf, _f32(0.0)
    return buf, _f32(1.0 / math.sqrt(mag))


def _dot64(a: list[float], b: list[float]) -> float:
    return _f32(sum(_f32(lhs * rhs) for lhs, rhs in zip(a, b, strict=False)))


def _cosine(a: list[float], b: list[float], ni_a: float, ni_b: float) -> float:
    if ni_a == 0.0 or ni_b == 0.0:
        return _f32(0.0)
    raw = _f32(_dot64(a, b) * ni_a * ni_b)
    if raw > 1.0:
        return _f32(1.0)
    if raw < 0.0:
        return _f32(0.0)
    return raw


def _token_jaccard(a_toks: list[str], b_toks: list[str]) -> float:
    if not a_toks or not b_toks:
        return _f32(0.0)
    intersect = 0
    for token in a_toks:
        if token in b_toks:
            intersect += 1
    union = len(a_toks) + len(b_toks) - intersect
    if union == 0:
        return _f32(0.0)
    return _f32(float(intersect) / float(union))


def _role_boost(role: str, hint_toks: list[str]) -> float:
    if not role or not hint_toks:
        return _f32(0.0)
    has_unit = any(token in {"unit", "per", "each"} for token in hint_toks)
    has_ext = any(token in {"ext", "extended", "total", "amount"} for token in hint_toks)
    if role == "unit_measure":
        if has_unit:
            return _f32(0.12)
        if has_ext:
            return _f32(-0.08)
    if role == "derived_measure":
        if has_ext:
            return _f32(0.12)
        if has_unit:
            return _f32(-0.08)
    return _f32(0.0)


def _prior_boost(source_type: str, col_raw: str) -> float:
    if source_type == "POS":
        if _contains_lower(col_raw, "unit") and (
            _contains_lower(col_raw, "price") or _contains_lower(col_raw, "cost")
        ):
            return _f32(0.10)
    elif source_type == "BACKLOG":
        if (_contains_lower(col_raw, "ext") or _contains_lower(col_raw, "extended")) and (
            _contains_lower(col_raw, "price") or _contains_lower(col_raw, "cost")
        ):
            return _f32(0.10)
    elif source_type == "INVOICE":
        if _contains_lower(col_raw, "amount") or _contains_lower(col_raw, "total"):
            return _f32(0.10)
    return _f32(0.0)


def _format_f32(value: float) -> float:
    return _f32(value)


def _json_str(key: str, value: str) -> str:
    return f'"{key}":"{value}"'


def _json_f32(key: str, value: float) -> str:
    vi = int(_f32(value) * 10000.0 + 0.5)
    whole = vi // 10000
    frac = vi % 10000
    return f'"{key}":{whole}.{frac:04d}'


def _json_bool(key: str, value: bool) -> str:
    return f'"{key}":{"true" if value else "false"}'


def run_column_rank_v2(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except Exception:
        return '{"error":"missing query.name"}'

    query = payload.get("query", {})
    q_name = str(query.get("name", ""))
    q_role = str(query.get("role_hint", ""))
    q_src = str(query.get("source", ""))
    if not q_name:
        return '{"error":"missing query.name"}'

    top_k = int(payload.get("top_k", 5) or 5)
    q_buf, q_ni = _build_vec(q_name)
    q_toks = _split_tokens(q_name)
    hint_toks = _split_tokens(q_role)

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return '{"error":"missing candidates"}'

    results: list[dict[str, object]] = []
    for candidate in candidates:
        c_src = str(candidate.get("source", ""))
        c_name = str(candidate.get("name", ""))
        if not c_name:
            continue
        c_buf, c_ni = _build_vec(c_name)
        nsim = _cosine(q_buf, c_buf, q_ni, c_ni)
        tsim = _token_jaccard(q_toks, _split_tokens(c_name))
        tb = _role_boost(q_role, hint_toks)
        pb = _prior_boost(q_src, c_name)
        raw_score = _f32(_f32(W_NAME * nsim) + _f32(W_TOKEN * tsim) + tb + pb)
        score = _f32(max(0.0, min(1.0, raw_score)))
        results.append(
            {
                "source": c_src,
                "column": c_name,
                "score": _format_f32(score),
                "name_sim": _format_f32(nsim),
                "token_sim": _format_f32(tsim),
                "type_boost": _format_f32(tb),
                "prior_boost": _format_f32(pb),
            }
        )

    results.sort(key=lambda item: float(item["score"]), reverse=True)
    out_n = min(len(results), top_k)
    gap = _f32(0.0)
    if len(results) >= 2:
        gap = _f32(float(results[0]["score"]) - float(results[1]["score"]))
    ambiguous = bool(len(results) >= 2 and gap < AMBIG_GAP)
    parts = ['{"matches":[']
    for index in range(out_n):
        if index > 0:
            parts.append(",")
        result = results[index]
        parts.extend(
            [
                "{",
                _json_str("source", str(result["source"])),
                ",",
                _json_str("column", str(result["column"])),
                ",",
                _json_f32("score", float(result["score"])),
                ",",
                _json_f32("name_sim", float(result["name_sim"])),
                ",",
                _json_f32("token_sim", float(result["token_sim"])),
                ",",
                _json_f32("type_boost", float(result["type_boost"])),
                ",",
                _json_f32("prior_boost", float(result["prior_boost"])),
                "}",
            ]
        )
    parts.extend(
        [
            "],",
            _json_f32("confidence_gap", float(gap)),
            ",",
            _json_bool("ambiguous", ambiguous),
            "}",
        ]
    )
    return "".join(parts)
