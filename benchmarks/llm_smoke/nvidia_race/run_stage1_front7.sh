#!/usr/bin/env bash
# run_stage1_front7.sh — FRONT 7 stage 1: the PROOFS and the DIAGNOSTIC, before any raced cell.
#
# Order is the owner's standing rule: bit-identity proven FULL-ELEMENT before any speed claim.
#   1. `_hv` on the 256-token fixture      — the verify machinery + G0/G1 at a short m
#   2. `_hv` on RAG prompt 0 (m=4096)      — the 411,041,792-element proof where the lever lives
#   3. `_h0` on RAG prompt 0 with the 16-token --no-eos-stop oracle — is the STRONGER gate valid?
#      Round 6 shipped a 5-token RAG oracle (the reference stops at EOS) because post-EOS
#      continuation is undefined for a chat model. If the baseline reproduces the reference's 16
#      tokens, every arm can be gated on 16 instead of 5; if it diverges at token 6, that is
#      recorded as the reason the gate stops where it does, and the 5-token gate stands.
#   4. `_hd` on RAG prompt 0               — the in-situ cublasLt table (diagnostic, not raced)
#   5. the ptxas register counts of the twin vs the shipped FA2 kernel, because FRONT 5 lost 9.8%
#      of the RAG FA block to a codegen move that took one instantiation from 155 to 171
#      registers and dropped it from 3 CTAs/SM to 2. A twin that does not fit at 3 CTAs/SM is not
#      a win whatever the convert pass cost.
set -uo pipefail
cd "$HOME/front7/repo" || exit 1
MEAS=${MEAS:-$HOME/trtllm/front7}
AB=benchmarks/llm_smoke/nvidia_race/run_ab_7b_front7.sh
export ROUND=s1

echo "############ 0. GPU state ############"
nvidia-smi --query-gpu=clocks.sm,power.limit,temperature.gpu,memory.used --format=csv,noheader
nvidia-smi --query-compute-apps=pid --format=csv,noheader | head -3

echo "############ 5-first. FA2 register counts (twin vs shipped) ############"
python3 - "$MEAS"/build_*.log "$MEAS"/build*.log <<'PY'
"""Pair each `Compiling entry function` line with the register count that follows it."""
import glob, re, sys
seen = {}
for p in sorted(set(sum((glob.glob(a) for a in sys.argv[1:]), []))):
    pend = None
    for line in open(p, errors="replace"):
        m = re.search(r"Compiling entry function '([^']+)'", line)
        if m:
            pend = m.group(1)
            continue
        m = re.search(r"Used (\d+) registers", line)
        if m and pend:
            seen.setdefault(pend, set()).add(int(m.group(1)))
            pend = None
for k in sorted(seen):
    if "fa2_causal" in k or "fa_causal" in k or "swiglu" in k or "f32_to_f16" in k:
        print(f"  {k[:96]:96s} registers={sorted(seen[k])}")
shipped = {k: v for k, v in seen.items() if "_fa2_causal_kernel" in k}
twin = {k: v for k, v in seen.items() if "_fa2_causal_o16_kernel" in k}
print(f"  shipped FA2 instantiations: {len(shipped)}   twin instantiations: {len(twin)}")
if shipped and twin:
    lo_s = min(min(v) for v in shipped.values())
    lo_t = min(min(v) for v in twin.values())
    hi_s = max(max(v) for v in shipped.values())
    hi_t = max(max(v) for v in twin.values())
    print(f"  register range shipped {lo_s}-{hi_s}  twin {lo_t}-{hi_t} -> "
          f"{'OCCUPANCY NEUTRAL' if hi_t <= hi_s else 'TWIN USES MORE REGISTERS: check CTAs/SM'}")
PY

echo "############ 1+2. the bit-identity proof (_hv) ############"
PROOF=0 BUILD_ARMS=0 RUN_SWEEP=0 RUN_RAG=0 RUN_DIAG=0 RUN_VERIFY=1 STAGE=1 bash "$AB" \
    2>&1 | tee "$MEAS/stage1_verify.log" | grep -E "O16 VERIFY|TC O16 VERIFY|G0 RESULT|G1 RESULT|^==|CELL_WINDOW|DECLINED|WARN"

echo "############ 3. is the stronger 16-token post-EOS gate valid on the BASELINE? ############"
IDS0=$(python3 -c "
import json;p=json.load(open('/home/angel/trtllm/prompts.json'))
print(','.join(str(int(t)) for t in p['rag'][0]['ids']))")
NOEOS=$(python3 -c "
import json;d=json.load(open('/tmp/w7b/gate/ref_tokens_rag_noeos.json'))
print(','.join(str(int(t)) for t in d['rag_0']['generated_ids'][:16]))")
EOS5=$(python3 -c "
import json;d=json.load(open('/tmp/w7b/gate/ref_tokens_rag.json'))
print(','.join(str(int(t)) for t in d['rag_0']['generated_ids'][:16]))")
echo "  oracle(EOS-stopped, round 6's shipped form): $EOS5"
echo "  oracle(--no-eos-stop, 16 tokens)           : $NOEOS"
"$HOME/front7/bin/qwen25_7b_p3_graph_cuda_h0" --checkpoint /tmp/w7b/ckpt --arm p3 \
    --prompt-ids "$IDS0" --oracle "$NOEOS" --warmup 1 --runs 3 \
    --out "$MEAS/h0_noeos_gate.txt" > "$MEAS/stage1_h0_noeos.log" 2>&1
echo "  rc=$?"
grep -E "G0 RESULT|G1 RESULT|^prefill" "$MEAS/stage1_h0_noeos.log" | head -6
echo "  (a FAIL here on the UNTOUCHED baseline means the post-EOS continuation diverges between"
echo "   the CPU fp32 reference and the f16 CUDA engine, which is why round 6's gate stops at EOS;"
echo "   it is a gate property, not an engine defect — and it is recorded, not hidden)"

echo "############ 4. the in-situ cublasLt table (_hd, diagnostic) ############"
PROOF=0 BUILD_ARMS=0 RUN_SWEEP=0 RUN_RAG=0 RUN_VERIFY=0 RUN_DIAG=1 DIAG_PROMPT=0 \
    LT_SAMPLES=${LT_SAMPLES:-10} DIAG_RUNS=${DIAG_RUNS:-5} STAGE=1 bash "$AB" \
    2>&1 | tee "$MEAS/stage1_diag.log" | grep -E "TC LT INSITU|LT INSITU|TC LT:|G0 RESULT|G1 RESULT|^==|^prefill|DECLINED|WARN" | head -120

echo "############ stage 1 done ############"
nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader
ls -la "$MEAS" | tail -12
echo STAGE1_FRONT7_DONE
