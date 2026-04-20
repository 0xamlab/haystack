"""Tests for Wave 51 — Recommender Systems, Image Operations, Epidemiology."""

from recommender import (
    cosine_sim_users,
    predict_rating,
    popularity_ranking,
    mean_rating_per_item,
    mean_rating_per_user,
    top_n_items,
    item_overlap,
    cold_start_recommend,
    rmse_ratings,
)
from image_ops import (
    convolve_2d,
    sobel_x_kernel,
    sobel_y_kernel,
    gaussian_kernel_3x3,
    sharpen_kernel,
    histogram,
    threshold,
    invert,
    brightness,
    contrast,
    mean_pixel,
)
from epidemiology import (
    sir_step,
    sir_simulate,
    seir_step,
    basic_reproduction_number,
    herd_immunity_threshold,
    effective_reproduction,
    doubling_time,
    attack_rate,
    case_fatality_rate,
    incidence_rate,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Helper: build a ratings matrix ───────────────────────────────────────────


fn _make_ratings() -> List[List[Float64]]:
    """3 users, 4 items."""
    var r = List[List[Float64]]()
    # User 0: rated items 0,1,2
    var u0 = List[Float64]()
    u0.append(5.0); u0.append(3.0); u0.append(4.0); u0.append(0.0)
    # User 1: rated items 0,1,3
    var u1 = List[Float64]()
    u1.append(4.0); u1.append(2.0); u1.append(0.0); u1.append(5.0)
    # User 2: rated items 0,1,2,3
    var u2 = List[Float64]()
    u2.append(3.0); u2.append(5.0); u2.append(4.0); u2.append(3.0)
    r.append(u0^); r.append(u1^); r.append(u2^)
    return r^


# ── Helper: build a small image ──────────────────────────────────────────────


fn _make_image() -> List[List[Float64]]:
    """4x4 grayscale image."""
    var img = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(100.0); r0.append(150.0); r0.append(200.0); r0.append(50.0)
    var r1 = List[Float64]()
    r1.append(80.0); r1.append(120.0); r1.append(180.0); r1.append(30.0)
    var r2 = List[Float64]()
    r2.append(60.0); r2.append(90.0); r2.append(160.0); r2.append(20.0)
    var r3 = List[Float64]()
    r3.append(40.0); r3.append(70.0); r3.append(140.0); r3.append(10.0)
    img.append(r0^); img.append(r1^); img.append(r2^); img.append(r3^)
    return img^


# ── Recommender Tests ─────────────────────────────────────────────────────────


fn test_mean_rating_per_item() raises:
    print("  Testing mean_rating_per_item...")
    var r = _make_ratings()
    var m = mean_rating_per_item(r)
    _assert(len(m) == 4, "mean_rating_per_item length == 4")              # 1
    # Item 0: (5+4+3)/3 = 4.0
    _assert_close(m[0], 4.0, 1e-10, "item 0 avg == 4.0")                 # 2
    # Item 1: (3+2+5)/3 ≈ 3.333
    _assert_close(m[1], 10.0 / 3.0, 1e-10, "item 1 avg")                 # 3
    # Item 2: (4+4)/2 = 4.0 (user 1 didn't rate)
    _assert_close(m[2], 4.0, 1e-10, "item 2 avg == 4.0")                 # 4
    # Item 3: (5+3)/2 = 4.0
    _assert_close(m[3], 4.0, 1e-10, "item 3 avg == 4.0")                 # 5


fn test_mean_rating_per_user() raises:
    print("  Testing mean_rating_per_user...")
    var r = _make_ratings()
    var m = mean_rating_per_user(r)
    _assert(len(m) == 3, "mean_rating_per_user length == 3")              # 6
    # User 0: (5+3+4)/3 = 4.0
    _assert_close(m[0], 4.0, 1e-10, "user 0 avg == 4.0")                 # 7
    # User 1: (4+2+5)/3 ≈ 3.667
    _assert_close(m[1], 11.0 / 3.0, 1e-10, "user 1 avg")                 # 8


fn test_popularity_ranking() raises:
    print("  Testing popularity_ranking...")
    var r = _make_ratings()
    var ranked = popularity_ranking(r)
    _assert(len(ranked) == 4, "popularity_ranking length == 4")           # 9
    # Items 0 and 1 have 3 ratings each; items 2 and 3 have 2 each
    # First two should be 0 or 1
    var first = ranked[0]
    _assert(first == 0 or first == 1, "most popular is item 0 or 1")     # 10


fn test_cosine_sim_identical() raises:
    print("  Testing cosine_sim_users identical...")
    var r = _make_ratings()
    var sim = cosine_sim_users(r, 0, 0)
    _assert_close(sim, 1.0, 1e-10, "self-similarity == 1.0")             # 11


fn test_cosine_sim_range() raises:
    print("  Testing cosine_sim_users range...")
    var r = _make_ratings()
    var sim01 = cosine_sim_users(r, 0, 1)
    _assert(sim01 >= 0.0, "cosine_sim >= 0")                             # 12
    _assert(sim01 <= 1.0, "cosine_sim <= 1")                             # 13
    var sim02 = cosine_sim_users(r, 0, 2)
    _assert(sim02 >= 0.0, "cosine_sim 0,2 >= 0")                         # 14
    _assert(sim02 <= 1.0, "cosine_sim 0,2 <= 1")                         # 15


fn test_item_overlap() raises:
    print("  Testing item_overlap...")
    var r = _make_ratings()
    # Users 0 and 1 co-rated items 0,1 → 2
    var ov01 = item_overlap(r, 0, 1)
    _assert(ov01 == 2, "overlap(0,1) == 2")                              # 16
    # Users 0 and 2 co-rated items 0,1,2 → 3
    var ov02 = item_overlap(r, 0, 2)
    _assert(ov02 == 3, "overlap(0,2) == 3")                              # 17
    # Users 1 and 2 co-rated items 0,1,3 → 3
    var ov12 = item_overlap(r, 1, 2)
    _assert(ov12 == 3, "overlap(1,2) == 3")                              # 18


fn test_predict_rating() raises:
    print("  Testing predict_rating...")
    var r = _make_ratings()
    # User 0 has not rated item 3; predict it
    var pred = predict_rating(r, 0, 3, 2)
    _assert(pred >= 1.0, "predicted rating >= 1")                        # 19
    _assert(pred <= 5.0, "predicted rating <= 5")                        # 20


fn test_top_n_items() raises:
    print("  Testing top_n_items...")
    var scores = List[Float64]()
    scores.append(2.0); scores.append(5.0); scores.append(1.0); scores.append(4.0)
    var top2 = top_n_items(scores, 2)
    _assert(len(top2) == 2, "top_n_items returns 2")                     # 21
    _assert(top2[0] == 1, "top item index == 1")                         # 22
    _assert(top2[1] == 3, "second item index == 3")                      # 23


fn test_cold_start_recommend() raises:
    print("  Testing cold_start_recommend...")
    var r = _make_ratings()
    var recs = cold_start_recommend(r, 3)
    _assert(len(recs) == 3, "cold_start returns 3 items")                # 24
    # All indices valid
    for i in range(3):
        _assert(recs[i] >= 0 and recs[i] < 4, "cold_start idx valid")   # 25,26,27


fn test_rmse_ratings() raises:
    print("  Testing rmse_ratings...")
    var pred = List[Float64]()
    pred.append(3.0); pred.append(4.0); pred.append(0.0)
    var actual = List[Float64]()
    actual.append(3.0); actual.append(4.0); actual.append(0.0)
    var r = rmse_ratings(pred, actual)
    _assert_close(r, 0.0, 1e-10, "perfect predictions → RMSE 0")        # 28


# ── Image Tests ───────────────────────────────────────────────────────────────


fn test_sobel_x_kernel() raises:
    print("  Testing sobel_x_kernel...")
    var k = sobel_x_kernel()
    _assert(len(k) == 3, "sobel_x 3 rows")                              # 29
    _assert(len(k[0]) == 3, "sobel_x 3 cols")                           # 30
    _assert_close(k[0][0], -1.0, 1e-10, "sobel_x[0][0] == -1")         # 31
    _assert_close(k[1][0], -2.0, 1e-10, "sobel_x[1][0] == -2")         # 32
    _assert_close(k[0][2], 1.0, 1e-10, "sobel_x[0][2] == 1")           # 33


fn test_gaussian_kernel_sums_to_one() raises:
    print("  Testing gaussian_kernel_3x3 sum...")
    var k = gaussian_kernel_3x3()
    var s: Float64 = 0.0
    for r in range(3):
        for c in range(3):
            s += k[r][c]
    _assert_close(s, 1.0, 1e-10, "gaussian kernel sums to 1.0")         # 34


fn test_convolve_identity() raises:
    print("  Testing convolve_2d identity kernel...")
    var img = _make_image()
    # Identity kernel [[0,0,0],[0,1,0],[0,0,0]]
    var k = List[List[Float64]]()
    var kr0 = List[Float64](); kr0.append(0.0); kr0.append(0.0); kr0.append(0.0)
    var kr1 = List[Float64](); kr1.append(0.0); kr1.append(1.0); kr1.append(0.0)
    var kr2 = List[Float64](); kr2.append(0.0); kr2.append(0.0); kr2.append(0.0)
    k.append(kr0^); k.append(kr1^); k.append(kr2^)
    var out = convolve_2d(img, k)
    # Output should be 2x2 (4-3+1=2), matching center pixels
    _assert(len(out) == 2, "identity conv output rows == 2")             # 35
    _assert(len(out[0]) == 2, "identity conv output cols == 2")          # 36
    _assert_close(out[0][0], 120.0, 1e-10, "identity conv center")      # 37
    _assert_close(out[0][1], 180.0, 1e-10, "identity conv center2")     # 38


fn test_threshold() raises:
    print("  Testing threshold...")
    var img = _make_image()
    var t = threshold(img, 100.0)
    _assert(len(t) == 4, "threshold rows")                              # 39
    # All values should be 0 or 255
    for r in range(4):
        for c in range(4):
            _assert(
                t[r][c] == 0.0 or t[r][c] == 255.0,
                "threshold val 0 or 255",
            )                                                            # 40-55 (16 checks)


fn test_invert_double() raises:
    print("  Testing invert(invert(x)) ≈ x...")
    var img = _make_image()
    var inv2 = invert(invert(img))
    for r in range(4):
        for c in range(4):
            _assert_close(
                inv2[r][c], img[r][c], 1e-10, "double invert identity"
            )


fn test_brightness_clamp() raises:
    print("  Testing brightness clamp...")
    var img = _make_image()
    var bright = brightness(img, 300.0)
    for r in range(4):
        for c in range(4):
            _assert(bright[r][c] <= 255.0, "brightness <= 255")
            _assert(bright[r][c] >= 0.0, "brightness >= 0")
    var dark = brightness(img, -300.0)
    for r in range(4):
        for c in range(4):
            _assert(dark[r][c] == 0.0, "dark brightness == 0")


fn test_histogram_sum() raises:
    print("  Testing histogram sum...")
    var img = _make_image()
    var h = histogram(img, 8)
    var total = 0
    for i in range(8):
        total += h[i]
    _assert(total == 16, "histogram sum == 16 pixels")


fn test_mean_pixel() raises:
    print("  Testing mean_pixel...")
    var img = _make_image()
    var m = mean_pixel(img)
    # Sum all pixels: row0=500, row1=410, row2=330, row3=260 → total=1500
    # mean = 1500/16 = 93.75
    _assert_close(m, 93.75, 1e-10, "mean_pixel == 93.75")


fn test_contrast() raises:
    print("  Testing contrast...")
    var img = _make_image()
    var c = contrast(img, 1.0)
    # factor=1.0 should be identity
    for r in range(4):
        for cc in range(4):
            _assert_close(
                c[r][cc], img[r][cc], 1e-10, "contrast factor=1 identity"
            )


fn test_sharpen_kernel() raises:
    print("  Testing sharpen_kernel...")
    var k = sharpen_kernel()
    _assert_close(k[1][1], 5.0, 1e-10, "sharpen center == 5")
    _assert_close(k[0][1], -1.0, 1e-10, "sharpen top == -1")


# ── Epidemiology Tests ────────────────────────────────────────────────────────


fn test_basic_reproduction_number() raises:
    print("  Testing basic_reproduction_number...")
    var r0 = basic_reproduction_number(0.4, 0.1)
    _assert_close(r0, 4.0, 1e-10, "R0(0.4, 0.1) == 4.0")


fn test_herd_immunity_threshold() raises:
    print("  Testing herd_immunity_threshold...")
    var hit = herd_immunity_threshold(4.0)
    _assert_close(hit, 0.75, 1e-10, "HIT(4.0) ≈ 0.75")


fn test_sir_step_conservation() raises:
    print("  Testing sir_step conservation...")
    var S: Float64 = 990.0
    var I: Float64 = 10.0
    var R: Float64 = 0.0
    var N0 = S + I + R
    var step = sir_step(S, I, R, 0.4, 0.1, 0.1)
    var N1 = step[0] + step[1] + step[2]
    _assert_close(N1, N0, 1e-10, "SIR conserves population")


fn test_sir_simulate_length() raises:
    print("  Testing sir_simulate length...")
    var sim = sir_simulate(990.0, 10.0, 0.0, 0.4, 0.1, 0.1, 50)
    _assert(len(sim) == 51, "sir_simulate length == n_steps + 1")


fn test_sir_simulate_initial() raises:
    print("  Testing sir_simulate initial values...")
    var sim = sir_simulate(990.0, 10.0, 0.0, 0.4, 0.1, 0.1, 10)
    _assert_close(sim[0][0], 990.0, 1e-10, "sir_simulate S0")
    _assert_close(sim[0][1], 10.0, 1e-10, "sir_simulate I0")
    _assert_close(sim[0][2], 0.0, 1e-10, "sir_simulate R0")


fn test_seir_step_conservation() raises:
    print("  Testing seir_step conservation...")
    var S: Float64 = 980.0
    var E: Float64 = 10.0
    var I: Float64 = 10.0
    var R: Float64 = 0.0
    var N0 = S + E + I + R
    var step = seir_step(S, E, I, R, 0.4, 0.2, 0.1, 0.1)
    var N1 = step[0] + step[1] + step[2] + step[3]
    _assert_close(N1, N0, 1e-10, "SEIR conserves population")


fn test_effective_reproduction() raises:
    print("  Testing effective_reproduction...")
    var re = effective_reproduction(4.0, 0.75)
    _assert_close(re, 1.0, 1e-10, "Re(4.0, 0.75) ≈ 1.0")


fn test_doubling_time() raises:
    print("  Testing doubling_time...")
    # ln(2) ≈ 0.693147
    var dt = doubling_time(0.693147180559945)
    _assert_close(dt, 1.0, 1e-6, "doubling_time(ln2) ≈ 1.0")


fn test_attack_rate() raises:
    print("  Testing attack_rate...")
    var ar = attack_rate(2.0)
    _assert(ar > 0.0, "attack_rate(2.0) > 0")
    _assert(ar < 1.0, "attack_rate(2.0) < 1")
    # For R0=2, final size ≈ 0.797
    _assert_close(ar, 0.7968, 0.01, "attack_rate(2.0) ≈ 0.797")


fn test_attack_rate_subcritical() raises:
    print("  Testing attack_rate subcritical...")
    var ar = attack_rate(0.5)
    _assert_close(ar, 0.0, 1e-10, "attack_rate(0.5) == 0 (subcritical)")


fn test_case_fatality_rate() raises:
    print("  Testing case_fatality_rate...")
    var cfr = case_fatality_rate(10, 100)
    _assert_close(cfr, 0.1, 1e-10, "CFR(10, 100) == 0.1")


fn test_incidence_rate() raises:
    print("  Testing incidence_rate...")
    var ir = incidence_rate(50, 10000, 1.0)
    _assert_close(ir, 0.005, 1e-10, "incidence_rate(50, 10000, 1.0)")


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 51 Tests ===")

    # Recommender
    print(" Recommender tests:")
    test_mean_rating_per_item()
    test_mean_rating_per_user()
    test_popularity_ranking()
    test_cosine_sim_identical()
    test_cosine_sim_range()
    test_item_overlap()
    test_predict_rating()
    test_top_n_items()
    test_cold_start_recommend()
    test_rmse_ratings()

    # Image
    print(" Image tests:")
    test_sobel_x_kernel()
    test_gaussian_kernel_sums_to_one()
    test_convolve_identity()
    test_threshold()
    test_invert_double()
    test_brightness_clamp()
    test_histogram_sum()
    test_mean_pixel()
    test_contrast()
    test_sharpen_kernel()

    # Epidemiology
    print(" Epidemiology tests:")
    test_basic_reproduction_number()
    test_herd_immunity_threshold()
    test_sir_step_conservation()
    test_sir_simulate_length()
    test_sir_simulate_initial()
    test_seir_step_conservation()
    test_effective_reproduction()
    test_doubling_time()
    test_attack_rate()
    test_attack_rate_subcritical()
    test_case_fatality_rate()
    test_incidence_rate()

    print("All Wave 51 tests passed! ✅")
