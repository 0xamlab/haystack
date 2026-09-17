#!/bin/bash
# retake_r2.sh — mission protocol: ZERO off-pin tolerance. r6_R6_base_rag4096_r2 logged 1/109
# samples at 1380 MHz during bracket 1; re-take the cell (same label, same args) after chain6d
# finishes, verify offpin=0, then the summarizer re-pools the 14-run rag4096 median with the
# clean cell. Runs ONLY when the GPU is idle (chain6d done).
set -uo pipefail
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race || exit 1
export BIN_DIR=$HOME/lever6 MEAS=$HOME/lever6 CW_LOGFILE=$HOME/lever6/retake.log
export CUDA_VISIBLE_DEVICES=1
export MODULAR_HOME=${MODULAR_HOME:-$HOME/algenta/mojo_env/.pixi/envs/default/share/max}
# shellcheck disable=SC1091
source "$HOME/lever3/cell_watchdog.sh"
cw_init "$HOME/lever6/runs" "$HOME/lever6/logs" "$HOME/lever6/clocks" 1
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
sleep 20
cw_cell "r6_R6_base_rag4096_r2" "$HOME/lever6/R6_base" /mnt/ramblob/g3conv27b \
  --tokens-file /tmp/g3rag/rag4096.txt --max-new 256 --f16 --prefill
echo "--- retake verdict ---"
tail -2 "$CW_LOGFILE"
python3 - <<'PY'
import json
for line in reversed(open("/home/angel/lever6/runs/r6_R6_base_rag4096_r2.out", errors="replace").read().splitlines()):
    line = line.strip()
    if line.startswith("{") and '"generated"' in line:
        print("RETAKE ttft_ms =", json.loads(line)["ttft_ms"]); break
off = sum(1 for l in open("/home/angel/lever6/clocks/clocks_r6_R6_base_rag4096_r2.csv") if l.split()[1:2] and l.split()[1] != "1410")
print("RETAKE offpin =", off)
PY
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race
MEAS=~/lever6 /usr/bin/python3 summarize_gemma3_round6.py R6_base R6_kv16_bn32 || true
echo RETAKE_DONE
