"""Tests for Wave 64 — Petri Net, Cryptanalysis, Aerospace."""

from petri_net import (
    is_transition_enabled_2p,
    fire_transition_2p,
    token_count_3p,
    is_deadlocked_1t_2p,
    is_deadlocked_2t_2p,
    reachable_from_firing,
    place_bounded,
    is_live_transition,
    coverability_check,
    incidence_value,
    siphon_empty_3p,
    is_transition_enabled_list,
    fire_transition_list,
)
from cryptanalysis import (
    frequency_score_2,
    index_of_coincidence_2,
    expected_ic_random,
    expected_ic_english,
    friedman_key_length,
    kasiski_distance_gcd,
    caesar_decrypt_score,
    hamming_distance_bytes,
    entropy_bits_2,
    entropy_bits_4,
    brute_force_time_estimate,
    avalanche_effect,
)
from aerospace import (
    dynamic_pressure,
    lift_force,
    drag_force,
    lift_to_drag_ratio,
    thrust_required,
    specific_impulse,
    tsiolkovsky_delta_v,
    mach_number,
    speed_of_sound,
    orbital_velocity,
    escape_velocity,
    hohmann_delta_v,
)
from std.math import abs as fabs, sqrt, log as _ln


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Petri Net Tests ──────────────────────────────────────────────────────────


def test_petri_net_transition_enabled() raises:
    print("  test_petri_net_transition_enabled...")
    # Marking [3, 2], input arcs [1, 1] → enabled
    _assert(is_transition_enabled_2p(3, 2, 1, 1), "transition should be enabled")
    # Marking [0, 2], input arcs [1, 1] → not enabled
    _assert(not is_transition_enabled_2p(0, 2, 1, 1), "transition NOT enabled")
    # Exact match
    _assert(is_transition_enabled_2p(1, 1, 1, 1), "exact match enabled")
    # Zero arcs always enabled
    _assert(is_transition_enabled_2p(0, 0, 0, 0), "zero arcs enabled")


def test_petri_net_fire_transition() raises:
    print("  test_petri_net_fire_transition...")
    # Marking [3, 1], in [1, 0], out [0, 2] → new [2, 3], sum = 5
    _assert(fire_transition_2p(3, 1, 1, 0, 0, 2) == 5, "fire sum=5")
    # Marking [5, 5], in [2, 2], out [1, 1] → new [4, 4], sum = 8
    _assert(fire_transition_2p(5, 5, 2, 2, 1, 1) == 8, "fire sum=8")


def test_petri_net_token_count() raises:
    print("  test_petri_net_token_count...")
    _assert(token_count_3p(3, 2, 5) == 10, "token_count 3+2+5=10")
    _assert(token_count_3p(0, 0, 0) == 0, "token_count all zero")
    _assert(token_count_3p(1, 0, 0) == 1, "token_count 1+0+0=1")


def test_petri_net_deadlocked() raises:
    print("  test_petri_net_deadlocked...")
    # 1-transition: marking [0,0], need [1,0] → deadlocked
    _assert(is_deadlocked_1t_2p(0, 0, 1, 0), "1t deadlocked")
    # 1-transition: marking [1,0], need [1,0] → not deadlocked
    _assert(not is_deadlocked_1t_2p(1, 0, 1, 0), "1t not deadlocked")
    # 2-transition: marking [0,0], both need tokens → deadlocked
    _assert(is_deadlocked_2t_2p(0, 0, 1, 0, 0, 1), "2t deadlocked")
    # 2-transition: marking [1,0], t0 needs [1,0] → t0 enabled → not deadlocked
    _assert(not is_deadlocked_2t_2p(1, 0, 1, 0, 0, 1), "2t not deadlocked")


def test_petri_net_reachable() raises:
    print("  test_petri_net_reachable...")
    _assert(reachable_from_firing(10, 3, 5) == 12, "10-3+5=12")
    _assert(reachable_from_firing(5, 5, 5) == 5, "5-5+5=5")
    _assert(reachable_from_firing(0, 0, 0) == 0, "0-0+0=0")


def test_petri_net_place_bounded() raises:
    print("  test_petri_net_place_bounded...")
    _assert(place_bounded(3, 5), "3<=5 bounded")
    _assert(place_bounded(5, 5), "5<=5 bounded")
    _assert(not place_bounded(6, 5), "6>5 not bounded")


def test_petri_net_live_transition() raises:
    print("  test_petri_net_live_transition...")
    _assert_close(is_live_transition(5, 10), 0.5, 1e-9, "live 5/10")
    _assert_close(is_live_transition(10, 10), 1.0, 1e-9, "live 10/10")
    _assert_close(is_live_transition(0, 10), 0.0, 1e-9, "live 0/10")
    _assert_close(is_live_transition(0, 0), 0.0, 1e-9, "live 0/0")


def test_petri_net_coverability() raises:
    print("  test_petri_net_coverability...")
    _assert(coverability_check(5, 3), "5>=3 covers")
    _assert(coverability_check(3, 3), "3>=3 covers")
    _assert(not coverability_check(2, 3), "2<3 no cover")


def test_petri_net_incidence() raises:
    print("  test_petri_net_incidence...")
    _assert(incidence_value(3, 1) == 2, "inc 3-1=2")
    _assert(incidence_value(1, 3) == -2, "inc 1-3=-2")
    _assert(incidence_value(2, 2) == 0, "inc 2-2=0")


def test_petri_net_siphon() raises:
    print("  test_petri_net_siphon...")
    # Siphon members: places 0 and 2. Both have 0 tokens → empty siphon
    _assert(siphon_empty_3p(0, 5, 0, True, False, True), "siphon empty")
    # Place 0 has token → siphon not empty
    _assert(not siphon_empty_3p(1, 5, 0, True, False, True), "siphon not empty")
    # No siphon members → trivially empty
    _assert(siphon_empty_3p(5, 5, 5, False, False, False), "no members trivially empty")


def test_petri_net_list_variants() raises:
    print("  test_petri_net_list_variants...")
    # List-based transition enabled
    var marking = List[Int]()
    marking.append(3); marking.append(2)
    var arcs = List[Int]()
    arcs.append(1); arcs.append(1)
    _assert(is_transition_enabled_list(marking, arcs, 2), "list enabled")

    var marking2 = List[Int]()
    marking2.append(0); marking2.append(2)
    _assert(not is_transition_enabled_list(marking2, arcs, 2), "list not enabled")

    # List-based fire
    var inp = List[Int]()
    inp.append(1); inp.append(0)
    var out = List[Int]()
    out.append(0); out.append(2)
    _assert(fire_transition_list(marking, inp, out, 2) == 6, "list fire sum=6")


# ── Cryptanalysis Tests ──────────────────────────────────────────────────────


def test_crypto_frequency_score() raises:
    print("  test_crypto_frequency_score...")
    # Uniform: counts=[10,10], expected=[0.5,0.5] → chi2=0
    _assert_close(frequency_score_2(10, 10, 0.5, 0.5), 0.0, 1e-9, "uniform freq 0")
    # Skewed: counts=[20,0], expected=[0.5,0.5] → 20
    _assert_close(frequency_score_2(20, 0, 0.5, 0.5), 20.0, 1e-9, "skewed freq 20")


def test_crypto_ic() raises:
    print("  test_crypto_ic...")
    # counts=[10,10], total=20 → (10*9+10*9)/(20*19) = 180/380
    var ic = index_of_coincidence_2(10, 10, 20)
    _assert_close(ic, 180.0 / 380.0, 1e-6, "IC uniform")
    # Edge: total=1
    _assert_close(index_of_coincidence_2(1, 0, 1), 0.0, 1e-9, "IC total=1")


def test_crypto_expected_ic() raises:
    print("  test_crypto_expected_ic...")
    _assert_close(expected_ic_random(26), 1.0 / 26.0, 1e-9, "random IC 1/26")
    _assert_close(expected_ic_random(2), 0.5, 1e-9, "random IC 1/2")
    _assert_close(expected_ic_english(), 0.0667, 1e-9, "english IC")


def test_crypto_friedman() raises:
    print("  test_crypto_friedman...")
    var kl = friedman_key_length(0.0667, 26)
    _assert_close(kl, 1.0, 0.1, "friedman kl ~1 for english IC")
    var kl2 = friedman_key_length(0.045, 26)
    _assert(kl2 > 1.0, "friedman kl > 1 for lower IC")


def test_crypto_kasiski() raises:
    print("  test_crypto_kasiski...")
    _assert(kasiski_distance_gcd(12, 8) == 4, "gcd(12,8)=4")
    _assert(kasiski_distance_gcd(15, 10) == 5, "gcd(15,10)=5")
    _assert(kasiski_distance_gcd(7, 13) == 1, "gcd(7,13)=1")


def test_crypto_caesar() raises:
    print("  test_crypto_caesar...")
    _assert_close(caesar_decrypt_score(0, 0.127, 0.127), 0.0, 1e-9, "caesar perfect")
    _assert_close(caesar_decrypt_score(3, 0.127, 0.077), 0.05, 1e-9, "caesar off 0.05")


def test_crypto_hamming() raises:
    print("  test_crypto_hamming...")
    _assert(hamming_distance_bytes(0, 0) == 0, "hamming 0,0=0")
    _assert(hamming_distance_bytes(0xFF, 0x00) == 8, "hamming FF,00=8")
    _assert(hamming_distance_bytes(0b1010, 0b0101) == 4, "hamming 1010,0101=4")
    _assert(hamming_distance_bytes(0b1100, 0b1010) == 2, "hamming 1100,1010=2")


def test_crypto_entropy() raises:
    print("  test_crypto_entropy...")
    # Uniform 2: H = 1 bit
    _assert_close(entropy_bits_2(0.5, 0.5), 1.0, 1e-9, "entropy 2-uniform=1")
    # Certain: H = 0
    _assert_close(entropy_bits_2(1.0, 0.0), 0.0, 1e-9, "entropy certain=0")
    # Uniform 4: H = 2 bits
    _assert_close(entropy_bits_4(0.25, 0.25, 0.25, 0.25), 2.0, 1e-9, "entropy 4-uniform=2")


def test_crypto_brute_force() raises:
    print("  test_crypto_brute_force...")
    _assert_close(brute_force_time_estimate(8, 1e6), 256.0 / 1e6, 1e-12, "brute 8-bit")
    _assert_close(brute_force_time_estimate(0, 1000.0), 0.001, 1e-12, "brute 0-bit")
    # 2^16 = 65536
    _assert_close(brute_force_time_estimate(16, 65536.0), 1.0, 1e-9, "brute 16-bit")


def test_crypto_avalanche() raises:
    print("  test_crypto_avalanche...")
    _assert_close(avalanche_effect(64, 128), 0.5, 1e-9, "avalanche 0.5")
    _assert_close(avalanche_effect(0, 128), 0.0, 1e-9, "avalanche 0")
    _assert_close(avalanche_effect(128, 128), 1.0, 1e-9, "avalanche 1")
    _assert_close(avalanche_effect(0, 0), 0.0, 1e-9, "avalanche 0/0")


# ── Aerospace Tests ──────────────────────────────────────────────────────────


def test_aero_dynamic_pressure() raises:
    print("  test_aero_dynamic_pressure...")
    # q = 0.5 * 1.225 * 100^2 = 6125
    _assert_close(dynamic_pressure(1.225, 100.0), 6125.0, 1e-6, "dyn press")
    _assert_close(dynamic_pressure(0.0, 300.0), 0.0, 1e-9, "dyn press zero rho")


def test_aero_lift_drag() raises:
    print("  test_aero_lift_drag...")
    # L = 1.5 * 6125 * 20 = 183750
    _assert_close(lift_force(1.5, 6125.0, 20.0), 183750.0, 1e-6, "lift")
    # D = 0.03 * 6125 * 20 = 3675
    _assert_close(drag_force(0.03, 6125.0, 20.0), 3675.0, 1e-6, "drag")


def test_aero_ld_ratio() raises:
    print("  test_aero_ld_ratio...")
    _assert_close(lift_to_drag_ratio(1.5, 0.03), 50.0, 1e-9, "L/D=50")
    _assert_close(lift_to_drag_ratio(0.0, 0.03), 0.0, 1e-9, "L/D zero lift")
    _assert_close(lift_to_drag_ratio(1.5, 0.0), 0.0, 1e-9, "L/D zero drag")


def test_aero_thrust_required() raises:
    print("  test_aero_thrust_required...")
    _assert_close(thrust_required(100000.0, 50.0), 2000.0, 1e-6, "thrust req")
    _assert_close(thrust_required(100000.0, 0.0), 0.0, 1e-9, "thrust req zero ld")


def test_aero_specific_impulse() raises:
    print("  test_aero_specific_impulse...")
    var isp = specific_impulse(2000000.0, 200.0)
    _assert_close(isp, 2000000.0 / (200.0 * 9.80665), 1e-3, "isp")


def test_aero_tsiolkovsky() raises:
    print("  test_aero_tsiolkovsky...")
    var dv = tsiolkovsky_delta_v(300.0, 10000.0, 3000.0)
    var expected = 300.0 * 9.80665 * _ln(10000.0 / 3000.0)
    _assert_close(dv, expected, 1e-3, "tsiolkovsky dv")
    # Zero mass final → 0
    _assert_close(tsiolkovsky_delta_v(300.0, 10000.0, 0.0), 0.0, 1e-9, "tsiolkovsky zero mf")


def test_aero_mach() raises:
    print("  test_aero_mach...")
    _assert_close(mach_number(340.0, 340.0), 1.0, 1e-9, "mach 1")
    _assert_close(mach_number(680.0, 340.0), 2.0, 1e-9, "mach 2")
    _assert_close(mach_number(170.0, 340.0), 0.5, 1e-9, "mach 0.5")


def test_aero_speed_of_sound() raises:
    print("  test_aero_speed_of_sound...")
    var a = speed_of_sound(1.4, 287.0, 288.15)
    var expected = sqrt(1.4 * 287.0 * 288.15)
    _assert_close(a, expected, 1e-3, "speed of sound")


def test_aero_orbital_velocity() raises:
    print("  test_aero_orbital_velocity...")
    var v = orbital_velocity(3.986e14, 6.771e6)
    var expected = sqrt(3.986e14 / 6.771e6)
    _assert_close(v, expected, 1.0, "orbital vel LEO")


def test_aero_escape_velocity() raises:
    print("  test_aero_escape_velocity...")
    var v_esc = escape_velocity(3.986e14, 6.371e6)
    var expected = sqrt(2.0 * 3.986e14 / 6.371e6)
    _assert_close(v_esc, expected, 1.0, "escape vel")
    # v_esc = sqrt(2) * v_orb at same radius
    var v_orb = orbital_velocity(3.986e14, 6.371e6)
    _assert_close(v_esc / v_orb, sqrt(2.0), 1e-6, "escape=sqrt2*orbital")


def test_aero_hohmann() raises:
    print("  test_aero_hohmann...")
    # Same orbit → dv=0
    _assert_close(hohmann_delta_v(3.986e14, 6.771e6, 6.771e6), 0.0, 1e-3, "hohmann same")
    # LEO to GEO
    var dv = hohmann_delta_v(3.986e14, 6.771e6, 42.164e6)
    _assert(dv > 3000.0, "hohmann LEO-GEO > 3km/s")
    _assert(dv < 4500.0, "hohmann LEO-GEO < 4.5km/s")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 64 tests starting...")

    # Petri Net (12 test functions)
    test_petri_net_transition_enabled()
    test_petri_net_fire_transition()
    test_petri_net_token_count()
    test_petri_net_deadlocked()
    test_petri_net_reachable()
    test_petri_net_place_bounded()
    test_petri_net_live_transition()
    test_petri_net_coverability()
    test_petri_net_incidence()
    test_petri_net_siphon()
    test_petri_net_list_variants()

    # Cryptanalysis (10 test functions)
    test_crypto_frequency_score()
    test_crypto_ic()
    test_crypto_expected_ic()
    test_crypto_friedman()
    test_crypto_kasiski()
    test_crypto_caesar()
    test_crypto_hamming()
    test_crypto_entropy()
    test_crypto_brute_force()
    test_crypto_avalanche()

    # Aerospace (10 test functions)
    test_aero_dynamic_pressure()
    test_aero_lift_drag()
    test_aero_ld_ratio()
    test_aero_thrust_required()
    test_aero_specific_impulse()
    test_aero_tsiolkovsky()
    test_aero_mach()
    test_aero_speed_of_sound()
    test_aero_orbital_velocity()
    test_aero_escape_velocity()
    test_aero_hohmann()

    print("✅ Wave 64: All tests passed! (Petri Net, Cryptanalysis, Aerospace)")
