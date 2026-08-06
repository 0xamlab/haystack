"""test_stat_tests_nan_safety_probe.mojo — hand-verified probe for the NaN/Inf-safety
fix (pearson_r_strict / spearman_r_strict), added alongside stat_tests.mojo.

Not an auto-generated suite (tests/generate_mojo_tests.py, under mojo/tests/libs/,
only emits a plain smoke call per function -- it cannot express "call twice and
compare" or "expect a raise"). This hand-written probe proves, against real
NaN/Inf-contaminated data:

  1. `pearson_r`/`spearman_r` (unchanged, frozen) still silently return
     CorrResult(NaN, NaN) for NaN input -- the exact defect the investigation traced.
  2. `pearson_r_strict`/`spearman_r_strict` (new, additive) RAISE on that same input
     instead of returning a garbage-looking answer, and name which list + index.
  3. On clean, non-NaN input, the _strict siblings return EXACTLY the same r and
     p_value as the originals -- no regression on the correct-input path.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine \
    ../tests/mojo/test_stat_tests_nan_safety_probe.mojo
"""
from std.math import isnan, isinf
from stat_tests import pearson_r, spearman_r, pearson_r_strict, spearman_r_strict


def _mk(*values: Float64) -> List[Float64]:
    var out = List[Float64]()
    for v in values:
        out.append(v)
    return out^


def main() raises:
    var passed = 0
    var failed = 0

    # ── clean data: five points, no ties, no NaN ──────────────────────────────
    var cx = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var cy = _mk(2.0, 4.0, 5.0, 4.0, 6.0)

    var base_pearson = pearson_r(cx, cy)
    var strict_pearson = pearson_r_strict(cx, cy)
    if base_pearson.r == strict_pearson.r and base_pearson.p_value == strict_pearson.p_value:
        passed += 1
        print("  ✅ pearson_r_strict matches pearson_r exactly on clean input (r=", base_pearson.r, ")")
    else:
        failed += 1
        print("  ❌ pearson_r_strict DIFFERS from pearson_r on clean input:", base_pearson.r, "vs", strict_pearson.r)

    var base_spear = spearman_r(cx, cy)
    var strict_spear = spearman_r_strict(cx, cy)
    if base_spear.r == strict_spear.r and base_spear.p_value == strict_spear.p_value:
        passed += 1
        print("  ✅ spearman_r_strict matches spearman_r exactly on clean input (rho=", base_spear.r, ")")
    else:
        failed += 1
        print("  ❌ spearman_r_strict DIFFERS from spearman_r on clean input:", base_spear.r, "vs", strict_spear.r)

    # ── NaN-contaminated data: one poisoned element in y ───────────────────────
    var nan_value = Float64(0.0) / Float64(0.0)
    if not isnan(nan_value):
        failed += 1
        print("  ❌ could not synthesize a real NaN (0.0/0.0 was not NaN) — probe is broken")
    else:
        passed += 1
        print("  ✅ synthesized a real IEEE-754 NaN via 0.0/0.0")

    var nx = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var ny = _mk(2.0, 4.0, nan_value, 4.0, 6.0)

    # 1. Confirm the FROZEN function's actual current behavior: silent CorrResult(NaN, NaN).
    var poisoned = pearson_r(nx, ny)
    if isnan(poisoned.r) and isnan(poisoned.p_value):
        passed += 1
        print("  ✅ confirmed: pearson_r(NaN-contaminated) silently returns CorrResult(NaN, NaN) -- the traced defect, left untouched")
    else:
        failed += 1
        print("  ❌ pearson_r on NaN input did not reproduce the traced CorrResult(NaN, NaN) -- investigation trace may be stale:", poisoned.r, poisoned.p_value)

    # 2. Confirm pearson_r_strict RAISES on the exact same input.
    var pearson_raised = False
    var pearson_message = String("")
    try:
        _ = pearson_r_strict(nx, ny)
    except e:
        pearson_raised = True
        pearson_message = String(e)
    if pearson_raised:
        passed += 1
        print("  ✅ pearson_r_strict RAISED on NaN-contaminated input:", pearson_message)
    else:
        failed += 1
        print("  ❌ pearson_r_strict did NOT raise on NaN-contaminated input -- fix did not fire")

    # Confirm the raised message actually names list "y" and index 2 (0-based), as designed.
    if pearson_raised and "y[2]" in pearson_message:
        passed += 1
        print("  ✅ pearson_r_strict's error names the offending list+index (y[2])")
    else:
        failed += 1
        print("  ❌ pearson_r_strict's error did not name y[2] as expected:", pearson_message)

    # 3. Confirm spearman_r_strict RAISES on the exact same input.
    var spear_raised = False
    var spear_message = String("")
    try:
        _ = spearman_r_strict(nx, ny)
    except e:
        spear_raised = True
        spear_message = String(e)
    if spear_raised:
        passed += 1
        print("  ✅ spearman_r_strict RAISED on NaN-contaminated input:", spear_message)
    else:
        failed += 1
        print("  ❌ spearman_r_strict did NOT raise on NaN-contaminated input -- fix did not fire")

    if spear_raised and "y[2]" in spear_message:
        passed += 1
        print("  ✅ spearman_r_strict's error names the offending list+index (y[2])")
    else:
        failed += 1
        print("  ❌ spearman_r_strict's error did not name y[2] as expected:", spear_message)

    # ── +Inf case, in x this time, to prove both lists and both non-finite kinds work ──
    var inf_value = Float64(1.0) / Float64(0.0)
    if not isinf(inf_value):
        failed += 1
        print("  ❌ could not synthesize a real +Inf (1.0/0.0) — probe is broken")
    else:
        passed += 1
        print("  ✅ synthesized a real IEEE-754 +Inf via 1.0/0.0")

    var ix = _mk(1.0, inf_value, 3.0, 4.0, 5.0)
    var iy = _mk(2.0, 4.0, 5.0, 4.0, 6.0)

    var inf_pearson_raised = False
    var inf_pearson_message = String("")
    try:
        _ = pearson_r_strict(ix, iy)
    except e:
        inf_pearson_raised = True
        inf_pearson_message = String(e)
    if inf_pearson_raised and "x[1]" in inf_pearson_message:
        passed += 1
        print("  ✅ pearson_r_strict RAISED on +Inf in x, naming x[1]:", inf_pearson_message)
    else:
        failed += 1
        print("  ❌ pearson_r_strict did not raise/name correctly for +Inf in x:", inf_pearson_message)

    # ── mismatched lengths: two independently-filtered columns, same values shorter ──
    var mx = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var my_short = _mk(2.0, 4.0, 5.0)

    # 1. Confirm the FROZEN function's actual current behavior: it does not raise or
    #    crash on mismatched lengths, it silently returns SOME finite-looking answer
    #    (computed from `_mean` over each list's FULL length, but a covariance loop
    #    bounded to only the first min(len(x), len(y)) entries of each -- a real,
    #    distinct misalignment trap, separate from the NaN case above, and NOT the
    #    same number a caller who pre-truncated mx to len 3 would get, since `_mean`
    #    doesn't truncate even though the covariance loop does).
    var truncated = pearson_r(mx, my_short)
    if not isnan(truncated.r) and not isinf(truncated.r):
        passed += 1
        print("  ✅ confirmed: pearson_r on mismatched lengths silently returns a finite (not NaN/raise/crash) answer -- the traced misalignment trap, left untouched (r=", truncated.r, ")")
    else:
        failed += 1
        print("  ❌ pearson_r on mismatched lengths did not reproduce the traced silent-finite-answer behavior:", truncated.r)

    # 2. Confirm pearson_r_strict RAISES on the same mismatched-length input, before
    #    ever reaching the NaN/Inf check (there is no NaN here at all -- length alone
    #    must be enough to raise).
    var len_pearson_raised = False
    var len_pearson_message = String("")
    try:
        _ = pearson_r_strict(mx, my_short)
    except e:
        len_pearson_raised = True
        len_pearson_message = String(e)
    if len_pearson_raised and "5" in len_pearson_message and "3" in len_pearson_message:
        passed += 1
        print("  ✅ pearson_r_strict RAISED on mismatched lengths (5 vs 3):", len_pearson_message)
    else:
        failed += 1
        print("  ❌ pearson_r_strict did NOT raise correctly on mismatched lengths:", len_pearson_message)

    # 3. Same check for spearman_r_strict.
    var len_spear_raised = False
    var len_spear_message = String("")
    try:
        _ = spearman_r_strict(mx, my_short)
    except e:
        len_spear_raised = True
        len_spear_message = String(e)
    if len_spear_raised and "5" in len_spear_message and "3" in len_spear_message:
        passed += 1
        print("  ✅ spearman_r_strict RAISED on mismatched lengths (5 vs 3):", len_spear_message)
    else:
        failed += 1
        print("  ❌ spearman_r_strict did NOT raise correctly on mismatched lengths:", len_spear_message)

    print("  [test_stat_tests_nan_safety_probe] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_stat_tests_nan_safety_probe: " + String(failed) + " check(s) failed")
