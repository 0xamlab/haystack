#!/usr/bin/env bash
# run_trtllm_rag_trace7.sh [delay_s] [duration_s] — capture TensorRT-LLM 1.2.1's OWN kernel mix at
# the RAG-4096 shape, in the same session as the race.
#
# WHY THIS ROUND. Every round since the first has compared our per-layer decomposition against
# THEIR pp1024 kernel mix (`~/trtllm/front1/trtllm_kernel_mix.txt`, 12 requests) and scaled it by
# the number of 1024-row chunks. Round 6 stated the consequence plainly: its RAG-4096 side of the
# comparison was "still inferred by scaling round 2's pp1024 kernel mix". That inference is exactly
# the kind of term round 6 itself was burned by — the +9.8% gap between the isolated cublasLt
# timings and the in-situ ones is a shape-and-state effect that no per-chunk extrapolation can see,
# and their engine chunks a 4096-token prompt differently than we do (max_num_tokens 8192, so
# probably not at all). This script replaces the extrapolation with a measurement.
#
# METHOD: round 1's proven recipe (`~/trtllm_nsys.sh`), same image, same serve flags, same
# `serve_config.yaml`, with nsys wrapping `trtllm-serve` INSIDE the container (a host-side nsys
# cannot inject across the container boundary). One change matters: the requests are sent only
# AFTER the profile window has opened, computed from the launch timestamp rather than assumed —
# a window that opens after the requests captures their startup and nothing else, which would
# silently produce a kernel mix for the wrong work.
#
# The GPU is solo: our arms are drained before the container starts and the container is removed
# after, so neither side shares the device (owner's VRAM-hygiene rule).
#
# usage: bash run_trtllm_rag_trace7.sh [delay_s] [duration_s] [cells]
set -uo pipefail
DELAY=${1:-150}
DUR=${2:-150}
CELLS=${3:-rag0}
NAME=trtllm7b_nsys_rag
IMG=nvcr.io/nvidia/tensorrt-llm/release:1.2.1
MEAS=${MEAS:-$HOME/trtllm/front7}
OUT=${OUT:-$MEAS/trtllm_rag4096}
D="docker"; docker ps >/dev/null 2>&1 || D="sudo -n docker"
mkdir -p "$MEAS/nsys"

echo "clocks_before=$(nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader) $(date -u +%T)"
for _ in $(seq 1 300); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && break
    sleep 2
done
$D rm -f $NAME >/dev/null 2>&1 || true
rm -f "${OUT}.nsys-rep"

T0=$(date +%s)
$D run -d --name $NAME --gpus all --ipc=host --network host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -e HF_HOME=/tmp/hf -e TRANSFORMERS_OFFLINE=1 \
  -v $HOME/models/Qwen2.5-7B-Instruct:/model:ro -v $HOME/trtllm:/work \
  $IMG bash -lc "nsys profile -o /work/front7/trtllm_rag4096 -f true --trace=cuda --sample=none \
    --cpuctxsw=none --delay=$DELAY --duration=$DUR \
    trtllm-serve serve /model --backend pytorch --host 0.0.0.0 --port 8000 \
    --max_batch_size 64 --max_seq_len 8192 --max_num_tokens 8192 \
    --extra_llm_api_options /work/serve_config.yaml"
echo "container up rc=$? at $(date -u +%T); nsys window = [${DELAY}s, $((DELAY + DUR))s] after launch"

ready=""
for i in $(seq 1 240); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health || true)
  if [ "$code" = "200" ]; then ready=$(( $(date +%s) - T0 )); break; fi
  sleep 3
done
echo "health ready after ${ready}s at $(date -u +%T)"
[ -z "$ready" ] && { echo NO_HEALTH; $D logs --tail 30 $NAME; $D rm -f $NAME; exit 3; }

# ── do not send a single request before the collection window is open ──
OPEN=$((T0 + DELAY + 5))
NOW=$(date +%s)
if [ "$NOW" -lt "$OPEN" ]; then
    echo "waiting $((OPEN - NOW))s for the nsys window to open before sending requests"
    sleep $((OPEN - NOW))
fi
if [ "$(( $(date +%s) - T0 ))" -gt "$((T0 + DELAY + DUR - 60))" ]; then
    echo "WARN: less than 60s of collection window left; the capture may truncate the requests"
fi
echo "== sending $CELLS inside the window at $(date -u +%T) =="
python3 "$HOME/trtllm_race.py" --out "$MEAS/trtllm_nsys_rag.json" --container $NAME \
    --warmup 2 --runs ${RUNS:-10} --cells "$CELLS" 2>&1 | tail -14
echo "requests done at $(date -u +%T); waiting for nsys to finalize"

for i in $(seq 1 90); do
  [ -f "${OUT}.nsys-rep" ] && break
  sleep 5
done
ls -la "${OUT}.nsys-rep" 2>/dev/null || echo "NO REPORT — the window may not have closed"
$D run --rm -v $HOME/trtllm:/work $IMG bash -lc \
  "nsys stats --report cuda_gpu_kern_sum --format csv --output /work/front7/nsys/trtllm_rag_kernsum \
     /work/front7/trtllm_rag4096.nsys-rep && \
   nsys stats --report cuda_gpu_trace --format csv --output /work/front7/nsys/trtllm_rag_gputrace \
     /work/front7/trtllm_rag4096.nsys-rep" > "$MEAS/trtllm_rag_stats.log" 2>&1
echo "stats rc=$?"; tail -3 "$MEAS/trtllm_rag_stats.log"
$D rm -f $NAME >/dev/null 2>&1 || true
echo "container removed; clocks_now=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"
echo "vram_after=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"

# ── their per-RAG-prefill kernel mix: totals divided by the number of context iterations they
#    actually ran, taken from their own executor iter-log rather than assumed from --runs. ──
python3 - "$MEAS/trtllm_nsys_rag.json" "$MEAS/nsys/trtllm_rag_kernsum_cuda_gpu_kern_sum.csv" <<'PY'
import csv, json, sys
try:
    j = json.load(open(sys.argv[1]))
except Exception as ex:
    print("race json unreadable:", ex); sys.exit(0)
cells = j.get("cells", {})
n_req = 0
for k, v in cells.items():
    srv = v.get("server", {}) if isinstance(v, dict) else {}
    n = srv.get("n") or 0
    n_req += int(n)
    print(f"  cell {k}: n={n} server median {srv.get('median_ms')} ms "
          f"(prompt_tokens {v.get('prompt_tokens') if isinstance(v, dict) else '?'})")
try:
    rows = list(csv.DictReader(open(sys.argv[2])))
except Exception as ex:
    print("kern_sum unreadable:", ex); sys.exit(0)
print(f"\n  == THEIR kernel mix over {len(rows)} distinct kernels, {n_req} RAG-4096 requests ==")
print(f"  {'ms/request':>11} {'us/call':>9} {'insts':>7} {'%':>6}  name")
tot = 0.0
parsed = []
for r in rows:
    name = (r.get("Name") or "").strip()
    try:
        total_ns = float(r.get("Total Time (ns)") or 0)
        inst = int(float(r.get("Instances") or 0))
    except ValueError:
        continue
    tot += total_ns
    parsed.append((total_ns, inst, name))
for total_ns, inst, name in sorted(parsed, reverse=True)[:26]:
    per_req = total_ns / 1e6 / max(n_req, 1)
    per_call = total_ns / max(inst, 1) / 1e3
    print(f"  {per_req:11.3f} {per_call:9.2f} {inst:7d} {100*total_ns/max(tot,1):6.2f}  {name[:88]}")
print(f"  {'-'*11}")
print(f"  {tot/1e6/max(n_req,1):11.3f} ms/request of DEVICE KERNEL TIME across {n_req} requests")
print("  (their server median above is a device STEP time, so the two are comparable only up to")
print("   their own host gap — which is the point of measuring instead of extrapolating)")
PY
echo TRTLLM_RAG_TRACE7_DONE
