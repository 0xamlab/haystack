"""Tests for Wave 35 — Audio Processing, Set Operations, Geospatial Math."""

from audio import (
    amplitude_to_db,
    db_to_amplitude,
    frequency_to_midi,
    midi_to_frequency,
    generate_sine,
    rms_amplitude,
    zero_crossing_rate,
    envelope,
    normalize_audio,
    mix_signals,
)
from set_ops import (
    set_union,
    set_intersection,
    set_difference,
    set_symmetric_difference,
    is_subset,
    is_superset,
    set_equals,
    power_set_size,
    jaccard_index,
    to_set,
    set_contains,
    set_cardinality,
)
from earth import (
    haversine,
    bearing,
    midpoint,
    destination_point,
    bounding_box,
    deg_to_rad,
    rad_to_deg,
    is_valid_coordinate,
    distance_on_unit_sphere,
    cross_track_distance,
)
from std.math import abs as fabs, sqrt


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Audio tests ──────────────────────────────────────────────────────────────


def test_audio() raises:
    print("── Audio tests ──")
    var passed = 0

    # 1. amplitude_to_db(1.0) == 0.0
    _assert_close(amplitude_to_db(1.0), 0.0, 1e-9, "amp_to_db(1.0)")
    passed += 1

    # 2. amplitude_to_db(10.0) ≈ 20.0
    _assert_close(amplitude_to_db(10.0), 20.0, 0.01, "amp_to_db(10.0)")
    passed += 1

    # 3. amplitude_to_db(100.0) ≈ 40.0
    _assert_close(amplitude_to_db(100.0), 40.0, 0.01, "amp_to_db(100.0)")
    passed += 1

    # 4. db_to_amplitude(0.0) == 1.0
    _assert_close(db_to_amplitude(0.0), 1.0, 1e-9, "db_to_amp(0.0)")
    passed += 1

    # 5. db_to_amplitude(20.0) ≈ 10.0
    _assert_close(db_to_amplitude(20.0), 10.0, 0.01, "db_to_amp(20.0)")
    passed += 1

    # 6. roundtrip: db_to_amplitude(amplitude_to_db(x)) ≈ x
    var x_val: Float64 = 3.7
    _assert_close(db_to_amplitude(amplitude_to_db(x_val)), x_val, 1e-9, "amp<->db roundtrip")
    passed += 1

    # 7. frequency_to_midi(440.0) == 69.0
    _assert_close(frequency_to_midi(440.0), 69.0, 1e-9, "freq_to_midi(440)")
    passed += 1

    # 8. midi_to_frequency(69.0) == 440.0
    _assert_close(midi_to_frequency(69.0), 440.0, 1e-9, "midi_to_freq(69)")
    passed += 1

    # 9. frequency_to_midi(880.0) == 81.0
    _assert_close(frequency_to_midi(880.0), 81.0, 0.01, "freq_to_midi(880)")
    passed += 1

    # 10. midi_to_frequency(60.0) ≈ 261.63 (middle C)
    _assert_close(midi_to_frequency(60.0), 261.6256, 0.01, "midi_to_freq(60)")
    passed += 1

    # 11. roundtrip: midi_to_frequency(frequency_to_midi(f)) ≈ f
    var f_val: Float64 = 523.25
    _assert_close(midi_to_frequency(frequency_to_midi(f_val)), f_val, 0.01, "freq<->midi roundtrip")
    passed += 1

    # 12. generate_sine — correct length
    var sine = generate_sine(440.0, 44100.0, 100)
    _assert(len(sine) == 100, "sine length")
    passed += 1

    # 13. generate_sine — first sample ≈ 0
    _assert_close(sine[0], 0.0, 1e-9, "sine[0] ≈ 0")
    passed += 1

    # 14. rms_amplitude of sine wave ≈ 1/sqrt(2)
    var long_sine = generate_sine(1.0, 1000.0, 1000)
    var rms = rms_amplitude(long_sine)
    _assert_close(rms, 1.0 / sqrt(2.0), 0.01, "rms of sine ≈ 1/√2")
    passed += 1

    # 15. rms of constant signal
    var const_sig = List[Float64]()
    for i in range(100):
        const_sig.append(3.0)
    _assert_close(rms_amplitude(const_sig), 3.0, 1e-9, "rms constant")
    passed += 1

    # 16. zero_crossing_rate of alternating signal ≈ 1.0
    var alt = List[Float64]()
    for i in range(100):
        if i % 2 == 0:
            alt.append(1.0)
        else:
            alt.append(-1.0)
    _assert_close(zero_crossing_rate(alt), 1.0, 0.01, "zcr alternating")
    passed += 1

    # 17. zero_crossing_rate of constant signal == 0.0
    _assert_close(zero_crossing_rate(const_sig), 0.0, 1e-9, "zcr constant")
    passed += 1

    # 18. normalize_audio — max abs ≈ 1.0
    var raw = List[Float64]()
    raw.append(2.0)
    raw.append(-5.0)
    raw.append(3.0)
    var normed = normalize_audio(raw)
    # peak was 5.0, so max abs of result should be 1.0
    var max_abs: Float64 = 0.0
    for i in range(len(normed)):
        var av = fabs(normed[i])
        if av > max_abs:
            max_abs = av
    _assert_close(max_abs, 1.0, 1e-9, "normalize max abs")
    passed += 1

    # 19. normalize_audio preserves ratios
    _assert_close(normed[0], 0.4, 1e-9, "normalize ratio [0]")
    passed += 1

    # 20. mix_signals with weight 1.0 returns first signal
    var sig_a = List[Float64]()
    sig_a.append(1.0)
    sig_a.append(2.0)
    sig_a.append(3.0)
    var sig_b = List[Float64]()
    sig_b.append(10.0)
    sig_b.append(20.0)
    sig_b.append(30.0)
    var mixed = mix_signals(sig_a, sig_b, 1.0)
    _assert_close(mixed[0], 1.0, 1e-9, "mix w=1.0 [0]")
    _assert_close(mixed[1], 2.0, 1e-9, "mix w=1.0 [1]")
    passed += 1

    # 21. mix_signals with weight 0.0 returns second signal
    var mixed2 = mix_signals(sig_a, sig_b, 0.0)
    _assert_close(mixed2[0], 10.0, 1e-9, "mix w=0.0 [0]")
    passed += 1

    # 22. mix_signals with weight 0.5 is average
    var mixed3 = mix_signals(sig_a, sig_b, 0.5)
    _assert_close(mixed3[0], 5.5, 1e-9, "mix w=0.5 [0]")
    passed += 1

    # 23. envelope — output length matches input
    var env = envelope(long_sine, 5)
    _assert(len(env) == len(long_sine), "envelope length")
    passed += 1

    # 24. amplitude_to_db of zero returns floor
    _assert(amplitude_to_db(0.0) < -100.0, "amp_to_db(0) floor")
    passed += 1

    print("  Audio: " + String(passed) + " assertions passed")


# ── Set operations tests ─────────────────────────────────────────────────────


def test_set_ops() raises:
    print("── Set operations tests ──")
    var passed = 0

    var a = List[Int]()
    a.append(1); a.append(3); a.append(5)
    var b = List[Int]()
    b.append(2); b.append(3); b.append(4)

    # 1. set_union([1,3,5], [2,3,4]) == [1,2,3,4,5]
    var u = set_union(a, b)
    _assert(len(u) == 5, "union length")
    _assert(u[0] == 1 and u[1] == 2 and u[2] == 3 and u[3] == 4 and u[4] == 5, "union values")
    passed += 1

    # 2. set_intersection([1,3,5], [2,3,4]) == [3]
    var inter = set_intersection(a, b)
    _assert(len(inter) == 1, "intersection length")
    _assert(inter[0] == 3, "intersection value")
    passed += 1

    # 3. set_difference([1,3,5], [2,3,4]) == [1,5]
    var diff = set_difference(a, b)
    _assert(len(diff) == 2, "difference length")
    _assert(diff[0] == 1 and diff[1] == 5, "difference values")
    passed += 1

    # 4. set_symmetric_difference([1,3,5], [2,3,4]) == [1,2,4,5]
    var sym = set_symmetric_difference(a, b)
    _assert(len(sym) == 4, "sym_diff length")
    _assert(sym[0] == 1 and sym[1] == 2 and sym[2] == 4 and sym[3] == 5, "sym_diff values")
    passed += 1

    # 5. is_subset([1,3], [1,2,3]) == True
    var sub = List[Int]()
    sub.append(1); sub.append(3)
    var sup = List[Int]()
    sup.append(1); sup.append(2); sup.append(3)
    _assert(is_subset(sub, sup), "is_subset True")
    passed += 1

    # 6. is_subset([1,4], [1,2,3]) == False
    var not_sub = List[Int]()
    not_sub.append(1); not_sub.append(4)
    _assert(not is_subset(not_sub, sup), "is_subset False")
    passed += 1

    # 7. is_superset([1,2,3], [1,3]) == True
    _assert(is_superset(sup, sub), "is_superset True")
    passed += 1

    # 8. is_superset([1,3], [1,2,3]) == False
    _assert(not is_superset(sub, sup), "is_superset False")
    passed += 1

    # 9. set_equals([1,2,3], [1,2,3]) == True
    _assert(set_equals(sup, sup), "set_equals True")
    passed += 1

    # 10. set_equals([1,3,5], [2,3,4]) == False
    _assert(not set_equals(a, b), "set_equals False")
    passed += 1

    # 11. jaccard_index([1,2,3], [2,3,4]) ≈ 0.5
    var j1 = List[Int]()
    j1.append(1); j1.append(2); j1.append(3)
    var j2 = List[Int]()
    j2.append(2); j2.append(3); j2.append(4)
    _assert_close(jaccard_index(j1, j2), 0.5, 1e-9, "jaccard 0.5")
    passed += 1

    # 12. jaccard_index of identical sets == 1.0
    _assert_close(jaccard_index(j1, j1), 1.0, 1e-9, "jaccard identical")
    passed += 1

    # 13. jaccard_index of disjoint sets == 0.0
    var d1 = List[Int]()
    d1.append(1); d1.append(2)
    var d2 = List[Int]()
    d2.append(3); d2.append(4)
    _assert_close(jaccard_index(d1, d2), 0.0, 1e-9, "jaccard disjoint")
    passed += 1

    # 14. to_set([3,1,2,1]) == [1,2,3]
    var raw = List[Int]()
    raw.append(3); raw.append(1); raw.append(2); raw.append(1)
    var s = to_set(raw)
    _assert(len(s) == 3, "to_set length")
    _assert(s[0] == 1 and s[1] == 2 and s[2] == 3, "to_set values")
    passed += 1

    # 15. set_contains([1,2,3,4,5], 3) == True
    var big = List[Int]()
    big.append(1); big.append(2); big.append(3); big.append(4); big.append(5)
    _assert(set_contains(big, 3), "set_contains True")
    passed += 1

    # 16. set_contains([1,2,3,4,5], 6) == False
    _assert(not set_contains(big, 6), "set_contains False")
    passed += 1

    # 17. power_set_size(3) == 8
    _assert(power_set_size(3) == 8, "power_set_size(3)")
    passed += 1

    # 18. power_set_size(0) == 1
    _assert(power_set_size(0) == 1, "power_set_size(0)")
    passed += 1

    # 19. power_set_size(10) == 1024
    _assert(power_set_size(10) == 1024, "power_set_size(10)")
    passed += 1

    # 20. set_cardinality
    _assert(set_cardinality(big) == 5, "set_cardinality")
    passed += 1

    # 21. union with empty set
    var empty = List[Int]()
    var u_empty = set_union(a, empty)
    _assert(set_equals(u_empty, a), "union with empty")
    passed += 1

    # 22. intersection with empty set
    var i_empty = set_intersection(a, empty)
    _assert(len(i_empty) == 0, "intersection with empty")
    passed += 1

    print("  Set ops: " + String(passed) + " assertions passed")


# ── Earth / Geospatial tests ─────────────────────────────────────────────────


def test_earth() raises:
    print("── Earth tests ──")
    var passed = 0

    # 1. haversine(0,0,0,0) == 0
    _assert_close(haversine(0.0, 0.0, 0.0, 0.0), 0.0, 1e-9, "haversine zero")
    passed += 1

    # 2. haversine(0,0,0,90) ≈ 10007.5 km (quarter Earth circumference)
    var quarter = haversine(0.0, 0.0, 0.0, 90.0)
    _assert_close(quarter, 10007.5, 10.0, "haversine quarter earth")
    passed += 1

    # 3. haversine London-Paris ≈ 344 km
    var lp = haversine(51.5074, -0.1278, 48.8566, 2.3522)
    _assert_close(lp, 344.0, 5.0, "haversine London-Paris")
    passed += 1

    # 4. haversine is symmetric
    var lp2 = haversine(48.8566, 2.3522, 51.5074, -0.1278)
    _assert_close(lp, lp2, 1e-6, "haversine symmetric")
    passed += 1

    # 5. haversine poles = ~20015 km (half Earth)
    var poles = haversine(90.0, 0.0, -90.0, 0.0)
    _assert_close(poles, 20015.0, 20.0, "haversine poles")
    passed += 1

    # 6. bearing is finite and in [0, 360)
    var brng = bearing(51.5074, -0.1278, 48.8566, 2.3522)
    _assert(brng >= 0.0 and brng < 360.0, "bearing in [0,360)")
    passed += 1

    # 7. bearing due east from equator
    var brng_east = bearing(0.0, 0.0, 0.0, 90.0)
    _assert_close(brng_east, 90.0, 0.5, "bearing due east")
    passed += 1

    # 8. bearing due north
    var brng_north = bearing(0.0, 0.0, 45.0, 0.0)
    _assert_close(brng_north, 0.0, 0.5, "bearing due north")
    passed += 1

    # 9. midpoint(0,0,0,90) ≈ [0, 45]
    var mid = midpoint(0.0, 0.0, 0.0, 90.0)
    _assert_close(mid[0], 0.0, 0.5, "midpoint lat")
    _assert_close(mid[1], 45.0, 0.5, "midpoint lon")
    passed += 1

    # 10. is_valid_coordinate(45, 90) == True
    _assert(is_valid_coordinate(45.0, 90.0), "valid coord 45,90")
    passed += 1

    # 11. is_valid_coordinate(100, 0) == False
    _assert(not is_valid_coordinate(100.0, 0.0), "invalid coord 100,0")
    passed += 1

    # 12. is_valid_coordinate(0, 200) == False
    _assert(not is_valid_coordinate(0.0, 200.0), "invalid coord 0,200")
    passed += 1

    # 13. is_valid_coordinate(-90, -180) == True
    _assert(is_valid_coordinate(-90.0, -180.0), "valid coord -90,-180")
    passed += 1

    # 14. deg_to_rad(180) ≈ π
    _assert_close(deg_to_rad(180.0), 3.141592653589793, 1e-9, "deg_to_rad(180)")
    passed += 1

    # 15. rad_to_deg(π) ≈ 180
    _assert_close(rad_to_deg(3.141592653589793), 180.0, 1e-9, "rad_to_deg(π)")
    passed += 1

    # 16. deg_to_rad(0) == 0
    _assert_close(deg_to_rad(0.0), 0.0, 1e-12, "deg_to_rad(0)")
    passed += 1

    # 17. deg_to_rad(360) ≈ 2π
    _assert_close(deg_to_rad(360.0), 6.283185307179586, 1e-9, "deg_to_rad(360)")
    passed += 1

    # 18. bounding_box — min < center < max for lat
    var bb = bounding_box(40.0, -74.0, 100.0)
    _assert(bb[0] < 40.0, "bbox min_lat < center")
    _assert(bb[2] > 40.0, "bbox max_lat > center")
    passed += 1

    # 19. bounding_box — min < center < max for lon
    _assert(bb[1] < -74.0, "bbox min_lon < center")
    _assert(bb[3] > -74.0, "bbox max_lon > center")
    passed += 1

    # 20. destination_point — going 0 km stays at origin
    var dp0 = destination_point(45.0, 90.0, 0.0, 0.0)
    _assert_close(dp0[0], 45.0, 0.01, "dest_point 0km lat")
    _assert_close(dp0[1], 90.0, 0.01, "dest_point 0km lon")
    passed += 1

    # 21. destination_point — going north then measuring distance
    var dp_north = destination_point(0.0, 0.0, 0.0, 111.0)
    # ~1 degree north
    _assert_close(dp_north[0], 1.0, 0.1, "dest_point north lat")
    passed += 1

    # 22. distance_on_unit_sphere(0,0,0,0) == 0
    _assert_close(distance_on_unit_sphere(0.0, 0.0, 0.0, 0.0), 0.0, 1e-12, "unit_sphere zero")
    passed += 1

    # 23. cross_track_distance — point on the path gives ~0
    var ctd = cross_track_distance(0.0, 0.0, 0.0, 90.0, 0.0, 45.0)
    _assert_close(ctd, 0.0, 1.0, "cross_track on path")
    passed += 1

    # 24. cross_track_distance — point off path gives > 0
    var ctd2 = cross_track_distance(0.0, 0.0, 0.0, 90.0, 10.0, 45.0)
    _assert(ctd2 > 100.0, "cross_track off path > 0")
    passed += 1

    print("  Earth: " + String(passed) + " assertions passed")


# ── main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 35 Tests: Audio, Set Ops, Earth ===")
    test_audio()
    test_set_ops()
    test_earth()
    print("=== All Wave 35 tests passed! ===")
