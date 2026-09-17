#!/bin/bash
# Regenerate the a2a prompt fixtures on the fresh VM (tmpfs/scratch was wiped).
# Mirrors run_finish.sh section 1 exactly (same generator, same seed, same lengths),
# plus token-exact pp256 / pp1024 sets for the B1 prefill cells and 2 extra RAG seeds.
exec > /home/angel/trtllm/prep.log 2>&1
set -x
date -u
PY=/usr/bin/python3
G3=$HOME/g3flip
A2A=$HOME/a2a
MODEL=$HOME/models/gemma-3-27b-it
SONNET=$HOME/algenta/mojo_env/.pixi/envs/default/lib/python3.14/site-packages/max/benchmark/benchmark_shared/datasets/packaged_data/sonnet_4x.txt

echo "=== transformers availability ==="
$PY -c "import transformers; print('transformers', transformers.__version__)" || {
  echo "system python3 lacks transformers -> using vllm-venv python"
  PY=$HOME/vllm-venv/bin/python
  $PY -c "import transformers; print('transformers(venv)', transformers.__version__)"
}
ls -la "$SONNET"

echo "=== [1] race prompts 500 x 550 (seed 24301, prefix 200) ==="
rm -rf /tmp/g3race500
$PY $G3/benchmarks/llm_smoke/gemma3/make_race_prompts_many.py \
  --tokenizer $MODEL --sonnet "$SONNET" \
  --count 500 --in-len 550 --prefix 200 --out-dir /tmp/g3race500
echo "RC_RACE500=$? files=$(ls /tmp/g3race500 | wc -l)"

echo "=== [2] pp256 set (8 x 256 tokens, same recipe/seed) ==="
rm -rf /tmp/g3pp256
$PY $G3/benchmarks/llm_smoke/gemma3/make_race_prompts_many.py \
  --tokenizer $MODEL --sonnet "$SONNET" \
  --count 8 --in-len 256 --prefix 200 --out-dir /tmp/g3pp256
echo "RC_PP256=$? files=$(ls /tmp/g3pp256 | wc -l)"

echo "=== [3] pp1024 set (8 x 1024 tokens, same recipe/seed) ==="
rm -rf /tmp/g3pp1024
$PY $G3/benchmarks/llm_smoke/gemma3/make_race_prompts_many.py \
  --tokenizer $MODEL --sonnet "$SONNET" \
  --count 8 --in-len 1024 --prefix 200 --out-dir /tmp/g3pp1024
echo "RC_PP1024=$? files=$(ls /tmp/g3pp1024 | wc -l)"

echo "=== [4] RAG-4096 canonical (seed 4096) ==="
rm -rf /tmp/g3rag
$PY $A2A/make_rag4096.py --tokenizer $MODEL --sonnet "$SONNET" \
  --in-len 4096 --out-dir /tmp/g3rag
echo "RC_RAG4096=$?"

echo "=== [5] RAG-4096 variants (seeds 4097, 4098) ==="
for s in 4097 4098; do
  rm -rf /tmp/g3rag_$s
  $PY $A2A/make_rag4096.py --tokenizer $MODEL --sonnet "$SONNET" \
    --seed $s --in-len 4096 --out-dir /tmp/g3rag_$s
  echo "RC_RAG_$s=$?"
done

echo "=== [6] verify token counts ==="
$PY - <<'PYEOF'
from pathlib import Path
for name, d in (("race500", "/tmp/g3race500"), ("pp256", "/tmp/g3pp256"),
                ("pp1024", "/tmp/g3pp1024")):
    p = Path(d) / "prompt_0000.txt"
    ids = p.read_text().split(",")
    print(f"{name}: prompt_0000 ids={len(ids)} files={len(list(Path(d).glob('prompt_*.txt')))}")
for d in ("/tmp/g3rag", "/tmp/g3rag_4097", "/tmp/g3rag_4098"):
    p = Path(d) / "rag4096.txt"
    print(f"{d}: ids={len(p.read_text().split(','))} text_chars={len((Path(d)/'rag4096.text').read_text())}")
PYEOF
echo "=== DONE ==="
date -u
