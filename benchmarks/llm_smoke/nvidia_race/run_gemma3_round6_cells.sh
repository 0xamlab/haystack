#!/usr/bin/env bash
# run_gemma3_round6_cells.sh — the CELL RUNNER for the gemma-3-27b-it round-6 prefill A/B:
# one watchdog-wrapped, clock-pinned, 1 Hz-sampled cell per driver process, in the three stages
# the protocol needs. `run_ab_gemma3_round6.sh` orchestrates it; this file owns the cells so the
# protocol lives in exactly one place.
#
#   STAGE=smoke   two cells (ARM_B then ARM_A on pp1024, --max-new 1). Proves the fused kernel
#                 actually ARMED and gives a first delta before an hour of gated cells is spent.
#   STAGE=gate    the full oracle gate on ARM: pp256 / pp1024 / val550 at 16 and 64 greedy
#                 tokens with the 64-token run repeated for determinism, plus rag4096 at 64 with
#                 the EOS-stop rule. Writes into a PER-ARM runs dir ($MEAS/gate_<arm>/) so
#                 gating a second arm cannot overwrite the first arm's cells. Exits non-zero on
#                 ANY fail, which is what stops the orchestrator before any timing cell.
#   STAGE=timing  interleaved bracketed A/B over PROMPTS: 3 warmup + 7 measured per cell, the
#                 two arms alternating run-by-run, and ARM_A re-run twice at the END of each
#                 prompt group so the group is A..B..A and the drift is MEASURED. A lever delta
#                 that does not exceed that drift is reported NOT RESOLVED, not as a win.
#
# Every cell goes through cell_watchdog.sh: 600 s with no exit -> log STALL -> SIGKILL the whole
# process group -> continue -> no driver JSON line, so summarisers drop the cell (n falls)
# rather than silently reporting a partial run. That watchdog exists because a lever-2 gate cell
# was once killed mid-blob-load and its truncated .out was later misread as a crashed arm.
#
# Usage:
#   STAGE=smoke bash run_gemma3_round6_cells.sh
#   STAGE=gate  ARM=R6_fa2 bash run_gemma3_round6_cells.sh
#   STAGE=timing ARM_A=R6_base ARM_B=R6_fa2 bash run_gemma3_round6_cells.sh
#   STAGE=timing ARM_A=R6_base ARM_B=R6_fa2 \
#     PROMPTS="pp1024:/tmp/g3pp1024/prompt_0000.txt:1" bash run_gemma3_round6_cells.sh
set -uo pipefail

GPU=${GPU:-1}
STAGE=${STAGE:-smoke}
ARM=${ARM:-R6_fa2}
ARM_A=${ARM_A:-R6_base}
ARM_B=${ARM_B:-R6_fa2}
ARM_C=${ARM_C:-}          # optional third interleaved arm (round 6: R6_kv16)
CELLTAG=${CELLTAG:-}      # timing-label infix so a SECOND bracket does not overwrite the
                          # first bracket's cells: labels become r6b_<arm>_<prompt>_r<i>.
                          # summarize_gemma3_round6.py pools r6_, r6b_, r6c_ into one median.
BIN_DIR=${BIN_DIR:-$HOME/lever6}
MEAS=${MEAS:-$HOME/lever6}
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
WATCHDOG=${WATCHDOG:-$HOME/lever3/cell_watchdog.sh}
GATE_ANY=${GATE_ANY:-$HOME/lever3/gate_any.py}
ORACLE_DIR=${ORACLE_DIR:-$HOME/adj/oracle3}
DRIVER_PROMPTS=${PROMPTS:-"pp256:/tmp/g3pp256/prompt_0000.txt:1 pp1024:/tmp/g3pp1024/prompt_0000.txt:1 rag4096:/tmp/g3rag/rag4096.txt:256"}
CW_TIMEOUT_S=${CW_TIMEOUT_S:-600}
ENV_DIR=${ENV_DIR:-$HOME/algenta/mojo_env/.pixi/envs/default}
PY=${PY:-/usr/bin/python3}
export CUDA_VISIBLE_DEVICES=$GPU
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}

# the gate writes to its own per-arm tree; the timing cells are shared so one summariser sees
# every arm's runs side by side
if [[ "$STAGE" == "gate" ]]; then
  RUNS=$MEAS/gate_$ARM; LOGS=$RUNS/logs; CLK=$RUNS/clocks
else
  RUNS=$MEAS/runs; LOGS=$MEAS/logs; CLK=$MEAS/clocks
fi
CW_LOGFILE=${CW_LOGFILE:-$MEAS/cells.log}
export CW_LOGFILE
mkdir -p "$RUNS" "$LOGS" "$CLK"
# shellcheck disable=SC1091
source "$WATCHDOG"
cw_init "$RUNS" "$LOGS" "$CLK" "$GPU"

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }

quiesce() {
  # Self-excluding by construction: `_busy` walks pgrep's PIDs and skips this script and its
  # launcher. A busy-pattern that matches the runner's OWN command line wedges the loop forever
  # (the first cut of this round's battery carried `lv5[.]sh` in its pattern, pgrep matched the
  # running script on every poll, `clean` never reached 2, and the smoke stage sat in `sleep 15`
  # for ten minutes with the GPUs at 0 MiB). A quiescence check that can only be satisfied by a
  # process that is not us has to exclude us explicitly.
  local pat="lv3[.]sh|lv6[.]sh|rr_[c]hain.sh|rr_[t]rtllm.sh|trtllm[-]serve|R6_[a-z]|nsys [p]rofile"
  local clean=0 i mem p busy
  for i in $(seq 1 80); do
    busy=0
    for p in $(pgrep -f "$pat" 2>/dev/null); do
      if [[ "$p" != "$$" && "$p" != "$PPID" ]]; then busy=1; break; fi
    done
    if (( busy == 1 )); then
      clean=0
    else
      mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $GPU)
      if [[ "${mem:-9999}" -lt 500 ]]; then
        clean=$((clean + 1))
        if (( clean >= 2 )); then log "QUIESCENT mem=${mem}MiB"; return 0; fi
      else
        clean=0
      fi
    fi
    sleep 15
  done
  log "quiescence not reached"; return 1
}

banner_audit() { # $1 = arm
  local b=$BIN_DIR/$1 str l
  log "--- flag audit $1 (strings, positive control = 'G3 FLAGS: TCATTN =') ---"
  # bash string match, NOT `strings | grep -q`: under `set -o pipefail` a `grep -q` that exits on
  # its first match SIGPIPEs `strings`, the pipeline returns non-zero, and EVERY arm reads as
  # carrying no control literal. That is verbatim the failure mode scripts/audit_tc_flags.sh
  # documents and guards against, and this round's first battery script reproduced it.
  str=$(strings -a "$b")
  if [[ "$str" != *"G3 FLAGS: TCATTN ="* ]]; then
    log "FATAL: $1 carries no gemma-3 positive-control literal; the audit cannot read it"
    return 3
  fi
  while read -r l; do [[ -n "$l" ]] && log "  $1 HAS $l"; done \
    < <(grep -o 'TCFLAG ALGENTA_G3[A-Z0-9_]*=1' <<< "$str" | sort -u)
  log "  $1 sha256_16=$(sha256sum "$b" | cut -c1-16) bytes=$(stat -c %s "$b")"
}

ttft_of() { # $1 = label -> "ttft_ms=... n_gen=... tok0=..."
  $PY - "$RUNS/$1.out" <<'PY'
import json, sys
try:
    txt = open(sys.argv[1], errors="replace").read().splitlines()
except OSError:
    print("no-file"); raise SystemExit
for line in reversed(txt):
    line = line.strip()
    if line.startswith("{") and '"generated"' in line:
        d = json.loads(line)
        g = d.get("generated") or []
        print(f"ttft_ms= {d.get('ttft_ms')} n_gen= {d.get('n_generated')} tok0= "
              f"{g[0] if g else None}")
        break
else:
    print("no-json")
PY
}

# ─────────────────────────────────────── SMOKE ───────────────────────────────────────
if [[ "$STAGE" == "smoke" ]]; then
  log "=== STAGE=smoke (pid $$) GPU=$GPU ARM_B=$ARM_B ARM_C=$ARM_C ARM_A=$ARM_A ==="
  quiesce || exit 1
  for a in ${ARM_C:-} "$ARM_B" "$ARM_A"; do
    banner_audit "$a" || exit 3
    cw_cell "smoke_${a}_pp1024" "$BIN_DIR/$a" "$CKPT" \
      --tokens-file /tmp/g3pp1024/prompt_0000.txt --max-new 1 --f16 --prefill
    while read -r vl; do log "  smoke $a $vl"; done < <(grep -E \
        "flash attention( v2)? (ARMED|DECLINED)" "$RUNS/smoke_${a}_pp1024.out" 2>/dev/null)
    log "  smoke $a FLAGS: $(grep -m1 '^G3 FLAGS:' "$RUNS/smoke_${a}_pp1024.out" 2>/dev/null)"
    log "  smoke $a $(ttft_of "smoke_${a}_pp1024")"
  done
  log "=== SMOKE DONE ==="
  nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
  exit 0
fi

# ─────────────────────────────────────── GATE ────────────────────────────────────────
if [[ "$STAGE" == "gate" ]]; then
  log "=== STAGE=gate ARM=$ARM (per-arm runs dir $RUNS, oracle $ORACLE_DIR) ==="
  banner_audit "$ARM" || exit 3
  quiesce || exit 1
  BIN=$BIN_DIR/$ARM
  # GATE_SPECS lets a caller gate a SUBSET of the four prompts. The default is the full round-6
  # set, so nothing changes for any existing caller. ROUND 18 uses it because a full four-prompt
  # gate is 11 cells at ~110-135 s = ~38 min, and a 90-min cap that also has to fund staging
  # (~14 min), a build (~6 min) and an n=5 bracket (~41 min) cannot carry both a full gate and a
  # bracket. Gating the TWO BRACKETED SHAPES is the subset the timing claim actually rests on, and
  # a reduced gate is recorded as reduced in the ledger rather than passed off as the full one.
  GATE_SPECS=${GATE_SPECS:-"pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt \
val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"}
  n_specs=$(echo "$GATE_SPECS" | wc -w | tr -d ' ')
  (( n_specs != 4 )) && log "NOTE: NON-DEFAULT gate scope -- $n_specs of 4 prompts: [$GATE_SPECS]"
  for spec in $GATE_SPECS; do
    n=${spec%%:*}; f=${spec##*:}
    for k in 16 64; do
      [[ "$n" == "rag4096" && "$k" == "16" ]] && continue
      cw_cell "gate_${n}_maxnew${k}" "$BIN" "$CKPT" --tokens-file "$f" --max-new "$k" --f16 --prefill
    done
    cw_cell "gate_${n}_maxnew64_rep2" "$BIN" "$CKPT" --tokens-file "$f" --max-new 64 --f16 --prefill
  done
  # PASS THE SCOPE TO THE GATE. gate_any.py's PLAN enumerates all four prompts and used to report
  # all_pass=False for any prompt that had not run, so a deliberately reduced gate read as a FAILED
  # gate and the chain refused to time an arm whose in-scope cells had all passed. Deriving the
  # scope from the same GATE_SPECS that decided which cells to run makes the two impossible to
  # disagree, and gate_any.py prints the scope next to ALL_PASS so a reduced gate can never be
  # mistaken for a full one.
  gate_scope=$(echo "$GATE_SPECS" | tr ' ' '\n' | cut -d: -f1 | paste -sd, -)
  log "gate scope passed to gate_any.py: [$gate_scope]"
  $PY "$GATE_ANY" "$RUNS" "$MEAS/oracle_gate_$ARM.json" \
    "round-6 $ARM" "$gate_scope" 2>&1 | tee -a "$CW_LOGFILE"
  if ! $PY -c "import json,sys; sys.exit(0 if json.load(open('$MEAS/oracle_gate_$ARM.json'))['all_pass'] else 1)"; then
    log "GATE FAILED for $ARM -> no timing cells may be published for this arm"
    exit 1
  fi
  log "GATE PASSED for $ARM"
  exit 0
fi

# ─────────────────────────────────────── TIMING ──────────────────────────────────────
if [[ "$STAGE" == "timing" ]]; then
  log "=== STAGE=timing ARM_A=$ARM_A ARM_B=$ARM_B ARM_C=$ARM_C PROMPTS=[$DRIVER_PROMPTS] ==="
  banner_audit "$ARM_A" || exit 3
  banner_audit "$ARM_B" || exit 3
  [[ -n "$ARM_C" ]] && { banner_audit "$ARM_C" || exit 3; }
  quiesce || exit 1
  # Run counts are overridable so a SHORT bracket can complete inside a tight VM cap, which matters
  # because cells POOL across brackets by label (CELLTAG): a window that can only afford 5 cells per
  # arm still advances n and still closes the A..B..A group, rather than being forced to choose
  # between a full 12-cell bracket it cannot finish and no bracket at all. Defaults are the
  # protocol's 3 warmup + 7 measured + 2 closing, so nothing changes for a caller that does not ask.
  WARM_RUNS=${WARM_RUNS:-3}
  MEAS_RUNS=${MEAS_RUNS:-7}
  CLOSE_RUNS=${CLOSE_RUNS:-2}
  log "bracket shape: $WARM_RUNS warmup + $MEAS_RUNS measured + $CLOSE_RUNS closing per arm"
  (( WARM_RUNS != 3 || MEAS_RUNS != 7 )) && \
    log "NOTE: non-default bracket shape -- the pooled n and the drift armor must be reported with it"
  for spec in $DRIVER_PROMPTS; do
    n=$(echo "$spec" | cut -d: -f1); f=$(echo "$spec" | cut -d: -f2); mn=$(echo "$spec" | cut -d: -f3)
    for i in $(seq 1 "$WARM_RUNS"); do
      cw_cell "r6${CELLTAG}_${ARM_A}_${n}_warm$i" "$BIN_DIR/$ARM_A" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
      cw_cell "r6${CELLTAG}_${ARM_B}_${n}_warm$i" "$BIN_DIR/$ARM_B" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
      [[ -n "$ARM_C" ]] && cw_cell "r6${CELLTAG}_${ARM_C}_${n}_warm$i" "$BIN_DIR/$ARM_C" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
    done
    for i in $(seq 1 "$MEAS_RUNS"); do
      cw_cell "r6${CELLTAG}_${ARM_A}_${n}_r$i" "$BIN_DIR/$ARM_A" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
      cw_cell "r6${CELLTAG}_${ARM_B}_${n}_r$i" "$BIN_DIR/$ARM_B" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
      [[ -n "$ARM_C" ]] && cw_cell "r6${CELLTAG}_${ARM_C}_${n}_r$i" "$BIN_DIR/$ARM_C" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
    done
    # the closing bracket: A again, so the group is A..B..A and the drift over the group is a
    # measurement rather than an assumption
    for i in $(seq 1 "$CLOSE_RUNS"); do
      cw_cell "r6${CELLTAG}_${ARM_A}_${n}_close$i" "$BIN_DIR/$ARM_A" "$CKPT" --tokens-file "$f" --max-new "$mn" --f16 --prefill
    done
    log "CELLGROUP $n complete (A=$ARM_A B=$ARM_B C=$ARM_C)"
  done
  log "=== TIMING DONE ==="
  exit 0
fi

log "unknown STAGE=$STAGE"; exit 2
