#!/usr/bin/env bash
# chain_stage_qwen7b.sh -- STAGE A QWEN2.5-7B BOX FOR THE CUDA RELEASE-VERIFY BATTERY.
#
# This is the Qwen2.5-7B counterpart of chain7stage.sh, and it exists because chain7stage.sh is
# gemma3-27b end to end: it tokenises with ~/models/gemma-3-27b-it, REQUIRES the four /tmp/g3*
# fixtures, proves their identity against round 6's GEMMA gate echoes, and converts gemma at
# weights_dtype=f32. Pointed at a 7B wheel it aborts at "FIXTURE MISSING /tmp/g3pp256/prompt_0000.txt"
# -- after the window has already paid for the boot. verify_cuda_release_battery.sh selects between
# them with STAGE_SCRIPT; this file satisfies the same contract:
#
#   * leave a CONVERTED checkpoint (manifest.json + weights.blob + prompts.json) at $CKPT
#   * leave a comma-separated-token-id fixture file at every path named in $GATE_SPECS
#   * leave one oracle JSON per gate shape at $ORACLE_DIR/<shape>.json as {"generated": [...]}
#   * leave the GPU pinned at $CW_PIN_MHZ, verified, with ZERO off-pin tolerance
#   * print STAGE_OK on success; anything else and the battery refuses to measure
#
# ── WHAT THIS STAGE DOES *NOT* CLAIM: FIXTURE IDENTITY ─────────────────────────────────────────
# chain7stage.sh proves its fixtures byte-identical to round 6's certified gate echoes. The 7B lane
# has NO such banked echo set in the repo -- its gates (run_gates_7b.py, gate_cross_engine.py) were
# scored against a transformers oracle regenerated per window, and its raw cells lived in /tmp on
# algenta-ent-a100, which is wiped. So this stage sets STAGE_NEEDS_FIXTURE_IDENTITY semantics to
# "no marker emitted" and the battery records that in the verdict instead of silently implying a
# proof that did not happen. What still binds every token is the oracle gate itself.
#
# ── THE SHAPES, AND WHY THEY ARE NAMED pp256/pp1024/rag4096 ────────────────────────────────────
# gate_any.py's PLAN enumerates those names, and re-using them is not a gemma-ism: they describe the
# 7B lane's own conventions. pp256 IS the 7B fixture (prepare_qwen25_7b_checkpoint.py pads prompt 1
# to _FIXTURE_TOKENS = 256 exactly). pp1024 IS the 7B lane's long shape -- four_way_race.py builds it
# as `pp1024_ids = fixture_ids * 4` and asserts `len(pp) == 1024 and pp[:256] * 4 == pp`. rag4096 is
# the same construction extended to 16x, standing in for the 7B RAG-4096 shape whose generator was
# never committed (the race scripts only READ ~/trtllm/prompts.json["rag"]). val550 has no 7B
# analogue at all and is dropped from the scope, which is why the caller must also pass
# GATE_COVERAGE_PROMPTS without it -- otherwise the coverage evaluator refuses a scope it was told
# to expect four shapes from.
#
# ── BUDGET, STATED BECAUSE IT IS THE BINDING CONSTRAINT ────────────────────────────────────────
# Unlike the gemma box (checkpoint resident at ~/gemma3-27b, oracle pre-banked at ~/adj/oracle3), a
# 7B box starts COLD: it must fetch a ~15 GB HF snapshot, convert it to a ~57 GB f64 blob, and
# compute a CPU fp32 transformers oracle for three shapes. On the 208-vCPU a3-highgpu-8g that is
# roughly 5 + 15 + 20 = ~40 min BEFORE the first gate cell runs, against a 60+5 min cap that also
# owes ~7 cells and the serve launch. It fits only just, and only on a high-vCPU box. On a
# 26-vCPU a3-highgpu-1g it does NOT fit. Set SKIP_CONVERT=1 / SKIP_ORACLE=1 when the box already
# holds those artifacts, which is the difference between a ~40 min and a ~2 min stage.
set -uo pipefail

STAGE_SRC=${STAGE_SRC:-$HOME/cuda_rel_verify}
L7=${L7:-$HOME/cuda_rel_verify_work}
LOG=${LOG:-$L7/stage.log}
GPU=${GPU:-1}
CKPT=${CKPT:-/tmp/w7b/ckpt}
HF_CKPT=${HF_CKPT:-$HOME/models/Qwen2.5-7B-Instruct}
HF_REPO=${HF_REPO:-Qwen/Qwen2.5-7B-Instruct}
CW_PIN_MHZ=${CW_PIN_MHZ:-1410}
GATE_SPECS=${GATE_SPECS:-}
ORACLE_DIR=${ORACLE_DIR:-$L7/oracle7b}
EOS_TOKENS=${EOS_TOKENS:-151645}
PY314=${PY314:-}
NR="$STAGE_SRC/benchmarks/llm_smoke/nvidia_race"
SKIP_CONVERT=${SKIP_CONVERT:-0}
SKIP_ORACLE=${SKIP_ORACLE:-0}
# The oracle is CPU fp32 transformers. How many tokens it must produce per shape is the gate's width,
# and generating 64 tokens for a 4096-token prompt on CPU is the single most expensive thing this
# stage does -- so the widths are a knob, and a window that cannot afford the 64-token rag4096 oracle
# can gate that shape at 16 and say so.
ORACLE_TOKENS=${ORACLE_TOKENS:-64}

mkdir -p "$L7" "$(dirname "$LOG")" "$ORACLE_DIR"
: > "$LOG"

PHASE="init"
setphase() { PHASE="$1"; echo "[$(date -u +%FT%TZ)] PHASE $PHASE" | tee -a "$LOG"; }
die() { echo "[$(date -u +%FT%TZ)] STAGE_FAILED phase=$PHASE: $*" | tee -a "$LOG"; exit 1; }
note() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

[ -n "$PY314" ] || PY314=$(command -v python3 2>/dev/null || true)
[ -n "$PY314" ] && [ -x "$PY314" ] || die "no python interpreter (set PY314=)"
note "python=$PY314 ($("$PY314" -V 2>&1))"
note "gpu=$GPU ckpt=$CKPT hf=$HF_CKPT pin=${CW_PIN_MHZ}MHz oracle_dir=$ORACLE_DIR eos=$EOS_TOKENS"

# ── 1. INVENTORY: what is already here, before anything is downloaded or converted ──────────────
setphase inventory
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader 2>&1 | tee -a "$LOG"
note "disk: $(df -h "$CKPT" 2>/dev/null | tail -1)"
note "already present: hf=$([ -f "$HF_CKPT/config.json" ] && echo yes || echo no) \
ckpt=$([ -f "$CKPT/manifest.json" ] && echo yes || echo no) \
oracle=$(ls -1 "$ORACLE_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')"

# ── 2. THE HF SNAPSHOT: --hf-checkpoint, and the tokenizer the oracle needs ─────────────────────
setphase hf_snapshot
if [ ! -f "$HF_CKPT/config.json" ]; then
  note "no snapshot at $HF_CKPT -- fetching $HF_REPO"
  # Public and ungated (Apache-2.0), so no token is required; huggingface_hub is already a
  # dependency of the shipped onboarding path, so this adds no new toolchain requirement.
  "$PY314" -c '
import os, sys
from huggingface_hub import snapshot_download
repo, dst = sys.argv[1], sys.argv[2]
snapshot_download(repo, local_dir=dst, allow_patterns=["*.json", "*.safetensors", "*.txt"],
                  token=os.environ.get("HF_TOKEN") or None)
print("SNAPSHOT_OK", dst)
' "$HF_REPO" "$HF_CKPT" >>"$LOG" 2>&1 || die "could not fetch $HF_REPO (no egress, or no huggingface_hub)"
fi
[ -f "$HF_CKPT/config.json" ] || die "still no config.json at $HF_CKPT"
note "HF snapshot OK: $HF_CKPT ($(du -sh "$HF_CKPT" 2>/dev/null | cut -f1))"

# ── 3. CONVERT: the f64 blob the shipped path loads ─────────────────────────────────────────────
# prepare_qwen25_7b_checkpoint.py is REUSED, not reimplemented: it is the 7B lane's own converter, it
# passes --backend=cuda (the SDK door defaults to metal, whose descriptor tables apply no q/k/v
# projection bias and whose tensor probe therefore REFUSES a bias-carrying Qwen2.5 snapshot), and it
# asserts the seven architecture facts after converting. It also writes prompts.json, which is where
# the 256-token fixture below comes from.
setphase convert_checkpoint
if [ "$SKIP_CONVERT" = "1" ] && [ -f "$CKPT/manifest.json" ]; then
  note "SKIP_CONVERT=1 and $CKPT/manifest.json exists -- reusing the resident blob"
elif [ -f "$CKPT/manifest.json" ] && [ -f "$CKPT/weights.blob" ]; then
  note "converted checkpoint already resident -- not re-converting"
else
  mkdir -p "$(dirname "$CKPT")"
  note "converting $HF_CKPT -> $CKPT (this is the ~57 GB f64 blob; the expensive step)"
  "$PY314" "$NR/prepare_qwen25_7b_checkpoint.py" "$HF_CKPT" "$CKPT" --backend=cuda >>"$LOG" 2>&1 \
    || die "prepare_qwen25_7b_checkpoint.py failed (see $LOG)"
fi
for f in manifest.json weights.blob prompts.json; do
  [ -f "$CKPT/$f" ] || die "converted checkpoint is missing $f"
done
note "converted OK: $(du -sh "$CKPT" 2>/dev/null | cut -f1) at $CKPT"

# ── 4. FIXTURES: write the exact paths GATE_SPECS names ─────────────────────────────────────────
# wheel_gate_cells.py reads a fixture as comma-separated token ids on ONE line, while the 7B lane
# keeps its prompts as JSON inside the converted checkpoint. This phase is the adapter between the
# two, and it writes to the paths the caller declared rather than to paths of its own choosing -- a
# stage that invented its own fixture locations would leave the battery pointing at nothing.
setphase prep_fixtures
[ -n "$GATE_SPECS" ] || die "GATE_SPECS is empty -- nothing to stage fixtures for"
GATE_SPECS="$GATE_SPECS" CKPT="$CKPT" "$PY314" - <<'PYFIX' 2>&1 | tee -a "$LOG"
import json, os, sys
from pathlib import Path

ckpt = Path(os.environ["CKPT"])
prompts = json.loads((ckpt / "prompts.json").read_text(encoding="utf-8"))
fixture = list(prompts["fixture"]["ids"])
if len(fixture) != 256:
    sys.exit("the 7B fixture must be exactly 256 ids, got %d" % len(fixture))

# shape name -> how many times the 256-token fixture is repeated. pp1024 is the 7B lane's own
# construction (four_way_race.py: fixture_ids * 4); rag4096 extends it to 16x.
REPEATS = {"pp256": 1, "pp1024": 4, "rag4096": 16}
specs = [s for s in os.environ["GATE_SPECS"].split() if s.strip()]
if not specs:
    sys.exit("GATE_SPECS parsed to nothing")
for spec in specs:
    name, _, path = spec.partition(":")
    if not path:
        sys.exit("malformed GATE_SPECS entry %r (want name:/path/to/fixture.txt)" % spec)
    if name not in REPEATS:
        sys.exit("no 7B construction for shape %r; known shapes are %s"
                 % (name, sorted(REPEATS)))
    ids = fixture * REPEATS[name]
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(",".join(str(i) for i in ids) + "\n", encoding="utf-8")
    print("FIXTURE %s -> %s (%d ids)" % (name, dst, len(ids)))
print("FIXTURES_OK count=%d" % len(specs))
PYFIX
[ "${PIPESTATUS[0]}" = "0" ] || die "fixture generation failed"
for spec in $GATE_SPECS; do
  f="${spec##*:}"
  [ -s "$f" ] || die "fixture $f was not written"
  n=$(tr ',' '\n' < "$f" | grep -c . || true)
  note "FIXTURE $f ($n ids)"
done

# ── 5. ORACLE: independent of the engine, which is what makes it an oracle ───────────────────────
# ref_transformers_cpu.py is the 7B lane's own reference: fp32 transformers on CPU, greedy, with
# repetition_penalty PINNED to 1.0 (Qwen2.5-7B-Instruct ships a generation_config.json with 1.05,
# which flipped the chat_1 step-6 near-tie). It is deliberately NOT the engine's own f64 path: the
# converted 7B blob is already f64, so comparing the shipped path against the engine reading the same
# blob would compare a thing with itself and certify nothing. gate_any.py wants one JSON per shape
# holding {"generated": [...]}, so the reference output is re-keyed into that shape here.
setphase oracle
if [ "$SKIP_ORACLE" = "1" ]; then
  note "SKIP_ORACLE=1 -- assuming $ORACLE_DIR is already populated"
else
  for spec in $GATE_SPECS; do
    name="${spec%%:*}"
    fixture_path="${spec##*:}"
    out="$ORACLE_DIR/$name.json"
    if [ -s "$out" ]; then note "oracle for $name already present -- not recomputing"; continue; fi
    note "oracle $name: CPU fp32 transformers, $ORACLE_TOKENS tokens (the slow step)"
    CASE_DIR="$L7/oracle_case_$name"
    mkdir -p "$CASE_DIR"
    # One prompts.json per shape, in the format ref_transformers_cpu.py reads, so the reference sees
    # EXACTLY the ids the cell will see -- not a re-tokenisation of the same text.
    "$PY314" - "$fixture_path" "$CASE_DIR/prompts.json" <<'PYPROMPT'
import json, sys
from pathlib import Path
ids = [int(t) for t in Path(sys.argv[1]).read_text().strip().replace("\n", ",").split(",") if t.strip()]
Path(sys.argv[2]).write_text(json.dumps(
    {"fixture": {"ids": ids, "n_tokens": len(ids)}, "chat_prompts": []}, indent=1), encoding="utf-8")
print("prompt case written: %d ids" % len(ids))
PYPROMPT
    [ -s "$CASE_DIR/prompts.json" ] || die "could not write the oracle prompt case for $name"
    "$PY314" "$NR/ref_transformers_cpu.py" --model-dir "$HF_CKPT" --ckpt "$CKPT" \
      --prompts "$CASE_DIR/prompts.json" --cases fixture --n-tokens "$ORACLE_TOKENS" \
      --out "$CASE_DIR/ref.json" >>"$LOG" 2>&1 || die "ref_transformers_cpu.py failed for $name"
    "$PY314" - "$CASE_DIR/ref.json" "$out" <<'PYORC'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
row = src.get("fixture") or (src.get("cases") or {}).get("fixture")
if not row:
    sys.exit("no 'fixture' case in the reference output: keys=%s" % sorted(src))
ids = row.get("generated_ids") or row.get("generated")
if not ids:
    sys.exit("the reference generated no ids for this shape")
# gate_any.py reads exactly one key: "generated".
json.dump({"generated": list(ids)}, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
print("ORACLE %s -> %s (%d ids)" % (sys.argv[2], sys.argv[2], len(ids)))
PYORC
    [ $? = 0 ] || die "could not re-key the reference output for $name"
    [ -s "$out" ] || die "oracle file for $name was not written"
  done
fi
for spec in $GATE_SPECS; do
  name="${spec%%:*}"
  [ -s "$ORACLE_DIR/$name.json" ] || die "no oracle for $name at $ORACLE_DIR/$name.json"
done
note "ORACLE_OK dir=$ORACLE_DIR files=$(ls -1 "$ORACLE_DIR"/*.json | wc -l | tr -d ' ')"

# ── 6. CLOCK PIN, VERIFIED, ZERO TOLERANCE ──────────────────────────────────────────────────────
# Identical discipline to chain7stage.sh: persistence mode on, graphics clocks locked min=max, then
# READ BACK and refuse if the GPU is not at the pin. A measurement taken off-pin is not comparable
# with anything, and a pin that was requested but not honoured is the failure mode this catches.
setphase clock_pin
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1
sudo -n nvidia-smi -lgc "$CW_PIN_MHZ,$CW_PIN_MHZ" >>"$LOG" 2>&1
nvidia-smi --query-gpu=index,clocks.current.sm,clocks.max.sm,persistence_mode \
  --format=csv,noheader 2>&1 | tee -a "$LOG"
PIN=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits 2>/dev/null)
note "GPU$GPU clocks.current.sm=$PIN (want $CW_PIN_MHZ -- ZERO off-pin tolerance)"
if [ "$PIN" != "$CW_PIN_MHZ" ]; then
  note "OFF_PIN: $PIN != $CW_PIN_MHZ. This SKU may not honour that lock; re-request with"
  note "  CW_PIN_MHZ set to a value nvidia-smi -q -d SUPPORTED_CLOCKS lists, and do not measure"
  note "  until the read-back matches. Measuring off-pin would not be comparable."
  die "off pin ($PIN != $CW_PIN_MHZ)"
fi

setphase done
note "shapes staged: $(for s in $GATE_SPECS; do printf '%s ' "${s%%:*}"; done)"
echo "STAGE_OK" | tee -a "$LOG"
