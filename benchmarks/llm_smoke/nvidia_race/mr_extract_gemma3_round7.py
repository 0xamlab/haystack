#!/usr/bin/env python3
"""mr_extract_gemma3_round7.py — MEASURED-REQUEST extraction from an algenta nsys sqlite trace.

ROUND 7 CHANGES ONE THING versus round 6's extractor, and it is the fix round 6's own integrity
note 4 asked for. Round 6 bounded the captured region by IDLE GAP (>3 ms) and took the last
surviving cluster. That is right for a served request but WRONG for the priming-only capture:
model load flows straight into seal()-time priming with no >3 ms idle gap anywhere between them,
so the priming trace's "last cluster" swallowed 304 ms of Mojo weight staging. Subtracting that
from the full trace made the `norms` and `mojo_per_layer` rows come out NEGATIVE and therefore
invalid, which is why round 6 could only report norm-accum and rope as GEOMETRY-ATTRIBUTED
estimates (instance-share 248/310, by launch geometry) rather than exact per-kernel numbers, and
why its ranked-lever list had to hedge both buckets with a "~".

`--from-first-attn` bounds the region at the FIRST fused-attention launch instead. Model load
issues no fused attention (it is weight staging and dequant), so that launch is a clean boundary
no idle-gap heuristic has to guess at. With it the priming capture is priming ONLY, the
subtraction stops producing negative rows, and norm-accum / rope / geglu become exactly measured
rather than attributed — which is what round 7 needs, because its two compensation levers live in
precisely those buckets. If no launch matches, this is a HARD STOP rather than a silent fallback:
falling back would reproduce the exact defect this option exists to remove.

Everything else is round 6's verbatim, including the bucket rules (residentk_ BEFORE gemm —
"gemma" contains "gemm"; pagedkvcache/batchprefill BEFORE the KV rule) so an algenta bucket and a
TRT-LLM bucket stay like-for-like.

Exact-FLOP model (gemma-3-27b-it, from the driver banner): d_model 5376, d_ff 21504, h_q 32,
h_kv 16, d_head 128, vocab 262208, 62 layers. Per token: qkv 2*5376*8192, o 2*4096*5376,
gate/up 2*5376*43008, down 2*21504*5376 = 825.7 MF; lm_head 2*5376*262208 = 2.82 GF once.
rag4096 (4096 tokens x 62 layers) = 209.6 TF of projection GEMM; pp1024 = 52.4 TF.

Usage:  python3 mr_extract_gemma3_round7.py <trace.sqlite> [--cell rag4096|pp1024|pp256]
            [--gap-ms 3] [--min-busy-ms 20] [--from-first-attn] [--attn-pattern fa_g3_window]
            [--json out.json]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

D_MODEL, D_FF, H_Q, H_KV, D_HEAD, VOCAB = 5376, 21504, 32, 16, 128, 262208
N_LAYERS = 62
QD = H_Q * D_HEAD              # 4096
KVD = H_KV * D_HEAD            # 2048
FLOP_PER_TOKEN = (2 * D_MODEL * (QD + 2 * KVD) + 2 * QD * D_MODEL
                  + 2 * D_MODEL * 2 * D_FF + 2 * D_FF * D_MODEL)   # 825.7 MF
CELL_TOKENS = {"pp256": 256, "pp1024": 1024, "val550": 550, "rag4096": 4096}

RULES = [
    ("fused_tc_attention", ["fa_g3_window", "fa_causal_kernel"]),
    ("attention",       ["fmha", "flash_attention", "flashattn", "xqa", "attention_", "_attn",
                         "softmax_warp", "masked_softmax", "bmm", "qk_gemm", "pv_gemm",
                         "score", "paged_attention", "unfused_attention",
                         "pagedkvcache", "batchprefill", "batchdecode"]),
    ("rope_bias_kv",    ["rope", "updatekv", "update_kv", "kv_cache", "kvcache", "addbias",
                         "applybias", "write_kv", "move_slot_kv", "kv_stage"]),
    ("swiglu_act",      ["swiglu", "geglu", "silu", "gelu", "activation", "_glu", "act_kernel"]),
    ("norms",           ["rmsnorm", "layernorm", "rms_norm", "layer_norm", "norm_rows", "_norm"]),
    ("lm_head_sampler", ["lm_head", "logits", "sampler", "topk", "topp", "argmax",
                         "softmax_last", "compute_logit", "vocab"]),
    ("f32_f16_convert", ["f32_to_f16", "f16_to_f32", "_to_f16", "cvt_", "convert", "repack",
                         "stage_weights", "transpose_into"]),
    ("weight_staging",  ["narrow", "upload_globals"]),
    ("mojo_per_layer",  ["residentk_", "residentk"]),
    ("gemm_projection", ["gemm", "cutlass", "nvjet", "xmma", "ampere", "sm90_", "sm80_",
                         "h16816", "hmma", "sgemm", "hgemm", "igemm", "s16816", "wgrad",
                         "dgrad", "implicit_gemm", "cublas"]),
    ("elementwise_copy", ["elementwise", "vectorized", "copy", "fill", "memset", "cast",
                          "reduce_kernel", "index_", "gather", "scatter", "cat_"]),
]


def bucket(name):
    low = name.lower()
    for b, keys in RULES:
        for k in keys:
            if k in low:
                return b
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite")
    ap.add_argument("--cell", default=None, help="pp256|pp1024|val550|rag4096 (for the FLOP model)")
    ap.add_argument("--gap-ms", type=float, default=3.0)
    ap.add_argument("--min-busy-ms", type=float, default=20.0)
    ap.add_argument("--from-first-attn", action="store_true",
                    help="bound the region at the FIRST fused-attention launch instead of the "
                         "last idle-gap cluster — the fix for round 6's integrity note 4, where "
                         "load->priming had no >3 ms gap and the priming capture swallowed "
                         "304 ms of weight staging, making the subtracted norms/mojo_per_layer "
                         "rows negative. Required for an exact priming subtraction.")
    ap.add_argument("--attn-pattern", default="fa_g3_window",
                    help="substring identifying the fused attention kernel in the demangled "
                         "name (default matches v1/v2/v3: _fa_g3_window{,2,3}_kernel)")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    cell = a.cell
    if cell is None:
        for k in CELL_TOKENS:
            if k in Path(a.sqlite).name:
                cell = k
                break

    con = sqlite3.connect(f"file:{a.sqlite}?mode=ro", uri=True)
    rows = con.execute("""
        SELECT k.start, k.end, s.value
        FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN StringIds s ON k.demangledName = s.id
        ORDER BY k.start
    """).fetchall()
    con.close()
    if not rows:
        print(f"{a.sqlite}: NO KERNEL RECORDS")
        sys.exit(1)

    # cluster on idle gaps
    gap_ns = a.gap_ms * 1e6
    clusters = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r[0] - cur[-1][1] > gap_ns:
            clusters.append(cur)
            cur = []
        cur.append(r)
    clusters.append(cur)

    big = []
    for c in clusters:
        busy = sum(e - s for s, e, _ in c) / 1e6
        wall = (c[-1][1] - c[0][0]) / 1e6
        if busy >= a.min_busy_ms:
            big.append({"n": len(c), "busy_ms": busy, "wall_ms": wall, "recs": c})

    print(f"=== {Path(a.sqlite).name}: {len(rows)} kernel records, "
          f"{len(clusters)} clusters, {len(big)} with busy >= {a.min_busy_ms} ms ===")
    for i, b in enumerate(big):
        print(f"  cluster {i}: n={b['n']:>6} busy={b['busy_ms']:>9.3f} ms "
              f"wall={b['wall_ms']:>9.3f} ms")
    if not big:
        sys.exit(1)
    if a.from_first_attn:
        # Round 7's boundary: the first fused-attention launch. Model load issues none (it is
        # weight staging + dequant), so everything before that launch is load, not priming.
        idx = next((i for i, r in enumerate(rows) if a.attn_pattern in r[2]), None)
        if idx is None:
            print(f"--from-first-attn: NO launch matching '{a.attn_pattern}' anywhere in this "
                  "trace. Falling back to the idle-gap cluster would silently reproduce the "
                  "negative-row defect this flag exists to remove, so this is a HARD STOP — "
                  "either the trace has no fused attention (wrong capture?) or the kernel name "
                  "changed and --attn-pattern needs updating.")
            sys.exit(1)
        mr = rows[idx:]
        drop = rows[:idx]
        print(f"  -> region = from the FIRST '{a.attn_pattern}' launch (record {idx} of "
              f"{len(rows)}): n={len(mr)}, busy={sum(e - s for s, e, _ in mr) / 1e6:.3f} ms")
        print(f"     EXCLUDED {len(drop)} leading records "
              f"({sum(e - s for s, e, _ in drop) / 1e6:.3f} ms busy) as model load / weight "
              "staging — this is the 304 ms round 6's idle-gap cluster could not separate")
        # name the boundary kernel so a wrong --attn-pattern is visible, not silent
        print(f"     boundary kernel: {mr[0][2][:80]}")
    else:
        mr = big[-1]["recs"]
        print(f"  -> measured request = LAST cluster (n={len(mr)}, "
              f"busy={sum(e - s for s, e, _ in mr) / 1e6:.3f} ms)")

    buckets = {}
    for s, e, name in mr:
        b = bucket(name)
        d = buckets.setdefault(b, {"ms": 0.0, "n": 0, "kernels": {}})
        d["ms"] += (e - s) / 1e6
        d["n"] += 1
        d["kernels"][name] = d["kernels"].get(name, [0, 0.0])
        d["kernels"][name][0] += 1
        d["kernels"][name][1] += (e - s) / 1e6

    print(f"\n{'bucket':<20}{'ms':>10}{'inst':>8}{'us/layer':>10}  top kernel")
    out = {"trace": a.sqlite, "cell": cell,
           "region": ("first_attn:" + a.attn_pattern) if a.from_first_attn
                     else "last_idle_cluster",
           "measured_request": {"n": len(mr),
                                "busy_ms": round(sum(e - s for s, e, _ in mr) / 1e6, 3)},
           "buckets": {}}
    for b, d in sorted(buckets.items(), key=lambda kv: -kv[1]["ms"]):
        top = max(d["kernels"].items(), key=lambda kv: kv[1][1])
        print(f"{b:<20}{d['ms']:>10.3f}{d['n']:>8}{d['ms'] * 1000 / N_LAYERS:>10.2f}  "
              f"{top[0][:56]} (n={top[1][0]}, {top[1][1]:.3f} ms)")
        out["buckets"][b] = {"ms": round(d["ms"], 3), "instances": d["n"],
                             "top": [[k, v[0], round(v[1], 3)] for k, v in
                                     sorted(d["kernels"].items(),
                                            key=lambda kv: -kv[1][1])[:6]]}

    if cell in CELL_TOKENS:
        tok = CELL_TOKENS[cell]
        flops = FLOP_PER_TOKEN * tok * N_LAYERS + 2 * D_MODEL * VOCAB
        g = buckets.get("gemm_projection", {"ms": 0.0})["ms"]
        if g > 0:
            tf = flops / (g / 1000.0) / 1e12
            print(f"\nGEMM exact-FLOP model ({cell}: {tok} tokens x {N_LAYERS} layers + "
                  f"lm_head = {flops / 1e12:.1f} TF):")
            print(f"  gemm_projection {g:.3f} ms -> {tf:.1f} TFLOP/s achieved "
                  f"({100 * tf / (989.0 * 1410 / 1980):.1f}% of the 1410 MHz-pinned "
                  f"989 TF/s dense f16/bf16 peak)")
            out["gemm_mfu"] = {"tflop": flops / 1e12, "ms": round(g, 3),
                               "tflops": round(tf, 1),
                               "pct_of_pinned_peak": round(100 * tf / (989.0 * 1410 / 1980), 1)}
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2))
        print(f"\nWROTE {a.json}")


if __name__ == "__main__":
    main()
