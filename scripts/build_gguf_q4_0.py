#!/usr/bin/env python3
"""Build a Q4_0 GGUF from an F16 GGUF (campaign helper; the Q4_0 TinyLlama acceptance artifact).

Quantizes every 2-D GEMM weight tensor (attn_q/k/v/output, ffn_gate/up/down) to ggml's exact
Q4_0 block format (`quantize_row_q4_0_ref` from ggml-quants.c), leaves embeddings/lm_head as F16
and norm vectors as their original F32, and rewrites the GGUF container. This is a LOCAL
transformation of an existing F16 GGUF -- it downloads nothing. The result is a genuine Q4_0 GGUF
that `algenta.inference.prepare_model_checkpoint_from_gguf` dequantizes (see
tests/test_gguf_loading.py::test_tinyllama_q4_0_gguf_converts_within_quant_tolerance).

Usage:
    python scripts/build_gguf_q4_0.py [SRC_F16_GGUF] [DST_Q4_0_GGUF]

Defaults: /private/tmp/tinyllama-f16.gguf -> /private/tmp/tinyllama-q4_0.gguf
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "packages" / "algenta"))

from algenta.inference import _read_gguf_header  # noqa: E402

_GGML_F32, _GGML_F16, _GGML_Q4_0 = 0, 1, 2
_GEMM_SUFFIXES = (
    "attn_q.weight", "attn_k.weight", "attn_v.weight", "attn_output.weight",
    "ffn_gate.weight", "ffn_up.weight", "ffn_down.weight",
)


def quantize_q4_0(x: np.ndarray) -> bytes:
    """ggml's quantize_row_q4_0_ref, exact. `x` is a flat array, len % 32 == 0. Returns the Q4_0
    block bytes (f16 scale + 16 nibble bytes per 32-element block)."""
    x = np.ascontiguousarray(x, dtype=np.float32)
    n = x.shape[0]
    if n % 32 != 0:
        raise ValueError(f"Q4_0 needs a multiple of 32 elements, got {n}")
    nb = n // 32
    xb = x.reshape(nb, 32)
    idx = np.argmax(np.abs(xb), axis=1)          # first occurrence of the abs-max
    maxv = xb[np.arange(nb), idx]                 # signed value with the max magnitude
    d = maxv / np.float32(-8.0)
    id_ = np.where(d != 0, np.float32(1.0) / d, np.float32(0.0))
    x0 = xb[:, :16] * id_[:, None]
    x1 = xb[:, 16:] * id_[:, None]
    # C `(int8_t)(v + 8.5f)` truncates toward zero; MIN(15, .) caps.
    xi0 = np.minimum(15, (x0 + np.float32(8.5)).astype(np.int8)).astype(np.uint8)
    xi1 = np.minimum(15, (x1 + np.float32(8.5)).astype(np.int8)).astype(np.uint8)
    qs = xi0 | (xi1 << np.uint8(4))
    d_f16 = d.astype(np.float16)
    out = bytearray()
    for i in range(nb):
        out += struct.pack("<e", float(d_f16[i]))
        out += qs[i].tobytes()
    return bytes(out)


def _gguf_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _gguf_kv(key: str, value) -> bytes:
    if isinstance(value, bool):
        return _gguf_string(key) + struct.pack("<I", 7) + struct.pack("<B", 1 if value else 0)
    if isinstance(value, str):
        return _gguf_string(key) + struct.pack("<I", 8) + _gguf_string(value)
    if isinstance(value, float):
        return _gguf_string(key) + struct.pack("<I", 6) + struct.pack("<f", value)
    if isinstance(value, int):
        return _gguf_string(key) + struct.pack("<I", 4) + struct.pack("<I", value)
    if isinstance(value, list):
        if all(isinstance(v, str) for v in value):
            et, payload = 8, b"".join(_gguf_string(v) for v in value)
        elif all(isinstance(v, float) for v in value):
            et, payload = 6, b"".join(struct.pack("<f", v) for v in value)
        elif all(isinstance(v, int) for v in value):
            et, payload = 4, b"".join(struct.pack("<I", v) for v in value)
        else:
            raise AssertionError(f"mixed-type metadata list for {key!r}; extend the writer")
        return (
            _gguf_string(key) + struct.pack("<I", 9) + struct.pack("<I", et)
            + struct.pack("<Q", len(value)) + payload
        )
    raise AssertionError(f"unhandled metadata value type for {key!r}: {type(value)}")


def build_q4_0(src: Path, dst: Path) -> None:
    metadata, infos, data_start = _read_gguf_header(src)
    alignment = metadata.get("general.alignment", 32)

    new_tensors: list[tuple[str, int, list, bytes]] = []
    with src.open("rb") as h:
        for info in infos:
            name, dims, ggml_type = info["name"], info["dims"], info["ggml_type"]
            n_elements = 1
            for d in dims:
                n_elements *= int(d)
            if ggml_type == _GGML_F16:
                nbytes = 2 * n_elements
            elif ggml_type == _GGML_F32:
                nbytes = 4 * n_elements
            else:
                raise AssertionError(f"unexpected source dtype {ggml_type} for {name!r}")
            h.seek(data_start + info["offset"])
            raw = h.read(nbytes)
            is_gemm = len(dims) == 2 and any(name.endswith(s) for s in _GEMM_SUFFIXES)
            if is_gemm and ggml_type == _GGML_F16 and n_elements % 32 == 0:
                x = np.frombuffer(raw, dtype="<f2").astype(np.float32)
                new_tensors.append((name, _GGML_Q4_0, dims, quantize_q4_0(x)))
            else:
                new_tensors.append((name, ggml_type, dims, raw))

    offsets: list[int] = []
    offset = 0
    for _, _, _, raw in new_tensors:
        offsets.append(offset)
        offset += len(raw)
        offset = (offset + alignment - 1) // alignment * alignment

    body = bytearray(b"GGUF" + struct.pack("<IQQ", 3, len(new_tensors), len(metadata)))
    for key, value in metadata.items():
        body += _gguf_kv(key, value)
    for (name, t, dims, _), off in zip(new_tensors, offsets):
        body += _gguf_string(name)
        body += struct.pack("<I", len(dims))
        body += struct.pack(f"<{len(dims)}Q", *dims)
        body += struct.pack("<IQ", t, off)
    data_start_new = (len(body) + alignment - 1) // alignment * alignment
    body += b"\x00" * (data_start_new - len(body))
    for _, _, _, raw in new_tensors:
        body += raw
        body += b"\x00" * (((len(raw) + alignment - 1) // alignment * alignment) - len(raw))
    dst.write_bytes(bytes(body))

    md, infos2, _ = _read_gguf_header(dst)
    counts: dict[int, int] = {}
    for i in infos2:
        counts[i["ggml_type"]] = counts.get(i["ggml_type"], 0) + 1
    print(f"wrote {dst} ({dst.stat().st_size} bytes); dtype counts {counts} (2=Q4_0,1=F16,0=F32)")
    if md.get("general.architecture") != metadata.get("general.architecture"):
        raise AssertionError("metadata architecture did not round-trip")


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/private/tmp/tinyllama-f16.gguf")
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/private/tmp/tinyllama-q4_0.gguf")
    if not src.is_file():
        raise SystemExit(f"source F16 GGUF not found: {src}")
    build_q4_0(src, dst)


if __name__ == "__main__":
    main()
