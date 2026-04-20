"""test_forensics.mojo — auto-generated tests for forensics library."""
from std.math import isnan, isinf
from forensics import time_of_death_newton, algor_mortis_rate, blood_alcohol_widmark, alcohol_elimination_rate, rigor_mortis_stage, ballistic_drop, bloodstain_impact_angle, dna_match_probability, fingerprint_minutiae_score, glass_refractive_index_match, decomposition_add, toxicology_lethal_dose

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_time_of_death_newton = time_of_death_newton(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_time_of_death_newton): passed += 1; print("  ✅ forensics::time_of_death_newton =", _v_time_of_death_newton)
    else: failed += 1; print("  ❌ forensics::time_of_death_newton → non-finite:", _v_time_of_death_newton)
    var _v_algor_mortis_rate = algor_mortis_rate(0.5, 0.5)
    if is_finite(_v_algor_mortis_rate): passed += 1; print("  ✅ forensics::algor_mortis_rate =", _v_algor_mortis_rate)
    else: failed += 1; print("  ❌ forensics::algor_mortis_rate → non-finite:", _v_algor_mortis_rate)
    var _v_blood_alcohol_widmark = blood_alcohol_widmark(0.5, 0.5, 0.5)
    if is_finite(_v_blood_alcohol_widmark): passed += 1; print("  ✅ forensics::blood_alcohol_widmark =", _v_blood_alcohol_widmark)
    else: failed += 1; print("  ❌ forensics::blood_alcohol_widmark → non-finite:", _v_blood_alcohol_widmark)
    var _v_alcohol_elimination_rate = alcohol_elimination_rate(0.5, 0.5, 0.5)
    if is_finite(_v_alcohol_elimination_rate): passed += 1; print("  ✅ forensics::alcohol_elimination_rate =", _v_alcohol_elimination_rate)
    else: failed += 1; print("  ❌ forensics::alcohol_elimination_rate → non-finite:", _v_alcohol_elimination_rate)
    _ = rigor_mortis_stage(0.5)
    passed += 1; print("  ✅ forensics::rigor_mortis_stage")
    var _v_ballistic_drop = ballistic_drop(0.5, 0.5, 0.5)
    if is_finite(_v_ballistic_drop): passed += 1; print("  ✅ forensics::ballistic_drop =", _v_ballistic_drop)
    else: failed += 1; print("  ❌ forensics::ballistic_drop → non-finite:", _v_ballistic_drop)
    var _v_bloodstain_impact_angle = bloodstain_impact_angle(0.5, 0.5)
    if is_finite(_v_bloodstain_impact_angle): passed += 1; print("  ✅ forensics::bloodstain_impact_angle =", _v_bloodstain_impact_angle)
    else: failed += 1; print("  ❌ forensics::bloodstain_impact_angle → non-finite:", _v_bloodstain_impact_angle)
    var _v_dna_match_probability = dna_match_probability(0.5, 0.5)
    if is_finite(_v_dna_match_probability): passed += 1; print("  ✅ forensics::dna_match_probability =", _v_dna_match_probability)
    else: failed += 1; print("  ❌ forensics::dna_match_probability → non-finite:", _v_dna_match_probability)
    var _v_fingerprint_minutiae_score = fingerprint_minutiae_score(0.5, 0.5)
    if is_finite(_v_fingerprint_minutiae_score): passed += 1; print("  ✅ forensics::fingerprint_minutiae_score =", _v_fingerprint_minutiae_score)
    else: failed += 1; print("  ❌ forensics::fingerprint_minutiae_score → non-finite:", _v_fingerprint_minutiae_score)
    _ = glass_refractive_index_match(0.5, 0.5, 0.5)
    passed += 1; print("  ✅ forensics::glass_refractive_index_match")
    var _v_decomposition_add = decomposition_add(0.5, 0.5, 0.5)
    if is_finite(_v_decomposition_add): passed += 1; print("  ✅ forensics::decomposition_add =", _v_decomposition_add)
    else: failed += 1; print("  ❌ forensics::decomposition_add → non-finite:", _v_decomposition_add)
    var _v_toxicology_lethal_dose = toxicology_lethal_dose(0.5, 0.5)
    if is_finite(_v_toxicology_lethal_dose): passed += 1; print("  ✅ forensics::toxicology_lethal_dose =", _v_toxicology_lethal_dose)
    else: failed += 1; print("  ❌ forensics::toxicology_lethal_dose → non-finite:", _v_toxicology_lethal_dose)

    print("  [forensics] Passed:", passed, "Failed:", failed)
