#!/usr/bin/env python3
"""check_bitident_gemma3_round18.py -- is the LEVER arm's generated token stream BIT-IDENTICAL to
the CONTROL arm's, cell for cell?  argv: <meas_dir> <arm_a> <arm_b>

WHY THIS EXISTS AS ITS OWN CHECK, when the fp32-oracle gate already passed. Round 18's lever
(`-D ALGENTA_G3_PF_GEGLU_V2`, the vectorised f16 prefill GeGLU twin) claims something ROPEVEC and
LTALGO could not: that it is **bit-identical to the control**, not merely in agreement with the
oracle. GeGLU is purely elementwise -- no reduction, no accumulation, no cross-element data
movement -- so there is no association order for a vectorised twin to disturb, and
`_g3_geglu_f16_elem` is the scalar twin's body transposed verbatim. The CPU-side evidence for that
is a PTX-body differential (the per-element instruction sequence, 8x, with the same four f32
immediates) plus a lane-order proof against `cuda_fp16.hpp`'s own `cvt.rn.f16x2.f32` operand
convention. This script is the VM-side half: it compares the two arms' ACTUAL OUTPUTS.

It is strictly stronger than the gate, and it is nearly free. The gate compares each arm to the
oracle; two arms can both match a 64-token oracle prefix and still differ at token 65. This
compares the arms to EACH OTHER, over every cell both ran -- including the bracket's rag4096 cells
at --max-new 256, which the bracket was going to produce anyway. So a "100% BITIDENT over N cells
and M tokens" line here is evidence the gate cannot supply.

A single BITDIFF falsifies the construction argument. It would not make the lever WRONG (the oracle
gate is the correctness authority) but it would demote the claim from "exact" to "oracle-certified",
i.e. to ROPEVEC's class, and the ledger would have to say so. That is why the count is computed
rather than assumed, and why a non-zero BITDIFF exits non-zero.

Cells are paired two ways, because the two stages name their outputs differently:
  * the timing/smoke stage writes ONE shared runs dir with the arm name INSIDE the label
    (r6<tag>_<arm>_<prompt>_r<i>.out), so the twin is the same path with arm_a -> arm_b;
  * the gate stage writes a PER-ARM dir ($MEAS/gate_<arm>/) whose files do NOT carry the arm name,
    so the twin is the same filename under the other arm's dir.
A cell with no twin is reported NOT-COMPARED rather than silently skipped or silently passed.
"""

import json
import sys
from pathlib import Path

MEAS = Path(sys.argv[1])
A = sys.argv[2]
B = sys.argv[3]


def last_generated(path):
    """The driver's JSON result line: the LAST line carrying "generated", same rule gate_any.py
    uses, so the two scripts can never disagree about what a cell produced."""
    if not path.exists():
        return None
    found = None
    for line in reversed(path.read_text(errors="replace").splitlines()):
        line = line.strip()
        if line.startswith("{") and '"generated"' in line:
            d = json.loads(line) if _is_json(line) else None
            if d is not None and d.get("generated") is not None:
                found = d["generated"]
                break
    return found


def _is_json(line):
    """json.loads without the bare `except: continue` -- a truncated result line (a cell the
    watchdog killed mid-write) is EXPECTED here, not an error, but it must not be swallowed
    silently in a way that also swallows a real parse bug."""
    try:
        json.loads(line)
    except ValueError:
        return False
    return True


pairs = []  # (label, path_a, path_b)
# 1. shared runs dir: the arm name is inside the label
for d in (MEAS / "runs", MEAS):
    if not d.is_dir():
        continue
    for p in sorted(d.glob("*.out")):
        if f"_{A}_" not in p.name and not p.name.startswith(f"{A}_"):
            continue
        twin = p.with_name(p.name.replace(A, B))
        pairs.append((p.name[:-4], p, twin))
    if d == MEAS / "runs":
        break
# 2. per-arm gate dirs: the arm name is the directory
ga, gb = MEAS / f"gate_{A}", MEAS / f"gate_{B}"
if ga.is_dir() and gb.is_dir():
    for p in sorted(ga.glob("*.out")):
        pairs.append((f"gate/{p.name[:-4]}", p, gb / p.name))

if not pairs:
    print(f"NO COMPARABLE CELLS found for {A} vs {B} under {MEAS}")
    print("  (expected label shapes: r6*_<arm>_<prompt>_*.out in runs/, or gate_<arm>/*.out)")
    print("NOT-COMPARED -- this is INCONCLUSIVE, not a pass")
    sys.exit(2)

ident = diff = notrun = 0
tot_tok = 0
print(f"=== BITIDENT {A} (control) vs {B} (lever) ===")
print(f"{'verdict':>11} {'n_tok':>6}  cell")
print("-" * 96)
for label, pa, pb in pairs:
    ta, tb = last_generated(pa), last_generated(pb)
    if ta is None or tb is None:
        notrun += 1
        miss = A if ta is None else B
        print(f"{'NOT-COMPARED':>11} {'-':>6}  {label}  (no 'generated' from {miss})")
        continue
    n = min(len(ta), len(tb))
    tot_tok += n
    if ta == tb:
        ident += 1
        print(f"{'BITIDENT':>11} {n:>6}  {label}")
    else:
        diff += 1
        fd = next((i for i in range(n) if ta[i] != tb[i]), None)
        fd = fd if fd is not None else n
        print(
            f"{'BITDIFF':>11} {n:>6}  {label}  first_diff@{fd} "
            f"{A}={ta[fd] if fd < len(ta) else None} {B}={tb[fd] if fd < len(tb) else None}"
            + ("  LEN-DIFFERS" if len(ta) != len(tb) else "")
        )
print("-" * 96)
print(f"BITIDENT {ident}   BITDIFF {diff}   NOT-COMPARED {notrun}   tokens compared {tot_tok}")
if diff == 0 and ident > 0 and notrun == 0:
    print(f"VERDICT: 100% BITIDENT over {ident} cell(s) / {tot_tok} token(s).")
    print("         The vectorised twin reproduces the scalar twin's output EXACTLY, which is the")
    print("         claim its construction makes: elementwise only, no reduction to re-associate.")
    sys.exit(0)
if diff == 0 and ident > 0:
    print(f"VERDICT: 0 BITDIFF over {ident} compared cell(s), but {notrun} NOT-COMPARED.")
    print("         Bit-identity HOLDS on everything comparable; uncovered cells are named above.")
    sys.exit(0)
if diff > 0:
    print("VERDICT: BITDIFF PRESENT. The 'bit-identical by construction' claim is FALSIFIED")
    print("         for these cells. The lever is not thereby wrong -- the fp32-oracle gate is")
    print("         still the correctness authority -- but it must be reported as oracle-")
    print("         certified rather than exact, i.e. demoted to ROPEVEC's class, and the ledger")
    print("         must say so.")
    sys.exit(1)
print("VERDICT: nothing comparable ran. INCONCLUSIVE, not a pass.")
sys.exit(2)
