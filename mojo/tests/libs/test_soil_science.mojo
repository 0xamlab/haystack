"""test_soil_science.mojo — auto-generated tests for soil_science library."""
from std.math import isnan, isinf
from soil_science import soil_texture_sand_silt_clay, bulk_density, particle_density_typical, total_porosity, volumetric_water_content, gravimetric_water_content, field_capacity_estimate, wilting_point_estimate, available_water, cation_exchange_capacity_estimate, soil_organic_carbon, infiltration_rate_horton

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

    _ = soil_texture_sand_silt_clay(0.5, 0.5, 0.5)
    passed += 1; print("  ✅ soil_science::soil_texture_sand_silt_clay")
    var _v_bulk_density = bulk_density(0.5, 0.5)
    if is_finite(_v_bulk_density): passed += 1; print("  ✅ soil_science::bulk_density =", _v_bulk_density)
    else: failed += 1; print("  ❌ soil_science::bulk_density → non-finite:", _v_bulk_density)
    var _v_particle_density_typical = particle_density_typical()
    if is_finite(_v_particle_density_typical): passed += 1; print("  ✅ soil_science::particle_density_typical =", _v_particle_density_typical)
    else: failed += 1; print("  ❌ soil_science::particle_density_typical → non-finite:", _v_particle_density_typical)
    var _v_total_porosity = total_porosity(0.5, 0.5)
    if is_finite(_v_total_porosity): passed += 1; print("  ✅ soil_science::total_porosity =", _v_total_porosity)
    else: failed += 1; print("  ❌ soil_science::total_porosity → non-finite:", _v_total_porosity)
    var _v_volumetric_water_content = volumetric_water_content(0.5, 0.5)
    if is_finite(_v_volumetric_water_content): passed += 1; print("  ✅ soil_science::volumetric_water_content =", _v_volumetric_water_content)
    else: failed += 1; print("  ❌ soil_science::volumetric_water_content → non-finite:", _v_volumetric_water_content)
    var _v_gravimetric_water_content = gravimetric_water_content(0.5, 0.5)
    if is_finite(_v_gravimetric_water_content): passed += 1; print("  ✅ soil_science::gravimetric_water_content =", _v_gravimetric_water_content)
    else: failed += 1; print("  ❌ soil_science::gravimetric_water_content → non-finite:", _v_gravimetric_water_content)
    var _v_field_capacity_estimate = field_capacity_estimate(0.5)
    if is_finite(_v_field_capacity_estimate): passed += 1; print("  ✅ soil_science::field_capacity_estimate =", _v_field_capacity_estimate)
    else: failed += 1; print("  ❌ soil_science::field_capacity_estimate → non-finite:", _v_field_capacity_estimate)
    var _v_wilting_point_estimate = wilting_point_estimate(0.5)
    if is_finite(_v_wilting_point_estimate): passed += 1; print("  ✅ soil_science::wilting_point_estimate =", _v_wilting_point_estimate)
    else: failed += 1; print("  ❌ soil_science::wilting_point_estimate → non-finite:", _v_wilting_point_estimate)
    var _v_available_water = available_water(0.5, 0.5, 0.5)
    if is_finite(_v_available_water): passed += 1; print("  ✅ soil_science::available_water =", _v_available_water)
    else: failed += 1; print("  ❌ soil_science::available_water → non-finite:", _v_available_water)
    var _v_cation_exchange_capacity_estimate = cation_exchange_capacity_estimate(0.5, 0.5)
    if is_finite(_v_cation_exchange_capacity_estimate): passed += 1; print("  ✅ soil_science::cation_exchange_capacity_estimate =", _v_cation_exchange_capacity_estimate)
    else: failed += 1; print("  ❌ soil_science::cation_exchange_capacity_estimate → non-finite:", _v_cation_exchange_capacity_estimate)
    var _v_soil_organic_carbon = soil_organic_carbon(0.5)
    if is_finite(_v_soil_organic_carbon): passed += 1; print("  ✅ soil_science::soil_organic_carbon =", _v_soil_organic_carbon)
    else: failed += 1; print("  ❌ soil_science::soil_organic_carbon → non-finite:", _v_soil_organic_carbon)
    var _v_infiltration_rate_horton = infiltration_rate_horton(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_infiltration_rate_horton): passed += 1; print("  ✅ soil_science::infiltration_rate_horton =", _v_infiltration_rate_horton)
    else: failed += 1; print("  ❌ soil_science::infiltration_rate_horton → non-finite:", _v_infiltration_rate_horton)

    print("  [soil_science] Passed:", passed, "Failed:", failed)
