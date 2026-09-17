#!/usr/bin/env bash
# run_ab_7b_front7.sh — pinned-clocks interleaved A/B for FRONT 7 (widening the RAG-4096
# 1.0221x margin round 6 won, without regressing pp256 / pp1024 / decode).
#
# The baseline `_h0` is FRONT 6's SHIP ARM `_g2` (PASS4096 + LTALGO on top of round 5's `_f1`),
# REBUILT from this branch — never a remembered number. Every FRONT-7 lever is a build flag that
# defaults OFF, so `_h0` is round 6's adopted arm and must reproduce its published cells
# (RAG-4096 15324.50 tok/s / 267.284 ms, pp256 12880.81, pp1024 15464.19) or the round is not
# comparable to the one it claims to widen.
#
#   _h0  baseline   FRONT 6's ship arm: _g2 == round 5's _f1 + PF_PASS4096 + 7B_PF_LTALGO.
#                   Links the LT-only shim object, which PROOF=1 compares section-for-section
#                   against a build of FRONT 6's own tc_shim.cu (commit da3829ae0) — the FA2
#                   body refactor this round needed for the f16 O twin must be provably neutral
#                   to the object the baseline links, not merely intended to be.
#   _hv  PROOF ARM  _h0 + ALGENTA_7B_PF_O16TWIN + ALGENTA_7B_PF_O16VERIFY. Not raced. FA2's
#                   epilogue writes BOTH the f32 O and the f16 twin, o_proj consumes the twin
#                   exactly as the ship arm does, and every element of every layer is compared
#                   as BITS (`__half_as_ushort`) — 28 x 4096 x 3584 = 411,041,792 per prefill.
#                   The bit-identity claim is discharged here, before any speed claim is made.
#   _h1  LEVER 1    _h0 + ALGENTA_7B_PF_O16TWIN. The f16 O twin: FA2's epilogue writes the
#                   position-major f16 O straight into `tc_a16` and o_proj — the one projection
#                   whose A was still f32 — consumes it directly. Removes 28 launches of
#                   `_f32_to_f16_kernel` (2.344 ms of FRONT 6's 260.967 ms busy, at 1052 GB/s =
#                   68% of roof) AND the 58.7 MB/layer f32 O write that existed only to feed it
#                   (the ship arm passes o_f32 = NULL). BIT-EXACT by FRONT 4's KVTWIN argument
#                   and proven full-element by _hv, so the gates confirm rather than decide it.
#   _h2  LEVER 1+REV _h1 + ALGENTA_7B_PF_FAREV: FA2's row-block dispatch order reversed
#                   (heaviest-CTA-first). Bit-exact by construction, and a RUNTIME argument to
#                   the same kernel, so _h1/_h2 are the same binary and the A/B cannot be
#                   confounded by codegen. FRONT 6's target 5; the counter-argument (an x-major
#                   grid over 64 row-blocks x 28 heads already puts every row-block of ~5 heads
#                   in each ~324-CTA wave, so the causal imbalance may be wave-balanced already)
#                   is what this arm measures rather than argues.
#   _hd  DIAGNOSTIC _h1 + ALGENTA_7B_PF_LTINSITU, run with --lt-insitu/--warmup and NOT raced as
#                   a ship candidate: it rotates the cublasLt candidates in situ (one sample per
#                   layer per prefill), freezes each shape on its best in-situ MEDIAN, and prints
#                   the whole table — isolated stage-time mean beside in-situ median, per
#                   candidate. Its cells are reported as diagnostic only, because the algorithm
#                   it freezes on was chosen AFTER G0/G1 ran (deliberately: the gates must cover
#                   a fixed selection, not a rotating one).
#   _h3  LEVER 3    _hd's binary with ALGENTA_LT_PICK pinning the in-situ winners _hd found, so
#                   the raced arm runs a FIXED algorithm set that G0/G1 cover normally. Built
#                   only if _hd's table differs from FRONT 6's stage-time pick; LT_PICK is a
#                   literal in this script so the arm is reproducible from the recorded log.
#
# PROTOCOL (rounds 2-6's, unchanged): one process per arm per cell; each cell is the driver's own
# median of --runs 20 with rel-IQR and outlier reporting; arms interleaved with the baseline
# bracketing the sweep as drift armor; G0 (greedy tokens vs the fp32 transformers oracle, with
# round 6's --no-eos-stop long-prompt oracles) and G1 (64/64 self-consistency) run inside every
# bench process, so every cell in the sweep is gate-checked by construction.
#
# FRONT 7 ADDITION — CLOCK/POWER AT 200 ms, NOT 1 Hz. FRONT 6 disclosed a ZERO-DRIFT BREACH it
# could not resolve: 203/4814 off-pin samples at 1 Hz, min 1230 MHz, inside 14 cell windows,
# attributed to the 400 W cap against draws to 532.9 W. A 267 ms cell is shorter than a 1 Hz
# sample interval, so that data could say nothing about WHICH cells were affected or by how much.
# This round samples clocks.sm + power.draw + temperature every 200 ms for the whole stage and
# prints `CELL_WINDOW <arm><tag> <t0> <t1>` per cell, so front7_clocks.py can attribute off-pin
# time to individual cells and bound it against the claimed margin.
#
# VRAM HYGIENE (owner rule): every arm is its own short-lived process — nothing is left resident
# between stages, and the GPU is drained to 0 MiB before the next arm is launched.
#
# Usage (on algenta-ent-a100, from the repo root):
#   bash run_ab_7b_front7.sh                       # proof + build every arm + the sweep
#   STAGE=1 PROOF=1 BUILD_ARMS=1 RUN_SWEEP=0 RUN_RAG=0 bash run_ab_7b_front7.sh
#   RUN_VERIFY=1 BUILD_ARMS=0 bash run_ab_7b_front7.sh          # the _hv bit-identity proof
#   RUN_DIAG=1 DIAG_PROMPT=0 bash run_ab_7b_front7.sh           # the in-situ algorithm table
#   BUILD_ONLY="_h1" BUILD_ARMS=1 RUN_SWEEP=0 RUN_RAG=0 bash run_ab_7b_front7.sh
set -uo pipefail
SRC=benchmarks/llm_smoke/nvidia_race/qwen25_7b_p3_graph_cuda.mojo
SHIM=benchmarks/llm_smoke/nvidia_race/tc_shim.cu
RTK=benchmarks/llm_smoke/nvidia_race/tc_rt_kernels.cu
NV=${NV:-$HOME/front7/bin}
CKPT=${CKPT:-/tmp/w7b/ckpt}
MEAS=${MEAS:-$HOME/trtllm/front7}
RUNS=${RUNS:-20}
SM=${SM:-sm_80}
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/w7b/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
STAGE=${STAGE:-1}
TC_OBJ_R6=${TC_OBJ_R6:-/tmp/front7_shim_r6_${SM}.o}      # FRONT 6's source, LT only
TC_OBJ_LT=${TC_OBJ_LT:-/tmp/front7_shim_lt_${SM}.o}      # this source, LT only  -> _h0
TC_OBJ_O16=${TC_OBJ_O16:-/tmp/front7_shim_o16_${SM}.o}   # + O16                 -> _hv _h1 _h2
TC_OBJ_INS=${TC_OBJ_INS:-/tmp/front7_shim_ins_${SM}.o}   # + O16 + LTINSITU      -> _hd _h3
PTXD=${PTXD:-/tmp/front7_ptxd_${SM}}
# FRONT 6's source, for the shim-neutrality proof. `8fe9a7e7b` is the SQUASH MERGE of PR #1000
# and is in main's history, so a fresh clone can resolve it; da3829ae0 (its pre-merge branch tip)
# carries a byte-identical tc_shim.cu — both md5 901a895f146208bbd04938a7d88491ed, checked, not
# assumed. Rebase note: a branch based on a squash-merged PR still shows that PR's commits, and
# `git rebase origin/main` then tries to REPLAY them into conflicts; `git rebase --onto
# origin/main <pre-merge-tip>` replays only this round's commits and applies clean.
R6_SHA=${R6_SHA:-8fe9a7e7b}
# ALGENTA_LT_PICK: set from _hd's printed in-situ table (format "NxK:idx;NxK:idx"). Empty means
# "no override": _h3 then races _hd's binary on FRONT 6's stage-time pick, which is a valid but
# uninteresting arm — the harness says so rather than pretending it is the searched set.
export ALGENTA_LT_PICK=${ALGENTA_LT_PICK:-}
# round 2's base + rounds 3/4/5's levers + round 6's two = FRONT 7's `_h0`
BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_18944 -D ALGENTA_PF_ONEPASS_B1 \
-D ALGENTA_PF_ATTN_FLASH_B1 -D ALGENTA_PF_ATTN_FLASH2_B1 -D ALGENTA_TC_NOSEAM \
-D ALGENTA_7B_PF_TCATTN -D ALGENTA_TC_SHIM -D ALGENTA_7B_PF_SM1P \
-D ALGENTA_7B_PF_F16NORM -D ALGENTA_7B_PF_F16MLP -D ALGENTA_7B_CTX8192 \
-D ALGENTA_7B_PF_FA -D ALGENTA_7B_PF_FASTEXP -D ALGENTA_7B_PF_BIASROPE"
G0="-D ALGENTA_7B_PF_KVTWIN -D ALGENTA_7B_PF_FA2 -D ALGENTA_7B_PF_ROPEVEC"
G1="-D ALGENTA_PF_PASS4096"
G2="-D ALGENTA_7B_PF_LTALGO"

mkdir -p "$NV" "$MEAS" "$PTXD" "$MEAS/nsys"

# The oracle is regenerated per boot (/tmp is wiped on this image). A missing ref_tokens.json
# must not turn every cell into a silent G0-skip: say so loudly and let G1 still run.
REF=/tmp/w7b/gate/ref_tokens.json
RAGREF=${RAGREF:-/tmp/w7b/gate/ref_tokens_rag.json}
ORACLE=""
if [ -f "$REF" ]; then
    ORACLE=$(python3 - "$REF" <<'PY'
import json, sys
ref = json.load(open(sys.argv[1]))
print(",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16]))
PY
)
else
    echo "WARN: $REF missing -- G0 will NOT run in these cells (G1 still does). Regenerate with ~/a2a/run_oracle.sh"
fi

build_shim() { # out_obj source_file [extra nvcc -D ...]
    local out="$1" src="$2"; shift 2
    # the shim #includes the embedded-PTX header build_tc_drivers.sh's recipe generates
    if [[ ! -f "$PTXD/tc_rt_ptx.h" ]]; then
        "$CUDA_HOME/bin/nvcc" -ptx -arch=compute_80 "$RTK" -o "$PTXD/tc_rt_kernels.ptx" || return 1
        python3 - "$PTXD/tc_rt_kernels.ptx" "$PTXD/tc_rt_ptx.h" <<'PY' || return 1
import sys
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
chunks = []
for i in range(0, len(data), 24):
    chunks.append(",".join(str(b) for b in data[i:i + 24]))
with open(dst, "w") as out:
    out.write("/* generated by run_ab_7b_front7.sh - embedded PTX */\n")
    out.write("static const unsigned char g_tc_rt_ptx[] = {\n")
    out.write(",\n".join(chunks))
    out.write(",0};\n")
PY
    fi
    echo "== nvcc $(basename "$(dirname "$src")")/$(basename "$src") ${*:-(stock)} -> $out"
    rm -f "$out"
    "$CUDA_HOME/bin/nvcc" -O3 -arch="$SM" -Xcompiler -fPIC -I"$PTXD" -Xptxas -v "$@" \
        -c "$src" -o "$out" 2>&1 \
        | grep -E "error|_fa2_causal_kernel|_fa2_causal_o16_kernel|registers|spill" \
        | head -80
    [[ -f "$out" ]] || { echo "SHIM BUILD FAIL $out"; return 1; }
}

build_arm() { # suffix shim_obj link_extra_flags -- extra-flags...
    local suf="$1" obj="$2" lflags="$3"; shift 3
    # shellcheck disable=SC2086
    "$MOJO" build $BASE "$@" --target-accelerator "$SM" -I mojo/engine -I attention_forge \
        "$SRC" -o "$NV/qwen25_7b_p3_graph_cuda${suf}" \
        -Xlinker "$obj" -Xlinker -lcublas $lflags -Xlinker -lcudart \
        -Xlinker "-L$CUDA_HOME/lib64" \
        > "$MEAS/build_${suf}.log" 2>&1 \
        && echo "BUILD_OK $suf ($(basename "$obj"))" \
        || { echo "BUILD_FAIL $suf (tail):"; tail -25 "$MEAS/build_${suf}.log"; return 1; }
}

# ── PROOF: the object `_h0` links is identical to a build of FRONT 6's own source ──
# FRONT 6 proved its baseline carried none of its lever by comparing `.text`/`.rodata`/`.data`/
# `.bss` and the DEFINED symbol table, after learning that a whole-file md5 is the wrong test
# (an ELF object embeds its source path in an STT_FILE symbol, so two builds of identical code
# from different directories differ). The same trap applies one level down: the device code lives
# in `.nv_fatbin`, whose PTX carries a `.file` directive naming the source, so BOTH sources are
# copied to one neutral path and compiled from there. That makes `.nv_fatbin` comparable too —
# and it is the section that actually holds `_fa2_causal_kernel`, which is the point:
#
# FRONT 7 refactored that kernel's body into a `static __device__ __forceinline__` template so the
# f16-O twin could be a second wrapper over the same body instead of a 250-line copy that could
# drift. If the refactor moved one byte of the object the BASELINE links, `_h0` is not FRONT 6's
# arm and every ratio below is against something else. FRONT 5 was burned by exactly this class of
# change — adding a defaulted `MINB` template parameter to `__launch_bounds__` moved the same
# instantiation from 155 to 171 registers and cost +9.8% on the RAG-4096 FA block.
PROOF_DIR=${PROOF_DIR:-/tmp/front7_proof}
CHECK_O16=benchmarks/llm_smoke/nvidia_race/check_o16_copy.py
proof_shim_neutral() {
    local r6src="$PROOF_DIR/r6_tc_shim.cu"
    mkdir -p "$PROOF_DIR"
    # The twin is a COPY of the shipped kernel, because the shared-body refactor this lever first
    # tried was REJECTED by this very proof (it moved the SASS of all seven instantiations while
    # every host section stayed identical). A copy can drift, so drift is a checked invariant:
    # re-derive the twin from the shipped kernel and require character equality.
    if [[ -f "$CHECK_O16" ]]; then
        python3 "$CHECK_O16" "$SHIM" \
            || { echo "O16_COPY_DRIFT: FAILED -- refusing to build arms from a drifted twin"; return 3; }
    fi
    if [[ ! -f "$r6src" ]]; then
        if git cat-file -e "${R6_SHA}:benchmarks/llm_smoke/nvidia_race/tc_shim.cu" 2>/dev/null; then
            git show "${R6_SHA}:benchmarks/llm_smoke/nvidia_race/tc_shim.cu" > "$r6src" \
                && echo "== extracted FRONT 6 tc_shim.cu from ${R6_SHA:0:9}"
        elif [[ -f "$HOME/front6/repo/benchmarks/llm_smoke/nvidia_race/tc_shim.cu" ]]; then
            cp "$HOME/front6/repo/benchmarks/llm_smoke/nvidia_race/tc_shim.cu" "$r6src" \
                && echo "== copied FRONT 6 tc_shim.cu from ~/front6/repo"
        else
            echo "PROOF_UNAVAILABLE: neither ${R6_SHA:0:9} nor ~/front6/repo has FRONT 6's source"
            return 2
        fi
    fi
    # both compiled from the SAME path under the SAME name, so the embedded `.file` directive and
    # the STT_FILE symbol cannot be what differs.
    cp "$SHIM" "$PROOF_DIR/tc_shim.cu"
    build_shim "$TC_OBJ_LT" "$PROOF_DIR/tc_shim.cu" -D ALGENTA_TC_SHIM_LT || return 1
    cp "$r6src" "$PROOF_DIR/tc_shim.cu"
    build_shim "$TC_OBJ_R6" "$PROOF_DIR/tc_shim.cu" -D ALGENTA_TC_SHIM_LT || return 1
    cp "$SHIM" "$PROOF_DIR/tc_shim.cu"     # leave the neutral dir holding this round's source
    python3 - "$TC_OBJ_R6" "$TC_OBJ_LT" <<'PY'
"""Section + defined-symbol comparison of two ELF objects (FRONT 6's recipe, plus .nv_fatbin)."""
import hashlib, subprocess, sys

SECS = (".text", ".rodata", ".data", ".bss", ".nv_fatbin", ".nvFatBinSegment")

def sections(path):
    out = {}
    txt = subprocess.run(["readelf", "-S", "-W", path], capture_output=True, text=True).stdout
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0].startswith("[") and parts[0].endswith("]"):
            if parts[1] in SECS:
                out[parts[1]] = (parts[4], parts[5])       # offset, size
    data = open(path, "rb").read()
    return {n: (int(s, 16), hashlib.md5(data[int(o, 16):int(o, 16) + int(s, 16)]).hexdigest()
                if int(s, 16) else "-") for n, (o, s) in out.items()}

def symbols(path):
    txt = subprocess.run(["nm", "--defined-only", "-S", path], capture_output=True, text=True).stdout
    return sorted(l.split()[1:] for l in txt.splitlines() if len(l.split()) >= 3)

a, b = sys.argv[1], sys.argv[2]
sa, sb = sections(a), sections(b)
ta, tb = symbols(a), symbols(b)
print("PROOF sections (r6 = FRONT 6's source, f7 = FRONT 7's with the O16/LTINSITU macros off):")
bad = []
for k in sorted(set(sa) | set(sb)):
    va, vb = sa.get(k), sb.get(k)
    same = va == vb
    if not same:
        bad.append(k)
    print(f"  {k:20s} r6={va} f7={vb} {'SAME' if same else 'DIFFERS'}")
print(f"PROOF defined symbols: r6={len(ta)} f7={len(tb)} "
      f"{'IDENTICAL' if ta == tb else 'DIFFER'}")
if ta != tb:
    print("  only in r6:", [s for s in ta if s not in tb][:10])
    print("  only in f7:", [s for s in tb if s not in ta][:10])
    bad.append("symbols")
print("PROOF_SHIM_NEUTRAL", "PASS" if not bad else f"FAIL ({', '.join(bad)})")
sys.exit(0 if not bad else 1)
PY
    local rc=$?
    # The per-kernel SASS diff: the decisive check that `_fa2_causal_kernel` itself did not move,
    # independent of anything else in the fatbin.
    for o in "$TC_OBJ_R6" "$TC_OBJ_LT"; do
        "$CUDA_HOME/bin/cuobjdump" -sass "$o" 2>/dev/null \
            > "$MEAS/sass_$(basename "$o" .o).txt" || true
    done
    if [[ -s "$MEAS/sass_$(basename "$TC_OBJ_R6" .o).txt" ]]; then
        python3 - "$MEAS/sass_$(basename "$TC_OBJ_R6" .o).txt" \
                  "$MEAS/sass_$(basename "$TC_OBJ_LT" .o).txt" <<'PY'
"""Per-kernel SASS digest: proves the FA2 refactor left every shipped kernel's machine code alone."""
import hashlib, re, sys

def kernels(path):
    out, name, body = {}, None, []
    for line in open(path, errors="replace"):
        m = re.search(r"Function : (.+)$", line)
        if m:
            if name:
                out[name] = hashlib.md5("\n".join(body).encode()).hexdigest()
            name, body = m.group(1).strip(), []
        elif name and re.match(r"\s+/\*[0-9a-f]+\*/", line):
            body.append(line.split("*/", 1)[-1].strip())
    if name:
        out[name] = hashlib.md5("\n".join(body).encode()).hexdigest()
    return out

a, b = kernels(sys.argv[1]), kernels(sys.argv[2])
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
print(f"SASS kernels: r6={len(a)} f7={len(b)} differing={len(diff)}")
for k in diff[:12]:
    print("  DIFFERS:", k, a.get(k), b.get(k))
fa2 = [k for k in a if "_fa2_causal_kernel" in k]
print("SASS_FA2_NEUTRAL",
      "PASS" if fa2 and all(a[k] == b.get(k) for k in fa2) else "FAIL",
      f"({len(fa2)} _fa2_causal_kernel instantiations compared)")
PY
    fi
    [[ $rc -eq 0 ]] && echo "SHIM_NEUTRALITY: the LT-only object built from FRONT 7's source is" \
        "section- and symbol-identical to one built from FRONT 6's -- _h0 links FRONT 6's code" \
        || echo "SHIM_NEUTRALITY: FAILED -- _h0 is NOT FRONT 6's arm; do not race it as such"
    return $rc
}

wait_gpu_idle() {
    for _ in $(seq 1 300); do
        [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
        sleep 2
    done
    return 1
}

# One 200 ms clock/power/temperature sampler for the whole stage. Started here rather than per
# cell because a per-cell sampler loses the interval that spans a cell boundary — the exact
# blind spot that made FRONT 6's 1 Hz data unable to say which cells were throttled.
CLOCK_CSV="$MEAS/clocks_stage${STAGE}_200ms.csv"
start_clocks() {
    mkdir -p "$(dirname "$CLOCK_CSV")"
    nvidia-smi --query-gpu=timestamp,clocks.sm,power.draw,temperature.gpu,utilization.gpu \
        --format=csv -lms 200 > "$CLOCK_CSV" 2>&1 &
    CLOCK_PID=$!
    # The redirect is set up by the forked child, so a stage with nothing in it can reach
    # stop_clocks before the file exists and `wc -l <` then fails on a path that is about to be
    # valid. Wait for the first sample instead of assuming the fork won the race.
    for _ in $(seq 1 50); do [[ -s "$CLOCK_CSV" ]] && break; sleep 0.1; done
    echo "CLOCKS: sampling at 200 ms -> $CLOCK_CSV (pid $CLOCK_PID, $(wc -l < "$CLOCK_CSV" 2>/dev/null || echo 0) lines at start)"
}
stop_clocks() {
    [[ -n "${CLOCK_PID:-}" ]] && kill "$CLOCK_PID" 2>/dev/null
    wait "$CLOCK_PID" 2>/dev/null
    echo "CLOCKS: stopped, $(wc -l < "$CLOCK_CSV" 2>/dev/null || echo 0) samples in $CLOCK_CSV"
}

run_arm() { # suffix [extra driver args...]
    local suf="$1"; shift
    wait_gpu_idle || echo "WARN: gpu not idle before $suf"
    local c0 c1 p0 t0 t1
    c0=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
    p0=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader)
    t0=$(date +%s.%N)
    "$NV/qwen25_7b_p3_graph_cuda${suf}" --checkpoint "$CKPT" --arm p3 "$@" \
        > "$MEAS/bench_${suf}$EXTRA_TAG.log" 2>&1
    local rc=$?
    t1=$(date +%s.%N)
    c1=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
    local mused
    mused=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)
    # CELL_WINDOW is what front7_clocks.py attributes off-pin samples with: epoch seconds with
    # nanosecond resolution, bracketing this cell and nothing else.
    echo "CELL_WINDOW ${suf}${EXTRA_TAG} ${t0} ${t1}"
    echo "== ${suf}${EXTRA_TAG} rc=$rc wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.1f", b-a}')s clocks=${c0}->${c1} power_at_start=${p0} vram_after=${mused}"
    grep -E "^prefill|^gen |G0 RESULT|G1 RESULT|O16 VERIFY RESULT|STAGED|TC FLAGS|TCFLAG|ARMED|DECLINED|LT INSITU: (FROZEN|PARTIAL|shape)|TC O16 VERIFY|TC LT INSITU: shape" \
        "$MEAS/bench_${suf}${EXTRA_TAG}.log" | head -60
}

want_arm() { case " ${BUILD_ONLY:-_h0 _hv _h1 _h2 _hd} " in *" $1 "*) return 0;; esac; return 1; }

if [ "${PROOF:-1}" = "1" ]; then
    build_shim "$TC_OBJ_LT" "$SHIM" -D ALGENTA_TC_SHIM_LT || exit 1
    proof_shim_neutral || echo "WARN: shim neutrality proof did not pass (rc=$?)"
fi

if [ "${BUILD_ARMS:-1}" = "1" ]; then
    # shellcheck disable=SC2086
    [[ -f "$TC_OBJ_LT" ]] || build_shim "$TC_OBJ_LT" "$SHIM" -D ALGENTA_TC_SHIM_LT || exit 1
    # The O16 object is what _hv, _h1 AND _h2 all link, and the INS object is what _hd and any
    # ALGENTA_LT_PICK arm link. The first version of this guarded each object on ONE arm (`want_arm
    # _hv`), so `BUILD_ONLY="_h0 _h1"` skipped the O16 object and _h1 failed at LINK with a bare
    # "ld returned 1 exit status" -- a missing shim object, reported as a link error. Guard on every
    # arm that links the object.
    # shellcheck disable=SC2086
    if want_arm _hv || want_arm _h1 || want_arm _h2; then
        build_shim "$TC_OBJ_O16" "$SHIM" -D ALGENTA_TC_SHIM_LT -D ALGENTA_TC_SHIM_O16 || exit 1
    fi
    # shellcheck disable=SC2086
    if want_arm _hd || want_arm _h3; then
        build_shim "$TC_OBJ_INS" "$SHIM" -D ALGENTA_TC_SHIM_LT -D ALGENTA_TC_SHIM_O16 \
            -D ALGENTA_TC_SHIM_LTINSITU || exit 1
    fi
    LT_LINK="-Xlinker -lcublasLt"
    # shellcheck disable=SC2086
    want_arm _h0 && build_arm _h0 "$TC_OBJ_LT" "$LT_LINK" $G0 $G1 $G2
    # shellcheck disable=SC2086
    want_arm _hv && build_arm _hv "$TC_OBJ_O16" "$LT_LINK" $G0 $G1 $G2 \
        -D ALGENTA_7B_PF_O16TWIN -D ALGENTA_7B_PF_O16VERIFY
    # shellcheck disable=SC2086
    want_arm _h1 && build_arm _h1 "$TC_OBJ_O16" "$LT_LINK" $G0 $G1 $G2 \
        -D ALGENTA_7B_PF_O16TWIN
    # shellcheck disable=SC2086
    want_arm _h2 && build_arm _h2 "$TC_OBJ_O16" "$LT_LINK" $G0 $G1 $G2 \
        -D ALGENTA_7B_PF_O16TWIN -D ALGENTA_7B_PF_FAREV
    # shellcheck disable=SC2086
    want_arm _hd && build_arm _hd "$TC_OBJ_INS" "$LT_LINK" $G0 $G1 $G2 \
        -D ALGENTA_7B_PF_O16TWIN -D ALGENTA_7B_PF_LTINSITU
fi

start_clocks

# ── the bit-identity proof, BEFORE any speed claim (owner's standing order) ──
if [ "${RUN_VERIFY:-0}" = "1" ]; then
    EXTRA_TAG="_verify_${ROUND:-$(date -u +%H%M%S)}"
    VORACLE=()
    [ -n "$ORACLE" ] && VORACLE=(--oracle "$ORACLE")
    run_arm _hv --warmup 1 --runs 1 "${VORACLE[@]}" --out "$MEAS/verify_hv.txt"
    IDS0=$(python3 - <<'PY'
import json
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][0]["ids"]))
PY
    )
    RORACLE0=""
    [[ -f "$RAGREF" ]] && RORACLE0=$(python3 - "$RAGREF" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get("rag_0")
print(",".join(str(int(t)) for t in c["generated_ids"][:16]) if c else "")
PY
)
    EXTRA_TAG="_verify_rag0_${ROUND:-$(date -u +%H%M%S)}"
    # The proof that matters: at m=4096, where the twin is live. 411,041,792 elements per prefill.
    if [[ -n "$RORACLE0" ]]; then
        run_arm _hv --prompt-ids "$IDS0" --oracle "$RORACLE0" --warmup 1 --runs 1 \
            --out "$MEAS/verify_hv_rag0.txt"
    else
        echo "WARN: no rag_0 oracle -- running the m=4096 verify WITHOUT G0 (G1 still runs)"
        run_arm _hv --prompt-ids "$IDS0" --warmup 1 --runs 1 --out "$MEAS/verify_hv_rag0.txt"
    fi
fi

# ── the in-situ algorithm search: the table is the deliverable either way ──
if [ "${RUN_DIAG:-0}" = "1" ]; then
    DP=${DIAG_PROMPT:-0}
    IDS=$(python3 - "$DP" <<'PY'
import json, sys
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][int(sys.argv[1])]["ids"]))
PY
    )
    RORACLE=""
    if [[ -f "$RAGREF" ]]; then
        RORACLE=$(python3 - "$RAGREF" "$DP" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get(f"rag_{sys.argv[2]}")
print(",".join(str(int(t)) for t in c["generated_ids"][:16]) if c else "")
PY
        )
    fi
    EXTRA_TAG="_diag_rag${DP}_${ROUND:-$(date -u +%H%M%S)}"
    # --warmup 6 gives 6 x 28 = 168 samples per shape over ~16 candidates = ~10 medians each,
    # which is what makes a median-of-10 comparison of candidates meaningful at rel-IQR <= 1%.
    if [[ -n "$RORACLE" ]]; then
        run_arm _hd --prompt-ids "$IDS" --oracle "$RORACLE" --warmup 6 --runs "${DIAG_RUNS:-5}" \
            --lt-insitu "${LT_SAMPLES:-10}" --out "$MEAS/diag_rag${DP}_hd.txt"
    else
        run_arm _hd --prompt-ids "$IDS" --warmup 6 --runs "${DIAG_RUNS:-5}" \
            --lt-insitu "${LT_SAMPLES:-10}" --out "$MEAS/diag_rag${DP}_hd.txt"
    fi
    cp "$MEAS/bench_hd${EXTRA_TAG}.log" "$MEAS/insitu_table_rag${DP}.log" 2>/dev/null || true
    echo "DIAG: in-situ table copied to $MEAS/insitu_table_rag${DP}.log"
fi

# ── the interleaved pp256/pp1024/decode sweep, baseline first and last (drift armor) ──
if [ "${RUN_SWEEP:-1}" = "1" ]; then
  for suf in ${ARMS:-_h0 _h1 _h2 _h0}; do
    EXTRA_TAG="_ra${ROUND:-$(date -u +%H%M%S)}"
    ORACLE_ARG=()
    [ -n "$ORACLE" ] && ORACLE_ARG=(--oracle "$ORACLE")
    run_arm "$suf" "${ORACLE_ARG[@]}" --runs "$RUNS" \
        --out "$MEAS/bench_${suf}${EXTRA_TAG}.txt"
  done
fi

# ── RAG-4096: the margin this round exists to widen. The three token-exact 4096-token prompts,
#    each with its own --no-eos-stop oracle (round 6's fix), so every cell carries a real G0. ──
if [ "${RUN_RAG:-0}" = "1" ]; then
  for suf in ${RAG_ARMS:-_h0 _h1 _h2}; do
    for i in ${RAG_PROMPTS:-0 1 2}; do
      IDS=$(python3 - "$i" <<'PY'
import json, sys
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][int(sys.argv[1])]["ids"]))
PY
      )
      RORACLE=""
      if [ -f "$RAGREF" ]; then
        RORACLE=$(python3 - "$RAGREF" "$i" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get(f"rag_{sys.argv[2]}")
print(",".join(str(int(t)) for t in c["generated_ids"][:16]) if c else "")
PY
        )
      fi
      EXTRA_TAG="_rag${i}_${ROUND:-$(date -u +%H%M%S)}"
      if [ -n "$RORACLE" ]; then
        run_arm "$suf" --prompt-ids "$IDS" --oracle "$RORACLE" --runs "$RUNS" \
            --out "$MEAS/rag${i}_${suf}.txt"
      else
        echo "WARN: $RAGREF has no rag_${i} case -- this cell carries G1 ONLY (no oracle gate)"
        run_arm "$suf" --prompt-ids "$IDS" --runs "$RUNS" --out "$MEAS/rag${i}_${suf}.txt"
      fi
    done
  done
fi

stop_clocks
echo "AB_FRONT7_DONE stage=$STAGE clocks=$CLOCK_CSV"
