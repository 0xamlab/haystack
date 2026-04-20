"""test_fire_safety.mojo — auto-generated tests for fire_safety library."""
from std.math import isnan, isinf
from fire_safety import fire_load_density, heat_release_rate, flashover_mfo, sprinkler_activation_time, smoke_layer_height, evacuation_time, safe_egress_time, fire_resistance_rating, ventilation_factor, fire_severity, co_concentration_danger, occupant_load

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

    var _v_fire_load_density = fire_load_density(0.5, 0.5)
    if is_finite(_v_fire_load_density): passed += 1; print("  ✅ fire_safety::fire_load_density =", _v_fire_load_density)
    else: failed += 1; print("  ❌ fire_safety::fire_load_density → non-finite:", _v_fire_load_density)
    var _v_heat_release_rate = heat_release_rate(0.5, 0.5)
    if is_finite(_v_heat_release_rate): passed += 1; print("  ✅ fire_safety::heat_release_rate =", _v_heat_release_rate)
    else: failed += 1; print("  ❌ fire_safety::heat_release_rate → non-finite:", _v_heat_release_rate)
    var _v_flashover_mfo = flashover_mfo(0.5, 0.5, 0.5)
    if is_finite(_v_flashover_mfo): passed += 1; print("  ✅ fire_safety::flashover_mfo =", _v_flashover_mfo)
    else: failed += 1; print("  ❌ fire_safety::flashover_mfo → non-finite:", _v_flashover_mfo)
    var _v_sprinkler_activation_time = sprinkler_activation_time(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_sprinkler_activation_time): passed += 1; print("  ✅ fire_safety::sprinkler_activation_time =", _v_sprinkler_activation_time)
    else: failed += 1; print("  ❌ fire_safety::sprinkler_activation_time → non-finite:", _v_sprinkler_activation_time)
    var _v_smoke_layer_height = smoke_layer_height(0.5, 0.5, 0.5)
    if is_finite(_v_smoke_layer_height): passed += 1; print("  ✅ fire_safety::smoke_layer_height =", _v_smoke_layer_height)
    else: failed += 1; print("  ❌ fire_safety::smoke_layer_height → non-finite:", _v_smoke_layer_height)
    var _v_evacuation_time = evacuation_time(0.5, 0.5, 0.5)
    if is_finite(_v_evacuation_time): passed += 1; print("  ✅ fire_safety::evacuation_time =", _v_evacuation_time)
    else: failed += 1; print("  ❌ fire_safety::evacuation_time → non-finite:", _v_evacuation_time)
    var _v_safe_egress_time = safe_egress_time(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_safe_egress_time): passed += 1; print("  ✅ fire_safety::safe_egress_time =", _v_safe_egress_time)
    else: failed += 1; print("  ❌ fire_safety::safe_egress_time → non-finite:", _v_safe_egress_time)
    var _v_fire_resistance_rating = fire_resistance_rating(0.5, 0.5)
    if is_finite(_v_fire_resistance_rating): passed += 1; print("  ✅ fire_safety::fire_resistance_rating =", _v_fire_resistance_rating)
    else: failed += 1; print("  ❌ fire_safety::fire_resistance_rating → non-finite:", _v_fire_resistance_rating)
    var _v_ventilation_factor = ventilation_factor(0.5, 0.5)
    if is_finite(_v_ventilation_factor): passed += 1; print("  ✅ fire_safety::ventilation_factor =", _v_ventilation_factor)
    else: failed += 1; print("  ❌ fire_safety::ventilation_factor → non-finite:", _v_ventilation_factor)
    var _v_fire_severity = fire_severity(0.5, 0.5)
    if is_finite(_v_fire_severity): passed += 1; print("  ✅ fire_safety::fire_severity =", _v_fire_severity)
    else: failed += 1; print("  ❌ fire_safety::fire_severity → non-finite:", _v_fire_severity)
    _ = co_concentration_danger(0.5)
    passed += 1; print("  ✅ fire_safety::co_concentration_danger")
    var _v_occupant_load = occupant_load(0.5, 0.5)
    if is_finite(_v_occupant_load): passed += 1; print("  ✅ fire_safety::occupant_load =", _v_occupant_load)
    else: failed += 1; print("  ❌ fire_safety::occupant_load → non-finite:", _v_occupant_load)

    print("  [fire_safety] Passed:", passed, "Failed:", failed)
