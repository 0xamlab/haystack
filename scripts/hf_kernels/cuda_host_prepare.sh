#!/usr/bin/env bash
# One-session preparation on an NVIDIA host (Ubuntu 22.04, driver >= 580, the pinned toolchain
# installed in ~/hfk-src/mojo_env): convert the Qwen3 checkpoint with the SDK, compute an
# independent CPU reference for the decode probe, and build the CUDA library set of algenta-llm
# natively. Everything lands in ~/hfk-out; the caller copies the native closure back.
#
#   bash scripts/hf_kernels/cuda_host_prepare.sh <hf snapshot dir> <prompt ids, space separated>
set -euo pipefail
SNAPSHOT="${1:?hf snapshot dir}"; shift
PROMPT_IDS="$*"
SRC="$HOME/hfk-src"; OUT="$HOME/hfk-out"; mkdir -p "$OUT"
PY="$SRC/mojo_env/.pixi/envs/default/bin/python3"
export PATH="$HOME/.pixi/bin:$PATH"
echo "== host: $(hostname) $(uname -m) glibc $(ldd --version | head -1 | awk '{print $NF}')"
nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv,noheader
"$PY" --version
"$PY" -m pip install --quiet numpy 2>&1 | tail -1 || true

echo "== convert checkpoint (SDK prepare_model_checkpoint, f64 manifest + weights.blob)"
CONVERTED="$OUT/qwen3-0.6b-converted"
if [ ! -f "$CONVERTED/manifest.json" ]; then
  PYTHONPATH="$SRC/packages/algenta" "$PY" - "$SNAPSHOT" "$CONVERTED" $PROMPT_IDS <<'EOF'
import sys
from algenta.inference import prepare_model_checkpoint
snapshot, out = sys.argv[1], sys.argv[2]
ids = [int(x) for x in sys.argv[3:]]
print("converted ->", prepare_model_checkpoint(snapshot, ids, out_dir=out))
EOF
fi
ls -la "$CONVERTED" | tail -3

echo "== independent reference: transformers fp32 greedy on the CPU"
python3 -m pip install --quiet --user transformers 2>&1 | tail -1 || true
python3 "$SRC/scripts/hf_kernels/transformers_reference.py" --snapshot "$SNAPSHOT" --prompt-ids $PROMPT_IDS --max-new-tokens 8 --out "$OUT/reference_tokens.json"
cat "$OUT/reference_tokens.json"

echo "== build algenta-llm CUDA (sm_75 sm_80 sm_89 sm_90) natively"
cd "$SRC"
export ALGENTA_SOURCE_COMMIT="${ALGENTA_SOURCE_COMMIT:-unknown}" ALGENTA_SOURCE_DIRTY="${ALGENTA_SOURCE_DIRTY:-1}"
rm -rf "$OUT/algenta-llm_cuda"
"$PY" scripts/build_hf_kernel_family.py --family algenta-llm --backend cuda --out "$OUT/algenta-llm_cuda" 2>&1 | grep -v -E "deprecated|@parameter|\^~|^\s*comptime\s*$" | tail -5
"$PY" -c "import json; m=json.load(open('$OUT/algenta-llm_cuda/_native/manifest.json')); print('cuda targets', m['cuda_targets'], 'kernels included', m['engine_kernels_included_count'], 'files', len(m['files']), sum(v['bytes'] for v in m['files'].values())//1000000, 'MB')"
tar -czf "$OUT/algenta-llm_cuda_native.tgz" -C "$OUT/algenta-llm_cuda" _native
ls -la "$OUT/algenta-llm_cuda_native.tgz"
echo "== prepare done"
