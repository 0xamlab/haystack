"""Tests for Wave 62 — Spectral Analysis, Geodesy, Formal Logic."""

from spectral import (
    power_spectral_density,
    cross_spectral_density,
    coherence,
    spectral_centroid,
    spectral_bandwidth,
    spectral_rolloff,
    spectral_flatness,
    spectral_entropy,
    band_energy,
    peak_frequency,
)
from geodesy import (
    haversine_distance,
    vincenty_distance,
    initial_bearing,
    destination_point,
    midpoint,
    cross_track_distance,
    along_track_distance,
    geodetic_to_ecef,
    ecef_to_geodetic,
    rhumb_distance,
)
from formal_logic import (
    truth_and,
    truth_or,
    truth_not,
    truth_implies,
    truth_iff,
    truth_xor,
    truth_nand,
    truth_nor,
    modus_ponens,
    modus_tollens,
    hypothetical_syllogism,
    disjunctive_syllogism,
    is_tautology_2var,
    is_contradiction_2var,
)
from std.math import abs as fabs, log


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Spectral Analysis tests ─────────────────────────────────────────────────


fn test_power_spectral_density() raises:
    print("  test_power_spectral_density...")
    # Simple DC signal: [1, 1, 1, 1] → PSD[0] should dominate
    var sig = List[Float64]()
    sig.append(1.0)
    sig.append(1.0)
    sig.append(1.0)
    sig.append(1.0)
    var psd = power_spectral_density(sig, 1.0)
    _assert(len(psd) == 3, "PSD length for N=4 should be 3")  # 1
    _assert(psd[0] > psd[1], "DC component should dominate")  # 2
    _assert_close(psd[0], 4.0, 0.01, "PSD DC = N^2/N = N")   # 3
    # Empty signal
    var empty = List[Float64]()
    var psd_e = power_spectral_density(empty, 1.0)
    _assert(len(psd_e) == 0, "empty signal PSD empty")  # 4
    print("    PASSED")


fn test_cross_spectral_density() raises:
    print("  test_cross_spectral_density...")
    # Signal with itself → should equal PSD
    var sig = List[Float64]()
    sig.append(1.0)
    sig.append(0.0)
    sig.append(-1.0)
    sig.append(0.0)
    var csd = cross_spectral_density(sig, sig, 1.0)
    var psd = power_spectral_density(sig, 1.0)
    _assert(len(csd) == len(psd), "CSD same length as PSD")  # 5
    _assert_close(csd[0], psd[0], 0.01, "CSD(x,x)=PSD at DC")  # 6
    _assert_close(csd[1], psd[1], 0.01, "CSD(x,x)=PSD at f1")  # 7
    print("    PASSED")


fn test_coherence() raises:
    print("  test_coherence...")
    # Signal with itself → coherence = 1 everywhere (where non-zero)
    var sig = List[Float64]()
    sig.append(1.0)
    sig.append(2.0)
    sig.append(3.0)
    sig.append(4.0)
    var coh = coherence(sig, sig, 1.0)
    _assert(len(coh) > 0, "coherence non-empty")  # 8
    # Non-DC bins should have coherence ~1.0
    _assert_close(coh[1], 1.0, 0.01, "self-coherence ~1 at bin 1")  # 9
    _assert_close(coh[2], 1.0, 0.01, "self-coherence ~1 at bin 2")  # 10
    print("    PASSED")


fn test_spectral_centroid() raises:
    print("  test_spectral_centroid...")
    var mags = List[Float64]()
    var freqs = List[Float64]()
    mags.append(0.0)
    mags.append(1.0)
    mags.append(0.0)
    freqs.append(100.0)
    freqs.append(200.0)
    freqs.append(300.0)
    var c = spectral_centroid(mags, freqs)
    _assert_close(c, 200.0, 0.01, "centroid at peak freq")  # 11
    # Uniform magnitudes → centroid = mean freq
    var mags2 = List[Float64]()
    var freqs2 = List[Float64]()
    mags2.append(1.0)
    mags2.append(1.0)
    mags2.append(1.0)
    freqs2.append(100.0)
    freqs2.append(200.0)
    freqs2.append(300.0)
    var c2 = spectral_centroid(mags2, freqs2)
    _assert_close(c2, 200.0, 0.01, "uniform mags → mean freq")  # 12
    print("    PASSED")


fn test_spectral_bandwidth() raises:
    print("  test_spectral_bandwidth...")
    var mags = List[Float64]()
    var freqs = List[Float64]()
    mags.append(0.0)
    mags.append(1.0)
    mags.append(0.0)
    freqs.append(100.0)
    freqs.append(200.0)
    freqs.append(300.0)
    var bw = spectral_bandwidth(mags, freqs, 200.0)
    _assert_close(bw, 0.0, 0.01, "single peak → zero bandwidth")  # 13
    # Two equal peaks
    var mags2 = List[Float64]()
    var freqs2 = List[Float64]()
    mags2.append(1.0)
    mags2.append(0.0)
    mags2.append(1.0)
    freqs2.append(100.0)
    freqs2.append(200.0)
    freqs2.append(300.0)
    var c = spectral_centroid(mags2, freqs2)
    var bw2 = spectral_bandwidth(mags2, freqs2, c)
    _assert(bw2 > 0.0, "two-peak bandwidth > 0")  # 14
    _assert_close(bw2, 100.0, 0.01, "two peaks ±100 → bw=100")  # 15
    print("    PASSED")


fn test_spectral_rolloff() raises:
    print("  test_spectral_rolloff...")
    var mags = List[Float64]()
    var freqs = List[Float64]()
    mags.append(10.0)
    mags.append(0.0)
    mags.append(0.0)
    freqs.append(100.0)
    freqs.append(200.0)
    freqs.append(300.0)
    # 85% of energy is in first bin
    var ro = spectral_rolloff(mags, freqs, 0.85)
    _assert_close(ro, 100.0, 0.01, "rolloff at first bin")  # 16
    # 100% threshold
    var ro2 = spectral_rolloff(mags, freqs, 1.0)
    _assert_close(ro2, 100.0, 0.01, "100% rolloff at first bin")  # 17
    print("    PASSED")


fn test_spectral_flatness() raises:
    print("  test_spectral_flatness...")
    # Uniform spectrum → flatness = 1
    var mags = List[Float64]()
    mags.append(5.0)
    mags.append(5.0)
    mags.append(5.0)
    mags.append(5.0)
    var sf = spectral_flatness(mags)
    _assert_close(sf, 1.0, 0.01, "uniform → flatness=1")  # 18
    # One-hot spectrum → flatness = 0 (has zeros)
    var mags2 = List[Float64]()
    mags2.append(0.0)
    mags2.append(1.0)
    mags2.append(0.0)
    var sf2 = spectral_flatness(mags2)
    _assert_close(sf2, 0.0, 0.01, "zero-containing → flatness=0")  # 19
    # Non-uniform positive → 0 < flatness < 1
    var mags3 = List[Float64]()
    mags3.append(1.0)
    mags3.append(2.0)
    mags3.append(4.0)
    var sf3 = spectral_flatness(mags3)
    _assert(sf3 > 0.0 and sf3 < 1.0, "non-uniform flatness in (0,1)")  # 20
    print("    PASSED")


fn test_spectral_entropy() raises:
    print("  test_spectral_entropy...")
    # Uniform → max entropy = log(N)
    var mags = List[Float64]()
    mags.append(1.0)
    mags.append(1.0)
    mags.append(1.0)
    mags.append(1.0)
    var se = spectral_entropy(mags)
    _assert_close(se, log(4.0), 0.01, "uniform entropy=log(4)")  # 21
    # Single bin → entropy = 0
    var mags2 = List[Float64]()
    mags2.append(0.0)
    mags2.append(0.0)
    mags2.append(5.0)
    var se2 = spectral_entropy(mags2)
    _assert_close(se2, 0.0, 0.01, "single-bin entropy=0")  # 22
    print("    PASSED")


fn test_band_energy() raises:
    print("  test_band_energy...")
    var mags = List[Float64]()
    var freqs = List[Float64]()
    mags.append(3.0)
    mags.append(4.0)
    mags.append(5.0)
    freqs.append(100.0)
    freqs.append(200.0)
    freqs.append(300.0)
    # Band [150, 250] → only freq 200, mag=4 → energy=16
    var be = band_energy(mags, freqs, 150.0, 250.0)
    _assert_close(be, 16.0, 0.01, "band energy [150,250]")  # 23
    # Band [0, 500] → all bins: 9+16+25=50
    var be2 = band_energy(mags, freqs, 0.0, 500.0)
    _assert_close(be2, 50.0, 0.01, "full band energy")  # 24
    # Band outside → 0
    var be3 = band_energy(mags, freqs, 400.0, 500.0)
    _assert_close(be3, 0.0, 0.01, "out-of-band energy=0")  # 25
    print("    PASSED")


fn test_peak_frequency() raises:
    print("  test_peak_frequency...")
    var mags = List[Float64]()
    var freqs = List[Float64]()
    mags.append(1.0)
    mags.append(5.0)
    mags.append(3.0)
    freqs.append(100.0)
    freqs.append(200.0)
    freqs.append(300.0)
    var pf = peak_frequency(mags, freqs)
    _assert_close(pf, 200.0, 0.01, "peak at 200Hz")  # 26
    print("    PASSED")


# ── Geodesy tests ────────────────────────────────────────────────────────────


fn test_haversine_distance() raises:
    print("  test_haversine_distance...")
    # London (51.5074, -0.1278) to Paris (48.8566, 2.3522) ≈ 343 km
    var d = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
    _assert_close(d, 343.0, 5.0, "London-Paris ~343km")  # 27
    # Same point → 0
    var d2 = haversine_distance(40.0, -74.0, 40.0, -74.0)
    _assert_close(d2, 0.0, 0.01, "same point → 0km")  # 28
    # Antipodal points ≈ half circumference ~20015km
    var d3 = haversine_distance(0.0, 0.0, 0.0, 180.0)
    _assert_close(d3, 20015.0, 100.0, "antipodal ~20015km")  # 29
    print("    PASSED")


fn test_vincenty_distance() raises:
    print("  test_vincenty_distance...")
    # Same London-Paris
    var d = vincenty_distance(51.5074, -0.1278, 48.8566, 2.3522)
    _assert_close(d, 343.5, 5.0, "vincenty London-Paris ~343km")  # 30
    # Same point
    var d2 = vincenty_distance(40.0, -74.0, 40.0, -74.0)
    _assert_close(d2, 0.0, 0.01, "vincenty same point → 0")  # 31
    # Vincenty should be close to haversine for short distances
    var hav = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
    _assert(fabs(d - hav) < 2.0, "vincenty close to haversine")  # 32
    print("    PASSED")


fn test_initial_bearing() raises:
    print("  test_initial_bearing...")
    # Due east from equator → ~90°
    var b = initial_bearing(0.0, 0.0, 0.0, 1.0)
    _assert_close(b, 90.0, 0.1, "due east bearing ~90°")  # 33
    # Due north → ~0°
    var b2 = initial_bearing(0.0, 0.0, 1.0, 0.0)
    _assert_close(b2, 0.0, 0.1, "due north bearing ~0°")  # 34
    # Due south → ~180°
    var b3 = initial_bearing(1.0, 0.0, 0.0, 0.0)
    _assert_close(b3, 180.0, 0.1, "due south bearing ~180°")  # 35
    # Due west → ~270°
    var b4 = initial_bearing(0.0, 1.0, 0.0, 0.0)
    _assert_close(b4, 270.0, 0.1, "due west bearing ~270°")  # 36
    print("    PASSED")


fn test_destination_point() raises:
    print("  test_destination_point...")
    # From equator, go north 111.2 km ≈ 1° latitude
    var dp = destination_point(0.0, 0.0, 0.0, 111.2)
    _assert_close(dp[0], 1.0, 0.1, "~1° north after 111km")  # 37
    _assert_close(dp[1], 0.0, 0.1, "lon unchanged going north")  # 38
    print("    PASSED")


fn test_midpoint() raises:
    print("  test_midpoint...")
    # Midpoint of (0,0) and (0,2) should be (0,1)
    var mp = midpoint(0.0, 0.0, 0.0, 2.0)
    _assert_close(mp[0], 0.0, 0.01, "midpoint lat ~0")  # 39
    _assert_close(mp[1], 1.0, 0.01, "midpoint lon ~1")  # 40
    # Midpoint of (10,0) and (-10,0) should be (0,0)
    var mp2 = midpoint(10.0, 0.0, -10.0, 0.0)
    _assert_close(mp2[0], 0.0, 0.01, "symmetric midpoint lat=0")  # 41
    print("    PASSED")


fn test_cross_track_distance() raises:
    print("  test_cross_track_distance...")
    # Point on the path → cross-track ≈ 0
    var d = cross_track_distance(0.5, 0.0, 0.0, 0.0, 1.0, 0.0)
    _assert_close(d, 0.0, 1.0, "on-path cross-track ~0")  # 42
    # Point off path → positive distance
    var d2 = cross_track_distance(0.5, 1.0, 0.0, 0.0, 1.0, 0.0)
    _assert(d2 > 50.0, "off-path cross-track > 50km")  # 43
    print("    PASSED")


fn test_along_track_distance() raises:
    print("  test_along_track_distance...")
    # Point near the midpoint of the path
    var d = along_track_distance(0.5, 0.0, 0.0, 0.0, 1.0, 0.0)
    _assert(d > 0.0, "along-track distance > 0")  # 44
    _assert(d < 120.0, "along-track distance < 120km for 1° path")  # 45
    print("    PASSED")


fn test_geodetic_to_ecef() raises:
    print("  test_geodetic_to_ecef...")
    # (0, 0, 0) → (a, 0, 0) where a = WGS84_A
    var ecef = geodetic_to_ecef(0.0, 0.0, 0.0)
    _assert_close(ecef[0], 6378137.0, 1.0, "ECEF x at origin")  # 46
    _assert_close(ecef[1], 0.0, 1.0, "ECEF y at origin")  # 47
    _assert_close(ecef[2], 0.0, 1.0, "ECEF z at origin")  # 48
    # North pole (90, 0, 0) → (0, 0, b)
    var ecef2 = geodetic_to_ecef(90.0, 0.0, 0.0)
    _assert_close(ecef2[0], 0.0, 1.0, "ECEF x at north pole")  # 49
    _assert_close(ecef2[1], 0.0, 1.0, "ECEF y at north pole")  # 50
    _assert_close(ecef2[2], 6356752.314, 1.0, "ECEF z at north pole")  # 51
    print("    PASSED")


fn test_ecef_to_geodetic() raises:
    print("  test_ecef_to_geodetic...")
    # Round-trip: geodetic → ECEF → geodetic
    var ecef = geodetic_to_ecef(40.0, -74.0, 100.0)
    var geo = ecef_to_geodetic(ecef[0], ecef[1], ecef[2])
    _assert_close(geo[0], 40.0, 0.001, "round-trip lat")  # 52
    _assert_close(geo[1], -74.0, 0.001, "round-trip lon")  # 53
    _assert_close(geo[2], 100.0, 1.0, "round-trip alt")  # 54
    print("    PASSED")


fn test_rhumb_distance() raises:
    print("  test_rhumb_distance...")
    # Same point → 0
    var d = rhumb_distance(40.0, -74.0, 40.0, -74.0)
    _assert_close(d, 0.0, 0.01, "rhumb same point → 0")  # 55
    # Along equator: (0,0)→(0,1) ≈ 111.2 km
    var d2 = rhumb_distance(0.0, 0.0, 0.0, 1.0)
    _assert_close(d2, 111.2, 2.0, "rhumb 1° equator ~111km")  # 56
    # Rhumb should be ≥ great-circle (slightly longer path)
    var rh = rhumb_distance(51.5074, -0.1278, 48.8566, 2.3522)
    var gc = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)
    _assert(rh >= gc - 1.0, "rhumb >= great-circle (approx)")  # 57
    print("    PASSED")


# ── Formal Logic tests ──────────────────────────────────────────────────────


fn test_truth_and() raises:
    print("  test_truth_and...")
    _assert(truth_and(True, True) == True, "T∧T=T")  # 58
    _assert(truth_and(True, False) == False, "T∧F=F")  # 59
    _assert(truth_and(False, True) == False, "F∧T=F")  # 60
    _assert(truth_and(False, False) == False, "F∧F=F")  # 61
    print("    PASSED")


fn test_truth_or() raises:
    print("  test_truth_or...")
    _assert(truth_or(True, True) == True, "T∨T=T")  # 62
    _assert(truth_or(True, False) == True, "T∨F=T")  # 63
    _assert(truth_or(False, False) == False, "F∨F=F")  # 64
    print("    PASSED")


fn test_truth_not() raises:
    print("  test_truth_not...")
    _assert(truth_not(True) == False, "¬T=F")  # 65
    _assert(truth_not(False) == True, "¬F=T")  # 66
    print("    PASSED")


fn test_truth_implies() raises:
    print("  test_truth_implies...")
    _assert(truth_implies(True, True) == True, "T→T=T")  # 67
    _assert(truth_implies(True, False) == False, "T→F=F")  # 68
    _assert(truth_implies(False, True) == True, "F→T=T")  # 69
    _assert(truth_implies(False, False) == True, "F→F=T")  # 70
    print("    PASSED")


fn test_truth_iff() raises:
    print("  test_truth_iff...")
    _assert(truth_iff(True, True) == True, "T↔T=T")  # 71
    _assert(truth_iff(True, False) == False, "T↔F=F")  # 72
    _assert(truth_iff(False, False) == True, "F↔F=T")  # 73
    print("    PASSED")


fn test_truth_xor() raises:
    print("  test_truth_xor...")
    _assert(truth_xor(True, True) == False, "T⊕T=F")  # 74
    _assert(truth_xor(True, False) == True, "T⊕F=T")  # 75
    _assert(truth_xor(False, True) == True, "F⊕T=T")  # 76
    print("    PASSED")


fn test_truth_nand_nor() raises:
    print("  test_truth_nand_nor...")
    _assert(truth_nand(True, True) == False, "NAND(T,T)=F")  # 77
    _assert(truth_nand(True, False) == True, "NAND(T,F)=T")  # 78
    _assert(truth_nor(False, False) == True, "NOR(F,F)=T")  # 79
    _assert(truth_nor(True, False) == False, "NOR(T,F)=F")  # 80
    print("    PASSED")


fn test_modus_ponens() raises:
    print("  test_modus_ponens...")
    # p=T, p→q=T → q=T
    _assert(modus_ponens(True, True) == True, "MP: T,T→T")  # 81
    # p=F → no valid conclusion
    _assert(modus_ponens(False, True) == False, "MP: F,T→F")  # 82
    print("    PASSED")


fn test_modus_tollens() raises:
    print("  test_modus_tollens...")
    # ¬q=T, p→q=T → ¬p=T
    _assert(modus_tollens(True, True) == True, "MT: T,T→T")  # 83
    # ¬q=F → no valid conclusion
    _assert(modus_tollens(False, True) == False, "MT: F,T→F")  # 84
    print("    PASSED")


fn test_hypothetical_syllogism() raises:
    print("  test_hypothetical_syllogism...")
    _assert(hypothetical_syllogism(True, True) == True, "HS: T,T→T")  # 85
    _assert(hypothetical_syllogism(True, False) == False, "HS: T,F→F")  # 86
    _assert(hypothetical_syllogism(False, True) == False, "HS: F,T→F")  # 87
    print("    PASSED")


fn test_disjunctive_syllogism() raises:
    print("  test_disjunctive_syllogism...")
    _assert(disjunctive_syllogism(True, True) == True, "DS: T,T→T")  # 88
    _assert(disjunctive_syllogism(True, False) == False, "DS: T,F→F")  # 89
    _assert(disjunctive_syllogism(False, True) == False, "DS: F,T→F")  # 90
    print("    PASSED")


fn test_tautology_contradiction() raises:
    print("  test_tautology_contradiction...")
    # fn_idx=15 is tautology (always True)
    _assert(is_tautology_2var(15) == True, "idx 15 is tautology")  # 91
    # fn_idx=1 is AND (not tautology)
    _assert(is_tautology_2var(1) == False, "AND not tautology")  # 92
    # fn_idx=0 is contradiction (always False)
    _assert(is_contradiction_2var(0) == True, "idx 0 is contradiction")  # 93
    # fn_idx=7 is OR (not contradiction)
    _assert(is_contradiction_2var(7) == False, "OR not contradiction")  # 94
    # fn_idx=13 is IMPLIES → tautology? No (T→F=F)
    _assert(is_tautology_2var(13) == False, "implies not tautology")  # 95
    print("    PASSED")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 62 tests: Spectral Analysis, Geodesy, Formal Logic")
    print("=" * 60)

    print("\n[Spectral Analysis]")
    test_power_spectral_density()
    test_cross_spectral_density()
    test_coherence()
    test_spectral_centroid()
    test_spectral_bandwidth()
    test_spectral_rolloff()
    test_spectral_flatness()
    test_spectral_entropy()
    test_band_energy()
    test_peak_frequency()

    print("\n[Geodesy]")
    test_haversine_distance()
    test_vincenty_distance()
    test_initial_bearing()
    test_destination_point()
    test_midpoint()
    test_cross_track_distance()
    test_along_track_distance()
    test_geodetic_to_ecef()
    test_ecef_to_geodetic()
    test_rhumb_distance()

    print("\n[Formal Logic]")
    test_truth_and()
    test_truth_or()
    test_truth_not()
    test_truth_implies()
    test_truth_iff()
    test_truth_xor()
    test_truth_nand_nor()
    test_modus_ponens()
    test_modus_tollens()
    test_hypothetical_syllogism()
    test_disjunctive_syllogism()
    test_tautology_contradiction()

    print("\n" + "=" * 60)
    print("Wave 62: ALL 95 assertions PASSED")
