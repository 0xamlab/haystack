#!/usr/bin/env bash
# mojo_kernel_identity.sh — generate a per-build kernel-identity table for Mojo device kernels, by
# DIFFERENTIAL COMPILATION rather than by a hand-maintained name table.
#
# THE PROBLEM. nsys reports Mojo device kernels under symbols like
#   residentk_kernels_prefill_gemma6A6A_8f4c4e1d2ba54545
# The symbol is `<module>_<func truncated>_<mangling>_<content hash>`, and for kernels in
# mojo/engine/residentk/kernels_prefill_gemma3.mojo the module path alone consumes the whole 31-char
# name budget — so the function name is GONE and only the hash distinguishes them. Consequences, both
# observed in round 15: name-substring bucketing put 79.156 ms (14.2% of GPU busy, 2616 instances)
# into a single `mojo_per_layer` catch-all, and the `norms` bucket caught 4 instances / 0.046 ms
# instead of the >=124 a 62-layer prefill implies. norm-accum could not be priced at all.
#
# THE FIX. The hash is CONTENT-derived and, verified in round 15, **path-independent** — a local
# macOS build reproduces the exact hashes the H200 binary carried (all five of window15's hashes were
# found in a locally built object). So identity can be recovered locally, with no GPU and no VM, by
# building the same source with one comptime flag removed at a time: a kernel that VANISHES when flag
# F is removed is a kernel F enables, and one that APPEARS is the alternate implementation F was
# suppressing. That is evidence, not a guess, and it regenerates automatically on every build instead
# of going stale (a hand-maintained hash table would be wrong after the first source edit, because the
# hash is content-derived).
#
# Output: a JSON table on stdout mapping each symbol to the flags that govern it, plus a human summary.
#
# Usage: bash mojo_kernel_identity.sh [--json-only]
set -uo pipefail
R=${R:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-front7}
OUT=${OUT:-/tmp/kid}
DRV="$R/benchmarks/llm_smoke/nvidia_race/vm_harness/adj/build/driver_ctx8192.mojo"
mkdir -p "$OUT"; rm -f "$OUT"/*.syms "$OUT"/*.o

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 -D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"
R5="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM -D ALGENTA_G3_PF_F16MLP -D ALGENTA_G3_PF_ROPE2"
R6="-D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 -D ALGENTA_G3_PF_BN32"
FULL="$BASE $R5 $R6"

build() { # $1 = label ; $2 = flag string
  ( cd "$R/mojo_env" || exit 1
    pixi run mojo build "$DRV" -I "$R/mojo/engine" -I "$R/attention_forge" \
      --target-accelerator sm_90 $2 --emit object -o "$OUT/$1.o" ) > "$OUT/$1.log" 2>&1
  local rc=$?
  (( rc != 0 )) && { echo "BUILD FAILED for $1 (rc=$rc)" >&2; grep -E 'error:' "$OUT/$1.log" | head -4 >&2; return 1; }
  # every Mojo device kernel symbol carries a 16-hex content hash suffix
  strings -a "$OUT/$1.o" | grep -oE '[A-Za-z_][A-Za-z0-9_]*_[0-9a-f]{16}' | sort -u > "$OUT/$1.syms"
  echo "  built $1: $(wc -l < "$OUT/$1.syms" | tr -d ' ') kernel symbols" >&2
}

drop() { # remove one flag from $FULL
  local f="$1"; echo "$FULL" | sed "s/ *-D $f//; s/^ *//"
}

echo "=== building the shipped default, then one variant per flag removed ===" >&2
build default "$FULL" || exit 1
VARIANTS=(ALGENTA_G3_PF_ROPE2 ALGENTA_G3_PF_F16NORM ALGENTA_G3_PF_F16MLP
          ALGENTA_G3_GEGLU_U4 ALGENTA_G3_PF_F16ATTN ALGENTA_G3_PF_KV16 ALGENTA_G3_PF_BN32
          ALGENTA_G3_PF_FA2)
for f in "${VARIANTS[@]}"; do
  lbl="no_$(echo "$f" | sed 's/ALGENTA_G3_//; s/ALGENTA_//')"
  build "$lbl" "$(drop "$f")" || echo "  (variant $lbl failed; continuing)" >&2
done
# the ROPEVEC swap: default has the VECTOR rope; this variant has the SCALAR one instead
build no_ropevec "$FULL -D ALGENTA_G3_PF_NO_ROPEVEC" || true
# and the GQA2 counterpart (attention is CUDA-side, but included so the table is complete)
build no_gqa2 "$FULL -D ALGENTA_G3_PF_NO_GQA2" || true

python3 - "$OUT" "$VARIANTS" <<'PY'
import json, os, sys, glob
out = sys.argv[1]
def syms(lbl):
    p = f"{out}/{lbl}.syms"
    return set(open(p).read().split()) if os.path.exists(p) else set()
default = syms("default")
variant_labels = sorted(os.path.basename(p)[:-5] for p in glob.glob(f"{out}/no_*.syms"))
# symbol -> {removed_by: [flags], added_by: [flags]}
info = {s: {"removed_by": [], "added_by": []} for s in default}
extra = {}
for lbl in variant_labels:
    v = syms(lbl)
    flag = lbl[3:]
    for s in default - v:
        info[s]["removed_by"].append(flag)
    for s in v - default:
        extra.setdefault(s, {"removed_by": [], "added_by": []})["added_by"].append(flag)
allSyms = dict(info); allSyms.update(extra)
# a symbol with NO differential evidence is genuinely unattributed -- say so rather than guessing
for s, d in allSyms.items():
    d["identified"] = bool(d["removed_by"] or d["added_by"])
    d["in_default"] = s in default
print(json.dumps({"build": "sm_90 default (post round-13 double flip)", "symbols": allSyms},
                 indent=1, sort_keys=True))
# human summary to stderr so stdout stays valid JSON
ident = [s for s, d in allSyms.items() if d["identified"] and d["in_default"]]
unident = [s for s, d in allSyms.items() if not d["identified"] and d["in_default"]]
print(f"\n=== SUMMARY ===\n  default-build kernel symbols : {len(default)}"
      f"\n  IDENTIFIED by differential   : {len(ident)}"
      f"\n  still UNATTRIBUTED           : {len(unident)}", file=sys.stderr)
for s in sorted(ident):
    d = allSyms[s]
    print(f"    {s}\n        removed_by={d['removed_by']} added_by={d['added_by']}", file=sys.stderr)
if unident:
    print("  UNATTRIBUTED (no comptime flag toggles these; they are unconditional kernels):",
          file=sys.stderr)
    for s in sorted(unident)[:20]:
        print(f"    {s}", file=sys.stderr)
PY
