"""test_packaging.mojo — auto-generated tests for packaging library."""
from std.math import isnan, isinf
from packaging import box_volume, box_surface_area, cylinder_volume, cylinder_surface_area, material_utilization, compression_strength_mckee, stacking_load, cushion_curve_g, pallet_efficiency, fill_percentage, shelf_life_arrhenius, dimensional_weight

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

    var _v_box_volume = box_volume(0.5, 0.5, 0.5)
    if is_finite(_v_box_volume): passed += 1; print("  ✅ packaging::box_volume =", _v_box_volume)
    else: failed += 1; print("  ❌ packaging::box_volume → non-finite:", _v_box_volume)
    var _v_box_surface_area = box_surface_area(0.5, 0.5, 0.5)
    if is_finite(_v_box_surface_area): passed += 1; print("  ✅ packaging::box_surface_area =", _v_box_surface_area)
    else: failed += 1; print("  ❌ packaging::box_surface_area → non-finite:", _v_box_surface_area)
    var _v_cylinder_volume = cylinder_volume(0.5, 0.5)
    if is_finite(_v_cylinder_volume): passed += 1; print("  ✅ packaging::cylinder_volume =", _v_cylinder_volume)
    else: failed += 1; print("  ❌ packaging::cylinder_volume → non-finite:", _v_cylinder_volume)
    var _v_cylinder_surface_area = cylinder_surface_area(0.5, 0.5)
    if is_finite(_v_cylinder_surface_area): passed += 1; print("  ✅ packaging::cylinder_surface_area =", _v_cylinder_surface_area)
    else: failed += 1; print("  ❌ packaging::cylinder_surface_area → non-finite:", _v_cylinder_surface_area)
    var _v_material_utilization = material_utilization(0.5, 0.5)
    if is_finite(_v_material_utilization): passed += 1; print("  ✅ packaging::material_utilization =", _v_material_utilization)
    else: failed += 1; print("  ❌ packaging::material_utilization → non-finite:", _v_material_utilization)
    var _v_compression_strength_mckee = compression_strength_mckee(0.5, 0.5, 0.5)
    if is_finite(_v_compression_strength_mckee): passed += 1; print("  ✅ packaging::compression_strength_mckee =", _v_compression_strength_mckee)
    else: failed += 1; print("  ❌ packaging::compression_strength_mckee → non-finite:", _v_compression_strength_mckee)
    var _v_stacking_load = stacking_load(0.5, 0.5)
    if is_finite(_v_stacking_load): passed += 1; print("  ✅ packaging::stacking_load =", _v_stacking_load)
    else: failed += 1; print("  ❌ packaging::stacking_load → non-finite:", _v_stacking_load)
    var _v_cushion_curve_g = cushion_curve_g(0.5, 0.5, 0.5)
    if is_finite(_v_cushion_curve_g): passed += 1; print("  ✅ packaging::cushion_curve_g =", _v_cushion_curve_g)
    else: failed += 1; print("  ❌ packaging::cushion_curve_g → non-finite:", _v_cushion_curve_g)
    var _v_pallet_efficiency = pallet_efficiency(0.5, 0.5, 0.5)
    if is_finite(_v_pallet_efficiency): passed += 1; print("  ✅ packaging::pallet_efficiency =", _v_pallet_efficiency)
    else: failed += 1; print("  ❌ packaging::pallet_efficiency → non-finite:", _v_pallet_efficiency)
    var _v_fill_percentage = fill_percentage(0.5, 0.5)
    if is_finite(_v_fill_percentage): passed += 1; print("  ✅ packaging::fill_percentage =", _v_fill_percentage)
    else: failed += 1; print("  ❌ packaging::fill_percentage → non-finite:", _v_fill_percentage)
    var _v_shelf_life_arrhenius = shelf_life_arrhenius(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_shelf_life_arrhenius): passed += 1; print("  ✅ packaging::shelf_life_arrhenius =", _v_shelf_life_arrhenius)
    else: failed += 1; print("  ❌ packaging::shelf_life_arrhenius → non-finite:", _v_shelf_life_arrhenius)
    var _v_dimensional_weight = dimensional_weight(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_dimensional_weight): passed += 1; print("  ✅ packaging::dimensional_weight =", _v_dimensional_weight)
    else: failed += 1; print("  ❌ packaging::dimensional_weight → non-finite:", _v_dimensional_weight)

    print("  [packaging] Passed:", passed, "Failed:", failed)
