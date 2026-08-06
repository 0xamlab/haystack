"""Tests for Wave 63 — Cellular Automata, Auction, Music Theory."""

from cellular_automata import (
    elementary_rule,
    rule_step_1d,
    game_of_life_cell,
    game_of_life_step,
    totalistic_rule,
    langtons_ant_step,
    wireworld_cell,
    rule110_cell,
    majority_rule,
    parity_rule,
)
from auction import (
    first_price_sealed,
    second_price_sealed,
    english_auction_revenue,
    dutch_auction_revenue,
    all_pay_revenue,
    revenue_equivalence_check,
    vcg_payment,
    reserve_price_filter,
    bid_shading_optimal,
    expected_revenue_uniform,
    winners_curse_adjustment,
)
from music_theory import (
    frequency_from_midi,
    midi_from_frequency,
    cents_between,
    semitones_between,
    note_in_scale,
    interval_ratio_just,
    beat_frequency,
    tempo_to_beat_duration,
    measures_duration,
    transpose_midi,
    octave_from_midi,
    is_enharmonic,
)
from std.math import abs as fabs


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Cellular Automata tests ─────────────────────────────────────────────────


def test_elementary_rule() raises:
    print("  test_elementary_rule...")
    # Rule 30: 111->0, 110->0, 101->0, 100->1, 011->1, 010->1, 001->1, 000->0
    _assert(elementary_rule(30, 1, 1, 1) == 0, "rule30 111->0")        # 1
    _assert(elementary_rule(30, 0, 0, 1) == 1, "rule30 001->1")        # 2
    _assert(elementary_rule(30, 0, 1, 1) == 1, "rule30 011->1")        # 3
    _assert(elementary_rule(30, 1, 0, 0) == 1, "rule30 100->1")        # 4
    # Rule 110
    _assert(elementary_rule(110, 1, 1, 1) == 0, "rule110 111->0")      # 5
    _assert(elementary_rule(110, 1, 1, 0) == 1, "rule110 110->1")      # 6
    _assert(elementary_rule(110, 0, 0, 0) == 0, "rule110 000->0")      # 7
    print("    PASSED")


def test_rule_step_1d() raises:
    print("  test_rule_step_1d...")
    # Single 1 in center with rule 30
    var cells = List[Int]()
    cells.append(0)
    cells.append(0)
    cells.append(1)
    cells.append(0)
    cells.append(0)
    var next = rule_step_1d(cells, 5, 30)
    _assert(len(next) == 5, "step preserves length")                    # 8
    _assert(next[1] == 1, "rule30 step: pos 1 should be 1")            # 9
    _assert(next[2] == 1, "rule30 step: pos 2 should be 1")            # 10
    _assert(next[3] == 1, "rule30 step: pos 3 should be 1")            # 11
    print("    PASSED")


def test_game_of_life_cell() raises:
    print("  test_game_of_life_cell...")
    # Live cell with 2 neighbors → survives
    _assert(game_of_life_cell(True, 2) == True, "alive+2 survives")     # 12
    # Live cell with 3 neighbors → survives
    _assert(game_of_life_cell(True, 3) == True, "alive+3 survives")     # 13
    # Live cell with 1 neighbor → dies (underpopulation)
    _assert(game_of_life_cell(True, 1) == False, "alive+1 dies")        # 14
    # Live cell with 4 neighbors → dies (overpopulation)
    _assert(game_of_life_cell(True, 4) == False, "alive+4 dies")        # 15
    # Dead cell with 3 neighbors → birth
    _assert(game_of_life_cell(False, 3) == True, "dead+3 born")         # 16
    # Dead cell with 2 neighbors → stays dead
    _assert(game_of_life_cell(False, 2) == False, "dead+2 stays dead")  # 17
    print("    PASSED")


def test_game_of_life_step() raises:
    print("  test_game_of_life_step...")
    # 3x3 grid with blinker (horizontal)
    # 0 0 0
    # 1 1 1
    # 0 0 0
    var grid = List[Int]()
    grid.append(0); grid.append(0); grid.append(0)
    grid.append(1); grid.append(1); grid.append(1)
    grid.append(0); grid.append(0); grid.append(0)
    # Center cell (1,1) should have 2 neighbors
    var n_center = game_of_life_step(grid, 3, 3, 1, 1)
    _assert(n_center == 2, "center of blinker has 2 neighbors")         # 18
    # Top-center (0,1) should have 3 neighbors
    var n_top = game_of_life_step(grid, 3, 3, 0, 1)
    _assert(n_top == 3, "top-center of blinker has 3 neighbors")        # 19
    # Corner (0,0) neighbors: (1,0)=1, (1,1)=1 → 2 neighbors
    var n_corner = game_of_life_step(grid, 3, 3, 0, 0)
    _assert(n_corner == 2, "corner has 2 neighbors")                    # 20
    print("    PASSED")


def test_totalistic_rule() raises:
    print("  test_totalistic_rule...")
    # k=2, rule_number=110, total=0 → 110 % 2 = 0
    _assert(totalistic_rule(2, 110, 0) == 0, "totalistic k=2 r=110 t=0")  # 21
    # k=2, rule_number=110, total=1 → (110//2) % 2 = 55%2 = 1
    _assert(totalistic_rule(2, 110, 1) == 1, "totalistic k=2 r=110 t=1")  # 22
    # k=3, rule_number=12, total=0 → 12%3 = 0
    _assert(totalistic_rule(3, 12, 0) == 0, "totalistic k=3 r=12 t=0")    # 23
    # k=3, rule_number=12, total=1 → (12//3)%3 = 4%3 = 1
    _assert(totalistic_rule(3, 12, 1) == 1, "totalistic k=3 r=12 t=1")    # 24
    print("    PASSED")


def test_langtons_ant() raises:
    print("  test_langtons_ant...")
    # On white (0), facing north (0) → turn right → east (1), flip to black (1)
    var r1 = langtons_ant_step(0, 0)
    _assert(r1[0] == 1, "white: N→E")                                  # 25
    _assert(r1[1] == 1, "white: flip to black")                        # 26
    # On black (1), facing east (1) → turn left → north (0), flip to white (0)
    var r2 = langtons_ant_step(1, 1)
    _assert(r2[0] == 0, "black: E→N")                                  # 27
    _assert(r2[1] == 0, "black: flip to white")                        # 28
    # On white, facing west (3) → turn right → north (0)
    var r3 = langtons_ant_step(3, 0)
    _assert(r3[0] == 0, "white: W→N")                                  # 29
    print("    PASSED")


def test_wireworld_cell() raises:
    print("  test_wireworld_cell...")
    _assert(wireworld_cell(0, 0) == 0, "empty stays empty")            # 30
    _assert(wireworld_cell(1, 0) == 2, "head → tail")                  # 31
    _assert(wireworld_cell(2, 0) == 3, "tail → conductor")             # 32
    _assert(wireworld_cell(3, 1) == 1, "conductor+1 excited → head")   # 33
    _assert(wireworld_cell(3, 2) == 1, "conductor+2 excited → head")   # 34
    _assert(wireworld_cell(3, 0) == 3, "conductor+0 → stays")          # 35
    _assert(wireworld_cell(3, 3) == 3, "conductor+3 → stays")          # 36
    print("    PASSED")


def test_rule110_cell() raises:
    print("  test_rule110_cell...")
    _assert(rule110_cell(1, 1, 1) == 0, "rule110 111→0")               # 37
    _assert(rule110_cell(1, 1, 0) == 1, "rule110 110→1")               # 38
    _assert(rule110_cell(0, 1, 0) == 1, "rule110 010→1")               # 39
    _assert(rule110_cell(0, 0, 0) == 0, "rule110 000→0")               # 40
    print("    PASSED")


def test_majority_parity() raises:
    print("  test_majority_parity...")
    _assert(majority_rule(3, 5) == 1, "3/5 majority → 1")              # 41
    _assert(majority_rule(2, 5) == 0, "2/5 majority → 0")              # 42
    _assert(majority_rule(0, 0) == 0, "0/0 → 0")                       # 43
    _assert(parity_rule(3) == 1, "3 odd → 1")                          # 44
    _assert(parity_rule(4) == 0, "4 even → 0")                         # 45
    _assert(parity_rule(0) == 0, "0 even → 0")                         # 46
    print("    PASSED")


# ── Auction tests ────────────────────────────────────────────────────────────


def test_first_price_sealed() raises:
    print("  test_first_price_sealed...")
    var bids = List[Float64]()
    bids.append(10.0); bids.append(20.0); bids.append(15.0)
    var r = first_price_sealed(bids, 3)
    _assert_close(r[0], 1.0, 0.01, "winner is bidder 1")               # 47
    _assert_close(r[1], 20.0, 0.01, "price = 20")                      # 48
    print("    PASSED")


def test_second_price_sealed() raises:
    print("  test_second_price_sealed...")
    var bids = List[Float64]()
    bids.append(10.0); bids.append(20.0); bids.append(15.0)
    var r = second_price_sealed(bids, 3)
    _assert_close(r[0], 1.0, 0.01, "vickrey winner is bidder 1")       # 49
    _assert_close(r[1], 15.0, 0.01, "vickrey price = 15 (2nd highest)") # 50
    print("    PASSED")


def test_english_dutch_revenue() raises:
    print("  test_english_dutch_revenue...")
    var bids = List[Float64]()
    bids.append(10.0); bids.append(20.0); bids.append(15.0)
    var eng = english_auction_revenue(bids, 3)
    _assert_close(eng, 15.0, 0.01, "english revenue = 2nd highest")     # 51
    var dut = dutch_auction_revenue(bids, 3)
    _assert_close(dut, 20.0, 0.01, "dutch revenue = highest")           # 52
    print("    PASSED")


def test_all_pay_revenue() raises:
    print("  test_all_pay_revenue...")
    var bids = List[Float64]()
    bids.append(10.0); bids.append(20.0); bids.append(15.0)
    var rev = all_pay_revenue(bids, 3)
    _assert_close(rev, 45.0, 0.01, "all-pay total = 45")               # 53
    print("    PASSED")


def test_revenue_equivalence() raises:
    print("  test_revenue_equivalence...")
    # Close bids should pass revenue equivalence
    var bids = List[Float64]()
    bids.append(9.0); bids.append(10.0); bids.append(9.5)
    var eq = revenue_equivalence_check(bids, 3)
    _assert(eq == True, "close bids pass revenue equivalence")          # 54
    # Very different bids may fail
    var bids2 = List[Float64]()
    bids2.append(1.0); bids2.append(100.0); bids2.append(2.0)
    var eq2 = revenue_equivalence_check(bids2, 3)
    _assert(eq2 == False, "far bids fail revenue equivalence")          # 55
    print("    PASSED")


def test_vcg_payment() raises:
    print("  test_vcg_payment...")
    var vals = List[Float64]()
    vals.append(10.0); vals.append(20.0); vals.append(15.0)
    # Winner is idx 1 (highest value), VCG payment = max of others = 15
    var p = vcg_payment(vals, 3, 1)
    _assert_close(p, 15.0, 0.01, "VCG payment = 15")                   # 56
    print("    PASSED")


def test_reserve_price_filter() raises:
    print("  test_reserve_price_filter...")
    var bids = List[Float64]()
    bids.append(10.0); bids.append(20.0); bids.append(15.0)
    var r = reserve_price_filter(bids, 3, 12.0)
    _assert_close(r[0], 2.0, 0.01, "2 bids above reserve 12")          # 57
    _assert_close(r[1], 35.0, 0.01, "sum above reserve = 35")          # 58
    print("    PASSED")


def test_bid_shading() raises:
    print("  test_bid_shading...")
    # value=100, n=2 → bid = 100*(1/2) = 50
    var b = bid_shading_optimal(100.0, 2)
    _assert_close(b, 50.0, 0.01, "bid shade n=2 → 50")                 # 59
    # value=100, n=5 → bid = 100*(4/5) = 80
    var b2 = bid_shading_optimal(100.0, 5)
    _assert_close(b2, 80.0, 0.01, "bid shade n=5 → 80")                # 60
    # n=1 → bid = 0
    var b3 = bid_shading_optimal(100.0, 1)
    _assert_close(b3, 0.0, 0.01, "bid shade n=1 → 0")                  # 61
    print("    PASSED")


def test_expected_revenue_uniform() raises:
    print("  test_expected_revenue_uniform...")
    # n=2, max=100 → (1/3)*100 = 33.33
    var r = expected_revenue_uniform(2, 100.0)
    _assert_close(r, 33.333, 0.01, "E[rev] n=2 = 33.33")              # 62
    # n=10, max=100 → (9/11)*100 ≈ 81.82
    var r2 = expected_revenue_uniform(10, 100.0)
    _assert_close(r2, 81.818, 0.01, "E[rev] n=10 ≈ 81.82")            # 63
    print("    PASSED")


def test_winners_curse() raises:
    print("  test_winners_curse...")
    var adj = winners_curse_adjustment(100.0, 5)
    _assert_close(adj, 80.0, 0.01, "winner's curse adj n=5 → 80")      # 64
    var adj2 = winners_curse_adjustment(100.0, 1)
    _assert_close(adj2, 100.0, 0.01, "n=1 no adjustment")              # 65
    print("    PASSED")


# ── Music Theory tests ───────────────────────────────────────────────────────


def test_frequency_from_midi() raises:
    print("  test_frequency_from_midi...")
    # A4 = MIDI 69 → 440 Hz
    var f = frequency_from_midi(69)
    _assert_close(f, 440.0, 0.5, "MIDI 69 → 440 Hz")                  # 66
    # C4 = MIDI 60 → ~261.63 Hz
    var f2 = frequency_from_midi(60)
    _assert_close(f2, 261.63, 1.0, "MIDI 60 → ~261.63 Hz")            # 67
    # A5 = MIDI 81 → 880 Hz
    var f3 = frequency_from_midi(81)
    _assert_close(f3, 880.0, 1.0, "MIDI 81 → 880 Hz")                 # 68
    print("    PASSED")


def test_midi_from_frequency() raises:
    print("  test_midi_from_frequency...")
    _assert(midi_from_frequency(440.0) == 69, "440 Hz → MIDI 69")      # 69
    _assert(midi_from_frequency(261.63) == 60, "261.63 Hz → MIDI 60")  # 70
    _assert(midi_from_frequency(880.0) == 81, "880 Hz → MIDI 81")      # 71
    print("    PASSED")


def test_cents_between() raises:
    print("  test_cents_between...")
    # Octave = 1200 cents
    var c = cents_between(440.0, 880.0)
    _assert_close(c, 1200.0, 0.1, "octave = 1200 cents")               # 72
    # Unison = 0 cents
    var c2 = cents_between(440.0, 440.0)
    _assert_close(c2, 0.0, 0.01, "unison = 0 cents")                   # 73
    # Perfect fifth ≈ 702 cents (just: 3/2)
    var c3 = cents_between(440.0, 660.0)
    _assert_close(c3, 702.0, 1.0, "just fifth ≈ 702 cents")            # 74
    print("    PASSED")


def test_semitones_between() raises:
    print("  test_semitones_between...")
    _assert(semitones_between(60, 72) == 12, "C4-C5 = 12 semitones")   # 75
    _assert(semitones_between(69, 69) == 0, "same note = 0")           # 76
    _assert(semitones_between(60, 67) == 7, "C4-G4 = 7 semitones")    # 77
    print("    PASSED")


def test_note_in_scale() raises:
    print("  test_note_in_scale...")
    # C major (root=0): C(0), D(2), E(4), F(5), G(7), A(9), B(11) ✓
    _assert(note_in_scale(0, 0, 0) == True, "C in C major")            # 78
    _assert(note_in_scale(4, 0, 0) == True, "E in C major")            # 79
    _assert(note_in_scale(1, 0, 0) == False, "C# not in C major")      # 80
    # A minor (root=9): A(9), B(11), C(0), D(2), E(4), F(5), G(7)
    _assert(note_in_scale(9, 9, 1) == True, "A in A minor")            # 81
    _assert(note_in_scale(0, 9, 1) == True, "C in A minor")            # 82
    print("    PASSED")


def test_interval_ratio_just() raises:
    print("  test_interval_ratio_just...")
    _assert_close(interval_ratio_just(0), 1.0, 0.001, "unison = 1")    # 83
    _assert_close(interval_ratio_just(7), 1.5, 0.001, "fifth = 3/2")   # 84
    _assert_close(interval_ratio_just(12), 2.0, 0.001, "octave = 2")   # 85
    _assert_close(interval_ratio_just(5), 4.0/3.0, 0.001, "fourth=4/3") # 86
    print("    PASSED")


def test_beat_frequency() raises:
    print("  test_beat_frequency...")
    _assert_close(beat_frequency(440.0, 442.0), 2.0, 0.01, "beat=2Hz") # 87
    _assert_close(beat_frequency(440.0, 440.0), 0.0, 0.01, "beat=0Hz") # 88
    print("    PASSED")


def test_tempo_duration() raises:
    print("  test_tempo_duration...")
    # 120 BPM → 0.5 sec per beat
    var bd = tempo_to_beat_duration(120.0)
    _assert_close(bd, 0.5, 0.001, "120bpm → 0.5s/beat")                # 89
    # 60 BPM → 1.0 sec per beat
    var bd2 = tempo_to_beat_duration(60.0)
    _assert_close(bd2, 1.0, 0.001, "60bpm → 1s/beat")                  # 90
    # 4 measures of 4/4 at 120 BPM = 4*4*0.5 = 8 sec
    var md = measures_duration(120.0, 4, 4)
    _assert_close(md, 8.0, 0.01, "4 measures 4/4 120bpm = 8s")         # 91
    print("    PASSED")


def test_transpose_midi() raises:
    print("  test_transpose_midi...")
    _assert(transpose_midi(60, 12) == 72, "C4+octave=C5")              # 92
    _assert(transpose_midi(69, -12) == 57, "A4-octave=A3")             # 93
    _assert(transpose_midi(60, 7) == 67, "C4+fifth=G4")                # 94
    print("    PASSED")


def test_octave_from_midi() raises:
    print("  test_octave_from_midi...")
    _assert(octave_from_midi(60) == 4, "MIDI 60 = octave 4")           # 95
    _assert(octave_from_midi(69) == 4, "MIDI 69 = octave 4")           # 96
    _assert(octave_from_midi(0) == -1, "MIDI 0 = octave -1")           # 97
    print("    PASSED")


def test_is_enharmonic() raises:
    print("  test_is_enharmonic...")
    _assert(is_enharmonic(60, 72) == True, "C4 and C5 enharmonic")     # 98
    _assert(is_enharmonic(60, 61) == False, "C4 and C#4 not")          # 99
    _assert(is_enharmonic(69, 57) == True, "A4 and A3 enharmonic")     # 100
    print("    PASSED")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("Wave 63 tests: Cellular Automata, Auction, Music Theory")
    print("=" * 60)

    print("\n[Cellular Automata]")
    test_elementary_rule()
    test_rule_step_1d()
    test_game_of_life_cell()
    test_game_of_life_step()
    test_totalistic_rule()
    test_langtons_ant()
    test_wireworld_cell()
    test_rule110_cell()
    test_majority_parity()

    print("\n[Auction]")
    test_first_price_sealed()
    test_second_price_sealed()
    test_english_dutch_revenue()
    test_all_pay_revenue()
    test_revenue_equivalence()
    test_vcg_payment()
    test_reserve_price_filter()
    test_bid_shading()
    test_expected_revenue_uniform()
    test_winners_curse()

    print("\n[Music Theory]")
    test_frequency_from_midi()
    test_midi_from_frequency()
    test_cents_between()
    test_semitones_between()
    test_note_in_scale()
    test_interval_ratio_just()
    test_beat_frequency()
    test_tempo_duration()
    test_transpose_midi()
    test_octave_from_midi()
    test_is_enharmonic()

    print("\n" + "=" * 60)
    print("Wave 63: ALL 100 assertions PASSED")
