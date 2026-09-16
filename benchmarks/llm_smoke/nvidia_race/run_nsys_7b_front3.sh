#!/usr/bin/env bash
# run_nsys_7b_front3.sh <suffix> [runs] — kernel-level capture + per-layer decomposition of one
# 7B TC arm, FRONT-3 edition (2026-09-15, the TensorRT-LLM pp1024 / RAG-4096 gap round).
#
# Same capture recipe as the round-2 `fronts_nsys.sh` this front's baseline decomposition came
# from (`--trace=cuda --cuda-graph-trace=node --sample=none --cpuctxsw=none`, clocks read before
# and after, GPU drained first) so the _c8 and FRONT-3 arms are directly comparable, with one
# analyzer fix: round 2's `nsys_analyze.py` isolates the m=1024 prefill window by looking for a
# kernel whose name contains "ropewrt". `-D ALGENTA_7B_PF_BIASROPE` replaces
# `_pf_ropewrt_kernel` with `_pf_biasropewrt_kernel`, which Mojo's 11-character kernel-name
# truncation renders as `..._pf_biasrop...` — no "ropewrt" substring — so the round-2 analyzer
# finds no window and silently reports nothing for exactly the arm the lever ships in. The
# matcher below accepts both spellings.
set -uo pipefail
SUF="${1:?usage: run_nsys_7b_front3.sh <suffix> [runs]}"
RUNS="${2:-1}"
BIN=${BIN:-$HOME/front3/bin/qwen25_7b_p3_graph_cuda${SUF}}
CKPT=${CKPT:-/tmp/w7b/ckpt}
OUTD=${OUTD:-$HOME/trtllm/front3/nsys}
mkdir -p "$OUTD"
ORACLE=$(python3 - <<'PY'
import json
ref = json.load(open("/tmp/w7b/gate/ref_tokens.json"))
print(",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16]))
PY
)
for _ in $(seq 1 300); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && break
    sleep 2
done
echo "clocks_before=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader) $(date -u +%T)"
# PROMPT_IDS=<csv> captures a RAG-4096 (or any long-context) prefill instead of the 256-token
# fixture. The window matcher below keys off the RoPE+KV-write launch grid
# ((h_q+h_kv)*m = 32768 at m=1024), which a chunked 4096-token prefill produces once per
# 1024-row chunk, so the decomposition reports us/chunk/layer with n_exec = chunks x prefills.
EXTRA=()
if [[ -n "${PROMPT_IDS:-}" ]]; then
    EXTRA=(--prompt-ids "$PROMPT_IDS")
    echo "capturing a ${#PROMPT_IDS}-char prompt-id override (long-context window)"
fi
CSV_EXISTING=$(ls -1t "$OUTD"/trace_${SUF}*cuda_gpu_trace.csv 2>/dev/null | head -1)
if [[ "${ANALYZE_ONLY:-0}" == "1" && -n "$CSV_EXISTING" ]]; then
    # re-analyze a capture that already exists — the analyzer is the part that had a bug
    # (it matched the window marker by kernel NAME, which Mojo does not emit for kernels in
    # kernels_prefill_gemma3.mojo), and re-profiling to re-run a CSV parser would be both
    # wasteful and a fresh measurement nobody asked for.
    echo "ANALYZE_ONLY: reusing $CSV_EXISTING (no new capture)"
else
nsys profile --trace=cuda --cuda-graph-trace=node --sample=none --cpuctxsw=none \
    -o "$OUTD/rep_${SUF}" -f true "$BIN" --checkpoint "$CKPT" --arm p3 --oracle "$ORACLE" \
    "${EXTRA[@]+"${EXTRA[@]}"}" \
    --runs "$RUNS" --out "$OUTD/out_${SUF}.txt" > "$OUTD/nsys_${SUF}.log" 2>&1
echo "nsys rc=$?"
echo "clocks_after=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"
grep -E "^prefill|^gen |G0 RESULT|G1 RESULT|STAGED|TC FLAGS|TCFLAG|ARMED|DECLINED" \
    "$OUTD/nsys_${SUF}.log" | head -20
nsys stats --report cuda_gpu_trace --format csv --output "$OUTD/trace_${SUF}" \
    "$OUTD/rep_${SUF}.nsys-rep" > "$OUTD/stats_${SUF}.log" 2>&1
echo "stats rc=$?"
fi
CSV=$(ls -1t "$OUTD"/trace_${SUF}*cuda_gpu_trace.csv 2>/dev/null | head -1)
[[ -n "$CSV" ]] || { echo "NO CSV"; exit 1; }
python3 - "$CSV" "$OUTD/decomp_${SUF}.txt" <<'PY' | tee "$OUTD/decomp_${SUF}.txt"
"""Per-layer decomposition of the m=1024 one-pass prefill window, FRONT-3 matcher."""
import csv, re, sys
from collections import defaultdict
RMS_GRID = 32768      # (h_q + h_kv) * m at m=1024 — the RoPE+KV-write launch
N_LAYERS = 28
path, _out = sys.argv[1], sys.argv[2]

def short(name):
    n = re.sub(r"\s+", " ", name.strip())
    n = re.sub(r"<[^>]*>", "", n)
    return n.split("(")[0][:78]

def ropey(nm):
    # round 2's analyzer matched "ropewrt" only. Two reasons that is not enough here:
    #   * -D ALGENTA_7B_PF_BIASROPE swaps in _pf_biasropewrt_kernel, and
    #   * Mojo mangles kernels in kernels_prefill_gemma3.mojo to
    #     "residentk_kernels_prefill_gemma6A6A_<hash>" — the MODULE name plus a hash, with no
    #     function name at all — so neither "ropewrt" nor "biasrop" appears in the symbol.
    # Kept for the name-based fast path; the grid-based path below is what actually decides.
    low = nm.lower()
    return "ropewrt" in low or "biasrop" in low

rows, header = [], None
with open(path, newline="", errors="replace") as fh:
    for rec in csv.reader(fh):
        if not rec or rec[0].startswith(("**", "NOTICE", "SKIPPED")):
            continue
        if header is None:
            if rec[0].startswith("Start"):
                header = [h.strip() for h in rec]
            continue
        if len(rec) >= len(header):
            rows.append(dict(zip(header, [c.strip() for c in rec])))

def num(rec, *keys):
    for k in keys:
        if rec.get(k) not in (None, "", "N/A"):
            try:
                return float(rec[k])
            except ValueError:
                pass
    return None

ev = []
for rec in rows:
    st, du, gx = num(rec, "Start (ns)", "Start"), num(rec, "Duration (ns)", "Duration"), \
        num(rec, "GrdX", "Grid X", "GridX")
    if st is None or du is None:
        continue
    ev.append((st, du, int(gx) if gx else 0, short(rec.get("Name", "?"))))
print(f"parsed {len(ev)} gpu rows")
# Window marker: the RoPE+KV-write launch, identified by its GRID ((h_q+h_kv)*m = 32768 at
# m=1024) rather than by name, because the name is not recoverable for gemma3-module kernels.
# Exactly one distinct kernel may own that grid, or the window is ambiguous and we refuse to
# guess: printing the owner makes the choice auditable in the artifact.
at_grid = sorted([e for e in ev if e[2] == RMS_GRID], key=lambda e: e[0])
owners = sorted({e[3] for e in at_grid})
rope = [e for e in at_grid if ropey(e[3])]
if rope:
    print(f"window marker by NAME+grid: {sorted({e[3] for e in rope})}")
elif len(owners) == 1:
    rope = at_grid
    print(f"window marker by GRID only (name carries no function symbol): {owners[0]}")
else:
    print(f"grid={RMS_GRID} is owned by {len(owners)} distinct kernels {owners} — the "
          f"m=1024 window is ambiguous, refusing to attribute kernels to a guessed span")
    rope = []
if not rope:
    print(f"no usable grid={RMS_GRID} marker — not an m=1024 one-pass capture?")
    sys.exit(1)
lo, hi = rope[0][0], max(e[0] + e[1] for e in rope)
n_exec = max(1, round(len(rope) / float(N_LAYERS)))
print(f"m=1024 rope+kvwrite rows: {len(rope)} ({len(rope)/n_exec:.0f} per execution = layers),"
      f" prefill executions in span: {n_exec}")
agg = defaultdict(lambda: [0.0, 0])
for st, du, _gx, nm in ev:
    if lo - 1e5 <= st <= hi + 1e5:
        agg[nm][0] += du
        agg[nm][1] += 1
tot = sum(v[0] for v in agg.values())
print(f"\nspan {(hi-lo)/1e6:.2f} ms wall | GPU busy {tot/1e6:.2f} ms ({100*tot/(hi-lo):.1f}%)"
      f" | per execution {tot/n_exec/1e6:.3f} ms")
print(f"{'kernel':<80}{'n':>6}{'total ms':>11}{'ms/exec':>10}{'us/layer':>10}{'%':>7}")
for nm, (du, n) in sorted(agg.items(), key=lambda kv: -kv[1][0])[:34]:
    print(f"{nm:<80}{n:>6}{du/1e6:>11.3f}{du/n_exec/1e6:>10.3f}"
          f"{du/n_exec/N_LAYERS/1e3:>10.2f}{100*du/tot:>7.1f}")

fam = defaultdict(float)
for nm, (du, _n) in agg.items():
    low, key = nm.lower(), nm
    # NOTE: "gemm" is a substring of "gemma". Mojo mangles kernels in
    # kernels_prefill_gemma3.mojo to "residentk_kernels_prefill_gemma6A6A_<hash>", so a naive
    # `"gemm" in low` GEMM bucket silently swallows the SwiGLU epilogue, the masked softmax,
    # the head-major pack/unpack and the rmsnorm twins — round 2's analyzer had exactly this
    # bug and its family table reported cuBLAS GEMM at 93.3%/94.7% of a prefill that is really
    # ~77%. The mangled-Mojo test therefore runs FIRST and the GEMM test is anchored on the
    # cuBLAS/cutlass symbol prefixes, not on a bare substring.
    if "prefill_gemma6a6a" in low or "prefill_f326a6a" in low:
        key = "residentk kernels_prefill_* (Mojo-mangled: module name + hash, no symbol)"
    elif "fa_causal" in low:
        key = "FUSED FLASH ATTENTION (front3)"
    elif "fastexp" in low:
        key = "swiglu epilogue (__expf, front3)"
    elif "biasrop" in low:
        key = "bias+rope+KV write (fused, front3)"
    elif "rmsnorm" in low:
        key = "rmsnorm rows"
    elif "softmax" in low:
        key = "attn softmax (masked)"
    elif "ropewrt" in low:
        key = "rope + KV write"
    elif "swiglu" in low:
        key = "swiglu epilogue"
    elif "f32_to_f16" in low or "f16_to_f32" in low:
        key = "shim f32<->f16 convert (incl. K/V staging)"
    elif "bias" in low:
        key = "qkv bias add"
    elif "embed" in low:
        key = "embed rows gather"
    elif low.startswith(("ampere_", "sm80_", "nvjet", "cutlass", "void cutlass")) or \
            "s16816gemm" in low or "cutlass::kernel" in low:
        key = "cuBLAS/cutlass GEMM (projections)"
    elif "argmax" in low or "lm_head" in low:
        key = "lm_head + argmax"
    fam[key] += du
print(f"\n{'family':<44}{'ms/exec':>10}{'us/layer':>10}{'%':>7}")
for k, du in sorted(fam.items(), key=lambda kv: -kv[1]):
    print(f"{k:<44}{du/n_exec/1e6:>10.3f}{du/n_exec/N_LAYERS/1e3:>10.2f}"
          f"{100*du/tot:>7.1f}")
PY
echo "NSYS3_DONE_${SUF}"
