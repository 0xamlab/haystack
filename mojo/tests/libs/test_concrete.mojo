"""test_concrete.mojo — auto-generated tests for concrete library."""
from std.math import isnan, isinf
from concrete import water_cement_ratio, compressive_strength_abrams, cement_content, aggregate_volume, slump_estimate, maturity_nurse_saul, modulus_of_elasticity, splitting_tensile_strength, drying_shrinkage_estimate, carbonation_depth, rebar_development_length, concrete_density_estimate

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

    var _v_water_cement_ratio = water_cement_ratio(0.5, 0.5)
    if is_finite(_v_water_cement_ratio): passed += 1; print("  ✅ concrete::water_cement_ratio =", _v_water_cement_ratio)
    else: failed += 1; print("  ❌ concrete::water_cement_ratio → non-finite:", _v_water_cement_ratio)
    var _v_compressive_strength_abrams = compressive_strength_abrams(0.5, 0.5, 0.5)
    if is_finite(_v_compressive_strength_abrams): passed += 1; print("  ✅ concrete::compressive_strength_abrams =", _v_compressive_strength_abrams)
    else: failed += 1; print("  ❌ concrete::compressive_strength_abrams → non-finite:", _v_compressive_strength_abrams)
    var _v_cement_content = cement_content(0.5, 0.5)
    if is_finite(_v_cement_content): passed += 1; print("  ✅ concrete::cement_content =", _v_cement_content)
    else: failed += 1; print("  ❌ concrete::cement_content → non-finite:", _v_cement_content)
    var _v_aggregate_volume = aggregate_volume(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_aggregate_volume): passed += 1; print("  ✅ concrete::aggregate_volume =", _v_aggregate_volume)
    else: failed += 1; print("  ❌ concrete::aggregate_volume → non-finite:", _v_aggregate_volume)
    var _v_slump_estimate = slump_estimate(0.5)
    if is_finite(_v_slump_estimate): passed += 1; print("  ✅ concrete::slump_estimate =", _v_slump_estimate)
    else: failed += 1; print("  ❌ concrete::slump_estimate → non-finite:", _v_slump_estimate)
    var _v_maturity_nurse_saul = maturity_nurse_saul(0.5, 0.5, 0.5)
    if is_finite(_v_maturity_nurse_saul): passed += 1; print("  ✅ concrete::maturity_nurse_saul =", _v_maturity_nurse_saul)
    else: failed += 1; print("  ❌ concrete::maturity_nurse_saul → non-finite:", _v_maturity_nurse_saul)
    var _v_modulus_of_elasticity = modulus_of_elasticity(0.5)
    if is_finite(_v_modulus_of_elasticity): passed += 1; print("  ✅ concrete::modulus_of_elasticity =", _v_modulus_of_elasticity)
    else: failed += 1; print("  ❌ concrete::modulus_of_elasticity → non-finite:", _v_modulus_of_elasticity)
    var _v_splitting_tensile_strength = splitting_tensile_strength(0.5)
    if is_finite(_v_splitting_tensile_strength): passed += 1; print("  ✅ concrete::splitting_tensile_strength =", _v_splitting_tensile_strength)
    else: failed += 1; print("  ❌ concrete::splitting_tensile_strength → non-finite:", _v_splitting_tensile_strength)
    var _v_drying_shrinkage_estimate = drying_shrinkage_estimate(0.5, 0.5)
    if is_finite(_v_drying_shrinkage_estimate): passed += 1; print("  ✅ concrete::drying_shrinkage_estimate =", _v_drying_shrinkage_estimate)
    else: failed += 1; print("  ❌ concrete::drying_shrinkage_estimate → non-finite:", _v_drying_shrinkage_estimate)
    var _v_carbonation_depth = carbonation_depth(0.5, 0.5)
    if is_finite(_v_carbonation_depth): passed += 1; print("  ✅ concrete::carbonation_depth =", _v_carbonation_depth)
    else: failed += 1; print("  ❌ concrete::carbonation_depth → non-finite:", _v_carbonation_depth)
    var _v_rebar_development_length = rebar_development_length(0.5, 0.5, 0.5)
    if is_finite(_v_rebar_development_length): passed += 1; print("  ✅ concrete::rebar_development_length =", _v_rebar_development_length)
    else: failed += 1; print("  ❌ concrete::rebar_development_length → non-finite:", _v_rebar_development_length)
    var _v_concrete_density_estimate = concrete_density_estimate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_concrete_density_estimate): passed += 1; print("  ✅ concrete::concrete_density_estimate =", _v_concrete_density_estimate)
    else: failed += 1; print("  ❌ concrete::concrete_density_estimate → non-finite:", _v_concrete_density_estimate)

    print("  [concrete] Passed:", passed, "Failed:", failed)
