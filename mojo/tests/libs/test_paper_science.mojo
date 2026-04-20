"""test_paper_science.mojo — auto-generated tests for paper_science library."""
from std.math import isnan, isinf
from paper_science import basis_weight, caliper_to_density, bulk, tearing_resistance_index, tensile_index, burst_index, freeness_csf, kappa_number_to_lignin, pulp_yield, moisture_content_paper, stiffness_index, recycled_fiber_content

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

    var _v_basis_weight = basis_weight(0.5, 0.5)
    if is_finite(_v_basis_weight): passed += 1; print("  ✅ paper_science::basis_weight =", _v_basis_weight)
    else: failed += 1; print("  ❌ paper_science::basis_weight → non-finite:", _v_basis_weight)
    var _v_caliper_to_density = caliper_to_density(0.5, 0.5)
    if is_finite(_v_caliper_to_density): passed += 1; print("  ✅ paper_science::caliper_to_density =", _v_caliper_to_density)
    else: failed += 1; print("  ❌ paper_science::caliper_to_density → non-finite:", _v_caliper_to_density)
    var _v_bulk = bulk(0.5, 0.5)
    if is_finite(_v_bulk): passed += 1; print("  ✅ paper_science::bulk =", _v_bulk)
    else: failed += 1; print("  ❌ paper_science::bulk → non-finite:", _v_bulk)
    var _v_tearing_resistance_index = tearing_resistance_index(0.5, 0.5)
    if is_finite(_v_tearing_resistance_index): passed += 1; print("  ✅ paper_science::tearing_resistance_index =", _v_tearing_resistance_index)
    else: failed += 1; print("  ❌ paper_science::tearing_resistance_index → non-finite:", _v_tearing_resistance_index)
    var _v_tensile_index = tensile_index(0.5, 0.5)
    if is_finite(_v_tensile_index): passed += 1; print("  ✅ paper_science::tensile_index =", _v_tensile_index)
    else: failed += 1; print("  ❌ paper_science::tensile_index → non-finite:", _v_tensile_index)
    var _v_burst_index = burst_index(0.5, 0.5)
    if is_finite(_v_burst_index): passed += 1; print("  ✅ paper_science::burst_index =", _v_burst_index)
    else: failed += 1; print("  ❌ paper_science::burst_index → non-finite:", _v_burst_index)
    var _v_freeness_csf = freeness_csf(0.5)
    if is_finite(_v_freeness_csf): passed += 1; print("  ✅ paper_science::freeness_csf =", _v_freeness_csf)
    else: failed += 1; print("  ❌ paper_science::freeness_csf → non-finite:", _v_freeness_csf)
    var _v_kappa_number_to_lignin = kappa_number_to_lignin(0.5)
    if is_finite(_v_kappa_number_to_lignin): passed += 1; print("  ✅ paper_science::kappa_number_to_lignin =", _v_kappa_number_to_lignin)
    else: failed += 1; print("  ❌ paper_science::kappa_number_to_lignin → non-finite:", _v_kappa_number_to_lignin)
    var _v_pulp_yield = pulp_yield(0.5, 0.5)
    if is_finite(_v_pulp_yield): passed += 1; print("  ✅ paper_science::pulp_yield =", _v_pulp_yield)
    else: failed += 1; print("  ❌ paper_science::pulp_yield → non-finite:", _v_pulp_yield)
    var _v_moisture_content_paper = moisture_content_paper(0.5, 0.5)
    if is_finite(_v_moisture_content_paper): passed += 1; print("  ✅ paper_science::moisture_content_paper =", _v_moisture_content_paper)
    else: failed += 1; print("  ❌ paper_science::moisture_content_paper → non-finite:", _v_moisture_content_paper)
    var _v_stiffness_index = stiffness_index(0.5, 0.5)
    if is_finite(_v_stiffness_index): passed += 1; print("  ✅ paper_science::stiffness_index =", _v_stiffness_index)
    else: failed += 1; print("  ❌ paper_science::stiffness_index → non-finite:", _v_stiffness_index)
    var _v_recycled_fiber_content = recycled_fiber_content(0.5, 0.5)
    if is_finite(_v_recycled_fiber_content): passed += 1; print("  ✅ paper_science::recycled_fiber_content =", _v_recycled_fiber_content)
    else: failed += 1; print("  ❌ paper_science::recycled_fiber_content → non-finite:", _v_recycled_fiber_content)

    print("  [paper_science] Passed:", passed, "Failed:", failed)
