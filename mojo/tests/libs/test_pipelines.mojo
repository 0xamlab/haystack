"""test_pipelines.mojo — known-value tests for pipelines."""
from std.math import abs as fabs, isnan

from pipelines import (
    PipelineState,
    InverseResult,
    pipeline_fit,
    pipeline_transform,
    pipeline_inverse,
    pipeline_is_invertible,
    step_param_count,
)


fn _close(a: Float64, b: Float64) -> Bool:
    return fabs(a - b) <= 1e-12


fn _close_tol(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


fn _lists_close(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if fabs(a[i] - b[i]) > tol:
            return False
    return True


fn check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ pipelines::" + name)
    else:
        failed += 1
        print("  ❌ pipelines::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    var nanv = Float64(0.0) / Float64(0.0)

    # Hand data: X = [[1,2],[3,4],[5,6]], rows=3, cols=2 (row-major flat).
    var x6 = List[Float64]()
    x6.append(1.0); x6.append(2.0)
    x6.append(3.0); x6.append(4.0)
    x6.append(5.0); x6.append(6.0)
    var no_params = List[Float64]()

    # ── standardize: hand-computed mean / population std ─────────────────────
    # col0: mean 3, std = sqrt(((-2)^2 + 0 + 2^2)/3) = sqrt(8/3)
    #     = 1.6329931618554518; col1: mean 4, same std.
    # z col0 = [-1.224744871391589, 0, 1.224744871391589] (= ±sqrt(3/2)).
    var steps_std = List[Int]()
    steps_std.append(0)
    var st = pipeline_fit(x6, 3, 2, steps_std, no_params)
    check(st.ok, "fit standardize ok", passed, failed)
    check(
        len(st.learned) == 4
        and _close(st.learned[0], 3.0)
        and _close(st.learned[1], 4.0)
        and _close(st.learned[2], 1.6329931618554518)
        and _close(st.learned[3], 1.6329931618554518),
        "standardize learned [mean0,mean1,std0,std1] exact",
        passed,
        failed,
    )
    var z = pipeline_transform(st, x6, 3)
    var z_expect = List[Float64]()
    z_expect.append(-1.224744871391589); z_expect.append(-1.224744871391589)
    z_expect.append(0.0); z_expect.append(0.0)
    z_expect.append(1.224744871391589); z_expect.append(1.224744871391589)
    check(
        _lists_close(z, z_expect, 1e-12),
        "standardize transform hand values",
        passed,
        failed,
    )

    # ── standardize -> minmax chain: exact hand-computed values ──────────────
    # minmax fits on the z-scores: min = -1.2247..., max = +1.2247... per col,
    # so the chained output is exactly [0, 0, 0.5, 0.5, 1, 1]:
    # (z - min)/(max - min) with symmetric min/max gives 0, 0.5, 1 exactly
    # in binary FP (0/rng = 0, rng/rng = 1, a/(a+a) = 0.5).
    var steps_chain = List[Int]()
    steps_chain.append(0)
    steps_chain.append(1)
    var ch = pipeline_fit(x6, 3, 2, steps_chain, no_params)
    check(
        ch.ok and len(ch.offsets) == 2 and ch.offsets[0] == 0
        and ch.offsets[1] == 4 and len(ch.learned) == 8,
        "chain state offsets/learned layout",
        passed,
        failed,
    )
    check(
        _close(ch.learned[4], -1.224744871391589)
        and _close(ch.learned[6], 1.224744871391589),
        "chain minmax fitted on standardized data (min0/max0 = -/+ z)",
        passed,
        failed,
    )
    var u = pipeline_transform(ch, x6, 3)
    check(
        len(u) == 6
        and u[0] == 0.0 and u[1] == 0.0
        and u[2] == 0.5 and u[3] == 0.5
        and u[4] == 1.0 and u[5] == 1.0,
        "standardize->minmax chain exact [0,0,0.5,0.5,1,1]",
        passed,
        failed,
    )

    # ── chain on unseen data: hand value ─────────────────────────────────────
    # new row [7,8]: z0 = (7-3)/sqrt(8/3) = 2.449489742783178;
    # minmax: (2.4494... + 1.2247...)/2.4494... = 1.5 for both columns.
    var xnew = List[Float64]()
    xnew.append(7.0); xnew.append(8.0)
    var unew = pipeline_transform(ch, xnew, 1)
    check(
        len(unew) == 2
        and _close(unew[0], 1.5)
        and _close(unew[1], 1.5),
        "chain transform unseen row [7,8] -> [1.5, 1.5]",
        passed,
        failed,
    )

    # ── inverse round-trips the chain ────────────────────────────────────────
    check(pipeline_is_invertible(ch), "chain [0,1] is invertible", passed, failed)
    var inv = pipeline_inverse(ch, u, 3)
    check(
        inv.ok and _lists_close(inv.data, x6, 1e-9),
        "chain inverse round-trips training data",
        passed,
        failed,
    )
    var invnew = pipeline_inverse(ch, unew, 1)
    check(
        invnew.ok and _close_tol(invnew.data[0], 7.0, 1e-9)
        and _close_tol(invnew.data[1], 8.0, 1e-9),
        "chain inverse round-trips unseen row",
        passed,
        failed,
    )

    # ── log1p: hand values, round-trip, domain -> NaN ────────────────────────
    # x = [0,1,3]: log1p -> [0, log 2 = 0.6931471805599453,
    #                         log 4 = 1.3862943611198906]
    var xlog = List[Float64]()
    xlog.append(0.0); xlog.append(1.0); xlog.append(3.0)
    var steps_log = List[Int]()
    steps_log.append(2)
    var sl = pipeline_fit(xlog, 3, 1, steps_log, no_params)
    var yl = pipeline_transform(sl, xlog, 3)
    check(
        sl.ok and len(yl) == 3
        and _close(yl[0], 0.0)
        and _close(yl[1], 0.6931471805599453)
        and _close(yl[2], 1.3862943611198906),
        "log1p hand values [0, log2, log4]",
        passed,
        failed,
    )
    # (1e-9 tolerance: this repo's std.math exp/log are approximations with
    # ~1e-10 relative error away from exact powers of two.)
    var invl = pipeline_inverse(sl, yl, 3)
    check(
        invl.ok and _lists_close(invl.data, xlog, 1e-9),
        "log1p inverse (expm1) round-trips",
        passed,
        failed,
    )
    var xbad = List[Float64]()
    xbad.append(-2.0); xbad.append(0.5); xbad.append(nanv)
    var ybad = pipeline_transform(sl, xbad, 3)
    check(
        len(ybad) == 3 and isnan(ybad[0])
        and _close_tol(ybad[1], 0.4054651081081644, 1e-9)
        and isnan(ybad[2]),
        "log1p: 1+x<=0 -> NaN, NaN passes through, log(1.5) value",
        passed,
        failed,
    )

    # ── impute_median: NaN filled with per-column median ─────────────────────
    # rows=4 cols=2 flat: col0 = [NaN,2,4,10] -> median 4 (odd count 3);
    # col1 = [1,5,NaN,NaN] -> median (1+5)/2 = 3 (even-count average).
    var ximp = List[Float64]()
    ximp.append(nanv); ximp.append(1.0)
    ximp.append(2.0);  ximp.append(5.0)
    ximp.append(4.0);  ximp.append(nanv)
    ximp.append(10.0); ximp.append(nanv)
    var steps_imp = List[Int]()
    steps_imp.append(4)
    var si = pipeline_fit(ximp, 4, 2, steps_imp, no_params)
    check(
        si.ok and len(si.learned) == 2
        and _close(si.learned[0], 4.0)
        and _close(si.learned[1], 3.0),
        "impute_median learned medians [4, 3] (odd + even-count)",
        passed,
        failed,
    )
    var yi = pipeline_transform(si, ximp, 4)
    var yi_expect = List[Float64]()
    yi_expect.append(4.0);  yi_expect.append(1.0)
    yi_expect.append(2.0);  yi_expect.append(5.0)
    yi_expect.append(4.0);  yi_expect.append(3.0)
    yi_expect.append(10.0); yi_expect.append(3.0)
    check(
        _lists_close(yi, yi_expect, 1e-12),
        "impute_median fills NaN, leaves finite values",
        passed,
        failed,
    )
    # all-NaN column imputes 0.0
    var xallnan = List[Float64]()
    xallnan.append(nanv); xallnan.append(nanv)
    var san = pipeline_fit(xallnan, 2, 1, steps_imp, no_params)
    var yan = pipeline_transform(san, xallnan, 2)
    check(
        san.ok and _close(san.learned[0], 0.0)
        and _close(yan[0], 0.0) and _close(yan[1], 0.0),
        "impute_median all-NaN column -> 0.0",
        passed,
        failed,
    )
    check(
        not pipeline_is_invertible(si) and not pipeline_inverse(si, yi, 4).ok,
        "impute_median not invertible (inverse ok=False)",
        passed,
        failed,
    )

    # ── clip: hyperparams from params flat, hand values ──────────────────────
    var xclip = List[Float64]()
    xclip.append(-5.0); xclip.append(0.25); xclip.append(7.0)
    var steps_clip = List[Int]()
    steps_clip.append(3)
    var pclip = List[Float64]()
    pclip.append(0.0); pclip.append(1.0)
    var sc = pipeline_fit(xclip, 3, 1, steps_clip, pclip)
    var yc = pipeline_transform(sc, xclip, 3)
    check(
        sc.ok and len(sc.learned) == 2
        and _close(sc.learned[0], 0.0) and _close(sc.learned[1], 1.0)
        and _close(yc[0], 0.0) and _close(yc[1], 0.25) and _close(yc[2], 1.0),
        "clip(0,1): [-5,0.25,7] -> [0,0.25,1], bounds stored",
        passed,
        failed,
    )
    var pbad = List[Float64]()
    pbad.append(2.0); pbad.append(1.0)
    check(
        not pipeline_fit(xclip, 3, 1, steps_clip, pbad).ok,
        "clip lo>hi -> ok=False",
        passed,
        failed,
    )
    check(
        not pipeline_fit(xclip, 3, 1, steps_clip, no_params).ok,
        "clip missing params -> ok=False",
        passed,
        failed,
    )
    check(
        not pipeline_is_invertible(sc) and not pipeline_inverse(sc, yc, 3).ok,
        "clip not invertible (inverse ok=False)",
        passed,
        failed,
    )

    # ── full 5-step chain: impute -> log1p -> standardize -> minmax -> clip ──
    var steps_all = List[Int]()
    steps_all.append(4); steps_all.append(2); steps_all.append(0)
    steps_all.append(1); steps_all.append(3)
    var pall = List[Float64]()
    pall.append(0.05); pall.append(0.95)
    var xall = List[Float64]()
    xall.append(0.0); xall.append(1.0); xall.append(nanv)
    xall.append(3.0); xall.append(7.0); xall.append(15.0)
    var sa = pipeline_fit(xall, 6, 1, steps_all, pall)
    var ya = pipeline_transform(sa, xall, 6)
    var all_in_bounds = True
    for i in range(len(ya)):
        if isnan(ya[i]) or ya[i] < 0.05 or ya[i] > 0.95:
            all_in_bounds = False
    check(
        sa.ok and len(ya) == 6 and all_in_bounds,
        "5-step chain runs, output finite and clipped to [0.05,0.95]",
        passed,
        failed,
    )
    check(
        not pipeline_is_invertible(sa),
        "5-step chain not invertible (has clip+impute)",
        passed,
        failed,
    )
    # offsets/learned sizes: impute(1) + log1p(0) + standardize(2) +
    # minmax(2) + clip(2) = 7 learned params for cols=1
    check(
        len(sa.learned) == 7 and len(sa.offsets) == 5
        and sa.offsets[0] == 0 and sa.offsets[1] == 1 and sa.offsets[2] == 1
        and sa.offsets[3] == 3 and sa.offsets[4] == 5,
        "5-step chain learned layout / offsets",
        passed,
        failed,
    )

    # ── degenerate columns round-trip through the defined inverses ───────────
    # n=1 row standardize: std=0 -> z=0; inverse recovers the means.
    var x1 = List[Float64]()
    x1.append(5.0); x1.append(7.0)
    var s1 = pipeline_fit(x1, 1, 2, steps_std, no_params)
    var y1 = pipeline_transform(s1, x1, 1)
    var i1 = pipeline_inverse(s1, y1, 1)
    check(
        s1.ok and _close(y1[0], 0.0) and _close(y1[1], 0.0)
        and i1.ok and _close(i1.data[0], 5.0) and _close(i1.data[1], 7.0),
        "standardize n=1 (std=0) -> 0; inverse recovers means",
        passed,
        failed,
    )
    # all-equal column minmax: range=0 -> 0; inverse recovers the min.
    var xeq = List[Float64]()
    xeq.append(2.0); xeq.append(2.0); xeq.append(2.0)
    var steps_mm = List[Int]()
    steps_mm.append(1)
    var seq_st = pipeline_fit(xeq, 3, 1, steps_mm, no_params)
    var yeq = pipeline_transform(seq_st, xeq, 3)
    var ieq = pipeline_inverse(seq_st, yeq, 3)
    check(
        seq_st.ok and _close(yeq[0], 0.0) and _close(yeq[1], 0.0)
        and _close(yeq[2], 0.0) and ieq.ok
        and _close(ieq.data[0], 2.0) and _close(ieq.data[1], 2.0)
        and _close(ieq.data[2], 2.0),
        "minmax all-equal (range=0) -> 0; inverse recovers min",
        passed,
        failed,
    )

    # ── NaN passes through standardize/minmax; fit stats ignore NaN ──────────
    # col [1, NaN, 3]: mean 2, std = sqrt(((-1)^2 + 1^2)/2) = 1.
    var xnan = List[Float64]()
    xnan.append(1.0); xnan.append(nanv); xnan.append(3.0)
    var snan = pipeline_fit(xnan, 3, 1, steps_std, no_params)
    var ynan = pipeline_transform(snan, xnan, 3)
    check(
        snan.ok and _close(snan.learned[0], 2.0)
        and _close(snan.learned[1], 1.0)
        and _close(ynan[0], -1.0) and isnan(ynan[1]) and _close(ynan[2], 1.0),
        "standardize ignores NaN in fit, passes NaN through",
        passed,
        failed,
    )

    # ── empty spec = identity; invalid specs / shapes rejected ───────────────
    var steps_none = List[Int]()
    var s_id = pipeline_fit(x6, 3, 2, steps_none, no_params)
    var y_id = pipeline_transform(s_id, x6, 3)
    var i_id = pipeline_inverse(s_id, x6, 3)
    check(
        s_id.ok and _lists_close(y_id, x6, 0.0)
        and i_id.ok and _lists_close(i_id.data, x6, 0.0),
        "empty spec: transform and inverse are identity",
        passed,
        failed,
    )
    check(
        not pipeline_fit(x6, 0, 2, steps_std, no_params).ok,
        "rows=0 -> ok=False",
        passed,
        failed,
    )
    check(
        not pipeline_fit(x6, 3, 3, steps_std, no_params).ok,
        "len(x) != rows*cols -> ok=False",
        passed,
        failed,
    )
    var steps_unknown = List[Int]()
    steps_unknown.append(9)
    check(
        not pipeline_fit(x6, 3, 2, steps_unknown, no_params).ok,
        "unknown step id -> ok=False",
        passed,
        failed,
    )
    var wrong_len = List[Float64]()
    wrong_len.append(1.0); wrong_len.append(2.0); wrong_len.append(3.0)
    check(
        len(pipeline_transform(st, wrong_len, 3)) == 0,
        "transform shape mismatch -> empty",
        passed,
        failed,
    )
    var bad_state = PipelineState()
    check(
        len(pipeline_transform(bad_state, x6, 3)) == 0
        and not pipeline_inverse(bad_state, x6, 3).ok
        and not pipeline_is_invertible(bad_state),
        "unfitted state -> empty transform, inverse ok=False",
        passed,
        failed,
    )

    # ── step_param_count ─────────────────────────────────────────────────────
    check(
        step_param_count(0, 3) == 6 and step_param_count(1, 3) == 6
        and step_param_count(2, 3) == 0 and step_param_count(3, 3) == 2
        and step_param_count(4, 3) == 3 and step_param_count(9, 3) == -1,
        "step_param_count per id",
        passed,
        failed,
    )

    print("  [pipelines] Passed:", passed, "Failed:", failed)
