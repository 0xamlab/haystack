#!/bin/bash
# flip_validate_gemma3_round19.sh — CPU-ONLY validation of the round-19 GEGLU_V2 default flip, run
# with the VM TERMINATED. Compiles the REAL race driver for sm_90 (--emit object, so no link and no
# CUDA deps) under every reachable configuration of the flipped flag, then:
#   1. runs scripts/audit_tc_flags.sh over the artifacts, so the GEGLU_V2 row is EXERCISED rather
#      than argued about — and for a default-ON flag the reading is INVERTED (an ABSENT literal is
#      positive proof the opt-out was used);
#   2. proves the legacy opt-in is an exact NO-OP by BYTE-IDENTITY of the object, not by inspection;
#   3. proves the opt-out WINS over the legacy opt-in, also by byte-identity;
#   4. proves the F16MLP gating makes the flag inert by construction;
#   5. computes the kernel-symbol SET DIFFERENTIAL between the default and the opt-out, which must
#      be exactly 1 added / 0 removed and the added symbol must be the vector twin.
#
# CHECKED IN SO THE EVIDENCE IS REPRODUCIBLE RATHER THAN A CLAIM — the same reason
# `dryrun_backstop_r18.sh` is in the tree.
#
# LAST RUN (2026-09-19, VM TERMINATED, Mojo 1.0.0 ed45d567 via the repo's pixi env, sm_90):
#   FLIP_VALIDATE_VERDICT: PASS — all six configurations rc=0; the audit's GEGLU_V2 row read
#   PRESENT/PRESENT/absent/absent/absent/absent exactly as the table in `scripts/audit_tc_flags.sh`
#   records; all four byte-identity claims held (default == legacy_optin 981024 B,
#   nogegluv2 == both_opts 963384 B, nomlp_default == nomlp_and_optout 962920 B, and
#   default != nogegluv2 by -17640 B); differential 38 -> 39 = 1 added / 0 removed with the added
#   symbol b0496694ffefbc3c and the scalar twin 8f4c4e1d2ba54545 present in both.
#   RUN TWICE, and the second run — after docstring edits to `kernels_prefill_gemma3.mojo` — produced
#   BYTE-IDENTICAL objects (same sha256_16 for all six: 570515ac338b5cdf / a50754d09b352d0e /
#   87078d03158a60ec). That is a free extra fact worth keeping: a Mojo kernel's docstring does not
#   reach the compiled object at all, consistent with the campaign's finding that the 16-hex kernel
#   hash is NAME-derived — so documentation can be corrected without invalidating a hash pinned in
#   an earlier round's certification.
# bash 3.2 safe: no associative arrays, no heredoc inside $( ).
set -uo pipefail

WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-r19}
OUT=${OUT:-/private/tmp/gemma_r19/obj}
LOGD=${LOGD:-/private/tmp/gemma_r19/logs}
SM=${SM:-sm_90}
DRIVER="$WT/benchmarks/llm_smoke/nvidia_race/vm_harness/adj/build/driver_ctx8192.mojo"
HASH_SCALAR=${HASH_SCALAR:-8f4c4e1d2ba54545}   # _pf_geglu_rows_f16_kernel
HASH_VEC=${HASH_VEC:-b0496694ffefbc3c}         # _pf_geglu_rows_f16_vec_kernel

mkdir -p "$OUT" "$LOGD"
rm -f "$OUT"/*.o
cd "$WT/mojo_env" || exit 1

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 \
-D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"
R5="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM \
-D ALGENTA_G3_PF_F16MLP -D ALGENTA_G3_PF_ROPE2"
R6="$R5 -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 -D ALGENTA_G3_PF_BN32"
# R5 minus F16MLP: the gating parent off, so GEGLU_V2 must be inert by construction.
R5_NOMLP="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM \
-D ALGENTA_G3_PF_ROPE2 -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 -D ALGENTA_G3_PF_BN32"

NAMES="default nogegluv2 legacy_optin both_opts nomlp_and_optout nomlp_default"
flags_for() {
  case "$1" in
    default)          echo "$BASE $R6" ;;
    nogegluv2)        echo "$BASE $R6 -D ALGENTA_G3_PF_NO_GEGLUV2" ;;
    legacy_optin)     echo "$BASE $R6 -D ALGENTA_G3_PF_GEGLU_V2" ;;
    both_opts)        echo "$BASE $R6 -D ALGENTA_G3_PF_GEGLU_V2 -D ALGENTA_G3_PF_NO_GEGLUV2" ;;
    nomlp_and_optout) echo "$BASE $R5_NOMLP -D ALGENTA_G3_PF_NO_GEGLUV2" ;;
    nomlp_default)    echo "$BASE $R5_NOMLP" ;;
  esac
}

FAIL=0
for n in $NAMES; do
  f=$(flags_for "$n")
  # shellcheck disable=SC2086
  ( cd "$WT/mojo_env" && pixi run mojo build $f \
      --target-accelerator "$SM" -I "$WT/mojo/engine" -I "$WT/attention_forge" \
      --emit object "$DRIVER" -o "$OUT/$n.o" ) > "$LOGD/build_$n.log" 2>&1
  rc=$?
  sz=$(stat -f %z "$OUT/$n.o" 2>/dev/null || echo 0)
  sha=$(shasum -a 256 "$OUT/$n.o" 2>/dev/null | cut -c1-16 || echo none)
  echo "BUILD $n rc=$rc bytes=$sz sha256_16=$sha"
  if (( rc != 0 )); then
    FAIL=1; echo "  --- last 25 lines of $LOGD/build_$n.log ---"; tail -25 "$LOGD/build_$n.log"
  fi
done
echo

# ── 1. the audit script, exercised over the real artifacts ────────────────────────────────────
echo "=== audit_tc_flags.sh over the compiled configurations ==="
# the audit skips *.o by extension, so present the objects under extension-less names
AUD=$OUT/auditbins
rm -rf "$AUD"; mkdir -p "$AUD"
for n in $NAMES; do cp "$OUT/$n.o" "$AUD/$n" 2>/dev/null; done
bash "$WT/scripts/audit_tc_flags.sh" --bin-dir "$AUD" --glob '*' \
  --out "$LOGD/flag_audit.json" > "$LOGD/audit_run.log" 2>&1
echo "audit rc=$? -> $LOGD/flag_audit.json"
tail -3 "$LOGD/audit_run.log"
/usr/bin/python3 - "$LOGD/flag_audit.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("  %-18s %-10s %-10s %s" % ("arm", "GEGLU_V2", "F16MLP", "bytes"))
for a in sorted(d["arms"], key=lambda x: x["arm"]):
    inp = a["flags_in_binary"]
    g = "PRESENT" if "ALGENTA_G3_PF_GEGLU_V2" in inp else "absent"
    m = "PRESENT" if "ALGENTA_G3_PF_F16MLP" in inp else "absent"
    print("  %-18s %-10s %-10s %d" % (a["arm"], g, m, a["bytes"]))
PY
echo

# ── 2/3/4. byte-identity claims ───────────────────────────────────────────────────────────────
cmp_objs() { # $1 $2 $3 = claim
  if cmp -s "$OUT/$1.o" "$OUT/$2.o"; then
    echo "IDENTICAL  $1 == $2   ($3)  [$(stat -f %z "$OUT/$1.o") bytes]"
  else
    echo "DIFFER     $1 != $2   ($3)  [$(stat -f %z "$OUT/$1.o") vs $(stat -f %z "$OUT/$2.o") bytes]"
    FAIL=1
  fi
}
diff_objs() { # $1 $2 $3 = claim (must DIFFER)
  if cmp -s "$OUT/$1.o" "$OUT/$2.o"; then
    echo "*** UNEXPECTEDLY IDENTICAL  $1 == $2  ($3) — the opt-out changed NO compiled code"
    FAIL=1
  else
    echo "DIFFERS AS REQUIRED  $1 != $2   ($3)  [$(stat -f %z "$OUT/$1.o") vs $(stat -f %z "$OUT/$2.o") bytes]"
  fi
}
echo "=== byte-identity claims ==="
cmp_objs  default legacy_optin     "the legacy opt-in is an exact NO-OP post-flip"
cmp_objs  nogegluv2 both_opts      "the opt-out WINS over the legacy opt-in"
cmp_objs  nomlp_default nomlp_and_optout "with F16MLP off the flag is INERT by gating"
diff_objs default nogegluv2        "the opt-out really does remove compiled code"
echo

# ── 5. kernel-symbol set differential ─────────────────────────────────────────────────────────
khashes() {
  strings -a "$1" | grep -oE '\.visible \.entry [A-Za-z_][A-Za-z0-9_]*_[0-9a-f]{16}\(' \
    | sed -E 's/.*_([0-9a-f]{16})\($/\1/' | sort -u
}
echo "=== kernel-symbol differential (control=nogegluv2 -> default) ==="
khashes "$OUT/nogegluv2.o" > "$LOGD/h_nogegluv2.txt"
khashes "$OUT/default.o"   > "$LOGD/h_default.txt"
echo "  count nogegluv2=$(wc -l < "$LOGD/h_nogegluv2.txt" | tr -d ' ') default=$(wc -l < "$LOGD/h_default.txt" | tr -d ' ')"
ADDED=$(comm -13 "$LOGD/h_nogegluv2.txt" "$LOGD/h_default.txt")
REMOVED=$(comm -23 "$LOGD/h_nogegluv2.txt" "$LOGD/h_default.txt")
echo "  ADDED   by the default : ${ADDED:-<none>}"
echo "  REMOVED by the default : ${REMOVED:-<none>}"
n_add=$(echo -n "$ADDED" | grep -c . || true); n_rem=$(echo -n "$REMOVED" | grep -c . || true)
if (( n_add == 1 && n_rem == 0 )); then
  echo "  SET DIFFERENTIAL = 1 added / 0 removed  OK"
  if [[ "$ADDED" == "$HASH_VEC" ]]; then
    echo "  the single added kernel IS the predicted vector twin $HASH_VEC  OK"
  else
    echo "  *** the added kernel is $ADDED, NOT the predicted $HASH_VEC"; FAIL=1
  fi
else
  echo "  *** SET DIFFERENTIAL is $n_add/$n_rem, expected 1/0"; FAIL=1
fi
echo "  scalar twin $HASH_SCALAR present in BOTH: nogegluv2=$(grep -c "^$HASH_SCALAR$" "$LOGD/h_nogegluv2.txt") default=$(grep -c "^$HASH_SCALAR$" "$LOGD/h_default.txt")"

echo
echo "FLIP_VALIDATE_VERDICT: $([[ $FAIL == 0 ]] && echo PASS || echo FAIL)"
exit $FAIL
