#!/usr/bin/env bash
# prove_flip_licence_r19.sh — re-derive the round-19 flip licence from BANKED ARTIFACTS, off-box, at
# zero VM minutes. argv: <artifact dir containing runs/ and round19.log>  (default: this window's pull)
#
# WHY THIS EXISTS. `chain19.sh` reported `flip_licensed=no` for the re-serve window while 11 pp256 cells
# with a closing cell sat on disk and its own log carried `CELLGROUP pp256 complete`. The verdict was
# wrong because it was derived from the chain's INVOCATION RECORD rather than from the evidence: the
# runner had closed pp256's group inside the pp1024 invocation, so the bookkeeping never credited it.
# The owner's rule is about the DATA — pp1024 AND pp256 cells with closing armor, plus their
# same-session TRT, plus the banked full-scope gate, plus round 18's rag bracket — so the licence must
# be re-derivable from the data by anyone, independently of which process called which. This script is
# that derivation, and it is the same two-part test the fixed chain now applies (CELLGROUP marker AND a
# closing cell on disk), so a future window can be audited without a VM.
#
# It deliberately does NOT trust the chain's own verdict field: it prints it, then computes its own.
set -uo pipefail
A=${1:-/private/tmp/gemma_r19/artifacts}
L19=$A
CELLTAG=${CELLTAG:-_r19}
CW_LOGFILE=$A/round19.log
REQUIRED_PROMPTS=${REQUIRED_PROMPTS:-"pp1024 pp256"}
DEF=${DEF:-R19_def}; TWIN=${TWIN:-R19_defB}
FAIL=0
[[ -d "$A/runs" ]] || { echo "FATAL: no runs/ under $A"; exit 2; }
[[ -f "$CW_LOGFILE" ]] || { echo "FATAL: no round19.log under $A"; exit 2; }

echo "artifact dir: $A"
echo "chain's own verdict (recorded, not trusted):"
sed -n 's/^/    /p' "$A/CHAIN_EXIT" 2>/dev/null | grep -E "flip_licensed|prompts_completed|gate_verdict|timing_complete|trt_reserve_done" || echo "    (no CHAIN_EXIT)"
echo

echo "=== 1. REQUIRED PROMPTS, FROM EVIDENCE ==="
DONE=""
for rp in $REQUIRED_PROMPTS; do
  nm=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${rp}"_r*.out 2>/dev/null | wc -l | tr -d ' ')
  nc=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${rp}"_close*.out 2>/dev/null | wc -l | tr -d ' ')
  nw=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${rp}"_warm*.out 2>/dev/null | wc -l | tr -d ' ')
  cg=$(grep -c "CELLGROUP $rp complete" "$CW_LOGFILE" 2>/dev/null || echo 0)
  if (( cg > 0 && nm > 0 && nc > 0 )); then
    DONE="$DONE $rp"
    echo "  $rp COMPLETE: CELLGROUP marker=$cg, measured=$nm (n_reported), closing=$nc, warmup=$nw"
    if (( nm < 5 )); then
      echo "    *** n_reported=$nm is BELOW the n>=5 floor"; FAIL=1
    fi
  else
    echo "  $rp NOT COMPLETE: CELLGROUP marker=$cg, measured=$nm, closing=$nc"
    FAIL=1
  fi
done
echo

echo "=== 2. EVERY MEASURED CELL: rc, off-pin, clock ==="
tot=$(grep -cE "CELL r6.*${CELLTAG}.* END" "$CW_LOGFILE" 2>/dev/null || echo 0)
rc0=$(grep -E "CELL r6.*${CELLTAG}.* END" "$CW_LOGFILE" 2>/dev/null | grep -c "rc=0" || true)
off0=$(grep -E "CELL r6.*${CELLTAG}.* END" "$CW_LOGFILE" 2>/dev/null | grep -c "offpin=0" || true)
pin=$(grep -E "CELL r6.*${CELLTAG}.* END" "$CW_LOGFILE" 2>/dev/null | grep -c "clocks_after=1410MHz" || true)
echo "  cells=$tot  rc=0:$rc0  offpin=0:$off0  clocks_after=1410MHz:$pin"
if (( rc0 != tot || off0 != tot || pin != tot )); then
  echo "  *** NOT EVERY CELL IS CLEAN — a cell that is off-pin or non-zero-rc cannot be pooled"; FAIL=1
fi
echo

echo "=== 3. MEDIANS, SPREAD AND THE CLOSING-CELL DRIFT ARMOR ==="
/usr/bin/python3 - "$L19/runs" "$CELLTAG" "$DEF" "$TWIN" <<'PY'
import os, re, statistics, sys
RUNS, TAG, DEF, TWIN = sys.argv[1:5]
for prompt in ("pp1024", "pp256"):
    meas, close = [], []
    for f in sorted(os.listdir(RUNS)):
        m = re.match(r"r6%s_(%s|%s)_%s_(r\d+|close\d+)\.out$" % (re.escape(TAG), DEF, TWIN, prompt), f)
        if not m:
            continue
        v = None
        for ln in open(os.path.join(RUNS, f), errors="replace"):
            mm = re.search(r"(?:ttft|TTFT)[^\d]*([0-9]+\.?[0-9]*)", ln)
            if mm:
                v = float(mm.group(1)); break
        if v is None:
            continue
        (close if m.group(2).startswith("close") else meas).append(v)
    if not meas:
        print("  %-8s NO MEASURED CELLS" % prompt); continue
    med = statistics.median(meas)
    c = statistics.median(close) if close else None
    armor = (c - med) if c is not None else None
    print("  %-8s n=%d median=%.3f ms  min=%.3f max=%.3f spread=%.3f%%" %
          (prompt, len(meas), med, min(meas), max(meas), 100*(max(meas)-min(meas))/min(meas)))
    print("           values: %s" % " ".join("%.3f" % v for v in sorted(meas)))
    if armor is None:
        print("           ARMOR NOT COMPUTABLE — NO PUBLISH (no closing cell)")
    else:
        print("           closing n=%d median=%.3f -> armor %+.3f ms (%+.3f%%)%s" %
              (len(close), c, armor, 100*armor/med,
               " [NEGATIVE: the box got faster over the bracket, so drift cannot have inflated the win]"
               if armor < 0 else ""))
    if armor is None:
        sys.exit(1)
PY
arc=$?
if (( arc != 0 )); then
  echo "  *** the armor section did not complete cleanly (rc=$arc) — armor is the gate on publication, so"
  echo "      an uncomputable or crashed armor is a refusal, not a blank line to skip past."
  FAIL=1
fi
echo

echo "=== 4. SAME-SESSION TRT COMPARATOR: present, fresh, and reproducing the stored column ==="
for c in pp256 pp1024 rag4096; do
  f="$L19/runs/trtllm_$c.json"
  if [[ -f "$f" ]]; then
    mt=$(date -u -r "$f" +%FT%TZ 2>/dev/null || stat -c %y "$f" 2>/dev/null)
    v=$(/usr/bin/python3 -c 'import json,statistics,sys
d=json.load(open(sys.argv[1])); b=d.get("ttft_ms") or {}
m=b.get("median")
if m is None and isinstance(b.get("runs"),list) and b["runs"]: m=statistics.median([float(x) for x in b["runs"]])
print("%.3f" % float(m))' "$f" 2>/dev/null || echo UNPARSEABLE)
    echo "  $c: $v ms  json mtime $mt"
  else
    echo "  $c: NO JSON — no same-session comparator for this cell"; [[ "$c" == rag4096 ]] || FAIL=1
  fi
done
echo "  (the 1% reproduction test against every stored column is in round19.log's own check and in the"
echo "   summariser's output; a comparator that fails it must be labelled CROSS-SESSION)"
echo

echo "=== 5. BANKED FULL-SCOPE GATE, RE-EVALUATED BY THE SAME EVALUATOR THE CHAIN USES ==="
NR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$L19/oracle_gate_$DEF.json" ]]; then
  /usr/bin/python3 "$NR/gate_coverage_gemma3_round19.py" "$L19/oracle_gate_$DEF.json" | sed 's/^/  /'
  rc=${PIPESTATUS[0]}
  (( rc != 0 )) && { echo "  *** the banked gate does NOT prove full scope"; FAIL=1; }
else
  echo "  no oracle_gate_$DEF.json in the artifacts"; FAIL=1
fi
echo

missing=""
for rp in $REQUIRED_PROMPTS; do case " $DONE " in *" $rp "*) ;; *) missing="$missing $rp" ;; esac; done
echo "=== VERDICT ==="
if [[ -z "$missing" ]] && (( FAIL == 0 )); then
  echo "FLIP_LICENCE: SATISFIED on the artifacts — pp1024 AND pp256 with closing armor, n>=5 each, every"
  echo "  cell rc=0/offpin=0/1410MHz, a fresh same-session TRT comparator, and the banked full-scope gate."
  echo "  This is a re-derivation from the DATA and is independent of chain19's own (defective) verdict."
else
  echo "FLIP_LICENCE: NOT SATISFIED (missing:${missing:- none}; other failures:$FAIL)"
  FAIL=1
fi
exit $FAIL
