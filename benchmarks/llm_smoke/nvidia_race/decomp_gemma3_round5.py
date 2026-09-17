#!/usr/bin/env python3
"""decomp_gemma3_round5.py -- per-kernel decomposition of the round-5 gemma-3-27b arms.

argv: <nsys_dir> <out_json>

Two jobs, and the second is the reason this script exists rather than a bucket roll-up:

1. BUCKET ROLL-UP. Every kernel in each trace is classified by the same ordered rule list the
   H200 re-race used (rr_decomp2.py), so an algenta arm and a TRT-LLM arm are bucketed
   identically and a delta is a like-for-like delta. Two rules matter enough to restate:
   `residentk_` MUST precede the gemm rule (Mojo mangles kernels_prefill_gemma3 symbols to
   `residentk_kernels_prefill_gemma6A6A_<hash>`, and "gemma" CONTAINS "gemm" -- a bare
   `"gemm" in name` test silently moved every Mojo per-layer kernel into the cuBLAS bucket,
   which is how the old 397.5 ms "rag4096 GEMM" figure was born; the true value is 336.592 ms),
   and `pagedkvcache`/`batchprefill` must precede the KV rule so TRT-LLM's real
   flashinfer attention kernel is not counted as KV work.

2. ATTRIBUTION BY LAUNCH GEOMETRY, NOT BY NAME. Mojo kernel names mangle to a hash, so a name
   is not evidence. The grid geometry is: for gemma-3-27b (h_q=32, h_kv=16, d_head=128,
   d_model=5376, d_ff=21504, G3_PF_TILE=1024) a pp1024 tile dispatches
       16384 x 256  = ceil(h_q*m*d_head/256) = ceil(32*1024*128/256)  -> Q pack / O unpack
       86016 x 256  = ceil(m*d_ff/256)       = ceil(1024*21504/256)   -> GeGLU MLP activation
        8192 x 256  = ceil(h_kv*m*d_head/256)                          -> (unused at these shapes)
   This script reads the CUPTI kernel records out of the exported sqlite and attributes by
   (gridX, gridY, gridZ, blockX) exactly that way, and REFUSES to attribute a geometry it does
   not recognise -- an ambiguous row is reported as `unattributed` with its count and total, so
   a guessed attribution can never enter a published table.

   It also settles the `_f32_to_f16_kernel` question by INSTANCE COUNT, which needs no
   modelling at all: that one kernel is both the shim's per-call f32->f16 A conversion for the
   four projection GEMMs AND the K/V cache staging, so at pp1024 the baseline launches it
   4*62 + 2*62 + 1 = 373 times. The fused attention removes only the 124 KV launches; the
   pre-staged-A chain removes the other 248. The prediction is therefore
       R5_base 373  ->  R5_fa 249  ->  R5_all 1
   and `f32_to_f16_instance_check` below reports the observed counts against it. If the counts
   do not land there, the byte-share split this round publishes is wrong and says so.
"""
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

NS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/angel/lever5/nsys")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/home/angel/lever5/decomp_round5.json")
N_LAYERS = 62                     # gemma-3-27b-it num_hidden_layers
H_Q, H_KV, D_HEAD = 32, 16, 128
D_MODEL, D_FF, TILE = 5376, 21504, 1024
TG = 256

# (bucket, keys) -- ORDERED; first match wins.
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
    # the shim's f32<->f16 conversion kernel gets its OWN bucket this round: round 4 charged
    # all of it to "KV staging", but it is shared with the four projection A conversions and
    # the split is what the levers actually move.
    ("f32_f16_convert", ["f32_to_f16", "f16_to_f32", "_to_f16", "cvt_", "convert", "repack",
                         "stage_weights", "transpose_into"]),
    ("weight_staging",  ["narrow", "upload_globals"]),
    # MUST precede gemm_projection: "gemma" contains "gemm".
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


# launch geometry -> what it is, derived from the model's own shapes (never guessed)
def geom_role(gx, gy, gz, bx):
    """Attribute a Mojo launch by GEOMETRY. The traces are WHOLE-PROCESS, so they contain PR
    #993's `_prime_prefill_modules` prefills (tile rows TC_MIN_M=128, 256, 512, G3_PF_TILE=1024)
    as well as the timed request; the table therefore covers every tile row count the session can
    dispatch, not just 1024. Without that the priming launches land in UNATTRIBUTED and the timed
    prefill's share cannot be separated from seal()-time work."""
    def cd(n):
        return (n + TG - 1) // TG
    known = {}
    for tile in (128, 256, 512, 1024):
        # ceil(h_q*m*d_head/256): the head-major Q pack and the O unpack (16384 at m=1024)
        known[(cd(H_Q * tile * D_HEAD), 1, 1)] = \
            f"pf_q_pack_hm_f16 / pf_attn_unpack_hm_f32 (h_q*m*d, tile={tile})"
        # ceil(m*d_ff/256): the GeGLU MLP activation (86016 at m=1024)
        known[(cd(tile * D_FF), 1, 1)] = f"pf_geglu_rows[_f16]_kernel (m*d_ff, tile={tile})"
        # h_q*m blocks of d_head threads: the SIMT windowed attention (32768 at m=1024)
        known[(H_Q * tile, 1, 1)] = f"pf_attn_window_kernel SIMT (h_q*m, tile={tile})"
    known[(cd(D_MODEL), 1, 1)] = "row-copy / final-norm single row (d_model)"
    key = (gx, gy, gz)
    if key in known and bx in (TG, D_HEAD):
        return known[key]
    if bx == D_HEAD and gy == 1 and gz == 1 and gx % (H_Q + H_KV) == 0:
        return f"ropewrt / windowed-attn SIMT ((h_q+h_kv)*m or h_q*m = {gx})"
    if bx == TG and gy == 1 and gz == 1 and gx % TILE == 0 and gx // TILE in (1, 2, 4):
        return f"row-batched per-tile kernel (grid {gx} = {gx // TILE} x {TILE} tile rows)"
    return None


def read_kern_sum(path):
    rows = []
    if not path.exists():
        return rows
    with path.open(newline="", errors="replace") as f:
        rd = csv.DictReader(f)
        if not rd.fieldnames:
            return rows
        def pick(*cands):
            for c in rd.fieldnames:
                cl = c.strip().lower()
                for cand in cands:
                    if cl.startswith(cand):
                        return c
            return None
        c_tot = pick("total time")
        c_inst = pick("instances")
        c_name = pick("name")
        c_avg = pick("avg")
        if not (c_tot and c_inst and c_name):
            return rows
        for r in rd:
            try:
                rows.append({"name": r[c_name], "total_ms": float(r[c_tot]) / 1e6,
                             "instances": int(r[c_inst]),
                             "avg_us": (float(r[c_avg]) / 1e3) if c_avg and r.get(c_avg) else None})
            except (TypeError, ValueError):
                continue
    return rows


def read_sqlite_geom(path):
    """[(name, gridX, gridY, gridZ, blockX, instances, total_ms)] from the CUPTI kernel records."""
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    out = []
    try:
        cur = con.execute("""
            SELECT s.value, k.gridX, k.gridY, k.gridZ, k.blockX,
                   COUNT(*), SUM(k.end - k.start) / 1e6
            FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN StringIds s ON k.demangledName = s.id
            GROUP BY s.value, k.gridX, k.gridY, k.gridZ, k.blockX
            ORDER BY SUM(k.end - k.start) DESC
        """)
        for r in cur.fetchall():
            out.append({"name": r[0], "grid": [r[1], r[2], r[3]], "block": r[4],
                        "instances": r[5], "total_ms": round(r[6], 4)})
    except sqlite3.Error as e:
        print(f"  (sqlite read failed for {path.name}: {e})")
    finally:
        con.close()
    return out


def main():
    tags = sorted({p.name.replace("_stats_cuda_gpu_kern_sum.csv", "")
                   for p in NS.glob("*_stats_cuda_gpu_kern_sum.csv")})
    if not tags:
        tags = sorted({p.name.replace(".nsys-rep", "") for p in NS.glob("*.nsys-rep")})
    res = {"n_layers": N_LAYERS,
           "model_shape": {"h_q": H_Q, "h_kv": H_KV, "d_head": D_HEAD, "d_model": D_MODEL,
                           "d_ff": D_FF, "tile": TILE},
           "traces": {}}
    print("=== ROUND-5 gemma-3-27b per-kernel decomposition (clocks 1410 MHz) ===")
    for tag in tags:
        rows = read_kern_sum(NS / f"{tag}_stats_cuda_gpu_kern_sum.csv")
        geom = read_sqlite_geom(NS / f"{tag}.sqlite")
        if not rows and not geom:
            print(f"\n--- {tag}: NO KERNEL DATA (capture missing or nsys stats empty) ---")
            continue
        buckets = {}
        for r in rows:
            b = bucket(r["name"])
            d = buckets.setdefault(b, {"total_ms": 0.0, "instances": 0, "kernels": []})
            d["total_ms"] += r["total_ms"]
            d["instances"] += r["instances"]
            d["kernels"].append({**r, "per_layer_us": round(r["total_ms"] * 1000 / N_LAYERS, 3)})
        for b in buckets:
            buckets[b]["total_ms"] = round(buckets[b]["total_ms"], 4)
            buckets[b]["per_layer_us"] = round(buckets[b]["total_ms"] * 1000 / N_LAYERS, 3)
            buckets[b]["kernels"].sort(key=lambda k: -k["total_ms"])

        # the specific kernels the levers move, by name where the name is real (the shim's
        # nvcc kernels keep their symbols) and by geometry where it is not (Mojo's)
        conv = [r for r in rows if "f32_to_f16" in r["name"].lower()]
        softmax = [r for r in rows if "attn_softmax_mask" in r["name"].lower()]
        fa = [r for r in rows if "fa_g3_window" in r["name"].lower()
              or "fa_causal" in r["name"].lower()]
        attributed, unattributed = [], []
        for g in geom:
            if not g["name"].startswith("residentk"):
                continue
            role = geom_role(g["grid"][0], g["grid"][1], g["grid"][2], g["block"])
            rec = {**g, "role": role or "UNATTRIBUTED"}
            (attributed if role else unattributed).append(rec)

        res["traces"][tag] = {"buckets": buckets,
                              "f32_to_f16_instances": sum(r["instances"] for r in conv),
                              "f32_to_f16_total_ms": round(sum(r["total_ms"] for r in conv), 4),
                              "masked_softmax_total_ms": round(
                                  sum(r["total_ms"] for r in softmax), 4),
                              "fused_fa_total_ms": round(sum(r["total_ms"] for r in fa), 4),
                              "fused_fa_instances": sum(r["instances"] for r in fa),
                              "mojo_attributed": attributed,
                              "mojo_unattributed": unattributed,
                              "gpu_total_ms": round(sum(r["total_ms"] for r in rows), 4)}

        print(f"\n--- {tag} ---  GPU kernel total {res['traces'][tag]['gpu_total_ms']:.3f} ms")
        print(f"{'bucket':<20}{'total ms':>10}{'us/layer':>10}{'instances':>11}  top kernel")
        for b, d in sorted(buckets.items(), key=lambda kv: -kv[1]["total_ms"]):
            top = d["kernels"][0]["name"][:58] if d["kernels"] else ""
            print(f"{b:<20}{d['total_ms']:>10.3f}{d['per_layer_us']:>10.2f}"
                  f"{d['instances']:>11}  {top}")
        print(f"  _f32_to_f16_kernel: {res['traces'][tag]['f32_to_f16_instances']} launches, "
              f"{res['traces'][tag]['f32_to_f16_total_ms']:.3f} ms "
              f"(baseline pp1024 prediction 373 = 248 projection-A + 124 KV + 1 lm_head)")
        if fa:
            print(f"  fused TC flash attention: {res['traces'][tag]['fused_fa_instances']} "
                  f"launches, {res['traces'][tag]['fused_fa_total_ms']:.3f} ms "
                  f"({res['traces'][tag]['fused_fa_total_ms'] * 1000 / N_LAYERS:.2f} us/layer)")
        if unattributed:
            print(f"  UNATTRIBUTED Mojo geometries ({len(unattributed)}): reported, NOT guessed")
            for u in unattributed[:8]:
                print(f"    grid={u['grid']} block={u['block']} n={u['instances']} "
                      f"{u['total_ms']:.3f} ms  {u['name'][:60]}")

    # ── the instance-count check. This settles the KV-vs-projection-A attribution question by
    #    COUNT rather than by model, but only if the prediction is on the same basis as the
    #    observation: these traces are WHOLE-PROCESS, so they include the four priming prefills
    #    PR #993 added at seal() (tile rows TC_MIN_M=128, 256, 512, 1024) as well as the timed
    #    request. The first cut predicted per-prefill counts (373 at pp1024) and so reported
    #    MISMATCH against a correct measurement -- the prediction was wrong, not the split.
    #
    #    Per prefill of one 1024-row tile: 4 projection seams x 62 layers = 248 A-stagings,
    #    + 2 KV stagings x 62 = 124 when m >= 256 (the TC-attention crossover), + 1 lm_head A.
    #      priming (128, 256, 512, 1024) = 249 + 373 + 373 + 373            = 1368
    #      timed pp1024  (1 tile)        = 372 + 1                          =  373
    #      timed rag4096 (4 tiles)       = 4 x 372 + 1                      = 1489
    #    R5_fa  removes the 124 KV launches of every prefill with m >= 256: 4 at pp1024
    #           (3 priming + 1 timed), 7 at rag4096 (3 priming + 4 timed tiles).
    #    R5_mlp removes 3 of the 4 projection seams (qkv and gate/up via F16NORM, down via
    #           F16MLP) but KEEPS o_proj's -- F16ATTN is the fused kernel's f16 O, and R5_mlp
    #           has no fused kernel: 3 x 62 x 5 = 930 removed.
    #    R5_all removes both, and what is LEFT is itself a prediction: 5 lm_head A stagings plus
    #           62 o_proj A stagings from the m=128 priming prefill, where the fused attention
    #           declines (m < _G3_PF_FA_MIN_M = 256) so the SIMT kernel writes f32 pf_attn and
    #           o_proj falls back to the staging ladder. 5 + 62 = 67, not 1.
    PRIMING = 1368
    pred = {
        "R5_base_pp1024":  PRIMING + 373,             # 1741
        "R5_base_rag4096": PRIMING + 1489,            # 2857
        "R5_fa_pp1024":    PRIMING + 373 - 4 * 124,   # 1245
        "R5_fa_rag4096":   PRIMING + 1489 - 7 * 124,  # 1989
        "R5_mlp_pp1024":   PRIMING + 373 - 3 * 62 * 5,  # 811
        "R5_all_pp1024":   5 + 62,                    # 67
        "R5_all_rag4096":  5 + 62,                    # 67
    }
    chk = {}
    for tag, want in pred.items():
        got = res["traces"].get(tag, {}).get("f32_to_f16_instances")
        if got is not None:
            chk[tag] = {"predicted": want, "observed": got, "match": got == want}
    res["f32_to_f16_instance_check"] = chk
    res["f32_to_f16_prediction_basis"] = (
        "whole-process basis: priming prefills at seal() (tile rows 128/256/512/1024 = "
        "249+373+373+373 = 1368 launches) PLUS the timed request (pp1024 one tile = 373; "
        "rag4096 four tiles = 4x372+1 = 1489). Per tile: 4 projection seams x 62 layers = 248 "
        "A-stagings + 2 KV stagings x 62 = 124 when m >= 256 + 1 lm_head A. R5_fa drops the 124 "
        "KV launches of every m >= 256 prefill; R5_mlp drops 3 of the 4 projection seams "
        "(o_proj's survives -- its pre-staged A is F16ATTN, which needs the fused kernel); "
        "R5_all drops both and leaves 5 lm_head + 62 o_proj from the m=128 priming prefill, "
        "where the fused attention declines at m < 256 and o_proj falls back to the ladder.")
    if chk:
        print("\n=== _f32_to_f16_kernel INSTANCE-COUNT CHECK (attribution by count, not model) ===")
        n_ok = sum(1 for c in chk.values() if c["match"])
        for tag, c in chk.items():
            print(f"  {tag:<18} predicted {c['predicted']:>5}  observed {c['observed']:>5}  "
                  f"{'MATCH' if c['match'] else 'MISMATCH -- the byte-share split is wrong'}")
        print(f"  {n_ok}/{len(chk)} traces reconcile exactly")

    OUT.write_text(json.dumps(res, indent=2))
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
