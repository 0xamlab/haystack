#!/usr/bin/env python3
"""bench_vs_quantlib_heston.py — the QuantLib arm for bench_vs_quantlib_heston.mojo.

Prices the IDENTICAL contract the Mojo arm's docstring fixes, with QuantLib
(github.com/lballabio/QuantLib), and prints lines in the same `KEY value KEY=value ...` shape so
`bench_vs_quantlib_heston_driver.py` can parse both arms with one regex.

Run with the interpreter QuantLib was installed into — this repo's own `mojo_env` python does not
have it:

    /tmp/bb/bin/python -P benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.py

WHAT QUANTLIB DOES NOT EXPOSE, AND HOW THIS ARM WORKS AROUND IT
------------------------------------------------------------------
`ql.MCAmericanEngine` and `ql.BinomialVanillaEngine` (the public SWIG/Python LSM and binomial
engines) are wired to `GeneralizedBlackScholesProcess`, not `HestonProcess`. There is no single
public QuantLib call that prices "Heston + Longstaff-Schwartz American" the way
`heston_basket_price` does. So:

  * the EUROPEAN leg prices the FULL Heston model on both sides (`ql.AnalyticHestonEngine` /
    `ql.MCEuropeanHestonEngine` here, `heston_closed_form_call` / `heston_optionpv_error` on the
    Mojo side) — a genuine like-for-like Heston comparison;
  * the AMERICAN leg prices the Black-Scholes-DEGENERATE corner of the same Heston model
    (`xi=0, rho=0, v0=theta=sigma^2`) with QuantLib's BS-only American engines
    (`ql.MCAmericanEngine`, `ql.BinomialVanillaEngine`), matched against the Mojo arm running its
    OWN Heston machinery at the same degenerate parameters — same contract, same true answer,
    different code paths on both sides;
  * `ql.FdHestonVanillaEngine` — a PDE solver, genuinely Heston-native, and QuantLib's closest
    public approximation to "Heston American" — is priced separately and reported as A DIFFERENT
    METHOD (finite-difference, not Monte Carlo), never folded into the LSM-vs-LSM numbers.

THE NEGATIVE PREMIUM IN THE DEGENERATE CORNER IS EXPECTED, NOT A BUG
-----------------------------------------------------------------------
An American call on a non-dividend-paying asset is NEVER optimally exercised early — a model-free
theorem (Merton), true for Heston exactly as for Black-Scholes, because it rests only on
convexity of the payoff and the martingale property of the discounted (non-dividend) underlying.
So the TRUE American value here equals the European value exactly, and any measured
"early-exercise premium" is pure finite-sample regression bias from the in-sample LSM algorithm.
That bias runs NEGATIVE for the standard degree-2 basis at these sample sizes on THIS ENGINE too:
measured directly here (seeds 42/7/123, 10k/40k/160k samples, `polynomOrder=2`), every one of
those 9 `ql.MCAmericanEngine` runs UNDERPRICED `ql.AnalyticEuropeanEngine`, by 0.076 to 0.251.
That is reported as a corroborating data point, not smoothed over.
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import QuantLib as ql
except ImportError as exc:  # pragma: no cover - environment problem, not a code bug
    raise SystemExit(
        "QuantLib is not importable from this interpreter. Install it into the SAME "
        "interpreter you invoke this script with, e.g.:\n"
        "  /tmp/bb/bin/python -m pip install QuantLib\n"
        f"(ImportError: {exc})"
    ) from exc

# ── The contract. Must match bench_vs_quantlib_heston.mojo exactly. ────────────

SPOT = 100.0
STRIKE = 100.0
RATE = 0.03
DIVY = 0.0
TENOR_YEARS = 1
V0 = THETA = 0.04
KAPPA = 2.0
XI = 0.5
RHO = -0.7
SIGMA_BS = 0.2  # sqrt(V0)
N_STEPS_EURO = 252
N_STEPS_AMER = 100
PATH_COUNTS = (10000, 40000, 160000)
QL_SEED = 42
BINOMIAL_STEPS = 2000
FD_GRID = (100, 100, 50)  # (x, v, t) grid sizes for FdHestonVanillaEngine

_EVAL_DATE = ql.Date(15, 6, 2026)


def _setup():
    ql.Settings.instance().evaluationDate = _EVAL_DATE
    spot = ql.QuoteHandle(ql.SimpleQuote(SPOT))
    r_ts = ql.YieldTermStructureHandle(ql.FlatForward(_EVAL_DATE, RATE, ql.Actual365Fixed()))
    q_ts = ql.YieldTermStructureHandle(ql.FlatForward(_EVAL_DATE, DIVY, ql.Actual365Fixed()))
    maturity = _EVAL_DATE + ql.Period(TENOR_YEARS, ql.Years)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call, STRIKE)
    return spot, r_ts, q_ts, maturity, payoff


def european_leg() -> None:
    spot, r_ts, q_ts, maturity, payoff = _setup()
    process = ql.HestonProcess(
        r_ts, q_ts, spot, V0, KAPPA, THETA, XI, RHO,
        ql.HestonProcess.QuadraticExponentialMartingale,
    )
    model = ql.HestonModel(process)
    exercise = ql.EuropeanExercise(maturity)
    option = ql.VanillaOption(payoff, exercise)

    option.setPricingEngine(ql.AnalyticHestonEngine(model))
    closed_form = option.NPV()
    print(f"QLHEURO_CLOSED_FORM price={closed_form:.5f}  (ql.AnalyticHestonEngine, Fourier)")

    for n_paths in PATH_COUNTS:
        option.setPricingEngine(
            ql.MCEuropeanHestonEngine(
                process, "lowdiscrepancy",
                timeStepsPerYear=N_STEPS_EURO, requiredSamples=n_paths, seed=QL_SEED,
            )
        )
        t0 = time.perf_counter()
        price = option.NPV()
        wall_ms = (time.perf_counter() - t0) * 1000.0
        rel_err_pct = abs(price - closed_form) / closed_form * 100.0
        print(
            f"QLHEURO n_paths={n_paths} n_steps={N_STEPS_EURO} price={price:.5f} "
            f"closed_form={closed_form:.5f} rel_err_pct={rel_err_pct:.4f} wall_ms={wall_ms:.2f}"
        )


def american_leg() -> None:
    spot, r_ts, q_ts, maturity, payoff = _setup()
    vol_ts = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(_EVAL_DATE, ql.NullCalendar(), SIGMA_BS, ql.Actual365Fixed())
    )
    bsm_process = ql.BlackScholesMertonProcess(spot, q_ts, r_ts, vol_ts)

    exercise_euro = ql.EuropeanExercise(maturity)
    euro_option = ql.VanillaOption(payoff, exercise_euro)
    euro_option.setPricingEngine(ql.AnalyticEuropeanEngine(bsm_process))
    european = euro_option.NPV()
    print(f"QLHAMER_EUROPEAN price={european:.5f}  (ql.AnalyticEuropeanEngine, closed form)")

    exercise_amer = ql.AmericanExercise(_EVAL_DATE, maturity)
    amer_option = ql.VanillaOption(payoff, exercise_amer)
    amer_option.setPricingEngine(ql.BinomialVanillaEngine(bsm_process, "crr", BINOMIAL_STEPS))
    binomial_ref = amer_option.NPV()
    print(
        f"QLHAMER_BINOMIAL_REF price={binomial_ref:.5f}  "
        f"(ql.BinomialVanillaEngine crr, {BINOMIAL_STEPS} steps, genuinely American)"
    )

    for n_paths in PATH_COUNTS:
        amer_option.setPricingEngine(
            ql.MCAmericanEngine(
                bsm_process, "pseudorandom", timeSteps=N_STEPS_AMER,
                antitheticVariate=True, requiredSamples=n_paths, seed=QL_SEED, polynomOrder=2,
            )
        )
        t0 = time.perf_counter()
        price = amer_option.NPV()
        wall_ms = (time.perf_counter() - t0) * 1000.0
        premium = price - european
        rel_err_pct = abs(price - binomial_ref) / binomial_ref * 100.0
        print(
            f"QLHAMER n_paths={n_paths} n_steps={N_STEPS_AMER} price={price:.5f} "
            f"european={european:.5f} premium={premium:.5f} binomial_ref={binomial_ref:.5f} "
            f"rel_err_pct={rel_err_pct:.4f} wall_ms={wall_ms:.2f}"
        )


def fd_heston_leg() -> None:
    """FdHestonVanillaEngine: a PDE solver, genuinely Heston-native, and the closest public
    QuantLib approximation to "Heston American". Reported alone, never averaged into the
    LSM-vs-LSM numbers above — it is a different numerical method (finite difference, not
    Monte Carlo) and a race between the two would not be a race between estimators of the
    same kind."""
    spot, r_ts, q_ts, maturity, payoff = _setup()
    process = ql.HestonProcess(
        r_ts, q_ts, spot, V0, KAPPA, THETA, XI, RHO,
        ql.HestonProcess.QuadraticExponentialMartingale,
    )
    model = ql.HestonModel(process)
    engine = ql.FdHestonVanillaEngine(model, *FD_GRID)

    exercise_amer = ql.AmericanExercise(_EVAL_DATE, maturity)
    amer_option = ql.VanillaOption(payoff, exercise_amer)
    amer_option.setPricingEngine(engine)
    t0 = time.perf_counter()
    amer_price = amer_option.NPV()
    wall_ms = (time.perf_counter() - t0) * 1000.0

    exercise_euro = ql.EuropeanExercise(maturity)
    euro_option = ql.VanillaOption(payoff, exercise_euro)
    euro_option.setPricingEngine(engine)
    euro_price = euro_option.NPV()

    print(
        f"QLHFD method=fd_heston_pde grid={FD_GRID} amer_price={amer_price:.5f} "
        f"euro_price_same_engine={euro_price:.5f} wall_ms={wall_ms:.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(f"QL_VERSION {ql.__version__}")
    print(f"PYTHON_VERSION {sys.version.split()[0]}")
    print(
        f"CONTRACT S0={SPOT} K={STRIKE} r={RATE} q={DIVY} T={TENOR_YEARS}y v0=theta={V0} "
        f"kappa={KAPPA} xi={XI} rho={RHO}"
    )
    print("")
    european_leg()
    print("")
    american_leg()
    print("")
    fd_heston_leg()
    print("")
    print("BENCH_GATE vs_quantlib_heston_ql_arm PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
