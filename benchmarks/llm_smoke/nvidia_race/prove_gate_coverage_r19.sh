#!/usr/bin/env bash
# prove_gate_coverage_r19.sh — LOCAL PROOF, zero VM minutes, that the round-19 coverage audit is
# fixed and that it still refuses what it must.
#
# THE DEFECT UNDER TEST. Round 19's first window logged, on two adjacent lines at 22:29:38Z:
#     GATE VERDICT ... : ALL_PASS scope=pp1024,pp256,rag4096,val550 out_of_scope=none
#     *** THE GATE DID NOT COVER ALL FOUR SHAPES (1 of 4) ... NO timing, NO flip.
# The gate had in fact passed at full scope (11 cells on disk across all four shapes, 0 divergences),
# and the chain refused it because its counter
#     sed -n 's/.*scope=\([^ ]*\).*/\1/p'
# is GREEDY: `.*scope=` matched the LAST `scope=` on the line, which is the one inside
# `out_of_scope=none`, so it captured `none` and counted 1. A substring of one field name collided
# with another field name. The refusal direction was safe (fail-closed: no timing, no flip, no row
# moved) but it cost the window its remaining ~57 VM-minutes.
#
# WHAT IS PROVEN HERE, in order:
#   1. the OLD parse reproduces the false "1 of 4" on the exact verdict line from the banked log, so
#      the root cause is demonstrated rather than asserted;
#   2. the NEW evaluator returns COVERAGE_OK / rc=0 on the real banked JSON;
#   3. FOUR NEGATIVE CONTROLS, each a mutation of the real JSON, each of which MUST be refused with
#      the matching reason -- because an audit that passes everything is worse than no audit:
#        a. one shape's cells marked ran=False (the parent's hypothesis: scope claims four, cells ran
#           fewer) -> must refuse naming that shape;
#        b. a determinism repeat made DIVERGENT -> must refuse;
#        c. round 18's actual reduced scope (pp1024 only) -> must refuse;
#        d. all_pass=False -> must refuse.
#   4. a JSON that cannot be read is COVERAGE_UNREADABLE, never a pass.
#
# Usage:  bash prove_gate_coverage_r19.sh [path/to/oracle_gate_R19_def.json]
set -uo pipefail
NR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
EVAL="$NR/gate_coverage_gemma3_round19.py"
REAL=${1:-/private/tmp/gemma_r19/gatepull/oracle_gate_R19_def.json}
SB=${SB:-/private/tmp/gemma_r19/covproof}
PY=/usr/bin/python3
rm -rf "$SB"; mkdir -p "$SB"
FAIL=0
ck() { # $1 = label ; $2 = want_rc ; $3 = want_substring ; $4 = file
  local out rc
  out=$($PY "$EVAL" "$4" 2>&1); rc=$?
  if (( rc == $2 )) && [[ "$out" == *"$3"* ]]; then
    echo "  PASS  $1  (rc=$rc, matched '$3')"
  else
    echo "  FAIL  $1  (rc=$rc, wanted rc=$2 and '$3')"
    echo "$out" | sed 's/^/        | /'
    FAIL=1
  fi
}

[[ -f "$REAL" ]] || { echo "FATAL: no banked gate JSON at $REAL"; exit 2; }
echo "banked gate JSON: $REAL  md5=$(md5 -q "$REAL" 2>/dev/null || md5sum "$REAL" | cut -d' ' -f1)"
echo

echo "=== 1. the OLD greedy parse, reproduced on the verdict line the window actually logged ==="
LINE="ALL_PASS scope=pp1024,pp256,rag4096,val550 out_of_scope=none"
OLD_N=$(echo "$LINE" | sed -n 's/.*scope=\([^ ]*\).*/\1/p' | tr ',' '\n' | grep -c .)
OLD_CAP=$(echo "$LINE" | sed -n 's/.*scope=\([^ ]*\).*/\1/p')
echo "  verdict line : $LINE"
echo "  old sed captured '$OLD_CAP' -> counted $OLD_N shape(s)"
if [[ "$OLD_CAP" == "none" && "$OLD_N" == "1" ]]; then
  echo "  PASS  the defect is reproduced exactly: the greedy .*scope= matched out_of_scope=none"
else
  echo "  FAIL  expected the old parse to capture 'none' and count 1"; FAIL=1
fi
echo

echo "=== 2. the NEW evaluator on the REAL banked gate (must be COVERAGE_OK, rc=0) ==="
ck "real full-scope gate" 0 "COVERAGE_OK" "$REAL"
$PY "$EVAL" "$REAL" | head -1 | sed 's/^/        | /'
echo

echo "=== 3. negative controls — each mutation MUST be refused ==="
# (a) the parent's hypothesis, constructed rather than assumed: scope still claims four, but one
#     shape's cells did not run. This is the case a scope-field-trusting audit would wave through.
$PY - "$REAL" "$SB/a_norun.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["cells"]["val550"]["maxnew16"]["ran"] = False
d["cells"]["val550"]["maxnew16"]["pass"] = False
d["cells"]["val550"]["maxnew64"]["ran"] = False
d["cells"]["val550"]["maxnew64"]["pass"] = False
d["all_pass"] = True          # deliberately left True: the scope field still claims all four
json.dump(d, open(sys.argv[2], "w"))
PY
ck "scope claims 4 but val550 ran nothing" 1 "val550" "$SB/a_norun.json"

# (b) a determinism repeat that diverged
$PY - "$REAL" "$SB/b_det.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["cells"]["pp1024"]["maxnew64"]["determinism_pass"] = False
d["cells"]["pp1024"]["maxnew64"]["determinism"] = "DIVERGENT"
d["cells"]["pp1024"]["maxnew64"]["pass"] = False
json.dump(d, open(sys.argv[2], "w"))
PY
ck "divergent det repeat" 1 "DIVERGENT" "$SB/b_det.json"

# (c) round 18's ACTUAL reduced scope, reconstructed: pp1024 only, the other three out-of-scope
$PY - "$REAL" "$SB/c_reduced.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["scope"] = ["pp1024"]
d["out_of_scope_prompts"] = ["pp256", "rag4096", "val550"]
for p in ("pp256", "rag4096", "val550"):
    d["cells"][p] = {"out_of_scope": True,
                     "note": "not requested by this gate's scope; NOT certified either way"}
json.dump(d, open(sys.argv[2], "w"))
PY
ck "round-18-style reduced scope (pp1024 only)" 1 "CELL-derived coverage" "$SB/c_reduced.json"

# (d) all_pass False
$PY - "$REAL" "$SB/d_fail.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["all_pass"] = False
json.dump(d, open(sys.argv[2], "w"))
PY
ck "all_pass=False" 1 "all_pass is not True" "$SB/d_fail.json"

# (e) an EOS-stop the oracle does NOT corroborate: 22/22 would then be self-consistent only
$PY - "$REAL" "$SB/e_eos.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["cells"]["rag4096"]["maxnew64"]["oracle_also_eos_there"] = False
json.dump(d, open(sys.argv[2], "w"))
PY
ck "rag4096 EOS-stop not corroborated by the oracle" 1 "EOS-stop not corroborated" "$SB/e_eos.json"
echo

echo "=== 4. an unreadable JSON is UNKNOWN, never a pass ==="
echo "{ this is not json" > "$SB/broken.json"
ck "malformed JSON" 1 "COVERAGE_UNREADABLE" "$SB/broken.json"
echo

echo "PROOF_VERDICT: $([[ $FAIL == 0 ]] && echo PASS || echo FAIL)"
exit $FAIL
