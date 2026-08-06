"""test_forecast_metrics.mojo — forecast scoring.

The load-bearing tests are the Murphy IDENTITY (BS = REL - RES + UNC must hold exactly, or the
decomposition is not a decomposition), the RARE-EVENT check (a constant base-rate forecast must score
p(1-p), which is what makes raw Brier misleading and BSS the primary number), and TIE HANDLING in
Spearman (finishing positions tie, and integer ranks bias rho).
"""
from std.math import isnan, isinf
from forecast_metrics import (
    brier_score,
    base_rate,
    brier_skill_score,
    log_loss,
    reliability_bins,
    expected_calibration_error,
    murphy_decomposition,
    spearman_rho,
    metrics_version,
    metrics_selftest,
)


def approx(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


def main() raises:
    var failures = 0

    if metrics_version() != String("forecast-metrics/v1"):
        print("FAIL version", metrics_version())
        failures += 1
    if not approx(metrics_selftest(), 0.0, 1e-12):
        print("FAIL selftest reliability not ~0:", metrics_selftest())
        failures += 1

    # ── perfect and useless forecasts ─────────────────────────────────────────
    var perfect = List[Float64]()
    var coin = List[Float64]()
    var obs = List[Float64]()
    for i in range(1000):
        var y = 1.0 if i % 3 == 0 else 0.0
        obs.append(y)
        perfect.append(y)
        coin.append(0.5)
    var br = base_rate(obs)
    if not approx(brier_score(perfect, obs), 0.0, 1e-12):
        print("FAIL perfect brier", brier_score(perfect, obs))
        failures += 1
    if not approx(brier_skill_score(perfect, obs, br), 1.0, 1e-9):
        print("FAIL perfect BSS", brier_skill_score(perfect, obs, br))
        failures += 1
    if not approx(brier_score(coin, obs), 0.25, 1e-12):
        print("FAIL coin brier", brier_score(coin, obs))
        failures += 1
    # a coin flip must score WORSE than the base rate on a skewed target
    if brier_skill_score(coin, obs, br) >= 0.0:
        print("FAIL coin BSS not negative", brier_skill_score(coin, obs, br))
        failures += 1
    if not approx(expected_calibration_error(perfect, obs, 10), 0.0, 1e-12):
        print("FAIL perfect ECE", expected_calibration_error(perfect, obs, 10))
        failures += 1
    if log_loss(perfect, obs, 1e-9) > 1e-6:
        print("FAIL perfect log_loss", log_loss(perfect, obs, 1e-9))
        failures += 1
    # a confident miss must be heavy but FINITE
    var wrong = List[Float64]()
    var wobs = List[Float64]()
    wrong.append(0.0)
    wobs.append(1.0)
    var ll = log_loss(wrong, wobs, 1e-9)
    if isnan(ll) or isinf(ll) or ll < 10.0:
        print("FAIL confident miss log_loss", ll)
        failures += 1

    # ── rare event: a constant base-rate forecast must score p(1-p) ───────────
    # This is why raw Brier is not the primary number. The reference overtake fit reports 0.0275
    # against a 3.16% base rate, where a constant forecast already scores ~0.0306 -- about 10% skill.
    var rp = List[Float64]()
    var ro = List[Float64]()
    for i in range(131000):
        ro.append(1.0 if i < 4142 else 0.0)
    var rbr = base_rate(ro)
    for _ in range(131000):
        rp.append(rbr)
    if not approx(brier_score(rp, ro), rbr * (1.0 - rbr), 1e-9):
        print("FAIL base-rate brier != p(1-p):", brier_score(rp, ro), rbr * (1.0 - rbr))
        failures += 1
    if not approx(brier_skill_score(rp, ro, rbr), 0.0, 1e-6):
        print("FAIL base-rate forecast has nonzero skill", brier_skill_score(rp, ro, rbr))
        failures += 1

    # ── Murphy identity must hold exactly ────────────────────────────────────
    var mixed = List[Float64]()
    var mobs = List[Float64]()
    for i in range(2000):
        var p = Float64(i % 10) / 10.0 + 0.05
        mixed.append(p)
        mobs.append(1.0 if (i * 7) % 13 < 4 else 0.0)
    var m = murphy_decomposition(mixed, mobs, 10)
    var recon = m.reliability - m.resolution + m.uncertainty
    if not approx(recon, m.brier, 1e-9):
        print("FAIL Murphy identity", recon, "!=", m.brier)
        failures += 1
    if m.reliability < 0.0 or m.resolution < 0.0 or m.uncertainty < 0.0:
        print("FAIL negative Murphy term")
        failures += 1
    if not approx(m.uncertainty, m.base_rate * (1.0 - m.base_rate), 1e-12):
        print("FAIL uncertainty != p(1-p)")
        failures += 1

    # ── binning is shared, so counts must total n ─────────────────────────────
    var rb = reliability_bins(mixed, mobs, 10)
    var total = 0.0
    for b in range(len(rb.count)):
        total += rb.count[b]
    if not approx(total, 2000.0, 1e-9):
        print("FAIL bin counts do not total n", total)
        failures += 1

    # ── Spearman, including ties ─────────────────────────────────────────────
    var a = List[Float64]()
    var rev = List[Float64]()
    var tied = List[Float64]()
    for i in range(5):
        a.append(Float64(i + 1))
        rev.append(Float64(5 - i))
    tied.append(1.0)
    tied.append(1.0)
    tied.append(3.0)
    tied.append(3.0)
    tied.append(5.0)
    if not approx(spearman_rho(a, a), 1.0, 1e-12):
        print("FAIL spearman identical", spearman_rho(a, a))
        failures += 1
    if not approx(spearman_rho(a, rev), -1.0, 1e-12):
        print("FAIL spearman reversed", spearman_rho(a, rev))
        failures += 1
    # monotone with ties must be high but strictly below 1
    var rt = spearman_rho(a, tied)
    if rt <= 0.9 or rt >= 1.0:
        print("FAIL spearman with ties", rt)
        failures += 1
    # degenerate input must not blow up
    var flat = List[Float64]()
    for _ in range(5):
        flat.append(2.0)
    if spearman_rho(a, flat) != 0.0:
        print("FAIL spearman on constant input", spearman_rho(a, flat))
        failures += 1

    if failures == 0:
        print("test_forecast_metrics: PASS")
    else:
        print("test_forecast_metrics: FAILURES =", failures)
        raise Error("test_forecast_metrics failed")
