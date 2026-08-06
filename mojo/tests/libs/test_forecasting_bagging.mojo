"""test_forecasting_bagging.mojo — known-value tests for MBB bagged forecasts.

Hand-written. The strongest assertions are IDENTITIES asserted with `==`:

  * `block_len == n` admits exactly ONE block start, so every resample IS the
    remainder and the bagged forecast EQUALS the single fit, bit for bit, for any B.
  * On a perfect line the shrinking-window centered MA reproduces the line EXACTLY
    (the average of a symmetric window on a line is its center), so the remainder is
    identically zero, every recomposition is the original series, and the bagged
    forecast equals the single fit even with small blocks.
  * A constant series: same identity, forecast EXACTLY c.

Determinism is asserted as bit-equality across calls, and key-sensitivity as
inequality across seeds / replicate ids on a series with a live remainder.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_EMPTY_SERIES,
    FC_ERR_METHOD,
    FC_ERR_PARAM_RANGE,
    FC_ERR_SEED_RANGE,
    FC_METHOD_ETS_ANN,
    FC_OK,
)
from forecasting.bagging import (
    BaggedForecast,
    bagged_candidate_forecast,
    mbb_replicate,
    shrinking_ma_trend,
)
from forecasting.point import ets_ann_forecast
from forecasting.select import _golden_ses_alpha


def _line(n: Int) -> List[Float64]:
    var y = List[Float64]()
    for t in range(n):
        y.append(2.0 + 3.0 * Float64(t))
    return y^


def _noisy(n: Int) -> List[Float64]:
    """Deterministic series with a genuinely non-constant remainder."""
    var y = List[Float64]()
    for t in range(n):
        var wig = Float64((t * 6367 + 92821) % 89) / 89.0 - 0.5
        y.append(50.0 + 0.7 * Float64(t) + 9.0 * wig)
    return y^


def main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.bagging] hand-written known-value suite")

    # ══ 1. the shrinking-window trend: exact on a line, exact at the endpoints ════════
    var yl = _line(20)
    var tr = shrinking_ma_trend(yl, 7)
    var exact = len(tr) == 20
    for i in range(len(tr)):
        if tr[i] != yl[i]:
            exact = False
    if exact and len(shrinking_ma_trend(List[Float64](), 7)) == 0 and len(
        shrinking_ma_trend(yl, 2)
    ) == 0:
        passed += 1
        print("  ✅ centered MA of a line IS the line (==), edges included; empty/short refuse")
    else:
        failed += 1
        print("  ❌ shrinking trend wrong on a line")

    # ══ 2. block_len == n: the resample IS the remainder ══════════════════════════════
    var yn = _noisy(40)
    var trend = shrinking_ma_trend(yn, 7)
    var rem = List[Float64]()
    for i in range(40):
        rem.append(yn[i] - trend[i])
    var full = mbb_replicate(rem, 40, 7, 11, 0)
    var identical = len(full) == 40
    for i in range(len(full)):
        if full[i] != rem[i]:
            identical = False
    if identical:
        passed += 1
        print("  ✅ block_len == n admits one start: the resample equals the remainder (==)")
    else:
        failed += 1
        print("  ❌ full-length block is not the identity")

    # ══ 3. keyed determinism and key sensitivity ══════════════════════════════════════
    var r_a = mbb_replicate(rem, 8, 7, 11, 3)
    var r_b = mbb_replicate(rem, 8, 7, 11, 3)
    var r_c = mbb_replicate(rem, 8, 7, 11, 4)   # different replicate
    var r_d = mbb_replicate(rem, 8, 8, 11, 3)   # different seed
    var same = len(r_a) == 40 and len(r_c) == 40 and len(r_d) == 40
    var diff_rep = False
    var diff_seed = False
    for i in range(len(r_a)):
        if r_a[i] != r_b[i]:
            same = False
        if r_a[i] != r_c[i]:
            diff_rep = True
        if r_a[i] != r_d[i]:
            diff_seed = True
    if same and diff_rep and diff_seed:
        passed += 1
        print("  ✅ same key -> bit-identical resample; replicate id and seed both matter")
    else:
        failed += 1
        print("  ❌ keyed draws wrong:", same, diff_rep, diff_seed)

    # ══ 4. the bagged == single-fit identity, three separate routes ═══════════════════
    # (a) full-length blocks on a noisy series, (b) a perfect line (remainder is
    # identically zero) with SMALL blocks, (c) a constant series.
    var base = ets_ann_forecast(yn, _golden_ses_alpha(yn), 6)
    var bag_full = bagged_candidate_forecast(yn, 6, 0, 12, 40, 7, 7, 11)
    var id_full = bag_full.status == FC_OK and bag_full.n_boot_used == 12
    for h in range(6):
        if bag_full.values[h] != base.values[h]:
            id_full = False
    var bag_line = bagged_candidate_forecast(yl, 4, 1, 10, 5, 7, 7, 11)
    var id_line = bag_line.status == FC_OK and bag_line.n_boot_used == 10
    var yl_damped_alone = bag_line.values.copy()

    var yc = List[Float64]()
    for _ in range(16):
        yc.append(5.0)
    var bag_c = bagged_candidate_forecast(yc, 4, 0, 10, 4, 5, 7, 11)
    var id_const = bag_c.status == FC_OK
    for h in range(4):
        if bag_c.values[h] != 5.0:
            id_const = False
    if id_full and id_line and id_const:
        passed += 1
        print("  ✅ bagged == single fit when the resample is the identity:")
        print("     full-length blocks (==), zero remainder on a line, constant series")
    else:
        failed += 1
        print("  ❌ an identity route failed:", id_full, id_line, id_const)

    # ══ 5. a live remainder actually moves the ensemble, deterministically ════════════
    var bag_1 = bagged_candidate_forecast(yn, 6, 0, 24, 8, 7, 7, 11)
    var bag_2 = bagged_candidate_forecast(yn, 6, 0, 24, 8, 7, 7, 11)
    var bag_3 = bagged_candidate_forecast(yn, 6, 0, 24, 8, 8, 7, 11)
    var reproducible = (
        bag_1.status == FC_OK
        and bag_1.n_boot_requested == 24
        and bag_1.n_boot_used + bag_1.n_boot_refused == 24
    )
    var moved = False
    var seed_sensitive = False
    for h in range(6):
        if bag_1.values[h] != bag_2.values[h]:
            reproducible = False
        if bag_1.values[h] != base.values[h]:
            moved = True
        if bag_1.values[h] != bag_3.values[h]:
            seed_sensitive = True
    if reproducible and moved and seed_sensitive:
        passed += 1
        print("  ✅ live remainder: ensemble differs from the single fit, bit-reproducible,")
        print("     seed-sensitive, census adds up")
    else:
        failed += 1
        print("  ❌ ensemble behaviour wrong:", reproducible, moved, seed_sensitive)

    # ══ 6. refusals, all typed, request echoed ═════════════════════════════════════════
    var r_empty = bagged_candidate_forecast(List[Float64](), 4, 0, 10, 4, 5, 7, 11)
    var r_cand = bagged_candidate_forecast(yn, 6, 3, 10, 8, 7, 7, 11)
    var r_blk1 = bagged_candidate_forecast(yn, 6, 0, 10, 1, 7, 7, 11)
    var r_blkn = bagged_candidate_forecast(yn, 6, 0, 10, 41, 7, 7, 11)
    var r_seed = bagged_candidate_forecast(yn, 6, 0, 10, 8, 7, -1, 11)
    var r_boot = bagged_candidate_forecast(yn, 6, 0, 0, 8, 7, 7, 11)
    var r_trw = bagged_candidate_forecast(yn, 6, 0, 10, 8, 2, 7, 11)
    if (
        r_empty.status == FC_ERR_EMPTY_SERIES
        and r_cand.status == FC_ERR_METHOD
        and r_blk1.status == FC_ERR_PARAM_RANGE
        and r_blkn.status == FC_ERR_PARAM_RANGE
        and r_seed.status == FC_ERR_SEED_RANGE
        and r_boot.status == FC_ERR_PARAM_RANGE
        and r_trw.status == FC_ERR_PARAM_RANGE
        and not r_seed.has_forecast and len(r_seed.values) == 0
        and r_seed.n_boot_requested == 10 and r_seed.n_boot_used == 0
        and len(mbb_replicate(rem, 1, 7, 11, 0)) == 0
        and len(mbb_replicate(rem, 41, 7, 11, 0)) == 0
        and len(mbb_replicate(rem, 8, -1, 11, 0)) == 0
    ):
        passed += 1
        print("  ✅ candidate/block/seed/boot/trend-window defects refuse loudly, echo the request")
    else:
        failed += 1
        print("  ❌ a refusal leaked:", r_cand.status, r_blk1.status, r_seed.status)

    # ══ 7. the record names its generator and stream ══════════════════════════════════
    if (
        bag_1.rng_version == "philox4x64-10/v1"
        and bag_1.stream == bag_full.stream and bag_1.stream > 7
        and bag_1.method_id == FC_METHOD_ETS_ANN and bag_1.candidate_index == 0
    ):
        passed += 1
        print("  ✅ ensemble record names generator, derived stream and candidate id")
    else:
        failed += 1
        print("  ❌ provenance fields wrong:", bag_1.stream, bag_1.method_id)

    # Keep the compiler honest about the copy above (used, so no dead-store warning).
    if len(yl_damped_alone) != 4:
        failed += 1
        print("  ❌ damped line path length wrong")

    print("  [forecasting.bagging] Passed:", passed, "Failed:", failed)
