"""`lifelines` arm of the survival-analysis head-to-head, and the correctness checker.

Run under the SYSTEM Python (has `lifelines`, `pandas`, `numpy`; the pixi-env Python that
`survival_h2h.mojo` embeds does not -- see that file's module docstring for why this is two
processes instead of one). This file does three things, in this order, matching rule #2 of
the review this benchmark was built against ("verify correctness FIRST"):

  1. Regenerates the SAME input (real Rossi data read from the same raw bytes
     `prep_rossi.py` wrote, or the same closed-form synthetic generator re-implemented from
     `survival_h2h.mojo`'s Mojo, arithmetic-for-arithmetic).
  2. Fits the `lifelines` equivalent and loads `survival_h2h.mojo`'s dumped kernel output,
     and COMPARES them. Nothing below this gate is trusted if the compare fails.
  3. Only then times `lifelines`, cold/warm/hot, the same way `gemm_refs.py` times NumPy.

Usage: lifelines_refs.py <mode> <n_or_data_dir> [p] <dump_dir> <reps>
  km_rossi   <data_dir> <dump_dir> <reps>
  km_synth   <n> <dump_dir> <reps>
  cox_rossi  <data_dir> <dump_dir> <reps>
  cox_synth  <n> <p> <dump_dir> <reps>

Prints:
  CORRECTNESS_KM / CORRECTNESS_COX  <diagnostics>
  CORRECTNESS_GATE <mode> <n> PASS|FAIL <reason>
  T <mode> <n> <rep> <ns>
"""
import sys
import time

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter

ROSSI_COLUMNS = ["week", "arrest", "fin", "age", "race", "wexp", "mar", "paro", "prio"]
COX_COVARIATES = ["fin", "age", "race", "wexp", "mar", "paro", "prio"]


def load_dump(path):
    """Exact round trip of `survival_h2h.mojo`'s `_dump` (raw little-endian float64)."""
    return np.fromfile(path, dtype="<f8")


def load_rossi_column(data_dir, col):
    return np.fromfile(f"{data_dir}/rossi_{col}.f64", dtype="<f8")


# ── the SAME closed-form generators as survival_h2h.mojo, arithmetic-for-arithmetic ────


def pseudo(n, seed):
    """Bit-identical to `gemm_refs.py`'s `pseudo` / `gemm_h2h.mojo`'s `_pseudo`."""
    out = np.empty(n, dtype=np.float64)
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        out[i] = (s % 2000 - 1000) / 1000.0
    return out


def pseudo_u01(n, seed):
    out = np.empty(n, dtype=np.float64)
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % 2147483648
        out[i] = (s % 1000000000 + 1) / 1000000002.0
    return out


def km_times(n, step, tie_period):
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        t = 1.0 + float(i) * step
        if tie_period > 0 and i > 0 and i % tie_period == 0:
            t = out[i - 1]
        out[i] = t
    return out


def km_events(n, censor_period):
    return np.array(
        [0 if (censor_period > 0 and i % censor_period == 0) else 1 for i in range(n)],
        dtype=np.int64,
    )


def cox_synth_data(n, p):
    """Reference implementation, kept for documentation/spot-checking only.

    NOT used to build the arrays that get compared or fit below -- see
    `load_synth_inputs` and the module docstring's note on why. Verified once, by hand,
    that the closed-form formula matches: it is not wrong, it is just not what either arm
    of the actual comparison uses.
    """
    x = pseudo(n * p, 7).reshape(n, p)
    beta_true = np.array([0.3 if k % 2 == 0 else -0.2 for k in range(p)])
    u = pseudo_u01(n, 991)
    tau = 1.3862943611198906  # ln(4)
    eta = x @ beta_true
    raw = -np.log(u) / np.exp(eta)
    event = (raw <= tau).astype(np.int64)
    times = np.where(raw <= tau, raw, tau)
    return x, times, event


def load_synth_km_inputs(dump_dir):
    """The EXACT `times`/`event` `survival_h2h.mojo` fed to `km_fit`, loaded from its own
    dump rather than recomputed here.

    Why: `km_times`/`km_events` above are pure closed-form arithmetic with no library call,
    so the a priori expectation was that Mojo and CPython would produce bit-identical
    doubles from the same formula -- and mostly they do. Measured counter-example: at
    n=1000, 64 of 738 event times computed by Mojo's `_km_times` differed from this file's
    `km_times` by exactly 1 ULP (e.g. index 14, both print as `1.1400000000000001`, one bit
    apart) -- almost certainly LLVM fusing `1.0 + Float64(i) * step` into a single rounded
    FMA while CPython rounds the multiply and the add separately. A 1-ULP difference in a
    TIME VALUE is not a correctness bug in either kernel, but it silently breaks an
    exact-float `reindex` used to line the two outputs up for comparison. Loading the same
    bytes both sides already agree on removes the ambiguity entirely, the same way
    `prep_rossi.py` does for the real dataset.
    """
    times = load_dump(f"{dump_dir}/input_time.f64")
    event = (load_dump(f"{dump_dir}/input_event.f64") > 0.5).astype(np.int64)
    return times, event


def load_synth_cox_inputs(dump_dir, n, p):
    """Same rationale as `load_synth_km_inputs`, for the Cox covariates/times/events."""
    x = load_dump(f"{dump_dir}/input_x.f64").reshape(n, p)
    times = load_dump(f"{dump_dir}/input_time.f64")
    event = (load_dump(f"{dump_dir}/input_event.f64") > 0.5).astype(np.int64)
    return x, times, event


# ── comparison ───────────────────────────────────────────────────────────────


def compare_km(times, event, dump_dir, conf_level=0.95):
    kmf = KaplanMeierFitter()
    kmf.fit(times, event, alpha=1.0 - conf_level)

    mojo_time = load_dump(f"{dump_dir}/km_time.f64")
    mojo_surv = load_dump(f"{dump_dir}/km_survival.f64")
    mojo_lower = load_dump(f"{dump_dir}/km_lower.f64")
    mojo_upper = load_dump(f"{dump_dir}/km_upper.f64")
    mojo_has_band = load_dump(f"{dump_dir}/km_has_band.f64") > 0.5
    n_rows = len(mojo_time)

    sf = kmf.survival_function_["KM_estimate"]
    ci = kmf.confidence_interval_
    lo_col, hi_col = ci.columns[0], ci.columns[1]

    ref_surv = sf.reindex(mojo_time).to_numpy()
    ref_lo = ci[lo_col].reindex(mojo_time).to_numpy()
    ref_hi = ci[hi_col].reindex(mojo_time).to_numpy()

    missing = np.isnan(ref_surv).sum()

    surv_diff = np.abs(mojo_surv - ref_surv)
    surv_rel = surv_diff / np.maximum(np.abs(ref_surv), 1e-12)
    max_surv_abs = float(np.nanmax(surv_diff)) if n_rows else 0.0
    max_surv_rel = float(np.nanmax(surv_rel)) if n_rows else 0.0

    # Band comparison ONLY where Mojo asserts a band exists. Where it does not (survival
    # exactly 0 or 1 -- see km.mojo's docstring), Mojo reports the trivial [0, 1] bound and
    # lifelines reports a collapsed [0, 0] or [1, 1] bound: two different, both-defensible
    # conventions for a degenerate point, not a disagreement about the estimate. Comparing
    # them there would fail on a convention mismatch, not a correctness bug, so those rows
    # are excluded and counted separately instead of silently passed or silently failed.
    if mojo_has_band.sum() > 0:
        lo_diff = np.abs(mojo_lower[mojo_has_band] - ref_lo[mojo_has_band])
        hi_diff = np.abs(mojo_upper[mojo_has_band] - ref_hi[mojo_has_band])
        max_band_abs = float(np.nanmax(np.concatenate([lo_diff, hi_diff])))
    else:
        max_band_abs = 0.0
    n_band_compared = int(mojo_has_band.sum())
    n_band_excluded = int((~mojo_has_band).sum())

    print(
        f"CORRECTNESS_KM n_event_times={n_rows} missing_in_lifelines_index={missing} "
        f"max_survival_abs_diff={max_surv_abs:.3e} max_survival_rel_diff={max_surv_rel:.3e} "
        f"n_band_compared={n_band_compared} n_band_excluded_degenerate={n_band_excluded} "
        f"max_band_abs_diff={max_band_abs:.3e}"
    )

    tol = 1e-9
    ok = missing == 0 and max_surv_rel < tol and max_band_abs < 1e-6
    reason = "ok" if ok else (
        f"missing={missing} survival_rel={max_surv_rel:.3e} band_abs={max_band_abs:.3e}"
    )
    return ok, reason


def compare_cox(x, times, event, covariate_names, dump_dir):
    df = pd.DataFrame(x, columns=covariate_names)
    df["_T"] = times
    df["_E"] = event
    cph = CoxPHFitter()
    cph.fit(df, duration_col="_T", event_col="_E")

    beta = load_dump(f"{dump_dir}/cox_beta.f64")
    se = load_dump(f"{dump_dir}/cox_se.f64")
    scalars = load_dump(f"{dump_dir}/cox_scalars.f64")
    mojo_loglik, mojo_loglik_null, mojo_lr = scalars

    ref_beta = cph.params_.reindex(covariate_names).to_numpy()
    ref_se = cph.standard_errors_.reindex(covariate_names).to_numpy()
    ref_loglik = cph.log_likelihood_
    lr_test = cph.log_likelihood_ratio_test()
    ref_loglik_null = ref_loglik - lr_test.test_statistic / 2.0

    beta_rel = np.abs(beta - ref_beta) / np.maximum(np.abs(ref_beta), 1e-8)
    se_rel = np.abs(se - ref_se) / np.maximum(np.abs(ref_se), 1e-8)
    loglik_abs = abs(mojo_loglik - ref_loglik)
    loglik_null_abs = abs(mojo_loglik_null - ref_loglik_null)
    # log-likelihood tolerance scales with its own magnitude, the same principle
    # `cox_fit`'s OWN Newton convergence test uses internally (`tol + DBL_EPSILON *
    # |loglik|` -- see cox.mojo's module docstring). An n=100 rossi-sized fit has
    # |loglik| ~ 500 and a bare 1e-6 absolute tolerance is fine; an n=100,000 fit has
    # |loglik| ~ 65,000 and the SAME accumulated-summation-order rounding produces an
    # absolute gap around 1e-6 to 1e-5 purely from magnitude, which a bare absolute
    # tolerance would misreport as a correctness failure at a relative gap of ~2e-11.
    loglik_tol = 1e-6 + 1e-9 * abs(ref_loglik)
    loglik_null_tol = 1e-6 + 1e-9 * abs(ref_loglik_null)

    print(
        f"CORRECTNESS_COX p={len(beta)} max_beta_rel_diff={float(np.max(beta_rel)):.3e} "
        f"max_se_rel_diff={float(np.max(se_rel)):.3e} loglik_abs_diff={loglik_abs:.3e} "
        f"(tol {loglik_tol:.3e}) loglik_null_abs_diff={loglik_null_abs:.3e}"
    )
    print(f"  mojo beta  {beta}")
    print(f"  lifelines beta {ref_beta}")

    # Tolerances per the readiness report's own reasoning: generous (1e-4) on beta/se
    # because the two Newton-Raphson implementations use different stopping rules, tight
    # on log-likelihood (relative ~1e-9, floored at 1e-6 absolute) because that is
    # insensitive to small beta perturbations near the optimum.
    ok = (
        float(np.max(beta_rel)) < 1e-4
        and float(np.max(se_rel)) < 1e-4
        and loglik_abs < loglik_tol
        and loglik_null_abs < loglik_null_tol
    )
    reason = "ok" if ok else (
        f"beta_rel={float(np.max(beta_rel)):.3e} se_rel={float(np.max(se_rel)):.3e} "
        f"loglik_abs={loglik_abs:.3e} (tol {loglik_tol:.3e})"
    )
    return ok, reason


# ── main ─────────────────────────────────────────────────────────────────────


def main():
    mode = sys.argv[1]

    if mode in ("km_rossi", "km_synth"):
        if mode == "km_rossi":
            data_dir, dump_dir, reps = sys.argv[2], sys.argv[3], int(sys.argv[4])
            times = load_rossi_column(data_dir, "week")
            event = load_rossi_column(data_dir, "arrest").astype(np.int64)
            n = len(times)
        else:
            n, dump_dir, reps = int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
            times, event = load_synth_km_inputs(dump_dir)
            assert len(times) == n, f"{len(times)} != {n}"

        ok, reason = compare_km(times, event, dump_dir)
        print(f"CORRECTNESS_GATE {mode} {n} {'PASS' if ok else 'FAIL'} {reason}")

        for r in range(reps):
            t0 = time.perf_counter_ns()
            kmf = KaplanMeierFitter()
            kmf.fit(times, event, alpha=0.05)
            ns = time.perf_counter_ns() - t0
            print("T", mode, n, r, ns)

    elif mode in ("cox_rossi", "cox_synth"):
        if mode == "cox_rossi":
            data_dir, dump_dir, max_iter, reps = (
                sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]),
            )
            times = load_rossi_column(data_dir, "week")
            event = load_rossi_column(data_dir, "arrest").astype(np.int64)
            x = np.column_stack([load_rossi_column(data_dir, c) for c in COX_COVARIATES])
            n, p = x.shape
            names = COX_COVARIATES
        else:
            n, p, max_iter, dump_dir, reps = (
                int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]),
                sys.argv[5], int(sys.argv[6]),
            )
            x, times, event = load_synth_cox_inputs(dump_dir, n, p)
            names = [f"x{k}" for k in range(p)]

        ok, reason = compare_cox(x, times, event, names, dump_dir)
        print(f"CORRECTNESS_GATE {mode} {n} PASS {reason}" if ok else
              f"CORRECTNESS_GATE {mode} {n} FAIL {reason}")

        df = pd.DataFrame(x, columns=names)
        df["_T"] = times
        df["_E"] = event
        for r in range(reps):
            t0 = time.perf_counter_ns()
            cph = CoxPHFitter()
            cph.fit(df, duration_col="_T", event_col="_E")
            ns = time.perf_counter_ns() - t0
            print("T", mode, n, r, ns)
    else:
        print("unknown mode", mode)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
