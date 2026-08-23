"""check_blob_qkv.py — disambiguate the layer-0 qkv divergence (2026-08-23 bisection):
recompute the LAST prompt row's xn1 and qkv NUMERICALLY from the blob's own f64 weights
(numpy memmap, f64 math) and print the shared checksum format. If blob-math == transformers,
the weights are CORRECT and the engine's packing/GEMM is at fault; if blob-math == engine,
the blob weights themselves are wrong (converter bug).

Usage: python3 check_blob_qkv.py --ckpt /tmp/w7b/ckpt --prompt chat_1
"""

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="/tmp/w7b/ckpt")
    ap.add_argument("--prompt", default="chat_1")
    args = ap.parse_args()

    import numpy as np

    ckpt = Path(args.ckpt)
    manifest = json.loads((ckpt / "manifest.json").read_text())
    prompts = json.loads((ckpt / "prompts.json").read_text())
    if args.prompt == "fixture":
        ids = prompts["fixture"]["ids"]
    else:
        ids = prompts["chat_prompts"][int(args.prompt.split("_")[1])]["ids"]

    tensors = manifest["tensors"]
    blob = np.memmap(ckpt / "weights.blob", dtype=np.float64, mode="r")

    def tensor(name):
        t = tensors[name]
        n = t["n_elements"]
        shape = tuple(t["shape"])  # the ON-DISK (post-conversion) shape
        return blob[t["offset"]:t["offset"] + n].reshape(shape)

    d_model = manifest["config"]["hidden_size"]
    eps = manifest["config"]["rms_norm_eps"]

    # ── embed row of the final prompt token ──
    embed = tensor("model.embed_tokens.weight")          # [vocab, d_model]
    x = embed[ids[-1]].astype(np.float64)

    # ── xn1 = rmsnorm(x, ln1) — the engine's exact convention: x * inv * gain ──
    ln1 = tensor("model.layers.0.input_layernorm.weight")  # [d_model]
    inv = 1.0 / np.sqrt(np.mean(x * x) + eps)
    xn1 = x * inv * ln1
    s = float(xn1.sum())
    print(f"BLOB|-1|xn1|{xn1.size}|{s!r}|{float(np.abs(xn1).max())!r}"
          f"|{float(xn1[0])!r}|{float(xn1[1])!r}")

    # ── qkv = xn1 @ [q|k|v], weights in their ON-DISK layout ──
    # The manifest marks q/k/v/o/gate/up/down `transposed`: on disk [in, out].
    q_w = tensor("model.layers.0.self_attn.q_proj.weight")
    k_w = tensor("model.layers.0.self_attn.k_proj.weight")
    v_w = tensor("model.layers.0.self_attn.v_proj.weight")
    print(f"# on-disk shapes: q={q_w.shape} k={k_w.shape} v={v_w.shape} "
          f"(transposed flags: "
          f"{tensors['model.layers.0.self_attn.q_proj.weight']['transposed']}, "
          f"{tensors['model.layers.0.self_attn.k_proj.weight']['transposed']}, "
          f"{tensors['model.layers.0.self_attn.v_proj.weight']['transposed']})")

    def _as_in_out(w, transposed):
        # Return the weight as [in, out] regardless of the disk flag.
        return w if transposed else w.T

    q = xn1 @ _as_in_out(q_w, tensors["model.layers.0.self_attn.q_proj.weight"]["transposed"])
    k = xn1 @ _as_in_out(k_w, tensors["model.layers.0.self_attn.k_proj.weight"]["transposed"])
    v = xn1 @ _as_in_out(v_w, tensors["model.layers.0.self_attn.v_proj.weight"]["transposed"])
    qkv = np.concatenate([q, k, v])
    s = float(qkv.sum())
    print(f"BLOB|0|qkv|{qkv.size}|{s!r}|{float(np.abs(qkv).max())!r}"
          f"|{float(qkv[0])!r}|{float(qkv[1])!r}")
    print(f"# q part: sum={float(q.sum())!r} max={float(np.abs(q).max())!r} "
          f"v0={float(q[0])!r} v1={float(q[1])!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
