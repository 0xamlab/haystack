#!/bin/bash
# Resolve the CUDA 13 vs torch cu128 mismatch in the TRT-LLM 1.2.1 install.
exec > /home/angel/trtllm/fix_cuda.log 2>&1
set -x
date -u
. /home/angel/trtllm/venv/bin/activate
echo "=== declared requirements (METADATA) ==="
grep -E "^(Requires-Dist|Requires-Python|Name|Version)" /home/angel/trtllm/venv/lib/python3.10/site-packages/tensorrt_llm-1.2.1.dist-info/METADATA | head -60
echo "=== installed nvidia/torch pkgs ==="
pip list 2>/dev/null | grep -iE "nvidia|torch" | head -30
echo "=== what provides libcublasLt.so.13 in the venv ==="
find /home/angel/trtllm/venv -name "libcublasLt.so*" 2>/dev/null | head
echo "=== available torch cu130 builds ==="
pip index versions torch --index-url https://download.pytorch.org/whl/cu130 2>&1 | head -5
echo "=== INSTALL torch cu130 ==="
time pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu130 2>&1 | tail -25
echo "TORCH_CU130_RC=$?"
echo "=== recheck libcublasLt ==="
find /home/angel/trtllm/venv -name "libcublasLt.so*" 2>/dev/null | head
python -c "import torch; print('TORCH', torch.__version__, torch.version.cuda)"
echo "=== import tensorrt_llm ==="
python -c "import tensorrt_llm; print('TRTLLM_VERSION', tensorrt_llm.__version__)"
echo "IMPORT_RC=$?"
echo "=== trtllm-serve --help ==="
trtllm-serve --help > /home/angel/trtllm/serve_help.txt 2>&1
echo "SERVE_HELP_RC=$?"
wc -l /home/angel/trtllm/serve_help.txt
echo "=== DONE ==="
date -u
df -h / | tail -1
