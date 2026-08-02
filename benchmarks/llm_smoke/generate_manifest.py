"""Thin loading glue: safetensors -> {manifest.json, weights.blob} for the Mojo driver.

This is explicitly the "parsing glue" the task rules permit in Python — it does no forward-pass
arithmetic. It:

  1. Parses `model.safetensors`' own header (8-byte length + JSON) directly, the same way the recon
     pass did, to get every tensor's name / shape / byte offset. Does NOT use `safetensors.torch`'s
     loader so the byte-level parse is real, not delegated.
  2. Decodes each tensor's raw BF16 bytes to Float64 by an EXACT bit-widening (BF16 -> FP32 is
     zero-extension of the 16 truncated mantissa bits; this is lossless and matches what a native
     hardware/compiler cast does, including Mojo's `Scalar[DType.bfloat16](...).cast[DType.float64]()`
     in tensorx.dtype.dtx_round_trip).
  3. Pre-transposes every 2D weight that will be fed to `gemm.blocked.sgemm_flat` with
     `trans_a=False, trans_b=False` (q/k/v/o_proj, gate/up/down_proj) from HF's [out,in] storage to
     [in,out] -- a data-layout decision, not an arithmetic one (gap #7 in the recon: an untransposed
     call silently falls back to gemm's scalar triple loop). `model.embed_tokens.weight` is left in
     its native [vocab, hidden] layout on purpose: the tied lm_head projection calls `sgemm_flat`
     with `trans_b=True` and slices of embed_tokens are used AS-IS as a chunked `[n, k]` operand
     (gap #5 — the single-call projection exceeds GEMM_MAX_DIM_ELEMS and must be chunked by the
     driver over the vocab dimension).
  4. Writes one flat float64 blob (weights.blob) plus manifest.json (name -> offset/shape) and a
     handful of small derived arrays the Mojo driver also needs (input token ids, and RoPE cos/sin
     precomputed EXACTLY as `Qwen3RotaryEmbedding.forward` does it -- half-split convention, see
     mojo/engine/llmk/rope.mojo).

No forward-pass compute happens here. Every matrix multiply, norm, activation and attention score
is computed by the Mojo kernels in the driver, never here.
"""
import json
import struct

import numpy as np

MODEL_DIR = "/tmp/qwen3-0.6b-base"
SAFETENSORS_PATH = f"{MODEL_DIR}/model.safetensors"
OUT_MANIFEST = "/tmp/qwen3smoke/manifest.json"
OUT_BLOB = "/tmp/qwen3smoke/weights.blob"

with open("/tmp/qwen3smoke/reference_meta.json") as f:
    _ref_meta = json.load(f)
INPUT_IDS = _ref_meta["input_ids"]

HIDDEN_SIZE = 1024
NUM_LAYERS = 28
NUM_HEADS = 16
NUM_KV_HEADS = 8
HEAD_DIM = 128
INTERMEDIATE_SIZE = 3072
VOCAB_SIZE = 151936
ROPE_THETA = 1_000_000.0
RMS_EPS = 1e-6

# Tensors that get pre-transposed from HF's [out_features, in_features] to [in_features,
# out_features] so the driver can call sgemm_flat with trans_a=False, trans_b=False everywhere
# except the final tied lm_head projection.
_TRANSPOSE_SUFFIXES = (
    "self_attn.q_proj.weight",
    "self_attn.k_proj.weight",
    "self_attn.v_proj.weight",
    "self_attn.o_proj.weight",
    "mlp.gate_proj.weight",
    "mlp.up_proj.weight",
    "mlp.down_proj.weight",
)


def read_safetensors_header(path: str) -> tuple[dict, int]:
    """Byte-level safetensors header parse: 8-byte little-endian length, then that many bytes of
    JSON. Returns (header_dict, data_start_offset) where data_start_offset is where tensor byte
    ranges are relative FROM (i.e. absolute_offset = data_start_offset + data_offsets[0])."""
    with open(path, "rb") as f:
        header_len_bytes = f.read(8)
        (header_len,) = struct.unpack("<Q", header_len_bytes)
        header_json = f.read(header_len)
    header = json.loads(header_json)
    data_start = 8 + header_len
    return header, data_start


def bf16_bytes_to_f64(raw: bytes) -> np.ndarray:
    """Exact BF16 -> FP64 widen. BF16 IS the top 16 bits of FP32, so zero-extending the low 16
    bits reconstructs the FP32 bit pattern exactly; that FP32 value is then exact in FP64."""
    u16 = np.frombuffer(raw, dtype="<u2")
    u32 = u16.astype(np.uint32) << 16
    f32 = u32.view(np.float32)
    return f32.astype(np.float64)


def main() -> None:
    header, data_start = read_safetensors_header(SAFETENSORS_PATH)
    header.pop("__metadata__", None)

    blob_chunks: list[np.ndarray] = []
    manifest_tensors: dict[str, dict] = {}
    cursor = 0

    with open(SAFETENSORS_PATH, "rb") as f:
        raw_all = f.read()

    names = sorted(header.keys())
    expected = NUM_LAYERS * 11 + 2  # 11 tensors/layer + embed_tokens.weight + norm.weight
    assert len(names) == expected, f"expected {expected} tensors, got {len(names)}"

    for name in names:
        info = header[name]
        assert info["dtype"] == "BF16", f"{name} is {info['dtype']}, expected BF16"
        shape = info["shape"]
        start, end = info["data_offsets"]
        raw = raw_all[data_start + start : data_start + end]
        values = bf16_bytes_to_f64(raw)
        n_elements = int(np.prod(shape)) if shape else 1
        assert values.shape[0] == n_elements, (name, values.shape, shape)

        transposed = False
        if len(shape) == 2 and name.endswith(_TRANSPOSE_SUFFIXES):
            mat = values.reshape(shape)
            mat = mat.T.copy()  # [out,in] -> [in,out], row-major
            values = mat.reshape(-1)
            shape = [shape[1], shape[0]]
            transposed = True

        blob_chunks.append(values)
        manifest_tensors[name] = {
            "offset": cursor,
            "n_elements": n_elements,
            "shape": shape,
            "transposed": transposed,
        }
        cursor += n_elements

    blob = np.concatenate(blob_chunks)
    assert blob.dtype == np.float64
    blob.tofile(OUT_BLOB)

    # RoPE cos/sin are NOT precomputed here. `attnk.rope.rope_table(head_dim, max_pos, theta)` builds
    # them on the Mojo side from `rope_theta` alone (frozen kernel, half-split convention -- see
    # mojo/engine/llmk/__init__.mojo for why this driver calls it instead of a second copy). The
    # driver reads `rope_theta` out of `config` below.

    manifest = {
        "config": {
            "hidden_size": HIDDEN_SIZE,
            "num_hidden_layers": NUM_LAYERS,
            "num_attention_heads": NUM_HEADS,
            "num_key_value_heads": NUM_KV_HEADS,
            "head_dim": HEAD_DIM,
            "intermediate_size": INTERMEDIATE_SIZE,
            "vocab_size": VOCAB_SIZE,
            "rope_theta": ROPE_THETA,
            "rms_norm_eps": RMS_EPS,
            "n_tokens": len(INPUT_IDS),
        },
        "input_ids": INPUT_IDS,
        "tensors": manifest_tensors,
    }
    with open(OUT_MANIFEST, "w") as f:
        json.dump(manifest, f)

    print(f"wrote {OUT_BLOB}: {blob.nbytes / 1e9:.3f} GB, {cursor} float64 elements")
    print(f"wrote {OUT_MANIFEST}: {len(manifest_tensors)} tensors")
    print("sample entries:")
    for k in ["model.embed_tokens.weight", "model.layers.0.self_attn.q_proj.weight",
              "model.layers.0.self_attn.q_norm.weight", "model.layers.0.mlp.gate_proj.weight",
              "model.norm.weight"]:
        print(" ", k, manifest_tensors[k])


if __name__ == "__main__":
    main()
