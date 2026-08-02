"""test_quantfin_heston.mojo — known-value and refusal tests for Heston-QE + Longstaff-Schwartz.

Hand-written, not generated: `quantfin.heston`'s exported functions take `List[HestonParams]`,
`List[List[Float64]]` correlation matrices and `UInt64` Philox coordinates, none of which
`generate_mojo_tests.py`'s scalar sample values can synthesise (`quantfin` is in that script's
`SKIP_DIRS`, the same reason `determinism` is). This suite is therefore the only place these
kernels get import-verified test coverage outside the slower inline gates in
`benchmarks/mojo_benchmarks/bench_stac_a2_workload.mojo`.

Path/step counts here are kept SMALL on purpose — this suite runs as part of routine test
discovery, not as a benchmark. The slower, statistically meaningful convergence and timing
checks live in `bench_stac_a2_workload.mojo` and `bench_vs_quantlib_heston.mojo`.

Every numeric anchor below states where its expected value came from:
  * `8.92941` (the closed-form Heston call at the fixed contract in this file) was cross-checked
    against `ql.AnalyticHestonEngine` from QuantLib 1.43 at the SAME contract and agreed to
    0.00000% relative difference — see `benchmarks/mojo_benchmarks/bench_vs_quantlib_heston.py`.
  * every other anchor is a property of THIS module (a refusal code, a bit-identity, a
    deterministic self-test value) rather than an externally-sourced number.
"""

from std.math import abs as fabs

from quantfin.heston import (
    HestonParams, HESTON_OK, HESTON_ERR_BAD_SIZE, HESTON_ERR_BAD_PARAM, HESTON_ERR_NOT_PD,
    HESTON_SCHEME_QE, HESTON_SCHEME_FULL_TRUNCATION,
    heston_scheme_name, heston_qe_psi_critical, heston_contract_id, heston_feller,
    heston_rng_bit_identity, heston_lsm_regression_agreement, heston_closed_form_call,
    heston_bs_degeneracy, heston_asset_paths, heston_basket_paths, heston_basket_price,
    heston_binomial_earlyex_error, heston_realised_correlation, heston_worker_invariance,
    heston_selftest,
)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── scheme identity and contract constants ────────────────────────────────

    var qe_name = heston_scheme_name(HESTON_SCHEME_QE)
    var ft_name = heston_scheme_name(HESTON_SCHEME_FULL_TRUNCATION)
    if len(qe_name) > 0 and len(ft_name) > 0 and qe_name != ft_name:
        passed += 1
        print("  ✅ heston_scheme_name: QE and full-truncation print distinct, non-empty names")
    else:
        failed += 1
        print("  ❌ heston_scheme_name collided or was empty")

    if heston_qe_psi_critical() == 1.5:
        passed += 1
        print("  ✅ heston_qe_psi_critical == 1.5 (Andersen's own recommendation)")
    else:
        failed += 1
        print("  ❌ heston_qe_psi_critical drifted from 1.5")

    if heston_contract_id() == "heston/qe-andersen2008+lsm-ls2001/v1":
        passed += 1
        print("  ✅ heston_contract_id is the frozen identifier string")
    else:
        failed += 1
        print("  ❌ heston_contract_id changed: " + heston_contract_id())

    # ── heston_feller: known value, and the xi = 0 sentinel ───────────────────

    var feller_p = HestonParams(100.0, 0.04, 2.0, 0.04, 0.5, -0.7, 0.0)
    var feller = heston_feller(feller_p)
    if fabs(feller - 0.64) < 1.0e-9:
        passed += 1
        print("  ✅ heston_feller(kappa=2, theta=0.04, xi=0.5) == 0.64 exactly")
    else:
        failed += 1
        print("  ❌ heston_feller expected 0.64, got " + String(feller))

    var xi_zero_p = HestonParams(100.0, 0.04, 2.0, 0.04, 0.0, 0.0, 0.0)
    if heston_feller(xi_zero_p) > 1.0e300:
        passed += 1
        print("  ✅ heston_feller(xi=0) returns the +inf-style sentinel, not a division by zero")
    else:
        failed += 1
        print("  ❌ heston_feller(xi=0) did not return the sentinel")

    # ── HestonParams.bumped(): additive, non-mutating ─────────────────────────

    var base_p = HestonParams(100.0, 0.04, 2.0, 0.04, 0.5, -0.7, 0.01)
    var bumped_p = base_p.bumped(d_s0=1.0, d_kappa=0.5)
    if (
        bumped_p.s0 == 101.0 and bumped_p.kappa == 2.5
        and base_p.s0 == 100.0 and base_p.kappa == 2.0
        and bumped_p.v0 == base_p.v0 and bumped_p.rho == base_p.rho and bumped_p.q == base_p.q
    ):
        passed += 1
        print("  ✅ HestonParams.bumped() is additive on the named fields and leaves the base untouched")
    else:
        failed += 1
        print("  ❌ HestonParams.bumped() either mutated the base or bumped the wrong field")

    # ── RNG bit-identity and LSM regression agreement, at small n ─────────────

    if heston_rng_bit_identity(2000) == 0:
        passed += 1
        print("  ✅ heston_rng_bit_identity: 0 mismatches against the frozen counter_rng, 2000 draws")
    else:
        failed += 1
        print("  ❌ heston_rng_bit_identity found a mismatch against the frozen generator")

    var lsm_agreement = heston_lsm_regression_agreement(200, 2)
    if lsm_agreement >= 0.0 and lsm_agreement < 1.0e-6:
        passed += 1
        print("  ✅ heston_lsm_regression_agreement < 1e-6 against frozen regression.ols_multiple")
    else:
        failed += 1
        print("  ❌ heston_lsm_regression_agreement out of bound: " + String(lsm_agreement))

    # ── closed-form Heston price: cross-checked against QuantLib 1.43 ────────
    # See the module docstring above for the cross-check provenance.

    var cf = heston_closed_form_call(feller_p, 100.0, 0.03, 1.0)
    if fabs(cf - 8.92941) < 1.0e-4:
        passed += 1
        print("  ✅ heston_closed_form_call == 8.92941 (agrees with ql.AnalyticHestonEngine 1.43"
              + " to 0.00000%), got " + String(cf))
    else:
        failed += 1
        print("  ❌ heston_closed_form_call drifted from the QuantLib-cross-checked value: "
              + String(cf))

    # A degenerate call (xi <= 0) must refuse with the -1.0 sentinel, not divide by zero.
    if heston_closed_form_call(xi_zero_p, 100.0, 0.03, 1.0) == -1.0:
        passed += 1
        print("  ✅ heston_closed_form_call refuses (-1.0) at xi = 0 rather than dividing by zero")
    else:
        failed += 1
        print("  ❌ heston_closed_form_call did not refuse at xi = 0")

    # ── Black-Scholes degeneracy: deterministic at a fixed seed ───────────────

    var deg_a = heston_bs_degeneracy(100.0, 100.0, 0.2, 0.03, 1.0, 2000, 16, 12345, 1)
    var deg_b = heston_bs_degeneracy(100.0, 100.0, 0.2, 0.03, 1.0, 2000, 16, 12345, 1)
    if (
        deg_a.status == HESTON_OK and deg_a.mc_price == deg_b.mc_price
        and deg_a.z_score == deg_b.z_score
    ):
        passed += 1
        print("  ✅ heston_bs_degeneracy is a pure function of its coordinates (bit-identical rerun)")
    else:
        failed += 1
        print("  ❌ heston_bs_degeneracy was not reproducible at identical coordinates")
    if deg_a.status == HESTON_OK and deg_a.z_score <= 5.0:
        passed += 1
        print("  ✅ heston_bs_degeneracy Z score within 5 std errors of Black-Scholes at 2000 paths")
    else:
        failed += 1
        print("  ❌ heston_bs_degeneracy Z score too large: " + String(deg_a.z_score))

    # ── QE non-negativity at the branch-coverage config (Feller 0.64) ────────
    # This is the specific configuration where the QE exponential branch is genuinely taken
    # (see STAC_A2_WORKLOAD.md section 4b) — the corner a naive Euler scheme breaks on.

    var qe_paths = heston_asset_paths(
        feller_p, 0.03, 1.0, 2000, 32, UInt64(777), UInt64(1), UInt64(0),
        HESTON_SCHEME_QE, True, 2,
    )
    if qe_paths.status == HESTON_OK and qe_paths.n_negative_variance == 0:
        passed += 1
        print("  ✅ QE produces 0 negative variances at Feller 0.64 (2000 paths, 32 steps)")
    else:
        failed += 1
        print("  ❌ QE produced " + String(qe_paths.n_negative_variance) + " negative variances")

    # ── dimension refusals: bad input returns a status, never crashes ────────

    var one_asset = List[HestonParams]()
    one_asset.append(feller_p)
    var mismatched_corr = List[List[Float64]]()  # len 0, but n_assets = 1
    var mismatch = heston_basket_paths(
        one_asset, mismatched_corr, 0.03, 1.0, 100, 8, UInt64(1), UInt64(1),
        HESTON_SCHEME_QE, True, 1,
    )
    if mismatch.status == HESTON_ERR_BAD_SIZE:
        passed += 1
        print("  ✅ heston_basket_paths refuses a mismatched correlation matrix (HESTON_ERR_BAD_SIZE)")
    else:
        failed += 1
        print("  ❌ heston_basket_paths did not refuse the mismatched correlation matrix")

    var two_assets = List[HestonParams]()
    two_assets.append(feller_p)
    two_assets.append(feller_p)
    var not_pd = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(1.0)
    r0.append(2.0)  # not a valid correlation entry, and not positive definite either
    var r1 = List[Float64]()
    r1.append(2.0)
    r1.append(1.0)
    not_pd.append(r0^)
    not_pd.append(r1^)
    var not_pd_result = heston_basket_paths(
        two_assets, not_pd, 0.03, 1.0, 100, 8, UInt64(1), UInt64(1), HESTON_SCHEME_QE, True, 1,
    )
    if not_pd_result.status == HESTON_ERR_NOT_PD:
        passed += 1
        print("  ✅ heston_basket_paths refuses a non-positive-definite correlation matrix")
    else:
        failed += 1
        print("  ❌ heston_basket_paths did not refuse the non-PD correlation matrix ("
              + "status=" + String(not_pd_result.status) + ")")

    var single_corr = List[List[Float64]]()
    var single_row = List[Float64]()
    single_row.append(1.0)
    single_corr.append(single_row^)
    var bad_strike = heston_basket_price(
        one_asset, single_corr, -1.0, 0.03, 1.0, 100, 8, UInt64(1), UInt64(1),
        HESTON_SCHEME_QE, True, 2, 1,
    )
    if bad_strike.status == HESTON_ERR_BAD_PARAM:
        passed += 1
        print("  ✅ heston_basket_price refuses a non-positive strike (HESTON_ERR_BAD_PARAM)")
    else:
        failed += 1
        print("  ❌ heston_basket_price did not refuse the non-positive strike")

    # ── a valid small basket price has sane, self-consistent fields ──────────

    var price = heston_basket_price(
        one_asset, single_corr, 100.0, 0.03, 1.0, 2000, 16, UInt64(42), UInt64(1),
        HESTON_SCHEME_QE, True, 2, 1,
    )
    if (
        price.status == HESTON_OK and price.n_paths == 2000 and price.std_error >= 0.0
        and price.n_exercised >= 0 and price.n_negative_variance == 0
    ):
        passed += 1
        print("  ✅ heston_basket_price returns self-consistent fields on a valid small call")
    else:
        failed += 1
        print("  ❌ heston_basket_price returned an inconsistent result")

    # ── EARLYEX.ERR refusal on a non-positive sigma ───────────────────────────

    if heston_binomial_earlyex_error(100.0, 100.0, 0.0, 0.03, 1.0, 100, 8, UInt64(1), UInt64(1)) == -1.0:
        passed += 1
        print("  ✅ heston_binomial_earlyex_error refuses (-1.0) at sigma = 0")
    else:
        failed += 1
        print("  ❌ heston_binomial_earlyex_error did not refuse at sigma = 0")

    # ── realised correlation: refuses below n_assets = 2 ──────────────────────

    if heston_realised_correlation(1, single_corr, 100, UInt64(1), UInt64(1)) == -1.0:
        passed += 1
        print("  ✅ heston_realised_correlation refuses (-1.0) at n_assets = 1 (nothing to correlate)")
    else:
        failed += 1
        print("  ❌ heston_realised_correlation did not refuse at n_assets = 1")

    # ── worker invariance at small size: 1 vs 4 workers, bit-identical ────────

    var inv = heston_worker_invariance(
        one_asset, single_corr, 100.0, 0.03, 1.0, 2000, 16, UInt64(9), UInt64(1), 4,
    )
    if inv == 0:
        passed += 1
        print("  ✅ heston_worker_invariance: 1 vs 4 workers gives a bit-identical price")
    else:
        failed += 1
        print("  ❌ heston_worker_invariance found a worker-count-dependent price")

    # ── heston_selftest: a fixed, deterministic contract value ───────────────

    var self_a = heston_selftest()
    var self_b = heston_selftest()
    if self_a == self_b and self_a > 0.0:
        passed += 1
        print("  ✅ heston_selftest is deterministic and positive: " + String(self_a))
    else:
        failed += 1
        print("  ❌ heston_selftest was not reproducible")

    print("  [quantfin.heston] Passed:", passed, "Failed:", failed)
